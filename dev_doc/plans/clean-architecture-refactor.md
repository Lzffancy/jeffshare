# 规约: Clean Architecture 目录重构（对齐《The Clean Architecture》文章方案）

## 1. 背景与目标

- 当前 `app/` 采用 DDD 四层命名 `domain/application/infrastructure/presentation`，
  与团队书面规范（《The Clean Architecture》文章 + AGENTS.md SSD 范式）中
  `entity/logic/repository/service` 的词汇不一致，导致"两套词汇并存、越写越散"。
- 目标：将 `app/` 目录结构对齐文章方案，统一命名词汇，收拢端口契约，
  合并跨层编排逻辑，不改变任何业务行为。

## 2. 技术方案

### 新旧目录映射表

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `app/domain/agent/entities.py` | `app/entity/agent.py` | 实体 |
| `app/domain/agent/value_objects.py` | `app/entity/values.py` | 值对象 |
| `app/domain/execution/entities.py` | `app/entity/execution.py` | 执行记录实体 |
| `app/domain/agent/repository.py`（接口部分） | `app/entity/ports.py` | 端口契约 |
| `app/domain/agent/services.py`（接口部分） | `app/entity/ports.py` | 端口契约 |
| `app/domain/agent/services.py`（编排部分） | `app/logic/orchestrator.py` | 领域编排 |
| `app/application/agent/services.py`（SummarizeUseCase） | `app/logic/summarize.py` | 用例 |
| `app/application/agent/services.py`（SaveMarkdownUseCase） | `app/logic/save_markdown.py` | 用例 |
| `app/application/agent/dtos.py` | `app/logic/dtos.py` | DTO |
| `app/application/agent/registry.py` | `app/logic/registry.py` | 注册表 |
| `app/infrastructure/llm/openai_client.py` | `app/repository/llm/openai_client.py` | 适配器 |
| `app/infrastructure/persistence/repositories.py` | `app/repository/persistence/repositories.py` | 适配器 |
| `app/infrastructure/persistence/sqlite.py` | `app/repository/persistence/sqlite.py` | 适配器 |
| `app/infrastructure/workflow/langgraph_engine.py` | `app/repository/workflow/langgraph_engine.py` | 适配器 |
| `app/presentation/routes.py` | `app/service/routes.py` | 协议层 |
| `app/presentation/schemas.py` | `app/service/schemas.py` | 协议层 |
| `app/main.py`（OAuth 部分） | `app/middleware/oauth.py` | 横切关注点 |
| `app/seed.py` | `app/repository/persistence/seed.py` | 种子数据 |

### 目标结构

```
app/
├── main.py                      # 入口：FastAPI 创建 + 路由挂载
├── entity/                      # 【Entities】核心模型 + 值对象 + 接口契约
│   ├── agent.py                 # AgentDefinition / AgentVersion / AgentStep / ModelParams / StepLog
│   ├── execution.py             # ExecutionRecord
│   ├── values.py                # StepType / ConfigStatus / WorkflowType / ExecutionStatus
│   └── ports.py                 # ILlmClient / IWorkflowEngine / IAgentConfigRepo / IExecutionRepo
├── logic/                       # 【Use Cases】领域服务 + 应用用例
│   ├── orchestrator.py          # AgentOrchestrator / StepExecutor / WorkflowContext
│   ├── summarize.py             # SummarizeUseCase
│   ├── save_markdown.py         # SaveMarkdownUseCase
│   ├── dtos.py                  # 用例边界对象
│   └── registry.py              # Agent 注册表
├── repository/                  # 【Frameworks & Drivers】外部依赖实现（适配器）
│   ├── llm/openai_client.py
│   ├── persistence/{repositories,sqlite,seed}.py
│   └── workflow/langgraph_engine.py
├── service/                     # 【Interface Adapters】协议层 / 服务入口
│   ├── routes.py                # FastAPI 路由 + 组合根(DI)
│   └── schemas.py               # 请求/响应模型
└── middleware/                  # 横切关注点
    └── oauth.py                 # 从 main.py 抽出
```

### 依赖方向

```
service → logic → entity ← repository
```

- `entity/` 不 import 任何外层；`ports.py` 只声明抽象接口。
- `repository/` 实现 `entity/ports.py` 中的接口。
- `logic/` 依赖 `entity/`，编排用例。
- `service/` 是组合根：实例化 repository 适配器并注入 use case。

## 3. 详细设计

### entity/
- `values.py`：原 `domain/agent/value_objects.py`，含 StepType/ConfigStatus/WorkflowType/ExecutionStatus。
- `agent.py`：原 `domain/agent/entities.py`，含 AgentStep/AgentDefinition/AgentVersion/ModelParams/StepLog，
  import 从 `value_objects` 改为 `values`，从相对路径改为包路径。
- `execution.py`：原 `domain/execution/entities.py`，含 ExecutionRecord，
  import 从 `..agent.value_objects` 改为 `app.entity.values`。
- `ports.py`：新文件，聚合 ILlmClient / IWorkflowEngine / IAgentConfigRepo / IExecutionRepo。

### logic/
- `orchestrator.py`：原 `domain/agent/services.py` 中的 AgentOrchestrator / StepExecutor / WorkflowContext。
- `summarize.py`：原 `application/agent/services.py` 中的 SummarizeUseCase。
- `save_markdown.py`：原 `application/agent/services.py` 中的 SaveMarkdownUseCase。
- `dtos.py`：原 `application/agent/dtos.py`。
- `registry.py`：原 `application/agent/registry.py`。

### repository/
- `llm/openai_client.py`、`persistence/repositories.py`、`persistence/sqlite.py`、
  `workflow/langgraph_engine.py`、`persistence/seed.py`：原路径直接平移，更新 import。
- 注意：`seed.py` 原位于 `app/seed.py`，import 从 `app.infrastructure.persistence.sqlite` 等改为新路径。

### service/
- `routes.py`：原 `presentation/routes.py`，import 从 `app.domain.*`/`app.application.*`/`app.infrastructure.*` 改新路径。
- `schemas.py`：原 `presentation/schemas.py`，通常无跨层 import。

### middleware/
- `oauth.py`：从 `main.py` 抽出 OAuth 相关（admin-auth/callback/exchange/verify 路由 + state/session 逻辑）。

### main.py
- 精简为：创建 FastAPI 实例、挂载 CORS、include_router（service.routes + middleware.oauth）、根路由。
- 保留涂鸦墙 API（graffiti）在 main.py 或移入 service/routes.py —— 视原代码位置而定。

### import 改动清单
- `app.domain.agent.entities` → `app.entity.agent`
- `app.domain.agent.value_objects` → `app.entity.values`
- `app.domain.execution.entities` → `app.entity.execution`
- `app.domain.agent.services`（接口） → `app.entity.ports`；`app.logic.orchestrator`（编排）
- `app.domain.agent.repository` → `app.entity.ports`
- `app.application.agent.services` → `app.logic.summarize` / `app.logic.save_markdown`
- `app.application.agent.dtos` → `app.logic.dtos`
- `app.application.agent.registry` → `app.logic.registry`
- `app.infrastructure.*` → `app.repository.*`
- `app.presentation.*` → `app.service.*`
- `app.seed` → `app.repository.persistence.seed`

## 4. 验收标准

- [ ] 目录结构完全对齐文章方案（entity/logic/repository/service/middleware）。
- [ ] 所有模块 import 更新无遗漏，`python -c "import app.main"` 通过。
- [ ] FastAPI 应用可启动，路由数量与迁移前一致。
- [ ] 业务行为零变化（无逻辑改动，仅路径/import 迁移）。
- [ ] AGENTS.md 与 dev_doc 中目录说明同步更新。
