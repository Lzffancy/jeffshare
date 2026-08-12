# Agent 框架设计 — 配置驱动、版本化、多 Agent 架构

> 状态：实现中 | 创建：2026-08-12

## 1. 问题分析

### 当前实现的问题

```
app/agent/
├── prompts.py      ← prompt 写死在代码里，改 prompt = 改代码 + 发版
├── summarize.py    ← 模型参数写死 (temperature=0.3, max_tokens=2048)
                   ← 工作流写死 (线性三步)，无法换模式
                   ← 没有版本概念，回滚 = git revert
```

### 设计目标

| 目标 | 说明 |
|------|------|
| **配置与代码分离** | prompt、模型参数、工作流模式全部存 DB，代码只管执行 |
| **版本化** | 每次调整配置生成新版本，旧版本可回滚，同一条对话可用不同版本重跑对比 |
| **面向对象** | `BaseAgent` 抽象 Agent 的执行契约，具体 Agent（SummarizeAgent 等）只关注业务逻辑 |
| **多 Agent 扩展** | 同一框架下可注册多个 Agent 类型，支持 linear_chain / parallel / router 等模式 |
| **执行可观测** | 每次执行记录日志（耗时、状态、输入摘要），方便调试和 A/B 对比 |

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI (:8000)                      │
│                                                           │
│  POST /api/agent/summarize    POST /api/agent/save       │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                    │
│  │  AgentRegistry   │  ← 按 name 查找 Agent 类            │
│  │  { name → Agent }│                                    │
│  └───────┬──────────┘                                    │
│          │                                                │
│          ▼                                                │
│  ┌──────────────────┐                                    │
│  │ AgentConfigRepo  │  ← SQLite: agent_definitions       │
│  │ .get_active(     │           agent_versions            │
│  │   agent_name)    │           agent_executions          │
│  └───────┬──────────┘                                    │
│          │                                                │
│          ▼                                                │
│  ┌──────────────────┐     ┌──────────────────┐           │
│  │   BaseAgent      │────▶│    LLM Client     │           │
│  │  (配置 + 工作流) │     │  (OpenAI SDK)     │           │
│  └──────────────────┘     └──────────────────┘           │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 调用链路

```
API 端点 → AgentRegistry.get("conversation-summarizer")
        → AgentConfigRepo.get_active("conversation-summarizer")
        → AgentVersionConfig (version=1, steps=[...], model="gpt-4o-mini")
        → SummarizeAgent(config)
        → execute(conversation="...")
        → 按 workflow_type 执行 steps → 返回结果
        → AgentConfigRepo.log_execution(...)
```

## 3. 数据模型（SQLite）

### 3.1 ER 图

```
agent_definitions  1 ──── N  agent_versions
                                  │
                                  │
                          agent_executions (日志)
```

### 3.2 表结构

```sql
-- Agent 定义：一个「Agent 类型」只有一条记录
CREATE TABLE agent_definitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,   -- "conversation-summarizer"
    display_name TEXT   NOT NULL,          -- "AI 会话总结"
    description TEXT    DEFAULT '',
    workflow_type TEXT  NOT NULL DEFAULT 'linear_chain',
      -- linear_chain: 步骤串行执行，前一步输出作为后一步上下文
      -- parallel:     多步并发执行，最后汇总
      -- router:       根据条件路由到不同分支
    agent_class  TEXT   NOT NULL,          -- "SummarizeAgent" (import 用)
    created_at   TEXT   NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT   NOT NULL DEFAULT (datetime('now'))
);

-- Agent 版本：每个 Agent 可以有多个版本，同一时刻只有一个 active
CREATE TABLE agent_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    INTEGER NOT NULL REFERENCES agent_definitions(id),
    version     INTEGER NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'draft',
      -- draft:   编辑中，不会被执行
      -- active:  当前生效版本
      -- archived: 已归档，仅保留记录
    model       TEXT    NOT NULL DEFAULT 'gpt-4o-mini',
    model_params TEXT   NOT NULL DEFAULT '{}',
      -- JSON: {"temperature": 0.3, "max_tokens": 2048, "top_p": 1.0}
    steps       TEXT    NOT NULL DEFAULT '[]',
      -- JSON: [{order, name, type, prompt_template, prompt_params, output_key, ...}]
    changelog   TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(agent_id, version)
);

-- 执行日志：每次调用记录，用于可观测性和 A/B 对比
CREATE TABLE agent_executions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id     INTEGER NOT NULL,
    version_id   INTEGER NOT NULL,
    input_summary TEXT,       -- 输入摘要（截断前200字）
    output_summary TEXT,      -- 输出摘要（截断前200字）
    status       TEXT NOT NULL,  -- 'success' | 'error'
    duration_ms  INTEGER,
    error_msg    TEXT,
    steps_log    TEXT DEFAULT '[]',
      -- JSON: [{name, duration_ms, status, token_usage}]
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 3.3 steps JSON 结构

```json
[
  {
    "order": 1,
    "name": "内容分类",
    "type": "llm_call",
    "prompt_template": "你是...\n对话内容：\n{conversation}\n\n请返回JSON...",
    "prompt_params": ["conversation"],
    "output_key": "classify_result",
    "output_schema": {
      "category": "string",
      "title_hint": "string"
    },
    "model_override": null,
    "model_params_override": null
  },
  {
    "order": 2,
    "name": "提取结论",
    "type": "llm_call",
    "prompt_template": "...\n{classify_result}\n...",
    "prompt_params": ["conversation", "classify_result"],
    "output_key": "extract_result",
    "output_schema": {
      "key_points": ["string"],
      "decisions": ["string"],
      "action_items": ["string"],
      "tags": ["string"]
    },
    "model_override": null,
    "model_params_override": {"temperature": 0.1}
  },
  {
    "order": 3,
    "name": "组装 Markdown",
    "type": "transform",
    "transform_func": "assemble_markdown",
    "prompt_params": [],
    "output_key": "final_markdown"
  }
]
```

### 3.4 版本管理规则

- 每个 agent **有且仅有一个** `status='active'` 的版本
- 切换 active：旧版本 → `archived`，新版本 → `active`（事务）
- `draft` 状态不会被 API 执行，供调试用
- 版本号自增，不可回收

## 4. 代码设计

### 4.1 模块结构

```
app/
├── agent/
│   ├── __init__.py           # 公开接口：AgentRegistry.get()
│   ├── models.py             # Pydantic 模型：AgentVersionConfig, AgentStepConfig, ...
│   ├── db.py                 # SQLite 连接管理 + 建表 DDL
│   ├── repository.py         # AgentConfigRepository (CRUD)
│   ├── base.py               # BaseAgent 抽象基类
│   ├── llm_client.py         # OpenAI 客户端封装（单例）
│   ├── agents/
│   │   ├── __init__.py
│   │   └── summarize.py      # SummarizeAgent(BaseAgent): 会话总结业务逻辑
│   └── seed.py               # 初始化种子数据
└── main.py                   # 端点使用 AgentRegistry
```

### 4.2 Pydantic 模型 (`models.py`)

```python
class StepType(str, Enum):
    LLM_CALL  = "llm_call"
    TRANSFORM = "transform"
    CONDITION = "condition"

class WorkflowType(str, Enum):
    LINEAR_CHAIN = "linear_chain"
    PARALLEL     = "parallel"
    ROUTER       = "router"

class AgentStepConfig(BaseModel):
    order: int
    name: str
    type: StepType
    prompt_template: str = ""
    prompt_params: list[str] = []
    output_key: str
    output_schema: dict | None = None
    model_override: str | None = None       # 覆盖 agent 级 model
    model_params_override: dict | None = None
    transform_func: str | None = None       # type=transform 时指定函数名

class AgentVersionConfig(BaseModel):
    id: int | None = None
    agent_id: int | None = None
    version: int
    status: str  # draft | active | archived
    model: str
    model_params: dict  # {"temperature": 0.3, "max_tokens": 2048}
    steps: list[AgentStepConfig]
    changelog: str = ""
```

### 4.3 BaseAgent (`base.py`)

```python
class BaseAgent(ABC):
    """
    Agent 基类。
    子类必须实现 execute()——定义业务输入输出格式。
    工作流执行逻辑由基类提供（linear_chain / parallel / router）。
    """
    def __init__(self, config: AgentVersionConfig):
        self.config = config
        self.llm = get_llm_client()

    def run(self, **inputs) -> dict:
        """对外统一入口：记录执行日志 + 调用 execute()"""
        start = time.time()
        try:
            result = self.execute(**inputs)
            duration = int((time.time() - start) * 1000)
            self._log_execution(inputs, result, "success", duration)
            return result
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._log_execution(inputs, {}, "error", duration, str(e))
            raise

    @abstractmethod
    def execute(self, **inputs) -> dict:
        """子类实现：定义具体业务逻辑"""

    # ── 工作流执行器 ──
    def _execute_linear_chain(self, **inputs) -> dict:
        """串行执行 steps，每步输出注入上下文"""
        context = dict(inputs)
        for step in sorted(self.config.steps, key=lambda s: s.order):
            if step.type == StepType.LLM_CALL:
                result = self._llm_step(step, context)
            elif step.type == StepType.TRANSFORM:
                result = self._transform_step(step, context)
            context[step.output_key] = result
        return context

    def _llm_step(self, step: AgentStepConfig, context: dict) -> dict:
        model = step.model_override or self.config.model
        params = {**self.config.model_params, **(step.model_params_override or {})}
        prompt = step.prompt_template.format(
            **{k: context.get(k, "") for k in step.prompt_params}
        )
        return self.llm.chat(prompt, model=model, **params)

    def _transform_step(self, step, context):
        """纯代码转换步骤，由子类覆写映射"""
        ...
```

### 4.4 SummarizeAgent 实现

```python
class SummarizeAgent(BaseAgent):
    def execute(self, conversation: str, model: str | None = None) -> dict:
        # 如果请求指定了 model，临时覆盖
        if model:
            self.config.model = model
        
        result = self._execute_linear_chain(conversation=conversation)
        
        # 用 transform step 的结果组装最终输出
        return self._assemble_output(result)
    
    def _assemble_output(self, ctx: dict) -> dict:
        """子类负责业务输出格式"""
        classify = ctx.get("classify_result", {})
        extract = ctx.get("extract_result", {})
        return {
            "title": extract.get("title", ""),
            "tags": extract.get("tags", []),
            "markdown": ctx.get("final_markdown", ""),
            ...
        }
```

### 4.5 AgentRegistry (`__init__.py`)

```python
_registry: dict[str, type[BaseAgent]] = {}

def register(name: str):
    """装饰器：注册 Agent 类"""
    def decorator(cls):
        _registry[name] = cls
        return cls
    return decorator

def get(name: str) -> BaseAgent:
    """按名称获取 Agent 实例（自动加载最新 active 配置）"""
    cls = _registry.get(name)
    config = AgentConfigRepo().get_active_config(name)
    return cls(config)
```

### 4.6 AgentConfigRepository

```python
class AgentConfigRepository:
    def get_active_config(self, agent_name: str) -> AgentVersionConfig
    def get_version(self, agent_name: str, version: int) -> AgentVersionConfig
    def create_version(self, agent_name: str, config: AgentVersionConfig) -> AgentVersionConfig
    def activate_version(self, agent_name: str, version: int) -> AgentVersionConfig
    def list_versions(self, agent_name: str) -> list[AgentVersionConfig]
    def log_execution(self, agent_id, version_id, input_summary, output_summary, status, duration_ms, error_msg)
```

## 5. API 端点（不变，实现方式改变）

| 端点 | 变更 |
|------|------|
| `POST /api/agent/summarize` | 不再直接调 `summarize_conversation()`，改为 `AgentRegistry.get("conversation-summarizer").run(conversation=...)` |
| `POST /api/agent/save` | 不变 |

## 6. Seed 数据（init 时自动写入）

```sql
-- agent_definition
INSERT INTO agent_definitions (name, display_name, description, workflow_type, agent_class)
VALUES ('conversation-summarizer', 'AI 会话总结', '将 AI 对话沉淀为结构化博客草稿', 'linear_chain', 'SummarizeAgent');

-- agent_version v1 (active)
INSERT INTO agent_versions (agent_id, version, status, model, model_params, steps, changelog)
VALUES (1, 1, 'active', 'gpt-4o-mini',
  '{"temperature": 0.3, "max_tokens": 2048, "top_p": 1.0}',
  '[steps JSON]',
  '初始版本：三步串行（分类→提取→生成）');
```

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/agent/__init__.py` | 重写 | AgentRegistry |
| `app/agent/models.py` | 新增 | Pydantic 模型 |
| `app/agent/db.py` | 新增 | SQLite 连接 + DDL |
| `app/agent/repository.py` | 新增 | CRUD 仓储 |
| `app/agent/llm_client.py` | 新增 | OpenAI 客户端封装 |
| `app/agent/base.py` | 新增 | BaseAgent 基类 |
| `app/agent/agents/__init__.py` | 新增 | 子包入口 |
| `app/agent/agents/summarize.py` | 新增 | SummarizeAgent |
| `app/agent/seed.py` | 新增 | 种子数据 |
| `app/agent/prompts.py` | 删除 | prompt 移入 DB |
| `app/agent/summarize.py` | 重写 | 简化为 Agent 调用 |
| `app/main.py` | 修改 | 端点改为 AgentRegistry 调用 |
| `dev_doc/plans/agent-framework-design.md` | 新增 | 本 spec |

## 8. 扩展性示例

未来注册新 Agent：

```python
# app/agent/agents/reviewer.py
@register("code-reviewer")
class CodeReviewAgent(BaseAgent):
    def execute(self, code: str, language: str) -> dict:
        return self._execute_linear_chain(code=code, language=language)
```

Agent 间组合（未来 `parallel` 或 `router`）：

```python
# 配置中 workflow_type = "parallel"
# 多个 LLM 并行调用，然后投票/汇总
```

Prompt 迭代：

```
v1: "你是一个内容分析助手..."
v2: "你是一个资深技术博客编辑，擅长提炼对话精华..."  ← 改 prompt 只需 INSERT 新版本
v3: 改 model_params，换 model → gpt-4o
```
