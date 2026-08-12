"""Entity values — 枚举类型"""
from __future__ import annotations
from enum import Enum


class StepType(Enum):
    LLM_CALL = "llm_call"
    TRANSFORM = "transform"
    CONDITION = "condition"


class WorkflowType(Enum):
    LINEAR_CHAIN = "linear_chain"
    PARALLEL = "parallel"
    ROUTER = "router"


class ConfigStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ExecutionStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"
