# AGENTS.md — 个人博客 & 研究报告展示

## 项目目录结构

```
/srv/blog → 实际部署路径: /data/jeff_share_svr
├── app/
│   ├── main.py          # FastAPI 应用主入口，定义全部路由
│   ├── templates/       # Jinja2 模板 (base/index/blog_list/blog_post/reports_list)
│   └── static/          # 静态文件 (CSS)
├── content/
│   ├── posts/           # 博客文章 (.md, frontmatter: title/date/tags)
│   └── reports/         # 研究报告 (每个子目录一份报告, 放 HTML/PDF 等静态文件)
├── venv/                # Python 虚拟环境
└── requirements.txt
```

## 如何发布内容

### 新博客文章
在 `content/posts/` 下新建 `.md` 文件，frontmatter 格式:
```yaml
---
title: 文章标题
date: 2026-06-14
tags:
  - 标签1
  - 标签2
---
正文 (Markdown)
```

### 研究报告
在 `content/reports/` 下新建目录，放入文件。通过 `/reports/files/<目录名>/` 访问。

## 部署方式

**`git add && git commit && git push origin main` 即自动部署。**

- 本地 repo: `/data/jeff_share_svr`
- Bare repo: `/data/git/blog.git`
- Post-receive hook: 自动 checkout → pip install → systemctl restart blog

> **规则**: 任何 agent 在 `/data/jeff_share_svr` 下完成改动后，**必须 commit + push**。
> Commit message 格式: `agent: <简述改动>`

## 服务管理

| 组件 | 端口 | systemd unit | 说明 |
|------|------|-------------|------|
| FastAPI (uvicorn) | 127.0.0.1:8000 | `blog` | 应用主进程 |
| Caddy | :80 | `caddy` | 反向代理 + 静态文件 |

### 常用命令

```bash
# 查看应用日志
sudo journalctl -u blog -f

# 查看 Caddy 日志
sudo journalctl -u caddy -f

# 查看服务状态
sudo systemctl status blog
sudo systemctl status caddy

# 手动重启
sudo systemctl restart blog
sudo systemctl reload caddy

# Caddy 配置文件
/etc/caddy/Caddyfile

# Clash 代理 (解决 GitHub 被墙)
# 启动: /data/clash-linux-amd64-v1.13.0 -f /data/jeff_share/clash_proxy.txt
# 代理端口: 127.0.0.1:7890
```

## 技术栈

- **FastAPI** + Jinja2 模板
- **markdown-it-py** + python-frontmatter 处理博客
- **Caddy** 反向代理
- **systemd** 进程管理
- **Git** bare repo + post-receive hook 部署
- **CentOS 7**, 内核 3.10, Python 3.10
