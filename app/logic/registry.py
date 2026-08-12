"""AgentRegistry — 装饰器注册 + 工厂方法

避免 entity 层感知"注册"这个应用层概念，
因此 registry 放在 logic 层。
"""
from __future__ import annotations

import logging
from typing import Type

logger = logging.getLogger("jeff-api")

_registry: dict[str, Type] = {}


def register(name: str):
    """装饰器：将 Agent 类注册到全局注册表。"""
    def decorator(cls: Type) -> Type:
        _registry[name] = cls
        logger.info(f"Agent registered: {name} → {cls.__name__}")
        return cls
    return decorator


def list_registered() -> list[str]:
    """列出所有已注册的 Agent 名称。"""
    return list(_registry.keys())
