## 规约: app/ DDD 四层架构重构

### 1. 背景与目标

当前 `app/agent/` 把所有代码塞在一个包内：models、repository、base agent、llm client、workflow engine 混在一起，没有分层边界。
目标：按 DDD 四层架构重构，清晰分离关注点，每层只依赖下层。

### 2. 四层定义 & 依赖方向

```
presentation ──→ application ──→ domain ←── infrastructure
                   ↑                              ↓
                   └──────────────────────────────┘
```
- **domain**: 纯业务，零外部依赖（无 SQL、无 HTTP、无 OpenAI SDK）
- **application**: 用例编排，依赖 domain 抽象 + infrastructure 具体实现（通过 DI）
- **infrastructure**: 实现 domain 定义的接口
- **presentation**: FastAPI 路由，只依赖 application

### 3. 文件树

```
app/
├── main.py                          # 入口：依赖组装 + FastAPI 创建
├── domain/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── entities.py              # dataclass: AgentDefinition, AgentVersion, AgentStep, ModelParams
│   │   ├── value_objects.py         # Enum: StepType, WorkflowType, ConfigStatus
│   │   ├── services.py              # AgentOrchestrator + WorkflowContext
│   │   └── repository.py            # ABC: IAgentConfigRepo, IExecutionRepo
│   └── execution/
│       ├── __init__.py
│       └── entities.py              # dataclass: ExecutionRecord
├── application/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── dtos.py                  # SerializeInput, SerializeOutput, SaveMarkdownInput
│   │   ├── services.py              # SummarizeUseCase, SaveMarkdownUseCase
│   │   └── registry.py             # AgentRegistry
│   └── shared/
│       ├── __init__.py
│       └── uow.py                   # UnitOfWork (可选)
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── sqlite.py               # SQLite 连接 + DDL
│   │   └── repositories.py         # SqliteAgentConfigRepo, SqliteExecutionRepo
│   ├── llm/
│   │   ├── __init__.py
│   │   └── openai_client.py        # OpenAIClient (实现 LLM 调用)
│   └── workflow/
│       ├── __init__.py
│       └── langgraph_engine.py     # LangGraphWorkflowEngine
├── presentation/
│   ├── __init__.py
│   ├── routes.py                   # APIRouter: /api/agent/*
│   └── schemas.py                  # FastAPI ParseDratic models
└── seed.py                         # 启动种子数据写入
```

### 4. domain 层详细设计

**value_objects.py** — 枚举（纯值，无行为）
```python
class StepType(Enum): LLM_CALL = "llm_call"; TRANSFORM = "transform"; CONDITION = "condition"
class WorkflowType(Enum): LINEAR_CHAIN = "linear_chain"; PARALLEL = "parallel"; ROUTER = "router"
class ConfigStatus(Enum): DRAFT = "draft"; ACTIVE = "active"; ARCHIVED = "archived"
class ExecutionStatus(Enum): SUCCESS = "success"; ERROR = "error"; RUNNING = "running"
```

**entities.py** — dataclass（值对象 + 实体）
```python
@dataclass(frozen=True)  # 值对象
class ModelParams: temperature, max_tokens, top_p, ...

@dataclass                # 值对象
class AgentStep: order, name, type, prompt_template, prompt_params,
                  output_key, output_schema, model_override,
                  model_params_override, transform_func

@dataclass                # 实体
class AgentDefinition: id, name, display_name, description, workflow_type, agent_class

@dataclass                # 实体
class AgentVersion: id, agent_id, version, status, model, model_params, steps, changelog
```

**repository.py** — 抽象接口
```python
class IAgentConfigRepo(ABC):
    @abstractmethod def get_definition(self, name) -> Optional[AgentDefinition]
    @abstractmethod def get_active_version(self, name) -> AgentVersion
    @abstractmethod def list_versions(self, name) -> list[AgentVersion]
    @abstractmethod def create_version(...) -> AgentVersion
    @abstractmethod def activate_version(name, version) -> AgentVersion

class IExecutionRepo(ABC):
    @abstractmethod def log(record: ExecutionRecord) -> None
    @abstractmethod def list_by_agent(name, limit) -> list[ExecutionRecord]
```

**services.py** — 领域服务（LangGraph 执行编排）
```python
@dataclass
class WorkflowContext: inputs, outputs, steps_log, timings

class AgentOrchestrator:
    """编排步骤执行，纯领域逻辑，不依赖 OpenAI 或 LangGraph 的具体实现。
    通过 IStepExecutor / IWorkflowEngine 接口解耦。
    """
    def __init__(self, version: AgentVersion, engine: IWorkflowEngine, llm: ILlmClient)
    def execute(self, context: WorkflowContext) -> WorkflowContext
```

### 5. application 层详细设计

**dtos.py** — 数据传输对象
```python
@dataclass class SummarizeInput: conversation: str
@dataclass class SummarizeOutput: title, slug, tags, markdown, summary
@dataclass class SaveMarkdownInput: slug: str; markdown: str
```

**services.py** — 用例
```python
class SummarizeUseCase:
    def __init__(self, repo: IAgentConfigRepo, orchestrate: AgentOrchestratorFactory)
    async def execute(input: SummarizeInput) -> SummarizeOutput
```

**registry.py** — Agent 注册中心
```python
class AgentRegistry:
    _registry: dict[str, Type]
    @classmethod def register(cls, name) -> decorator
    @classmethod def get(cls, name) -> Type
```

### 6. infrastructure 层详细设计

- **persistence/sqlite.py**: 移除 DDL 字符串，通过 repository 初始化
- **persistence/repositories.py**: 实现 `IAgentConfigRepo` + `IExecutionRepo`
- **llm/openai_client.py**: 实现 LLM 调用（重试、超时、JSON 解析）
- **workflow/langgraph_engine.py**: 实现 `IWorkflowEngine`，基于 LangGraph StateGraph 构建执行图

### 7. presentation 层详细设计

**schemas.py**
```python
class SummarizeRequest(BaseModel): conversation: str
class SaveRequest(BaseModel): slug: str; markdown: str
```

**routes.py** — FastAPI APIRouter
```python
router = APIRouter(prefix="/api/agent")
@router.post("/summarize")  →  SummarizeUseCase
@router.post("/save")       →  SaveMarkdownUseCase
```

### 8. main.py 精简为依赖组装

```python
app = FastAPI()
app.include_router(agent_router)
@app.on_event("startup")  →  seed + 初始化
```

### 9. 验收标准

- [ ] domain 层 import 列表不含 sqlite3 / openai / fastapi / langgraph
- [ ] 所有实体使用 @dataclass，值对象使用 frozen=True
- [ ] repository 在 domain 层是 ABC 接口，实现在 infrastructure
- [ ] presentation/routes.py 不引用 domain 层直接类型
- [ ] 旧文件全部删除：app/agent/ 整个目录
- [ ] 所有现有功能不丢失：summarize、save、OAuth、graffiti
- [ ] 模块可正常导入 + Astro 构建通过
- [ ] 服务重启后正常工作
