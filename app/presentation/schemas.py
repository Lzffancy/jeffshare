"""Presentation schemas — FastAPI Pydantic 模型"""
from __future__ import annotations

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    conversation: str


class SaveRequest(BaseModel):
    slug: str
    markdown: str
