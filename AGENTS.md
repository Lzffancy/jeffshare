# AGENTS.md — 个人博客 & 研究报告展示

## 项目目录结构

```
/srv/blog → 实际部署路径: /data/jeff_share_svr
├── site/                          # [NEW] Astro 静态站点工程
│   ├── astro.config.mjs           # Astro 5 配置 (Vue + Tailwind)
│   ├── package.json               # 依赖: astro5, tailwindcss4, daisyui5, vue
│   ├── src/
│   │   ├── content.config.ts      # Content Collections schema (blog/reports/share)
│   │   ├── layouts/BaseLayout.astro
│   │   ├── components/            # Card, Hero, SiteNav
│   │   ├── pages/                 # index, blog/[slug], reports, share/[...path]
│   │   └── styles/global.css      # daisyUI 主题 (藏蓝#003087 + 橙色#e87722)
│   ├── public/admin/              # Decap CMS 后台 (config.yml + index.html)
│   └── dist/                      # 构建产物 → Caddy 直接提供
├── app/
│   ├── main.py                    # FastAPI: 入口 + 路由挂载
│   ├── entity/                    # Clean Architecture: 核心模型 + 端口契约
│   │   ├── agent.py               # AgentDefinition / AgentVersion / AgentStep / ModelParams
│   │   ├── execution.py           # ExecutionRecord
│   │   ├── values.py              # StepType / ConfigStatus / WorkflowType / ExecutionStatus
│   │   └── ports.py               # ILlmClient / IWorkflowEngine / IAgentConfigRepo / IExecutionRepo
│   ├── logic/                     # Clean Architecture: 用例层
│   │   ├── orchestrator.py        # AgentOrchestrator / StepExecutor / WorkflowContext
│   │   ├── summarize.py           # SummarizeUseCase（AI 会话总结）
│   │   ├── save_markdown.py       # SaveMarkdownUseCase（保存 Markdown）
│   │   ├── dtos.py                # 用例 DTO
│   │   └── registry.py            # Agent 注册表
│   ├── repository/                # Clean Architecture: 适配器层（外部依赖实现）
│   │   ├── llm/openai_client.py   # OpenAI LLM 适配器
│   │   ├── persistence/           # SQLite 仓储 + 种子数据
│   │   └── workflow/langgraph_engine.py  # LangGraph 工作流引擎
│   ├── service/                   # Clean Architecture: 协议层（FastAPI 路由 + 组合根）
│   │   ├── routes.py              # Agent API 路由 + DI
│   │   ├── schemas.py             # Pydantic 请求/响应模型
│   │   └── graffiti.py            # 涂鸦墙 API
│   └── middleware/                # 横切关注点
│       └── oauth.py               # Decap CMS OAuth 中转
├── content/
│   ├── posts/                     # 博客文章 (.md, frontmatter: title/date/tags/draft)
│   ├── reports/                   # 研究报告 (每个子目录一份报告)
│   └── share/                     # 分享工作台 (静态HTML)
├── dev_doc/                       # 项目开发文档 & 规划
│   ├── README.md                   #   开发文档目录索引
│   └── plans/                      #   开发 spec（先规划再开发）
├── venv/                          # Python 虚拟环境
└── requirements.txt               # FastAPI + httpx (不再需要 Jinja2/markdown-it-py)
```

## SSD 开发范式 (Specification-Driven Development)

本项目严格遵循 **SSD（规约驱动开发）** 范式。所有 agent 在 `/data/jeff_share_svr` 下进行任何改动时，**必须** 遵守以下流程：

### 核心原则

> **先写规约，再写代码。没有规约，不写代码。**

### 工作流程

1. **需求分析** → 理解用户需求，明确功能边界和验收标准
2. **编写规约 (Specification)** → 在开始编码前，产出以下内容：
   - **功能概述**：要做什么、为什么做
   - **技术方案**：涉及哪些文件/模块、数据流如何走
   - **UI/交互设计**（如涉及前端）：组件树、状态管理、用户交互流程
   - **接口定义**（如涉及 API）：请求/响应结构、错误处理
   - **验收标准**：如何判断功能完成
3. **规约评审** → 将规约呈现给用户确认（除非是微小变更，可自行判断后直接执行）
4. **按规约实现** → 严格按照规约逐步编码，每一步都对照规约检查
5. **验证** → 实现完成后对照验收标准自查

### 规约模板

当需要进行非微小变更时，按以下结构输出规约：

```markdown
## 规约: <功能名称>

### 1. 背景与目标
- 为什么要做这个改动
- 期望达成的效果

### 2. 技术方案
- 涉及的文件/模块及改动范围
- 数据流 / 组件关系图（文字描述即可）

### 3. 详细设计
- 每个文件的具体改动内容
- 新增/修改的函数、组件、类型定义

### 4. 验收标准
- [ ] 标准1
- [ ] 标准2
```

### 微小变更豁免

以下情况可跳过规约步骤，直接实施：
- 修复拼写错误、格式化代码
- 更新文档/注释
- 调整配置项（单行改动）
- 其他明显的单文件、单函数级微调

> **规则**: Agent 完成改动后，**必须 commit + push**。
> Commit message 格式: `agent: <简述改动>`

---

## 如何发布内容

### 方式一：网页后台 (Decap CMS)
访问 `https://jeffshare.com/admin/` → GitHub OAuth 登录 → 表单编辑 → 保存即自动 git commit + push

### 方式二：Git 手写发布
在 `content/posts/` 下新建 `.md` 文件，frontmatter 格式:
```yaml
---
title: 文章标题
date: 2026-06-14
tags:
  - 标签1
  - 标签2
draft: false
---
正文 (Markdown)
```

### 研究报告
在 `content/reports/` 下新建目录，放入文件。通过 `/reports-files/<目录名>/` 访问。

### 分享工作台
在 `content/share/` 下放入 `.html` 文件，通过 `/share/<文件名>` 访问（自动注入站点导航条）。

## 部署方式

**`git add && git commit && git push origin main` 即自动部署。**

- 本地 repo: `/data/jeff_share_svr`
- Bare repo: `/data/git/blog.git`
- Post-receive hook: 自动 checkout → pip install → `jeff-build`(Docker Node20 Astro构建) → systemctl restart jeff_share_svr → caddy reload

## 服务管理

| 组件 | 端口 | systemd unit | 说明 |
|------|------|-------------|------|
| Astro 构建产物 | - | - | `/data/jeff_share_svr/site/dist/`，由 Caddy 直接提供 |
| FastAPI (uvicorn) | 127.0.0.1:8000 | `jeff_share_svr` | API + OAuth 中转 |
| Caddy | :80/:443 | `caddy` | 静态文件服务 + `/api/*`和`/admin-auth/*`反代到:8000 |

### 常用命令

```bash
# 手动构建前端
jeff-build

# 查看应用日志
sudo journalctl -u jeff_share_svr -f

# 查看 Caddy 日志
sudo journalctl -u caddy -f

# 查看服务状态
sudo systemctl status jeff_share_svr
sudo systemctl status caddy

# 重启服务
sudo systemctl restart jeff_share_svr
sudo systemctl reload caddy    # Caddy 配置变更后

# Caddy 配置文件
/etc/caddy/Caddyfile

# Clash 代理 (解决 GitHub 被墙)
# 启动: /data/clash-linux-amd64-v1.13.0 -f /data/jeff_share/clash_proxy.txt
# 代理端口: 127.0.0.1:7890
```

## E2E 测试

### 环境架构

宿主机 CentOS 7 glibc 2.17 太老，Playwright Chromium 无法运行。测试在 Docker 容器内执行，通过 `--network host` 访问宿主机的 Caddy + FastAPI。

```
e2e/
├── Dockerfile              # node:20 (Debian) + Chromium + 系统依赖
├── package.json            # @playwright/test
├── playwright.config.ts    # 测试配置（baseURL、浏览器、trace）
├── run.sh                  # 一键构建镜像并运行测试
└── tests/
    └── smoke.spec.ts       # 冒烟测试
```

### 运行测试

```bash
# 前提：Caddy + FastAPI 必须已在宿主机运行
cd /data/jeff_share_svr/e2e

# 首次需要构建镜像（下载 Chromium ~177MB，约 2-3 分钟）
./run.sh

# 指定测试文件
./run.sh tests/smoke.spec.ts

# 按名称过滤
./run.sh --grep "博客"

# 更换目标 URL（CI 等场景）
BASE_URL=https://jeffshare.com ./run.sh
```

### 镜像说明

- **基础镜像**: `node:20`（Debian），不能用 Alpine（Chromium 需要 glibc）
- **内置浏览器**: 仅 Chromium（`npx playwright install chromium`）
- **镜像名**: `jeff-playwright`
- **网络模式**: `--network host`（容器直接访问宿主机 localhost:443 / :8000）
- 目标 URL 默认 `https://localhost`（Caddy 本地自签名证书，`ignoreHTTPSErrors: true`）

### 测试内容

冒烟测试覆盖：首页加载、导航栏、博客列表和导航、报告页、分享页、API 可达性。

### 为什么不是 Alpine

现有的 `site/Dockerfile.builder`（Astro 构建）用 `node:20-alpine`，因为 Tailwind CSS 有 `@tailwindcss/oxide-linux-x64-musl` 的 musl 构建。但 Playwright Chromium **只有 glibc 构建**，在 Alpine 上会跑不起来，所以必须用 Debian 系镜像。

## Docker 使用盘点

| 组件 | 运行方式 | 容器化 | 原因 |
|------|---------|--------|------|
| **Astro 构建** | Docker `node:20-alpine` | ✅ 必须 | 宿主机 CentOS 7 glibc 2.17，Node 18+ 要求 ≥2.28 |
| **E2E 测试** | Docker `node:20` | ✅ 必须 | Playwright Chromium 需要新版 glibc |
| **FastAPI** | 宿主机 venv + systemd | ❌ 不需要 | Python 3.10 在 CentOS 7 上工作正常，容器化收益不大 |
| **Caddy** | 宿主机 systemd | ❌ 不建议 | 网络层组件，处理证书和端口绑定，容器化反而增加复杂度 |
| **Clash** | 宿主机 | ❌ 不建议 | 代理需要劫持网络流量，容器化会引入嵌套网络问题 |

**结论**: 不追求全部容器化。当前"**跑不动的进 Docker，能跑的留宿主机**"是最务实的方案。

## 技术栈

- **Astro 5** + Tailwind CSS v4 + daisyUI v5 — 静态站点生成
- **Vue 3** (@astrojs/vue) — 交互岛（预留）
- **Decap CMS** — Git-based 网页内容管理后台
- **FastAPI** + httpx — OAuth 中转 + API 骨架
- **Caddy** — 反向代理 + 静态文件服务
- **Docker** (node:20-alpine + node:20) — Astro 构建 + E2E 测试
- **Playwright** — 端到端测试（Chromium，Docker 内运行）
- **systemd** — 进程管理
- **Git** bare repo + post-receive hook — 自动部署
- **CentOS 7**, 内核 3.10, Python 3.10
