"""Repository workflow — LangGraph 引擎实现

实现 entity.ports.IWorkflowEngine 接口。
"""
from __future__ import annotations

import logging
import time
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from app.entity.agent import AgentStep
from app.entity.ports import IWorkflowEngine
from app.entity.values import StepType
from app.logic.orchestrator import StepExecutor

logger = logging.getLogger("jeff-api")


class _AgentState(TypedDict, total=False):
    """LangGraph 内部状态。"""
    steps_log: list


class LangGraphWorkflowEngine(IWorkflowEngine):
    """IWorkflowEngine 的 LangGraph 实现。

    将 AgentVersion.steps 编译为 StateGraph，
    每个 step → 一个节点，节点间串行连接。
    """

    def compile(self, steps: list[AgentStep], executor: StepExecutor) -> Any:
        """构建并编译 LangGraph StateGraph。

        Returns:
            CompiledStateGraph（可直接 .invoke()）
        """
        sorted_steps = sorted(steps, key=lambda s: s.order)
        if not sorted_steps:
            raise ValueError("steps 为空")

        graph = StateGraph(_AgentState)

        # 加节点
        node_names: list[str] = []
        for step in sorted_steps:
            name = f"step_{step.order}_{step.name}"
            node_names.append(name)
            graph.add_node(name, self._make_node(step, executor))

        # 入口
        graph.set_entry_point(node_names[0])

        # 串行边
        for i, name in enumerate(node_names):
            if i < len(node_names) - 1:
                graph.add_edge(name, node_names[i + 1])
            else:
                graph.add_edge(name, END)

        return graph.compile()

    def _make_node(self, step: AgentStep, executor: StepExecutor):
        def node_fn(state: dict) -> dict:
            step_start = time.time()
            try:
                result = executor.execute(step, state)
                duration = int((time.time() - step_start) * 1000)
                log_entry = {"order": step.order, "name": step.name,
                             "type": step.type.value, "status": "success",
                             "duration_ms": duration}
                state.setdefault("steps_log", []).append(log_entry)
                return {step.output_key: result}
            except Exception as e:
                duration = int((time.time() - step_start) * 1000)
                log_entry = {"order": step.order, "name": step.name,
                             "type": step.type.value, "status": "error",
                             "duration_ms": duration, "error": str(e)[:200]}
                state.setdefault("steps_log", []).append(log_entry)
                raise
        return node_fn
