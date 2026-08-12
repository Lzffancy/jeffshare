"""Infrastructure persistence — 仓储实现

实现 domain 层定义的仓储接口。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.domain.agent.repository import IAgentConfigRepo, IExecutionRepo
from app.domain.agent.entities import (
    AgentDefinition,
    AgentVersion,
    AgentStep,
    ModelParams,
)
from app.domain.agent.value_objects import ConfigStatus, StepType

from .sqlite import get_conn

logger = logging.getLogger("jeff-api")

# 进程内缓存
_cache: dict[str, AgentVersion] = {}


class SqliteAgentConfigRepo(IAgentConfigRepo):
    """IAgentConfigRepo 的 SQLite 实现。"""

    def get_definition(self, name: str) -> Optional[AgentDefinition]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM agent_definitions WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return AgentDefinition.from_row(dict(row))

    def get_active_version(self, name: str) -> AgentVersion:
        if name in _cache:
            return _cache[name]

        conn = get_conn()
        row = conn.execute(
            """SELECT v.* FROM agent_versions v
               JOIN agent_definitions d ON d.id = v.agent_id
               WHERE d.name = ? AND v.status = 'active'""",
            (name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Agent '{name}' 不存在或无 active 版本")

        version = _row_to_version(dict(row))
        _cache[name] = version
        return version

    def list_versions(self, name: str) -> list[dict]:
        conn = get_conn()
        rows = conn.execute(
            """SELECT v.id, v.version, v.status, v.model, v.changelog, v.created_at
               FROM agent_versions v
               JOIN agent_definitions d ON d.id = v.agent_id
               WHERE d.name = ?
               ORDER BY v.version DESC""",
            (name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def create_version(
        self, name: str, version: AgentVersion, activate: bool = False
    ) -> AgentVersion:
        definition = self.get_definition(name)
        if definition is None:
            raise ValueError(f"Agent '{name}' 不存在")

        conn = get_conn()
        row = conn.execute(
            "SELECT MAX(version) FROM agent_versions WHERE agent_id = ?",
            (definition.id,),
        ).fetchone()
        next_version = (row[0] or 0) + 1

        steps_json = json.dumps(
            [_step_to_dict(s) for s in version.steps], ensure_ascii=False
        )
        params_json = json.dumps(
            {"temperature": version.model_params.temperature,
             "max_tokens": version.model_params.max_tokens,
             "top_p": version.model_params.top_p},
            ensure_ascii=False,
        )
        status = "active" if activate else "draft"

        conn.execute(
            """INSERT INTO agent_versions (agent_id, version, status, model, model_params, steps, changelog)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (definition.id, next_version, status, version.model, params_json, steps_json, version.changelog),
        )

        if activate:
            conn.execute(
                "UPDATE agent_versions SET status = 'archived' WHERE agent_id = ? AND status = 'active'",
                (definition.id,),
            )
            conn.execute(
                "UPDATE agent_versions SET status = 'active' WHERE agent_id = ? AND version = ?",
                (definition.id, next_version),
            )
            _cache.pop(name, None)

        conn.commit()
        logger.info(f"SqliteAgentConfigRepo: '{name}' 创建 v{next_version}, status={status}")

        # 重新查询
        row2 = conn.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? AND version = ?",
            (definition.id, next_version),
        ).fetchone()
        return _row_to_version(dict(row2))

    def activate_version(self, name: str, version: int) -> AgentVersion:
        definition = self.get_definition(name)
        if definition is None:
            raise ValueError(f"Agent '{name}' 不存在")

        conn = get_conn()
        conn.execute("BEGIN")
        try:
            conn.execute(
                "UPDATE agent_versions SET status = 'archived' WHERE agent_id = ? AND status = 'active'",
                (definition.id,),
            )
            conn.execute(
                "UPDATE agent_versions SET status = 'active' WHERE agent_id = ? AND version = ?",
                (definition.id, version),
            )
            conn.commit()
            _cache.pop(name, None)
            logger.info(f"SqliteAgentConfigRepo: '{name}' 切换到 v{version}")
        except Exception:
            conn.rollback()
            raise

        row = conn.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? AND version = ?",
            (definition.id, version),
        ).fetchone()
        return _row_to_version(dict(row))


class SqliteExecutionRepo(IExecutionRepo):
    """IExecutionRepo 的 SQLite 实现。"""

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
        conn = get_conn()
        conn.execute(
            """INSERT INTO agent_executions
               (agent_id, version_id, input_summary, output_summary, status, duration_ms, error_msg, steps_log)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                agent_id, version_id,
                input_summary[:500], output_summary[:500],
                status, duration_ms, error_msg[:1000],
                json.dumps(steps_log, ensure_ascii=False),
            ),
        )
        conn.commit()

    def list_by_agent(self, name: str, limit: int = 20) -> list[dict]:
        conn = get_conn()
        rows = conn.execute(
            """SELECT e.*, v.version
               FROM agent_executions e
               JOIN agent_versions v ON v.id = e.version_id
               JOIN agent_definitions d ON d.id = e.agent_id
               WHERE d.name = ?
               ORDER BY e.created_at DESC
               LIMIT ?""",
            (name, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── 辅助函数 ──────────────────────────────────────────────────────


def _step_to_dict(step: AgentStep) -> dict:
    d: dict = {
        "order": step.order,
        "name": step.name,
        "type": step.type.value,
        "prompt_template": step.prompt_template,
        "prompt_params": step.prompt_params,
        "output_key": step.output_key,
    }
    if step.model_override:
        d["model_override"] = step.model_override
    if step.model_params_override:
        d["model_params_override"] = step.model_params_override
    if step.transform_func:
        d["transform_func"] = step.transform_func
    if step.output_schema:
        d["output_schema"] = step.output_schema
    return d


def _row_to_version(row: dict) -> AgentVersion:
    steps_raw = json.loads(row.get("steps", "[]"))
    steps = []
    for s in steps_raw:
        step_type = StepType(s.get("type", "llm_call"))
        steps.append(AgentStep(
            order=s.get("order", 0),
            name=s.get("name", ""),
            type=step_type,
            prompt_template=s.get("prompt_template", ""),
            prompt_params=s.get("prompt_params", []),
            output_key=s.get("output_key", ""),
            output_schema=s.get("output_schema"),
            model_override=s.get("model_override"),
            model_params_override=s.get("model_params_override"),
            transform_func=s.get("transform_func"),
        ))

    params_raw = json.loads(row.get("model_params", "{}"))
    model_params = ModelParams(
        temperature=params_raw.get("temperature", 0.3),
        max_tokens=params_raw.get("max_tokens", 2048),
        top_p=params_raw.get("top_p", 1.0),
    )

    return AgentVersion(
        id=row["id"],
        agent_id=row["agent_id"],
        version=row["version"],
        status=ConfigStatus(row.get("status", "draft")),
        model=row.get("model", "gpt-4o-mini"),
        model_params=model_params,
        steps=steps,
        changelog=row.get("changelog", ""),
    )
