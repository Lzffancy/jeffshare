---
name: graffiti-wall
overview: 在首页下方增加公共涂鸦墙：Vue3 Canvas 组件 (自适应性 + 基础画笔工具) + FastAPI 后端存储 (每日自动清空)
design:
  architecture:
    framework: react
  styleKeywords:
    - 卡片式
    - 简洁
    - 主题一致
    - 亲和
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 20px
      weight: 700
    subheading:
      size: 14px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#003087"
      - "#1a5cb5"
      - "#e87722"
    background:
      - "#FFFFFF"
      - "#f0f2f5"
    text:
      - "#1a1a2e"
      - "#666666"
    functional:
      - "#ef4444"
      - "#10b981"
todos:
  - id: graffiti-api
    content: 在 app/main.py 新增 GET/POST /api/graffiti 端点，实现 PNG 文件读写与每日自动清理
    status: completed
  - id: graffiti-component
    content: 创建 site/src/components/GraffitiWall.vue，实现 Canvas 绘图、工具栏和 API 交互
    status: completed
    dependencies:
      - graffiti-api
  - id: homepage-integration
    content: 在 site/src/pages/index.astro 最新文章列表下方引入 GraffitiWall 组件
    status: completed
    dependencies:
      - graffiti-component
  - id: build-verify
    content: 构建验证并提交部署
    status: completed
    dependencies:
      - homepage-integration
---

## 产品概述

在首页「最新文章」列表下方增加一个公共涂鸦墙模块，任何人访问 `https://jeff.work` 都能在同一张画布上涂鸦，每天自动清空重新开始。

## 核心功能

- **自由涂鸦**：支持鼠标和触摸屏直接在画布上绘制线条
- **基础工具栏**：画笔颜色选择器、画笔粗细调节滑块、一键清除按钮
- **公共共享**：所有访客看到同一张画布，涂鸦数据实时同步到服务端
- **每日清零**：每天自动使用空画布，历史涂鸦保留 7 天后自动删除

## 技术栈

- **前端**：Vue 3 组件 (Composition API) + HTML5 Canvas API，嵌入 Astro 静态站点
- **后端**：FastAPI (新增两个端点)，存储为 PNG 文件
- **存储**：文件系统 `/data/jeff_share_svr/graffiti/`，按日期命名 `YYYY-MM-DD.png`
- **代理**：Caddy 已有 `/api/*` 反代规则，新增端点无需改配置

## 实现方案

### 整体策略

采用 **Canvas 绘图 + base64 PNG 传输** 方案。Vue 3 组件在浏览器端使用 Canvas API 处理所有绘图逻辑，每次绘制完成后将画布导出为 base64 PNG 通过 POST 发送到 FastAPI。页面加载时 GET 拉取当天已保存的涂鸦并渲染到画布上。

**为什么选 base64 PNG 而非笔画数据**：

- 笔画数据（坐标数组）更轻量但需要重放逻辑，多人协作时复杂
- PNG 直接就是画布快照，加载即渲染，无重放开销
- base64 传输天然自包含，无需额外的资源文件服务

### 每日清理机制

利用日期文件名实现**零成本的自动清理**：

- 存储文件名为 `YYYY-MM-DD.png`，每天自动生成新文件，旧文件不再被访问
- GET 端点每次被调用时，扫描 `/data/jeff_share_svr/graffiti/` 目录，删除 7 天前的文件（`os.remove`），保证磁盘不无限增长
- 无需 cron、systemd timer 等额外组件

### 数据流

```
页面加载 → GET /api/graffiti → 返回今日 PNG (base64) 或 null → 渲染到 Canvas
用户绘制 → pointerup 事件 → Canvas.toDataURL() → POST /api/graffiti {image: "base64..."} → 写入文件
点击清除 → 清空 Canvas → POST /api/graffiti {image: null} → 删除今日文件
```

### 性能考量

- Canvas 在 `pointerup` 时保存，而非每次 `pointermove`，避免频繁网络请求
- GET 请求携带 `If-None-Match` / `ETag`（文件修改时间），304 缓存进一步减少传输
- Canvas 物理分辨率设为 CSS 尺寸 × devicePixelRatio（上限 2x），保证 Retina 清晰度同时避免过大内存

## 实现细节

### 文件规划

```
site/src/components/GraffitiWall.vue  # [NEW] Vue 3 涂鸦墙组件
site/src/pages/index.astro             # [MODIFY] 在最新文章列表后引入 GraffitiWall
site/src/styles/global.css             # [MODIFY] 新增涂鸦墙相关的全局样式
app/main.py                            # [MODIFY] 新增 GET/POST /api/graffiti 端点
```

### Vue 组件关键设计 (GraffitiWall.vue)

- **响应式画布尺寸**：监听 `ResizeObserver`，宽度跟随容器且不超过 800px，高度固定 400px
- **绘图状态**：`isDrawing` ref 控制是否绘制中；`lastPoint` 记录上一坐标用于 `lineTo` 平滑连线
- **触摸兼容**：`pointerdown/pointermove/pointerup` 统一事件，设置 `touch-action: none` 禁止浏览器默认滚动/缩放
- **加载已有涂鸦**：`onMounted` 时 fetch `GET /api/graffiti`，若有 image 则绘制到 canvas
- **保存时机**：`pointerup` 时 `canvas.toDataURL('image/png')` → debounce 500ms → `POST /api/graffiti`
- **工具状态**：`color` ref（默认 `#003087` 主题色）、`brushSize` ref（默认 3，范围 1-20）
- **清除逻辑**：清空 canvas → POST `{image: null}` 删除服务端文件

### FastAPI 端点设计

`GET /api/graffiti`：

1. 构建今日文件路径 `graffiti/YYYY-MM-DD.png`
2. 若文件存在 → base64 编码返回 `{"image": "data:image/png;base64,..."}`
3. 若不存在 → 返回 `{"image": null}`
4. 附带清理逻辑：遍历目录删除 mtime 超过 7 天的文件

`POST /api/graffiti`：

1. 接受 `{"image": "base64..." | null}`
2. 若 image 为 null → 删除今日文件，返回 `{"status": "cleared"}`
3. 若 image 非空 → 解码 base64 写入 `graffiti/YYYY-MM-DD.png`，返回 `{"status": "saved"}`
4. `os.makedirs("graffiti", exist_ok=True)` 首次自动创建目录

### 与现有系统的兼容性

- GraffitiWall.vue 作为 Vue 3 组件嵌入 Astro 页面（`<GraffitiWall client:load />`），`client:load` 指令保证组件在浏览器端交互
- 不引入新 npm 依赖，Canvas API 为浏览器原生
- `/api/graffiti` 端点遵循现有 FastAPI 的 trace-log middleware 日志规范
- 涂鸦存储目录 `graffiti/` 加入 `.gitignore`，不纳入版本管理
- FastAPI 重启后历史文件保留，不受影响

## 设计风格

涂鸦墙延续站点 daisyUI 主题风格，以藏蓝(#003087)为主色调，橙色(#e87722)为强调色。整体采用卡片式容器，白底圆角阴影，与首页 Card 网格保持视觉一致性。工具栏横向排列在画布上方，清晰不拥挤。

## 页面结构

涂鸦墙模块位于首页「最新文章」列表下方，作为独立区块：

### 区块 1：标题栏

左侧「涂鸦墙」标题（text-xl bold primary），右侧提示文字「每天清空，随意涂鸦」（text-xs muted）

### 区块 2：工具栏

横向排列 3 个控件：颜色选择器（原生 input[type=color]，默认藏蓝）、粗细滑块（range 1-20，默认 3）、清除按钮（btn-outline btn-xs accent 色）。间距统一 gap-3

### 区块 3：画布区域

白底 Canvas，略小于容器宽度（max-w-[800px] mx-auto），固定高度 400px，带 1px 浅灰边框。canvas 元素设置 cursor: crosshair 提示可绘制。移动端 canvas 撑满卡片宽度

### 区块 4：底部状态

轻量状态栏，显示当前画笔颜色圆点和粗细值（text-xs muted）