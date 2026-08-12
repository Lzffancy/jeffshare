# 杰夫的工作台 — jeffshare.com

个人博客 + 研究报告 + 分享工作台的现代化静态站点。

## 整体架构（一张图）

```
你写 Markdown ──→ git push ──→ post-receive hook ──→ Docker 构建 ──→ 静态 HTML
     ↑                                                    │
     └─── Decap CMS 网页后台 ──── GitHub OAuth ──────────┘

浏览器 ──→ Caddy (:80/:443) ──→ site/dist/ 静态文件（秒开）
                     └──→ /api/* ──→ FastAPI :8000（OAuth 中转 + 预留 API）
```

**核心理念**：内容 = Markdown 文件 → 构建时生成 HTML → 运行时零开销（纯静态文件）。

## 目录结构

```
/data/jeff_share_svr/                  # 项目根目录
│
├── content/                           # ★ 内容仓库（Markdown + HTML）
│   ├── posts/                         #   博客文章 .md
│   ├── reports/                       #   研究报告（每份一个子目录）
│   └── share/                         #   分享工作台 .html
│
├── site/                              # ★ 前端工程（Astro 5 静态站点）
│   ├── astro.config.mjs               #   Astro 配置：集成 Vue + Tailwind
│   ├── package.json                   #   npm 依赖声明
│   ├── src/
│   │   ├── content.config.ts          #   ★ 内容 Schema（定义 blog/reports/share 结构）
│   │   ├── layouts/
│   │   │   └── BaseLayout.astro        #   ★ 全局布局（导航栏 + footer + SEO meta）
│   │   ├── components/                #   可复用 UI 组件
│   │   │   ├── Card.astro             #     卡片组件（首页入口卡片）
│   │   │   ├── Hero.astro             #     英雄横幅（渐变背景 + 徽标）
│   │   │   └── SiteNav.astro          #     导航栏（吸顶 + 移动端下拉菜单）
│   │   ├── pages/                     #   ★ 页面 = 文件路径 = URL 路径
│   │   │   ├── index.astro            #     / → 首页
│   │   │   ├── blog/
│   │   │   │   ├── index.astro        #     /blog → 文章列表
│   │   │   │   └── [slug].astro       #     /blog/xxx → 文章详情（动态路由）
│   │   │   ├── reports/
│   │   │   │   └── index.astro        #     /reports → 报告列表
│   │   │   ├── reports-files/
│   │   │   │   └── [...path].astro    #     /reports-files/xxx → 报告文件透传
│   │   │   └── share/
│   │   │       ├── index.astro        #     /share → 分享文件列表
│   │   │       └── [...path].astro    #     /share/xxx → 分享文件透传
│   │   └── styles/
│   │       └── global.css             #   全局样式（daisyUI 主题 + Markdown 排版）
│   ├── public/
│   │   └── admin/                     #   Decap CMS 网页后台
│   │       ├── index.html             #     后台入口页面
│   │       └── config.yml             #     后台配置（字段 = content.config.ts 的 schema）
│   └── dist/                          #   构建产物（Caddy 直接提供，不要手动改）
│
├── app/                               # 后端（FastAPI）
│   └── main.py                        #   OAuth 中转 + API 骨架
│
├── dev_doc/                           # ★ 项目开发文档
│   ├── README.md                       #   开发文档目录索引
│   └── plans/                          #   开发 spec（先规划再开发）
│       └── phase1-ai-summarize-pipeline.md
│
├── venv/                              # Python 虚拟环境
├── requirements.txt                   # Python 依赖
├── AGENTS.md                          # AI Agent 操作手册
└── README.md                          # 你正在看的这个文件
```

## 如何新增内容（零代码改动）

### 方式 1：网页后台（推荐，无需 Git 知识）

访问 `https://jeffshare.com/admin/` → GitHub 授权登录 → 填表单 → 保存 → **自动 git commit + 部署**（约 5-10 秒延迟）。

### 方式 2：直接写 Markdown（后端开发现场就行）

在 `content/posts/` 下新建 `.md` 文件：

```yaml
---
title: 你的文章标题
date: 2026-08-05
tags:
  - 标签1
  - 标签2
draft: false          # true = 不发布，首页不显示
---

正文（标准 Markdown 语法，支持代码块、表格、图片、引用）
```

然后 `git add && git commit && git push origin main`，自动构建部署。

### 新增报告

在 `content/reports/你的报告名/` 下放入 HTML/PDF 等文件，提交即可。访问 `/reports-files/你的报告名/`。

### 新增分享文件

在 `content/share/` 下放入 `.html` 文件，提交即可。访问 `/share/文件名`。**注意**：分享文件会自动注入站点导航条，不需要你手动加。

## 前端技术栈（给不熟悉前端的后端同学）

### 为什么选这些？

| 技术 | 类比后端概念 | 解决的问题 |
|------|-------------|-----------|
| **Astro 5** | 模板引擎 | 把 Markdown 编译成 HTML。`.astro` 文件 ≈ Jinja2 模板 |
| **Tailwind CSS v4** | 行内样式 | `class="text-primary bg-base-100"` ≈ `style="color:#003087;background:white"` |
| **daisyUI v5** | 组件库 | `class="btn btn-primary"` — 一行 class 就能渲染一个按钮，不用手写 CSS |
| **Vue 3** | 仅预留 | 未来需要交互时（搜索、留言）再启用，目前不影响任何功能 |

### 关键概念：文件即路由

```
src/pages/index.astro          →   /
src/pages/blog/index.astro     →   /blog
src/pages/blog/[slug].astro    →   /blog/hello-world      ([slug] 是动态参数)
src/pages/share/[...path].astro →  /share/anything/here   ([...path] 是多级通配)
```

这和 FastAPI 的 `@app.get("/blog/{slug}")` 思路一样，只是用**目录结构**替代了装饰器声明。

### 关键概念：Content Collections（内容集合）

`src/content.config.ts` 相当于 ORM 的 Schema 定义：

```typescript
const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "../content/posts" }),
  //  ↑ 告诉 Astro：去 ../content/posts 扫描所有 .md 文件
  schema: z.object({
    title: z.string(),           // 必填字符串
    date: z.coerce.date(),       // 自动转成日期对象
    tags: z.array(z.string()),   // 字符串数组
    draft: z.boolean(),          // true/false
  }),
  //  ↑ 定义 frontmatter 的字段和类型（相当于 Pydantic model）
});
```

**数据流**：`content/posts/xxx.md` → Astro 读取 frontmatter → 按 schema 校验 → 注入到页面模板 → 生成 HTML。

### 关键概念：daisyUI 主题变量

所有的颜色都在 `src/styles/global.css` 中定义，只有 2 个核心变量：

| 变量 | 值 | 用途 |
|------|-----|------|
| `--color-primary` | `#003087`（藏蓝） | 按钮、标题、导航栏 |
| `--color-accent` | `#e87722`（橙色） | 强调色、链接 hover |

daisyUI 会自动从中派生 `--color-primary-content`（白）、`--color-base-100`（背景白）、阴影、圆角等。如果要换主题，只改这一个文件。这就是 Tailwind + daisyUI 比手写 CSS 强的地方 — 不需要在几十个文件里 `git grep #003087`。

## 关于内容与代码的隔离

**当前状态：内容和代码在同一个 Git 仓库**。

```
/data/jeff_share_svr/
├── site/            ← 代码（git 管理）
├── app/             ← 代码（git 管理）
├── content/         ← 内容（也在 git 里！）
│   ├── posts/       ← 8 个文件被 git 跟踪
│   ├── reports/
│   └── share/
```

### 为什么放在一起？

1. **Decap CMS 网页后台**的工作原理就是：用户在网页填表 → CMS 自动 commit 到 GitHub → 触发 post-receive hook 部署。如果 content 不在 git 里，后台就废了。
2. **版本历史**：文章改来改去有记录，不怕改坏。
3. **服务器迁移**：`git clone` 一把梭，代码和内容一起下来。

### 如果你想让内容"只在机器上、不跟 git 走"

可以做到，但需要取舍：

```bash
# 方案 A：把 content/ 加入 .gitignore（内容不进入 git）
echo "content/" >> .gitignore

# 代价：
# 1. Decap CMS 网页后台无法使用（它依赖 git commit）
# 2. git push 不会带内容，换服务器需要手动拷贝 content/
# 3. 手动编辑内容后需要 ssh 到服务器
```

**我的建议**：保持现状。内容是博客的核心资产，用 git 管理更安全。代码和内容虽然在同一个仓库，但它们的**修改频率和责任人不同** — 日常发文章只需要动 `content/` 目录，不影响代码。

## 本地构建与部署

> ⚠️ **构建必须在 Docker 容器内完成，绝对不要在本机（CentOS 7）安装 Node.js！**
>
> 原因：生产服务器是 **CentOS 7，glibc 2.17**；而官方 Node.js 18+ 要求 **glibc ≥ 2.28**，
> 直接在本机跑 `npm install` / `astro build` 会报 `GLIBC_2.28 not found`（之前在这个坑上卡过）。
> 非官方的 `glibc-217` 兼容构建属于 experimental、无长期维护保证，**不要依赖**。
> **正确姿势：用 Node 官方镜像起一个临时容器，在容器里 `npm install && astro build`，构建完容器即销毁，宿主机全程不需要 Node。**

```bash
# 构建（在 site/ 目录下，必须用 Docker）
cd site
docker run --rm -v "$PWD":/app -w /app node:20-alpine \
  sh -c "npm install && npm run build"
# 构建产物输出到 site/dist/（已被 site/.gitignore 忽略，不进 git）。
# 用 alpine 镜像是因为依赖里是 @tailwindcss/oxide-linux-x64-musl（musl 版），别换成 debian 镜像。

# 开发模式（需要本地 Node.js —— 在「自己开发机」上跑，不要在服务器上跑）
cd site && npm run dev    # 启动热重载开发服务器

# 部署
git add . && git commit && git push origin main
# Post-receive hook 自动执行：
#   1. git checkout -f main
#   2. pip install  （Python 依赖）
#   3. docker run ... npm run build  （Astro 静态站点 Docker 构建，见上）
#   4. systemctl restart jeff_share_svr  （API 服务）
#   5. systemctl reload caddy            （Web 服务器）

# 查看部署日志
sudo journalctl -u jeff_share_svr -f
```

> 📌 想彻底去掉 Docker？只有把宿主机换成 **glibc ≥ 2.28** 的系统（如 Ubuntu 24.04）后，
> 才能直接装 Node 跑构建。在 CentOS 7 上不要尝试本地装 Node。

## 环境依赖

| 组件 | 运行位置 | 用途 |
|------|---------|------|
| Caddy | 宿主机 | Web 服务器，静态文件 + 反代 |
| Docker (node:20-alpine) | 容器 | Astro 构建（glibc 不兼容的 workaround） |
| Python 3.10 (venv) | 宿主机 | FastAPI API 服务 |
| Clash | 宿主机 :7890 | GitHub 代理 |

CentOS 7 太老装不了 Node 18+，所以构建走 Docker。如果未来换 Ubuntu 24.04，可以直接装 Node、去掉 Docker。
