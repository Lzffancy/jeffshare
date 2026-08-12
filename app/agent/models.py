"""Agent 配置数据模型 — Pydantic

所有与「配置」相关的数据结构定义在这里。
配置存储在 SQLite 中，代码只负责根据配置执行。
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


# ── 枚举 ──────────────────────────────────────────────────────────

class StepType(str, Enum):
    LLM_CALL  = "llm_call"
    TRANSFORM = "transform"
    CONDITION = "condition"


class WorkflowType(str, Enum):
    LINEAR_CHAIN = "linear_chain"
    PARALLEL     = "parallel"
    ROUTER       = "router"


class ConfigStatus(str, Enum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    ARCHIVED = "archived"


# ── 核心模型 ──────────────────────────────────────────────────────

class AgentStepConfig(BaseModel):
    """单个步骤的配置"""
    order: int
    name: str
    type: StepType
    prompt_template: str = ""
    prompt_params: list[str] = []           # 注入到 template 中的上下文 key
    output_key: str                          # 步骤输出存入上下文的 key
    output_schema: dict | None = None        # 期望的 JSON schema（文档用途）
    model_override: str | None = None        # 覆盖 agent 级 model
    model_params_override: dict | None = None # 覆盖 agent 级 model_params
    transform_func: str | None = None        # type=transform 时绑定的函数名


class AgentVersionConfig(BaseModel):
    """一个 Agent 版本的完整配置"""
    id: int | None = None
    agent_id: int | None = None
    version: int
    status: ConfigStatus = ConfigStatus.DRAFT
    model: str = "gpt-4o-mini"
    model_params: dict = {}                  # {"temperature": 0.3, "max_tokens": 2048}
    steps: list[AgentStepConfig] = []
    changelog: str = ""


class AgentDefinition(BaseModel):
    """Agent 类型定义"""
    id: int | None = None
    name: str
    display_name: str
    description: str = ""
    workflow_type: WorkflowType = WorkflowType.LINEAR_CHAIN
    agent_class: str = ""                    # 类名，如 "SummarizeAgent"


class AgentExecution(BaseModel):
    """执行日志"""
    id: int | None = None
    agent_id: int
    version_id: int
    input_summary: str = ""
    output_summary: str = ""
    status: str = ""                         # "success" | "error"
    duration_ms: int = 0
    error_msg: str = ""
    steps_log: list[dict] = []
