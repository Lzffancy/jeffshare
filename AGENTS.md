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
│   ├── main.py                    # FastAPI: OAuth中转 + 未来API骨架 (不再渲染页面)
├── content/
│   ├── posts/                     # 博客文章 (.md, frontmatter: title/date/tags/draft)
│   ├── reports/                   # 研究报告 (每个子目录一份报告)
│   └── share/                     # 分享工作台 (静态HTML)
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

## 技术栈

- **Astro 5** + Tailwind CSS v4 + daisyUI v5 — 静态站点生成
- **Vue 3** (@astrojs/vue) — 交互岛（预留）
- **Decap CMS** — Git-based 网页内容管理后台
- **FastAPI** + httpx — OAuth 中转 + API 骨架
- **Caddy** — 反向代理 + 静态文件服务
- **Docker** (node:20-alpine) — Astro 构建运行环境
- **systemd** — 进程管理
- **Git** bare repo + post-receive hook — 自动部署
- **CentOS 7**, 内核 3.10, Python 3.10
