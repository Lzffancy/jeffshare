# dev_doc — 项目开发文档

本目录存放项目开发相关的文档和规划，将开发过程沉淀为可追溯的 spec。

## 目录结构

```
dev_doc/
├── README.md                          # 本文件 — 目录说明
└── plans/                             # 开发规划文档
    └── phase1-ai-summarize-pipeline.md  # 阶段一：AI 会话自动沉淀流水线
```

## 使用约定

1. **先规划再开发**：每个新功能/阶段的开发，先在 `plans/` 下编写规划文档（spec），明确目标、设计、数据模型、接口等，再动手写代码。
2. **文档即 spec**：规划文档不只是"需求描述"，而是包含 **API 设计、数据模型、组件拆分、技术选型** 的完整规格书。后续开发和代码审查都以 spec 为准。
3. **命名规范**：`plans/phase{N}-{feature-slug}.md`，如 `phase1-ai-summarize-pipeline.md`。
4. **版本控制**：所有 dev_doc 内容纳入 git 管理，每次迭代更新 spec 时同步 commit。

## 与 AGENTS.md 的关系

| 文件 | 用途 |
|------|------|
| `AGENTS.md` | AI Agent 操作手册 — 项目结构、部署流程、常用命令（给 AI 看的） |
| `dev_doc/README.md` | 开发文档目录索引 |
| `dev_doc/plans/*.md` | 各阶段的开发 spec（给人看的，也是给 AI 执行的参考） |
