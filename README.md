# 杰夫的工作台 — jeffshare.com

个人博客 + 研究报告 + 分享工作台 + AI 工作台的现代化静态站点。

## 整体架构

```
你写 Markdown ──→ 改磁盘 content/ ──→ 手动 jeff-build ──┐
                                                      ├─→ 静态 HTML
代码改动 git push ──→ post-receive hook ──→ 自动 jeff-build ┘

浏览器 ──→ Caddy (:80/:443) ──→ site/dist/ 静态文件（秒开）
                     └──→ /api/*、/login* ──→ FastAPI :8000（API 骨架 + 预留鉴权）
```

**核心理念**：内容 = 磁盘上的 Markdown/HTML 文件 → 构建时生成静态 HTML → 运行时零开销（纯静态文件）。
**内容与代码解耦**：`content/` 不进 git，只留服务器磁盘；代码进 git，push 触发自动构建。

## 目录结构

```
/data/jeff_share_svr/                  # 项目根目录
│
├── content/                           # ★ 内容（不进 git，仅留磁盘）
│   ├── posts/                         #   博客文章 .md（每篇可配同目录 <slug>_pic/ 图片）
│   ├── reports/                       #   研究报告（每份一个子目录）
│   └── share/                         #   分享工作台 .html
│
├── site/                              # ★ 前端工程（Astro 5 静态站点）
│   ├── astro.config.mjs               #   Astro 配置：集成 Vue + Tailwind
│   ├── package.json                   #   npm 依赖声明
│   ├── Dockerfile.builder             #   构建镜像（node:20-alpine，含 node_modules 烤入）
│   ├── scripts/jeff-build             #   ★ 构建脚本（Docker 依赖指纹缓存 + 挂载 /content）
│   ├── src/
│   │   ├── content.config.ts          #   ★ 内容 Schema（定义 blog 集合；reports/share 由 fs 扫描）
│   │   ├── layouts/
│   │   │   └── BaseLayout.astro        #   ★ 全局布局（导航栏 + footer + SEO meta）
│   │   ├── components/                #   可复用 UI 组件（Card / Hero / SiteNav / WorkbenchApp.vue …）
│   │   ├── pages/                     #   ★ 页面 = 文件路径 = URL 路径
│   │   │   ├── index.astro            #     /            首页聚合
│   │   │   ├── blog/
│   │   │   │   ├── index.astro        #     /blog        文章列表
│   │   │   │   └── [slug].astro       #     /blog/xxx     文章详情（动态路由）
│   │   │   ├── reports/
│   │   │   │   ├── index.astro        #     /reports      报告列表
│   │   │   │   └── reports-files/[...path].astro  # /reports-files/xxx 报告文件透传
│   │   │   ├── share/
│   │   │   │   ├── index.astro        #     /share        分享文件列表
│   │   │   │   └── [...path].astro    #     /share/xxx    分享文件透传
│   │   │   └── workbench/index.astro  #     /workbench    AI 工作台（Vue 岛）
│   │   └── styles/
│   │       └── global.css             #   全局样式（daisyUI 主题 + Markdown 排版）
│   ├── public/                        #   ★ 站点级静态资源（进 git：logo/favicon/装饰图）
│   └── dist/                          #   构建产物（Caddy 直接提供，不要手动改）
│
├── app/                               # 后端（FastAPI）
│   └── main.py                        #   API 骨架 + 密码登录鉴权（require_auth，供未来网页后台）
│
├── dev_doc/                           # ★ 项目开发文档（README.md 索引 + plans/ 开发 spec）
├── venv/                              # Python 虚拟环境
├── requirements.txt                   # Python 依赖
├── AGENTS.md                          # AI Agent 操作手册（权威约定在此）
└── README.md                          # 你正在看的这个文件
```

## 内容如何驱动站点（新增内容零代码改动）

站点前台完全由 `content/` 目录驱动，新增文件即自动出现入口与路由，无需改代码：

| 内容 | 放哪 | 出现位置 |
|------|------|---------|
| 博客文章 | `content/posts/<slug>.md` | `/blog` 列表 + `/blog/<slug>` 详情，首页自动聚合 |
| 研究报告 | `content/reports/<目录名>/` 下文件 | `/reports` 列表 + `/reports-files/<目录名>/` 透传 |
| 分享页面 | `content/share/<文件名>.html` | `/share` 列表 + `/share/<文件名>` 透传（自动注入返回导航条）|

> `draft: true` 的文章不会进入 `/blog` 列表与首页，但仍可通过 `/blog/<slug>` 直接访问（草稿态）。

## 如何新增/修改内容

> **当前阶段没有网页后台**：所见即所得编辑器与"点发布"流程为**待开发**项，后续阶段再补。
> 现在发布内容 = 直接在服务器磁盘改 `content/` + 跑一次构建。

### 方式一：直接改磁盘文件（当前唯一方式，零依赖）

1. 在 `content/posts/` 下新建 `<slug>.md`：

```yaml
---
title: 你的文章标题
date: 2026-08-13
tags:
  - 标签1
  - 标签2
draft: false          # true = 草稿，不进列表
source: manual        # manual（手写）或 ai（AI 生成）
---
正文（标准 Markdown，支持代码块、表格、图片、引用）
```

2. （可选）该文的图片放进 `content/posts/<slug>_pic/`，md 里用相对路径引用（见下）。
3. 运行 `bash site/scripts/jeff-build` 手动重建静态站。

### 方式二：代码改动（自动部署）

改 `site/`、`app/` 等代码 → `git add && git commit && git push origin main` →
post-receive hook **自动**跑 `jeff-build` 完成部署（见"部署"章节）。

### 图片约定（两类，务必分清）

| 类别 | 放哪 | 进 git? | 引用方式 |
|------|------|--------|---------|
| **内容配图**（文章图） | `content/posts/<slug>_pic/` | ❌ 随 `content/` 脱管 | `![说明](./<slug>_pic/图.png)`（Astro 构建时自动打包进 `_astro/`）|
| **站点级资源**（logo/favicon/装饰图） | `site/public/images/` 或 `site/src/assets/` | ✅ 进 git | `/images/xxx` 或 import |

内容配图随文章目录 co-located，**下载整个 `<slug>` 目录即得一份完整、可携带的自包含笔记**。

## 前端技术栈（给不熟悉前端的后端同学）

### 为什么选这些？

| 技术 | 类比后端概念 | 解决的问题 |
|------|-------------|-----------|
| **Astro 5** | 模板引擎 | 把 Markdown 编译成 HTML。`.astro` 文件 ≈ Jinja2 模板 |
| **Tailwind CSS v4** | 行内样式 | `class="text-primary bg-base-100"` ≈ `style="color:#003087;background:white"` |
| **daisyUI v5** | 组件库 | `class="btn btn-primary"` — 一行 class 就能渲染按钮，不用手写 CSS |
| **Vue 3** | 交互岛 | `/workbench` 工作台用 Vue 岛调 FastAPI；其余页面纯静态 |

### 关键概念：文件即路由

```
src/pages/index.astro              →   /
src/pages/blog/index.astro         →   /blog
src/pages/blog/[slug].astro        →   /blog/hello-world      ([slug] 是动态参数)
src/pages/share/[...path].astro    →   /share/anything/here   ([...path] 是多级通配)
```

和 FastAPI 的 `@app.get("/blog/{slug}")` 思路一样，只是用**目录结构**替代装饰器声明。

### 关键概念：Content Collections（内容集合）

`src/content.config.ts` 相当于 ORM 的 Schema 定义（目前 `blog` 用集合，reports/share 由 fs 扫描）：

```typescript
const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "../content/posts" }),
  //  ↑ 告诉 Astro：去 ../content/posts 扫描所有 .md 文件
  schema: z.object({
    title: z.string(),                 // 必填字符串
    date: z.coerce.date(),             // 自动转成日期对象
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    source: z.enum(["manual","ai"]).default("manual"),
  }),
  //  ↑ 定义 frontmatter 的字段和类型（相当于 Pydantic model）
});
```

**数据流**：`content/posts/xxx.md` → Astro 读取 frontmatter → 按 schema 校验 → 注入页面模板 → 生成 HTML。

### 关键概念：daisyUI 主题变量

颜色统一在 `src/styles/global.css` 定义，核心两个：

| 变量 | 值 | 用途 |
|------|-----|------|
| `--color-primary` | `#003087`（藏蓝） | 按钮、标题、导航栏 |
| `--color-accent` | `#e87722`（橙色） | 强调色、链接 hover |

daisyUI 自动派生 `--color-primary-content`、背景、阴影、圆角等。换主题只改这一个文件。

## 本地开发

```bash
# 前端开发服务器（需要本地 Node.js —— 在你自己的开发机跑，别在服务器跑）
cd site && npm install && npm run dev    # 热重载，默认 http://localhost:4321

# 后端 API（需要 Python 3.10 venv）
source venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

## 部署

### 触发策略（何时重建静态站）

| 时机 | 触发方式 | 是否误触 |
|------|----------|----------|
| 代码改动 | `git push` → post-receive hook → `jeff-build` | 否（push 主动） |
| 本地改内容 | 手动跑 `bash site/scripts/jeff-build` | 否（不监听磁盘） |
| 网页发布 | 待开发（点"发布"→ API 调 `jeff-build`）| 否（仅点击） |

> **绝不挂文件监听器**：只有 push 或你手动敲命令才会重建，避免误改文件误触发。

### post-receive hook 流程（每次 push）

1. 备份 `content/` 与 `site/public/images/`（防 `reset --hard` 误删，因二者已脱管）
2. `git reset --hard main`
3. 恢复脱管目录
4. `site/scripts/jeff-build`（Docker 构建静态站）
5. 仅代码变更时 `kill -HUP` 滚动重启 uvicorn；内容变更只重建静态站
6. `caddy reload`

### 关于构建环境（重要）

> ⚠️ **构建在 Docker 容器内完成，服务器本机（CentOS 7）不装 Node.js。**
>
> 生产服务器是 **CentOS 7 / glibc 2.17**，而 Node 18+ 要求 **glibc ≥ 2.28**，
> 本机直跑 `npm install`/`astro build` 会报 `GLIBC_2.28 not found`。
> `site/scripts/jeff-build` 已封装好：用预装 `node_modules` 的 `jeff-astro-builder` 镜像
> （按 `package.json`+`package-lock.json`+`.npmrc` 的 SHA256 指纹缓存，依赖不变则跳过 `npm install`），
> 挂载 `site/src`、`site/public`、`content` 进容器跑 `npm run build`，构建完容器即销毁。
> 想去掉 Docker，需把宿主机换成 glibc ≥ 2.28 的系统（如 Ubuntu 24.04）。

```bash
# 手动构建前端（内容变更后）
bash site/scripts/jeff-build

# 查看服务/部署日志
sudo journalctl -u jeff_share_svr -f
sudo journalctl -u caddy -f
```

## 环境依赖

| 组件 | 运行位置 | 用途 |
|------|---------|------|
| Caddy | 宿主机 | Web 服务器：`root site/dist` 静态直出 + `/api/*`、`/login*` 反代 :8000 |
| Docker (`jeff-astro-builder`) | 容器 | Astro 构建（glibc 不兼容的 workaround，依赖指纹缓存） |
| Python 3.10 (venv) | 宿主机 | FastAPI API 服务 |
| Clash | 宿主机 :7890 | GitHub 代理（解决网络封锁） |

CentOS 7 太老装不了 Node 18+，所以构建走 Docker。换 Ubuntu 24.04 后可直装 Node、去掉 Docker。
