# 阶段一：AI 会话自动沉淀流水线

> 状态：规划中 | 创建：2026-08-12

## 1. 背景与目标

### 痛点

每次和 AI（ChatGPT / Claude / 本地 Agent 等）完成一次有价值的对话后，想沉淀成博客文章时面临这些步骤：

1. **手工复制粘贴**对话内容
2. **手动整理**为结构化 Markdown
3. **人工提取**关键结论和标签
4. **手动填写** frontmatter（title / date / tags / draft）
5. 最后 commit + push 发布

这个过程**打断创作心流**，导致很多有价值的对话最终没有沉淀。

### 目标

搭建一条 **AI 会话 → 一键沉淀为博客文章** 的半自动化流水线：

- 用户粘贴原始对话 → 系统自动生成结构化的 Markdown 草稿 → 用户在线预览/编辑 → 一键保存到 `content/posts/`
- 整个过程在网页上完成，无需手动操作文件系统

## 2. 架构概览

```
浏览器 (Vue SPA /workbench)
    │
    │  POST /api/agent/summarize  (粘贴原始对话 → 返回结构化 MD)
    │  GET  /api/agent/preview    (渲染 MD 为 HTML 预览)
    │  POST /api/agent/save       (保存到 content/posts/)
    │
    ▼
FastAPI (:8000)
    │
    │  LangGraph 工作流 (内置总结 Agent)
    │      Step 1: 解析对话，识别主题和类型
    │      Step 2: 提取关键结论和观点
    │      Step 3: 生成 frontmatter + 正文 Markdown
    │
    ▼
文件系统: content/posts/<slug>.md
    │
    ├──→ git commit + push
    └──→ Astro 构建 → 发布上线
```

## 3. API 设计

### 3.1 POST /api/agent/summarize

**功能**：接收原始对话文本，返回 AI 总结后的结构化 Markdown。

**Request**:

```json
{
  "conversation": "原始对话全文（支持多轮对话文本）",
  "model": "gpt-4o-mini"
}
```

**Response**:

```json
{
  "success": true,
  "result": {
    "title": "AI 生成的标题",
    "slug": "ai-generated-slug",
    "tags": ["标签1", "标签2"],
    "markdown": "完整的 Markdown 正文（含 frontmatter 和正文）",
    "summary": "一句话摘要"
  }
}
```

**Error Response**:

```json
{
  "success": false,
  "error": "错误描述"
}
```

### 3.2 GET /api/agent/preview

**功能**：将 Markdown 渲染为 HTML 预览。

**Query Params**: `?markdown=<url_encoded_markdown>`

**Response**: HTML 字符串

> 注：后续阶段可改为 POST body 传 markdown，避免 URL 长度限制。

### 3.3 POST /api/agent/save

**功能**：将编辑后的 Markdown 保存到 `content/posts/`。

**Request**:

```json
{
  "slug": "article-slug",
  "markdown": "完整 Markdown（含 frontmatter）"
}
```

**Response**:

```json
{
  "success": true,
  "path": "content/posts/article-slug.md",
  "message": "已保存，待 git commit + push 后上线"
}
```

## 4. LangGraph 工作流（总结 Agent）

### 4.1 工作流步骤

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Step 1      │     │  Step 2      │     │  Step 3      │
│  内容分类    │────▶│  提取结论    │────▶│  生成 MD     │
│              │     │              │     │              │
│ - 识别主题   │     │ - 核心观点   │     │ - frontmatter│
│ - 判定类型   │     │ - 关键决策   │     │ - 结构化正文 │
│ - 过滤噪音   │     │ - 行动项     │     │ - 标签推荐   │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 4.2 各步骤详解

**Step 1: 内容分类**

- 输入：原始对话文本
- 输出：`{ category: "tech"|"product"|"research"|"misc", title_hint: "主题关键词" }`
- LLM prompt：分析对话内容，判定属于技术讨论 / 产品设计 / 研究探索 / 其他

**Step 2: 提取结论**

- 输入：原始对话 + 分类结果
- 输出：`{ key_points: ["结论1", "结论2"], decisions: ["决策1"], action_items: ["行动项1"] }`
- LLM prompt：从对话中提取事实性结论、关键决策和待办行动项

**Step 3: 生成 Markdown**

- 输入：分类结果 + 结论提取 + 原始对话
- 输出：完整 Markdown 字符串（含 frontmatter）
- 将结构化信息组装成博客文章格式

### 4.3 技术选型

- **LangGraph**：编排多步 LLM 工作流（适合有依赖关系的多步总结）
- **LLM 模型**：通过 API 调用，可配置切换（默认 GPT-4o-mini，平衡效果与成本）
- **Python 内置实现**：不引入额外服务，直接在 FastAPI 进程中执行

## 5. 前端页面：/workbench

### 5.1 路由

- Astro 页面：`site/src/pages/workbench/index.astro`
- 交互组件：`site/src/components/WorkbenchApp.vue`（Vue 3 SPA）

### 5.2 页面布局

```
┌──────────────────────────────────────────────────┐
│  工作台 — AI 会话沉淀                             │
├──────────────────────────────────────────────────┤
│                                                    │
│  ┌─ Step 1: 粘贴对话 ──────────────────────────┐  │
│  │  [大文本框] 粘贴 AI 对话内容...               │  │
│  │                                [生成总结 →]  │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌─ Step 2: 预览 & 编辑 ───────────────────────┐  │
│  │  ┌──────────────┐  ┌──────────────────────┐  │  │
│  │  │  Markdown    │  │  实时 HTML 预览      │  │  │
│  │  │  编辑区      │  │                      │  │  │
│  │  │  (可编辑)    │  │  (渲染结果)          │  │  │
│  │  └──────────────┘  └──────────────────────┘  │  │
│  │                                [保存草稿 →]  │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌─ Step 3: 保存结果 ──────────────────────────┐  │
│  │  ✅ 已保存到 content/posts/xxx.md            │  │
│  │  📝 下一步：git commit + push 发布           │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 5.3 交互流程

1. 用户粘贴对话文本 → 点击「生成总结」
2. 调用 `POST /api/agent/summarize`，显示 loading 状态
3. 返回后展示左右分栏：左侧可编辑 Markdown，右侧实时渲染预览
4. 用户修改满意后 → 点击「保存草稿」
5. 调用 `POST /api/agent/save`，保存到文件系统
6. 显示成功提示，提示用户可以通过 git 发布

## 6. 数据模型变更

### 6.1 Content Schema 扩展

在 `site/src/content.config.ts` 的 blog collection schema 中新增字段：

```typescript
source: z.enum(["manual", "ai"]).default("manual"),
// manual: 手写文章
// ai: AI 总结生成的文章
```

### 6.2 Frontmatter 示例

```yaml
---
title: 使用 LangGraph 构建多步 LLM 工作流
date: 2026-08-12
tags:
  - AI
  - LangGraph
  - Agent
draft: false
source: ai
---
```

### 6.3 UI 显示变更

- 博客列表页：AI 来源的文章显示 `🤖 AI 总结` 徽标
- 文章详情页：在 frontmatter 区域显示来源标签

## 7. 文件清单

| 文件 | 说明 |
|------|------|
| `app/main.py` | 新增 3 个 `/api/agent/*` 端点 |
| `app/agent/__init__.py` | Agent 模块入口 |
| `app/agent/summarize.py` | LangGraph 总结工作流实现 |
| `app/agent/prompts.py` | LLM prompt 模板 |
| `site/src/pages/workbench/index.astro` | workbench 页面 |
| `site/src/components/WorkbenchApp.vue` | Vue 3 交互组件 |
| `site/src/content.config.ts` | 扩展 blog schema 新增 `source` 字段 |
| `site/src/components/Card.astro` | 展示 AI 来源徽标 |
| `site/src/pages/blog/[slug].astro` | 详情页展示来源标签 |

## 8. 依赖与风险

### 新增 Python 依赖

```
langgraph
openai  (LLM API 调用)
```

### 风险

| 风险 | 缓解 |
|------|------|
| LLM API 调用失败或超时 | 返回明确错误信息，允许重试；前端超时 60s |
| LLM 输出格式不稳定 | 使用 structured output / JSON mode 约束输出格式 |
| API 费用 | 默认使用 gpt-4o-mini（便宜）；workbench 页面加用量提示 |
| 生成的 .md 文件质量低 | 保留编辑环节，用户始终可以手动修改后再保存 |

## 9. 后续迭代（未来阶段）

- **阶段二**：从 Agent 沙箱自动推送对话记录（去掉"手动粘贴"这一步）
- **阶段三**：知识图谱 — 自动关联相关文章
- **阶段四**：数字分身 — 基于沉淀内容训练个人风格回复
