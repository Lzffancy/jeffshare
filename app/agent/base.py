"""BaseAgent — LangGraph 驱动的配置化 Agent 基类

配置中的 steps → LangGraph StateGraph 节点
workflow_type → 边的连接方式
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from .models import AgentVersionConfig, StepType, WorkflowType
from .llm_client import chat

logger = logging.getLogger("jeff-api")

# ── LangGraph 公共 State ──────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """Agent 执行过程中的共享状态。

    所有 step output 写入此 state，后续 step 从 state 读取上游输出。
    """
    # 业务输入（由子类 execute() 注入）
    conversation: str
    model: str

    # 执行元信息
    steps_log: list[dict]
    _start_ts: float
    _config: dict  # 序列化后的 config（供节点读取）


# ── 步骤标记（用于标记图中"上一个节点名"） ──

_PREV = "__prev__"


class BaseAgent(ABC):
    """Agent 基类。

    子类需实现：
      - build_graph(): 构建 LangGraph StateGraph（自定义业务节点）
      - 或直接使用 _build_graph_from_config()（标准线性/并行流程）

    使用方式：
      agent = SummarizeAgent(config)
      result = agent.run(conversation="...")
    """

    def __init__(self, config: AgentVersionConfig):
        self.config = config
        self._agent_id = config.agent_id or 0
        self._version_id = config.id or 0

    def run(self, **inputs: Any) -> dict:
        """对外统一入口：记录执行日志 + 调用 graph.invoke()"""
        start = time.time()
        steps_log: list[dict] = []

        # 注入元信息到 state
        inputs["steps_log"] = steps_log
        inputs["_start_ts"] = start
        inputs["_config"] = self._serialize_config()

        try:
            graph = self.build_graph()
            result = graph.invoke(inputs)
            duration = int((time.time() - start) * 1000)

            self._log_execution(inputs, result, "success", duration, steps_log)
            return self.assemble_output(result)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._log_execution(inputs, {}, "error", duration, steps_log, str(e))
            raise

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """子类实现：构建 LangGraph StateGraph。

        标准线性流程可直接返回 self._build_linear_graph()。
        """

    @abstractmethod
    def assemble_output(self, state: dict) -> dict:
        """子类实现：将最终的 state 转换为业务输出格式。"""

    # ── 图构建工具 ──────────────────────────────────────────────────

    def _build_linear_graph(self) -> StateGraph:
        """根据 config.steps 构建串行 LangGraph。

        每个 step → 一个节点，节点间串行连接 → END。
        """
        workflow = StateGraph(AgentState)

        steps = sorted(self.config.steps, key=lambda s: s.order)
        if not steps:
            raise ValueError("config.steps 为空，无法构建图")

        # 添加所有节点
        node_names: list[str] = []
        for step in steps:
            node_name = f"step_{step.order}_{step.name}"
            node_names.append(node_name)
            workflow.add_node(node_name, self._make_node(step))

        # 设置入口
        workflow.set_entry_point(node_names[0])

        # 串行边
        for i in range(len(node_names)):
            if i < len(node_names) - 1:
                workflow.add_edge(node_names[i], node_names[i + 1])
            else:
                workflow.add_edge(node_names[i], END)

        workflow.add_edge = workflow.add_edge  # type: ignore
        return workflow.compile()

    def _make_node(self, step):
        """生成 LangGraph 节点的工厂函数。"""

        def node_fn(state: AgentState) -> dict:
            step_start = time.time()
            step_log = {"name": step.name, "order": step.order, "type": step.type.value}

            try:
                if step.type == StepType.LLM_CALL:
                    result = self._llm_step(step, state)
                elif step.type == StepType.TRANSFORM:
                    result = self._transform_step(step, state)
                else:
                    result = {}

                duration = int((time.time() - step_start) * 1000)
                step_log["status"] = "success"
                step_log["duration_ms"] = duration

                state["steps_log"].append(step_log)
                return {step.output_key: result}
            except Exception as e:
                step_log["status"] = "error"
                step_log["error"] = str(e)[:200]
                state["steps_log"].append(step_log)
                raise

        return node_fn

    # ── Step 执行 ──────────────────────────────────────────────────

    def _llm_step(self, step, state: dict) -> Any:
        """执行 LLM 调用步骤。prompt 由 config 中的 template + context 渲染。"""
        # 构建渲染上下文
        context = dict(state)
        # 将 dict 类型的值序列化为可读字符串（供 prompt 注入）
        formatted_context = {}
        for k in step.prompt_params:
            v = context.get(k, "")
            if isinstance(v, (dict, list)):
                formatted_context[k] = json.dumps(v, ensure_ascii=False, indent=2)
            else:
                formatted_context[k] = str(v)

        prompt = step.prompt_template.format(**formatted_context)

        model = step.model_override or self.config.model
        params = {**self.config.model_params}
        if step.model_params_override:
            params.update(step.model_params_override)

        logger.info(f"  → LLM step '{step.name}': model={model}, prompt_len={len(prompt)}")
        return chat(prompt, model=model, **params)

    def _transform_step(self, step, state: dict) -> Any:
        """执行纯代码转换步骤。

        子类可覆写 _dispatch_transform() 来注册自定义转换函数。
        """
        func_name = step.transform_func
        if not func_name:
            raise ValueError(f"Transform step '{step.name}' 缺少 transform_func")

        handler = getattr(self, f"_transform_{func_name}", None)
        if handler is None:
            raise ValueError(f"未找到转换函数 _transform_{func_name}")

        logger.info(f"  → Transform step '{step.name}': func={func_name}")
        return handler(state)

    # ── 日志 ────────────────────────────────────────────────────────

    def _log_execution(
        self,
        inputs: dict,
        result: dict,
        status: str,
        duration_ms: int,
        steps_log: list[dict],
        error_msg: str = "",
    ):
        """写入 agent_executions 日志。延迟导入避免循环依赖。"""
        try:
            from .repository import AgentConfigRepository

            conversation = inputs.get("conversation", "")
            repo = AgentConfigRepository()
            repo.log_execution(
                agent_id=self._agent_id,
                version_id=self._version_id,
                input_summary=conversation[:200] if conversation else "",
                output_summary=json.dumps(result, ensure_ascii=False)[:500],
                status=status,
                duration_ms=duration_ms,
                error_msg=error_msg,
                steps_log=steps_log,
            )
        except Exception as e:
            logger.warning(f"记录执行日志失败: {e}")

    def _serialize_config(self) -> dict:
        return {
            "model": self.config.model,
            "model_params": self.config.model_params,
            "steps": [s.model_dump(exclude_none=True) for s in self.config.steps],
        }
