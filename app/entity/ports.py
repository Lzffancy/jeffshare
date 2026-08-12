"""Entity ports — 端口契约（依赖倒置）

内层声明"需要什么能力"，具体实现由 repository 层提供。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from .agent import AgentDefinition, AgentStep, AgentVersion

if TYPE_CHECKING:
    from app.logic.orchestrator import StepExecutor


class ILlmClient(ABC):
    """LLM 调用抽象（端口）。"""

    @abstractmethod
    def chat(self, prompt: str, model: str, **params: Any) -> dict:
        """调用 LLM 并返回 JSON dict。

        Raises:
            RuntimeError: 调用或解析失败
        """
        ...


class IWorkflowEngine(ABC):
    """工作流执行引擎抽象（端口）。

    LangGraph StateGraph 是其中一个实现。
    """

    @abstractmethod
    def compile(self, steps: list[AgentStep], executor: StepExecutor) -> Any:
        """根据 steps 构建可调用的工作流图。

        Returns:
            可调用的 graph 对象（实现相关，如 CompiledStateGraph）
        """
        ...


class IAgentConfigRepo(ABC):
    """Agent 配置仓储接口。"""

    @abstractmethod
    def get_definition(self, name: str) -> Optional[AgentDefinition]:
        """按名称获取 Agent 定义。"""
        ...

    @abstractmethod
    def get_active_version(self, name: str) -> AgentVersion:
        """获取指定 Agent 的 active 版本配置。

        Raises:
            ValueError: Agent 不存在或无 active 版本
        """
        ...

    @abstractmethod
    def list_versions(self, name: str) -> list[dict]:
        """列出某 Agent 的所有版本摘要。"""
        ...

    @abstractmethod
    def create_version(
        self, name: str, version: AgentVersion, activate: bool = False
    ) -> AgentVersion:
        """为 Agent 创建新版本。

        Args:
            name: Agent 名称
            version: 新版本数据（不含 id、agent_id、version 号，这些由 repo 生成）
            activate: 是否立即激活
        """
        ...

    @abstractmethod
    def activate_version(self, name: str, version: int) -> AgentVersion:
        """切换 active 版本。"""
        ...


class IExecutionRepo(ABC):
    """Agent 执行日志仓储接口。"""

    @abstractmethod
    def log(
        self,
        agent_id: int,
        version_id: int,
        input_summary: str,
        output_summary: str,
        status: str,
        duration_ms: int,
        error_msg: str,
        steps_log: list[dict],
    ) -> None:
        ...

    @abstractmethod
    def list_by_agent(self, name: str, limit: int = 20) -> list[dict]:
        ...
