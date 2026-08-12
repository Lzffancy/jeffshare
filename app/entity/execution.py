"""Entity execution — 执行记录"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .values import ExecutionStatus


@dataclass
class ExecutionRecord:
    """Agent 执行记录 — 实体。"""
    agent_id: int
    version_id: int
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: int = 0
    error_msg: str = ""
    steps_log: list[dict] = field(default_factory=list)
    created_at: str = ""
    id: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
