"""Logic orchestrator — 领域编排逻辑（Use Cases）

AgentOrchestrator / StepExecutor / WorkflowContext：
决定步骤按序执行、状态如何传递，不依赖基础设施层。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.entity.agent import AgentStep, AgentVersion, StepLog
from app.entity.ports import ILlmClient, IWorkflowEngine
from app.entity.values import StepType

logger = logging.getLogger("jeff-api")


class StepExecutor:
    """步骤执行器 — 持有 LLM 客户端，执行单个 step。

    放在 logic 层而非 repository，因为它只编排 call/transform 的分发逻辑，
    实际的 LLM 调用通过 ILlmClient 抽象完成。
    """

    def __init__(self, llm: ILlmClient, model: str):
        self._llm = llm
        self._model = model

    def execute(self, step: AgentStep, state: dict[str, Any]) -> Any:
        """执行单个步骤。"""
        if step.type == StepType.LLM_CALL:
            return self._execute_llm(step, state)
        elif step.type == StepType.TRANSFORM:
            return self._execute_transform(step, state)
        else:
            logger.warning(f"未处理的 step type: {step.type}")
            return {}

    def _execute_llm(self, step: AgentStep, state: dict[str, Any]) -> Any:
        prompt = step.render_prompt(state)
        model = step.model_override or self._model
        logger.info(f"  → LLM step '{step.name}': model={model}, prompt_len={len(prompt)}")
        return self._llm.chat(prompt, model=model)

    def _execute_transform(self, step: AgentStep, state: dict[str, Any]) -> Any:
        func_name = step.transform_func
        if not func_name:
            raise ValueError(f"Transform step '{step.name}' 缺少 transform_func")

        # 查找本实例上的 _transform_{name} 方法
        handler = getattr(self, f"_transform_{func_name}", None)
        if handler is None:
            raise ValueError(f"未找到转换函数 _transform_{func_name}")
        logger.info(f"  → Transform step '{step.name}': func={func_name}")
        return handler(state)

    # ── 内置 transform 函数 ────────────────────────────────────────

    def _transform_assemble_markdown(self, state: dict[str, Any]) -> str:
        """将 classify + extract 结果组装为博客 Markdown。"""
        classify = self._as_dict(state.get("classify_result", {}))
        extract = self._as_dict(state.get("extract_result", {}))

        title = extract.get("title") or classify.get("title_hint") or "未命名"
        summary = extract.get("summary", "由 AI 自动总结的会话内容")
        tags = extract.get("tags", [])
        body = extract.get("markdown", "")

        tag_lines = "\n".join(f"  - {t}" for t in tags) if tags else "  - ai-summary"

        return f"""---
title: {title}
date: {date.today().isoformat()}
tags:
{tag_lines}
draft: false
source: ai
---

> {summary}

{body}
"""

    @staticmethod
    def _as_dict(v: Any) -> dict:
        if isinstance(v, str):
            try:
                return json.loads(v)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                return {}
        return v if isinstance(v, dict) else {}


# ── 工作流上下文 ──────────────────────────────────────────────────


@dataclass
class WorkflowContext:
    """工作流执行上下文 — 携带输入、中间状态、输出、日志。"""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    steps_log: list[dict] = field(default_factory=list)
    start_ts: float = 0.0

    def __post_init__(self):
        if self.start_ts == 0.0:
            self.start_ts = time.time()

    def set(self, key: str, value: Any) -> None:
        """写入中间状态（供下游 step 读取）。"""
        self.outputs[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """读取状态（优先 outputs → inputs）。"""
        return self.outputs.get(key, self.inputs.get(key, default))

    def snapshot(self) -> dict[str, Any]:
        """合并 inputs + outputs 为单一 dict（供 prompt 渲染用）。"""
        return {**self.inputs, **self.outputs}

    def add_step_log(self, log: StepLog) -> None:
        self.steps_log.append(dict(
            order=log.order,
            name=log.name,
            type=log.type,
            status=log.status,
            duration_ms=log.duration_ms,
            error=log.error,
        ))


# ── 编排器 ────────────────────────────────────────────────────────


class AgentOrchestrator:
    """Agent 执行编排器 — 用例逻辑。

    职责：按 AgentVersion 的 steps 顺序执行，管理 WorkflowContext，
         每一步结果写入 context，供下游 step 使用。

    依赖：ILlmClient + IWorkflowEngine（通过 DI 注入）。
    """

    def __init__(
        self,
        version: AgentVersion,
        llm: ILlmClient,
        engine: IWorkflowEngine,
    ):
        self._version = version
        self._engine = engine
        self._executor = StepExecutor(llm, version.model)

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        """执行完整工作流。

        Args:
            context: 已填充 inputs 的上下文

        Returns:
            同一个 context（outputs 已填充）
        """
        steps = sorted(self._version.steps, key=lambda s: s.order)
        if not steps:
            raise ValueError("AgentVersion.steps 为空，无法执行")

        graph = self._engine.compile(steps, self._executor)

        # 注入初始 state
        initial_state = context.snapshot()

        # 执行
        final_state = graph.invoke(initial_state)

        # 将结果写回 context
        for key, value in final_state.items():
            if key not in context.inputs:
                context.set(key, value)

        return context
