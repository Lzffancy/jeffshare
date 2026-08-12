"""Application DTOs — 数据传输对象

纯数据，不含业务逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SummarizeInput:
    conversation: str


@dataclass
class SummarizeOutput:
    title: str
    slug: str
    tags: list[str] = field(default_factory=list)
    markdown: str = ""
    summary: str = ""


@dataclass
class SaveMarkdownInput:
    slug: str
    markdown: str
