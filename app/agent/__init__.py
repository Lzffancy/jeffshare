"""Agent 注册中心 — 装饰器注册 + 工厂方法"""
from __future__ import annotations

import logging
from typing import Type

from .base import BaseAgent
from .repository import AgentConfigRepository

logger = logging.getLogger("jeff-api")

_registry: dict[str, Type[BaseAgent]] = {}


def register(name: str):
    """装饰器：将 Agent 类注册到全局注册表。

    Usage:
        @register("conversation-summarizer")
        class SummarizeAgent(BaseAgent):
            ...
    """
    def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
        _registry[name] = cls
        logger.info(f"Agent registered: {name} → {cls.__name__}")
        return cls
    return decorator


def get(name: str) -> BaseAgent:
    """按名称获取 Agent 实例。

    自动从 DB 加载 active 配置，注入到 Agent 构造函数。

    Raises:
        ValueError: Agent 未注册或配置不存在
    """
    cls = _registry.get(name)
    if cls is None:
        raise ValueError(f"Agent '{name}' 未注册，已注册: {list(_registry.keys())}")

    repo = AgentConfigRepository()
    config = repo.get_active_config(name)
    return cls(config)


def list_registered() -> list[str]:
    """列出所有已注册的 Agent 名称。"""
    return list(_registry.keys())


def version_history(agent_name: str) -> list[dict]:
    """列出某 Agent 的版本历史。"""
    repo = AgentConfigRepository()
    return repo.list_versions(agent_name)


def execution_history(agent_name: str, limit: int = 20) -> list[dict]:
    """列出某 Agent 的执行历史。"""
    repo = AgentConfigRepository()
    return repo.get_executions(agent_name, limit=limit)
