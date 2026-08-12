"""Domain repository interfaces — 抽象接口（依赖倒置）

定义仓储契约，具体实现在 infrastructure 层。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import AgentDefinition, AgentVersion


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
