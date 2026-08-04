---
title: "排查实录：手机端访问 ERR_CONNECTION_RESET 的根因与修复"
date: 2026-08-02
tags:
  - 排查
  - Linux
  - TCP
  - 运维
  - 网络
---

## 问题

手机端访问 jeffshare.com 出现**间歇性**无法访问，报 `ERR_CONNECTION_RESET`。手机自带浏览器和微信内置浏览器都有此现象，但并非每次都失败：

- 有时候一次就能打开
- 有时候反复刷新依然失败
- 切换到 WiFi 或流量似乎没有明显规律

本文从 TCP 协议栈层面完整复盘这次排查。

---

## 系统架构

排查的第一步永远不是看某个具体配置，而是建立全局认知。本节目的服务的拓扑如下：

```
┌──────────────────────────────────────────────────────────────┐
│                       Internet                               │
│   📱 手机 (CGNAT IP)    💻 PC (宽带 IP)    🤖 爬虫/扫描器     │
└────────────┬─────────────────┬──────────────────┬────────────┘
             │                 │                  │
             └─────────────────┼──────────────────┘
                               │  :443 (HTTPS)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Tencent Cloud VM                          │
│                                                              │
│  ┌──────────┐     ┌───────────┐     ┌────────────────────┐   │
│  │ iptables │────▶│   Caddy   │────▶│  uvicorn (4 workers)│   │
│  │ (云镜 FW) │     │ :80 / :443│     │  127.0.0.1:8000   │   │
│  └──────────┘     └───────────┘     └────────────────────┘   │
│                                         │                    │
│                                    FastAPI + Jinja2          │
│                                    Markdown → HTML           │
└──────────────────────────────────────────────────────────────┘
```

从路径上看，一次 HTTP 请求需要经过 **iptables → Caddy → uvicorn → FastAPI** 四层。`ERR_CONNECTION_RESET` 出现在 TCP 握手阶段就失败了，意味着问题大概率在 iptables 或内核 TCP 协议栈，不可能在应用代码。

---

## 排查过程

### 第一步：并行拉取全局状态

```
  ┌─ systemctl status      → 服务在跑 ✓
  ├─ ss -tlnp              → 端口监听 ✓
  ├─ iptables -L -v -n     → 发现 YJ-FIREWALL 链 ⚠
  └─ journalctl            → 无应用层错误 ✓
```

确认服务正常、端口正常，但从 iptables 发现了一条关键规则：

```bash
# iptables -L INPUT -v -n
Chain INPUT (policy ACCEPT ...)
  pkts   bytes target     prot opt in   out   source    destination
 39547  7140K YJ-FIREWALL-INPUT  all  --  *  *  0.0.0.0/0  0.0.0.0/0
 40030  1719K DROP  tcp  --  *  *  0.0.0.0/0  0.0.0.0/0
       tcp flags:0x17/0x02 match-set YJ-GLOBAL-INBLOCK src
```

**40,030 个 TCP SYN 包被 iptables 直接 DROP**，来自一个名为 `YJ-GLOBAL-INBLOCK` 的 ipset 黑名单。这是腾讯云云镜（YunJing）主机安全产品维护的全球威胁情报黑名单，包含 **~10,468 个 IP**，每 5-10 分钟动态刷新，单 IP 封禁 TTL 为 7200 秒（2 小时）。

但这个线索指向的是"IP 被误封"，而不是间歇性失败——如果用户 IP 在黑名单里，应该**每次都访问不了**。所以黑名单只是一个潜在放大器，不是根因。

### 第二步：按错误类型分层收敛

不同浏览器错误码对应的含义差异很大，据此可以快速定位出问题在协议栈的哪一层：

```
ERR_CONNECTION_RESET
        │
        ├── TCP RST 收到（服务端主动发 RST）
        │       └── 可能原因: 端口未监听、防火墙 REJECT、连接被 abort
        │
        └── SYN 反复被丢弃 × N 次重传
                └── 客户端 TCP 栈最终报告 "connection reset"
                    可能原因: iptables DROP、内核参数误杀 SYN
```

这里的关键判断：如果是 7 层问题（应用 crash、超时），错误码通常是 `ERR_CONNECTION_REFUSED` 或 `ERR_TIMED_OUT`。**`ERR_CONNECTION_RESET` 明确指向 TCP 握手阶段失败**。

### 第三步：检查 TCP 内核参数

TCP 握手阶段能"选择性"丢弃 SYN 的内核参数，最知名的就是：

```bash
$ sysctl net.ipv4.tcp_tw_recycle
net.ipv4.tcp_tw_recycle = 1    # ← 就是它
```

### 第四步：对比历史流量确认

```
          修复前                         修复后
     tcp_tw_recycle=1              tcp_tw_recycle=0
   ┌─────────────────┐          ┌─────────────────┐
   │ ████████████░░░░ │          │ ████████████████ │
   │ ██ 成功 ██ 失败  │          │ ██ 全部成功 ████ │
   │ ████████████░░░░ │          │ ████████████████ │
   └─────────────────┘          └─────────────────┘
    手机 A: ✅                   手机 A: ✅
    手机 B: ❌ RESET             手机 B: ✅
    手机 A 再试: ✅              手机 A 再试: ✅
    手机 B 再试: ❌ RESET        手机 B 再试: ✅
```

修复 `tcp_tw_recycle=0` 后，手机浏览器立即恢复正常。但微信内置浏览器仍偶发失败——这是后续要讨论的客户端缓存问题。

---

## 根因分析

### 背景知识一：TCP Timestamp 选项（RFC 1323）

TCP Timestamp 是 RFC 1323（1992）引入的 TCP 扩展选项，位于 TCP 头部的 Options 字段：

```
TCP Header (simplified)
┌────────────────────────────────────────────────────────────┐
│ Src Port │ Dst Port │ Sequence Number │ ACK Number │ ...   │
├────────────────────────────────────────────────────────────┤
│ Kind=8  │ Length=10 │  TSval (4 bytes)  │  TSecr (4 bytes)│  ← TCP Timestamp Option
└────────────────────────────────────────────────────────────┘
   TSval = 发送方当前时间戳（单调递增的时钟值）
   TSecr = 回显对方最近收到的 TSval
```

两个用途：

| 用途 | 机制 |
|------|------|
| **RTTM** (Round-Trip Time Measurement) | `TSval` 和 `TSecr` 的差值精确计算 RTT，替代古老的"每个窗口取一个样本"方式 |
| **PAWS** (Protect Against Wrapped Sequences) | 利用时间戳单调递增的特性，判断一个包是"新包"还是"延迟到达的旧包" |

PAWS 的检查逻辑：

```
收到一个 TCP 包:
  if (包的时间戳 < 缓存的时间戳) {
      // 时间戳倒退了 → 这是一个"旧包"
      // 旧包可能: (1) 网络延迟 (2) 序列号回绕 (3) 攻击
      → 丢弃
  } else {
      // 时间戳正常递增
      → 更新缓存 = 包的时间戳
      → 正常处理
  }
```

这在单机上完全没有问题——一台机器的 TCP 时钟是严格单调递增的。**问题出在缓存的 key**。

### 背景知识二：Per-Host Timestamp Cache 的设计缺陷

`tcp_tw_recycle=1` 的行为链条：

```
tcp_tw_recycle = 1
        │
        ▼
启用 TIME_WAIT 快速回收（每个 RST 立即释放 socket）
        │
        ▼
为了保证"安全回收"，启用 PAWS 对 SYN 包的检查
        │
        ▼
PAWS 的缓存 key = 源 IP 地址（不含端口！）
        │
        ▼
同一 IP 的所有连接共享一条时间戳缓存记录
```

**关键缺陷在于缓存的 key 只取源 IP，不区分端口**。内核代码简化逻辑：

```c
// net/ipv4/tcp_ipv4.c (Linux 3.10)
// 伪代码简化

struct tcp_timewait_sock {
    u32 tw_ts_recent;  // 来自该 IP 的最近时间戳
    // 注意：只按 IP 索引，不按 IP+Port 索引！
};

int tcp_conn_request(...) {
    if (tcp_death_row.sysctl_tw_recycle) {
        // 检查 per-IP timestamp cache
        if (tmp_opt.saw_tstamp &&
            tcp_paws_check(&tmp_opt, TCP_PAWS_MSL)) {
            // PAWS 检查失败 → 时间戳倒退了
            goto drop_and_release;  // 直接丢弃 SYN！
        }
    }
    // 正常三次握手...
}
```

单台设备没问题：同一台机器的 TCP 时钟单调递增，后续连接的时间戳一定 >= 前一次连接。

多台设备共享 IP 就有问题：

```
            时刻 T1                     时刻 T2
    ┌────────────────────┐      ┌────────────────────┐
    │  手机 A（移动 5G）   │      │  手机 B（移动 5G）   │
    │  TCP 启动于 08:00   │      │  TCP 启动于 08:05   │
    │  ts_clock = 80000  │      │  ts_clock = 15000  │  ← 重启/待机后时钟偏移
    └────────┬───────────┘      └────────┬───────────┘
             │                           │
             │  SYN, TS=80000            │  SYN, TS=15000
             ▼                           ▼
    ┌────────────────────────────────────────────────────┐
    │        运营商级 CGNAT (Carrier-Grade NAT)           │
    │        公网出口 IP: 223.104.68.73                 │
    └──────────────────────┬─────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  服务器 106.52.49.30    │
              │                         │
              │  T1: 缓存 IP=223.104... │
              │       ts_recent=80000   │
              │                         │
              │  T2: PAWS 检查          │
              │  15000 < 80000 ✗        │
              │  → DROP SYN            │
              └─────────────────────────┘
```

### 背景知识三：为什么手机端问题显著，PC 端几乎不触发

这不是巧合，而是**网络拓扑差异**决定的：

```
┌── 家庭宽带 ──────────────────────────────────────────────┐
│                                                           │
│   PC1 ─┐                   ┌─ 独立公网 IP                  │
│   PC2 ─┼─ 家用 NAT ───────┼─ 或少量 (< 10) 设备共享       │
│   TV  ─┘                   └─ 时间戳碰撞概率 ~0             │
│                                                           │
│   → tcp_tw_recycle 的 PAWS 误杀几乎不会发生               │
└───────────────────────────────────────────────────────────┘

┌── 移动蜂窝网络 ──────────────────────────────────────────┐
│                                                           │
│   📱 A ─┐                                                │
│   📱 B ─┼─ 运营商 CGNAT ──── 公网 IP 223.104.68.73       │
│   📱 C ─┤                    ↑                           │
│   ...    │                    几百~几千 设备共享同一个 IP   │
│   📱 Z ─┘                    ↑                           │
│                              设备时钟各自独立              │
│   → 时间戳碰撞概率极高                                    │
│   → 任何一个设备的高时间戳都会"锁死"后续低时间戳设备        │
└───────────────────────────────────────────────────────────┘
```

中国三大运营商（移动、联通、电信）由于 IPv4 地址枯竭，大量 4G/5G 用户处于 CGNAT 后（共享 100.64.0.0/10 私有地址段），一个公网 IP 后面可能有 **数百甚至上千台手机**。在这种规模下，`tcp_tw_recycle` 的 per-IP timestamp cache 几乎必然触发 PAWS 误杀。

### 为什么是间歇性的

是否触发，取决于**同一 CGNAT IP 下前一个访问者的时间戳是否比你大**：

```
场景 A：手机 B 是第一个访问者
─────────────────────────────────
  缓存为空 → PAWS 检查不触发 → ✅ 成功

场景 B：手机 A 刚访问过，且 ts_A > ts_B
────────────────────────────────────────
  缓存有 ts_A=80000 → B 的 ts=15000 < 80000 → ❌ 被丢

场景 C：手机 A 刚访问过，但 ts_A < ts_B
────────────────────────────────────────
  缓存有 ts_A=5000 → B 的 ts=15000 > 5000 → ✅ 成功
```

由于不同手机的 TCP 时钟是独立且随机的，这个条件**本质上是一个概率游戏**。在数百设备共享一个 IP 的场景下，被误杀的概率远大于成功的概率。

### 为什么微信比系统浏览器更容易触发

修复后普通浏览器立刻恢复，但微信内置浏览器需要更长时间才恢复——原因在于微信的网络层有额外的缓存层：

```
普通浏览器                          微信内置浏览器
─────────                          ───────────────
修复后 DNS 缓存过期                 修复后
  ↓                                  ↓
重新 TCP 握手 → 成功 ✅              WebView 连接池中 socket 状态未更新
                                      ↓
                                    复用旧连接 / DNS 缓存 / 预连接
                                      ↓
                                    连接失败（ERR_CONNECTION_RESET）
                                      ↓
                                    等 WebView 进程回收或微信重启
                                      ↓
                                    重新握手 → 成功 ✅

缓存层级:
  • DNS 缓存 (TTL ~300s)            上述所有 +
  • 连接池 (TCP keepalive)          • X5/MMWebView 自有连接池
                                    • 微信代理层缓存
                                    • 内容安全扫描预连接
```

微信（特别是 Android 版）使用自研的 X5 浏览器内核，它对目标 URL 有**预解析（preconnect）机制**——用户还没点链接，微信已经在后台完成了 TCP 握手，占位了一个时间戳，后续真实访问时如果命中 PAWS 缓存就失败了。这在 `tcp_tw_recycle=1` 的环境下反而放大了问题暴露的概率。

---

## 修复

### 操作

```bash
# 立即生效
sysctl -w net.ipv4.tcp_tw_recycle=0

# 永久生效 /etc/sysctl.conf:
# net.ipv4.tcp_tw_recycle = 0
```

### 原理

```
tcp_tw_recycle = 0
        │
        ▼
不再在 SYN 阶段启用 PAWS 时间戳单调性检查
        │
        ▼
不再维护 per-IP timestamp cache
        │
        ▼
每个 SYN 包都正常进入三次握手
        │
        ▼
CGNAT 后不同设备的时钟差异不再影响连接建立 ✓
```

改一行参数，本质上是在内核中**关闭了一个优化路径上的错误安全检查**。

### TIME_WAIT 会堆积吗

不会。修复后服务器仍然有三道防线处理 TIME_WAIT：

```
TIME_WAIT 快速回收
┌──────────────────────────────────────────────────┐
│                                                  │
│  ① tcp_tw_reuse = 1                              │
│     客户端出方向连接时可复用 TIME_WAIT socket     │
│     安全检查保守（仅本机 timestamp 单调性）       │
│     → NAT 安全 ✓                                 │
│                                                  │
│  ② tcp_fin_timeout = 5                           │
│     FIN_WAIT_2 状态超时从默认 60s 缩短到 5s       │
│     → TCP 关闭流程加速 12 倍                      │
│                                                  │
│  ③ HTTP/2 Multiplexing (Caddy)                   │
│     多个请求复用一条 TCP 连接                      │
│     → 根本不会产生大量短连接                       │
│                                                  │
└──────────────────────────────────────────────────┘
```

### tcp_tw_reuse vs tcp_tw_recycle 对比

| | `tcp_tw_reuse` | `tcp_tw_recycle` |
|---|---|---|
| 作用方向 | 客户端出方向 | 服务端入方向 |
| 检查机制 | 本机 timestamp 单调性 | per-IP timestamp 单调性 |
| NAT 兼容 | ✅ 安全 | ❌ 误杀 |
| 安全检查范围 | 单机时钟（一定单调） | 对端 IP（不区分端口） |
| Linux 4.12+ | 保留 | **已删除** |
| 推荐 | ✅ 开启 | ❌ 必须关闭 |

### 历史背景

`tcp_tw_recycle` 的问题并非新发现。2016 年 Cloudflare 发表了一篇经典博文详细分析了这个参数在 CDN 场景下的危害——CDN 前面的用户同样经过各种 NAT，大量合法请求被 PAWS 误杀。Linux 社区在 **2017 年的 4.12 内核中彻底删除了 `tcp_tw_recycle`**（commit `4396e46187ca`），commit message 中明确写道：

> "tcp_tw_recycle is broken for active connections behind NAT"

CentOS 7 使用的是 3.10 内核（带了大量 Red Hat 回移植），这个有缺陷的功能一直保留到了 2024 年 6 月 CentOS 7 EOL。

---

## 附：云镜防火墙的潜在风险

排查过程中发现的另一个因素——腾讯云云镜（YunJing）主机安全产品的 iptables 规则：

```
┌── iptables INPUT 链 ──────────────────────────────────────┐
│                                                           │
│  ① YJ-FIREWALL-INPUT  ← 67 条单 IP REJECT 规则            │
│     针对 SSH 爆破检测到的攻击 IP，独立封禁                  │
│                                                           │
│  ② YJ-GLOBAL-INBLOCK  ← ipset 黑名单 ~10468 个 IP         │
│     匹配条件: tcp --syn (所有 SYN 包，不限端口)            │
│     动作: DROP                                            │
│     更新频率: 每 5-10 分钟                                 │
│     封禁 TTL: 7200 秒 (2 小时)                            │
│                                                           │
└───────────────────────────────────────────────────────────┘

日志证据:
  $ grep BruteForce /usr/local/qcloud/YunJing/log/ydservice.20260802.log
  bf_rule ips_size:30000 vul_ips_size:10468
  ban_seconds:7200 expire_seconds:21600
```

**潜在风险**：黑名单是云端的威胁情报推送下来的，如果某个 CGNAT 出口 IP（大量正常用户共享）因为同一 IP 下的某台被控设备发起了攻击行为被加入黑名单，**该 IP 后所有正常用户都无法访问服务器的任何端口**——而且是 TCP 握手阶段的 DROP，连 HTTP 响应都看不到，直接 `ERR_CONNECTION_RESET`。

排查命令（如果后续再次出现）：

```bash
# 添加临时 LOG 规则，记录被拦截的 IP
iptables -I INPUT -p tcp --syn -m set --match-set YJ-GLOBAL-INBLOCK src \
  -j LOG --log-prefix "YJ-DROP: "

# 复现问题后立刻查看
dmesg | grep "YJ-DROP" | tail -10

# 清理 LOG 规则
iptables -D INPUT -p tcp --syn -m set --match-set YJ-GLOBAL-INBLOCK src \
  -j LOG --log-prefix "YJ-DROP: "
```

---

## 排查方法论总结

```
现象层         手机端间歇性 ERR_CONNECTION_RESET
               ├─ 有时候能，有时候不能
               └─ 微信比浏览器更容易触发
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
全局视图     服务/端口/防火墙/日志       错误码语义分析
            ├─ 服务正常               ├─ RESET ≠ TIMEOUT
            ├─ 端口监听               ├─ RESET ≠ REFUSED
            └─ iptables 有大量 DROP⚠   └─ RESET → TCP 握手失败
                         │                         │
                         └──────────┬──────────────┘
                                    ▼
收敛分析     TCP 握手阶段"选择性"丢弃 SYN
            ├─ iptables DROP → 黑名单（始终拦截，不符合同歇性特征）
            └─ 内核参数 → tcp_tw_recycle=1（per-IP 缓存 + NAT = 间歇性碰撞）✓
                                    │
                                    ▼
根因验证     • 确认 tcp_tw_recycle=1
            • 理解 PAWS 机制 + per-IP cache 设计
            • 理解 CGNAT 拓扑 → 时间戳碰撞 → 间歇性误杀
            • 修复后观察 → 浏览器立刻恢复，微信延迟恢复（客户端缓存）
                                    │
                                    ▼
修复         sysctl -w net.ipv4.tcp_tw_recycle=0  立即生效
            /etc/sysctl.conf 写入                  永久化
```

核心原则只有一条：

> **间歇性问题优先怀疑状态竞争和资源边界，而非逻辑错误。**

逻辑错误是确定性的——同样的输入必然产生同样的错误输出。间歇性意味着有一个**可变的状态变量**在起作用（缓存、时钟、队列、计数器），排查的要务是找到"什么状态在什么条件下被污染了"，然后看这个状态为什么在某些场景下必然触发。

这次的状态变量是 `per-IP timestamp cache`，它被 NAT 后面的多设备时钟差异污染了。一行 `sysctl` 就修好了，但背后的知识链条跨越了 TCP 协议栈、CGNAT 网络架构、Linux 内核参数演进三个领域。
