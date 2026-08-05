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

## 如何发布内容

### 方式一：网页后台 (Decap CMS)
访问 `https://jeff.work/admin/` → GitHub OAuth 登录 → 表单编辑 → 保存即自动 git commit + push

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

> **规则**: 任何 agent 在 `/data/jeff_share_svr` 下完成改动后，**必须 commit + push**。
> Commit message 格式: `agent: <简述改动>`

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
