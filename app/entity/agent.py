"""Entity agent — dataclass 定义

所有实体使用 @dataclass，值对象使用 frozen=True。
遵循 Clean Architecture：在此层不引入任何 ORM / SQL / HTTP 依赖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .values import ConfigStatus, StepType, WorkflowType

# ── 值对象（不可变） ─────────────────────────────────────────────


@dataclass(frozen=True)
class ModelParams:
    """LLM 调用参数（值对象）。"""
    temperature: float = 0.3
    max_tokens: int = 2048
    top_p: float = 1.0

    def merge(self, overrides: dict[str, Any] | None) -> ModelParams:
        """用 overrides 覆盖部分字段，返回新实例。"""
        if not overrides:
            return self
        d = dict(
            temperature=overrides.get("temperature", self.temperature),
            max_tokens=overrides.get("max_tokens", self.max_tokens),
            top_p=overrides.get("top_p", self.top_p),
        )
        return ModelParams(**d)


@dataclass(frozen=True)
class StepLog:
    """单步骤执行日志（值对象）。"""
    order: int
    name: str
    type: str
    status: str = "success"
    duration_ms: int = 0
    error: str = ""


# ── 实体 ────────────────────────────────────────────────────────


@dataclass
class AgentStep:
    """Agent 执行步骤（值对象语义，但为了 mutable 操作不用 frozen）。"""
    order: int
    name: str
    type: StepType
    prompt_template: str = ""
    prompt_params: list[str] = field(default_factory=list)
    output_key: str = ""
    output_schema: dict[str, str] | None = None
    model_override: str | None = None
    model_params_override: dict[str, Any] | None = None
    transform_func: str | None = None

    def intercept_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """从 state 中提取 prompt 所需的参数，返回格式化上下文。

        值对象：对非字符串的值做 JSON 序列化以便注入 prompt。
        """
        import json

        ctx: dict[str, str] = {}
        for k in self.prompt_params:
            v = state.get(k, "")
            if isinstance(v, (dict, list)):
                ctx[k] = json.dumps(v, ensure_ascii=False, indent=2)
            else:
                ctx[k] = str(v)
        return ctx

    def render_prompt(self, state: dict[str, Any]) -> str:
        """用 state 渲染 prompt_template。"""
        return self.prompt_template.format(**self.intercept_context(state))


@dataclass
class AgentDefinition:
    """Agent 定义 — 聚合根（有唯一标识 id）。"""
    name: str
    display_name: str
    description: str = ""
    workflow_type: WorkflowType = WorkflowType.LINEAR_CHAIN
    agent_class: str = ""
    id: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> AgentDefinition:
        from .values import WorkflowType

        return cls(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row.get("description", ""),
            workflow_type=WorkflowType(row.get("workflow_type", "linear_chain")),
            agent_class=row.get("agent_class", ""),
        )


@dataclass
class AgentVersion:
    """Agent 版本 — 实体（有独立 id，关联到 AgentDefinition）。"""
    agent_id: int
    version: int
    model: str
    model_params: ModelParams = field(default_factory=ModelParams)
    steps: list[AgentStep] = field(default_factory=list)
    status: ConfigStatus = ConfigStatus.DRAFT
    changelog: str = ""
    id: int = 0
