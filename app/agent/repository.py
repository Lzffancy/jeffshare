"""AgentConfigRepository — 配置 CRUD + 版本管理 + 执行日志"""
from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger("jeff-api")

from .db import get_conn
from .models import AgentDefinition, AgentVersionConfig, AgentStepConfig

# 简单的单例缓存（同一进程内避免重复读 DB）
_cache: dict[str, AgentVersionConfig] = {}


class AgentConfigRepository:
    """Agent 配置仓储层。

    所有配置读写都经过此层，保证版本管理语义（active 唯一、事务切换等）。
    """

    # ── 查询 ──────────────────────────────────────────────────────

    def get_definition(self, agent_name: str) -> Optional[AgentDefinition]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM agent_definitions WHERE name = ?", (agent_name,)
        ).fetchone()
        if row is None:
            return None
        return AgentDefinition(**dict(row))

    def get_active_config(self, agent_name: str, use_cache: bool = True) -> AgentVersionConfig:
        """获取指定 Agent 的 active 版本配置。

        Raises:
            ValueError: Agent 不存在或无 active 版本
        """
        if use_cache and agent_name in _cache:
            return _cache[agent_name]

        conn = get_conn()
        row = conn.execute(
            """SELECT v.* FROM agent_versions v
               JOIN agent_definitions d ON d.id = v.agent_id
               WHERE d.name = ? AND v.status = 'active'""",
            (agent_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Agent '{agent_name}' 不存在或没有 active 版本。请先 seed。")

        config = self._row_to_config(dict(row))
        _cache[agent_name] = config
        return config

    def get_version(self, agent_name: str, version: int) -> Optional[AgentVersionConfig]:
        conn = get_conn()
        row = conn.execute(
            """SELECT v.* FROM agent_versions v
               JOIN agent_definitions d ON d.id = v.agent_id
               WHERE d.name = ? AND v.version = ?""",
            (agent_name, version),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_config(dict(row))

    def list_versions(self, agent_name: str) -> list[dict]:
        """列出某 Agent 的所有版本（摘要信息）。"""
        conn = get_conn()
        rows = conn.execute(
            """SELECT v.id, v.version, v.status, v.model, v.changelog, v.created_at
               FROM agent_versions v
               JOIN agent_definitions d ON d.id = v.agent_id
               WHERE d.name = ?
               ORDER BY v.version DESC""",
            (agent_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 写 ────────────────────────────────────────────────────────

    def create_version(
        self, agent_name: str, config: AgentVersionConfig, activate: bool = False
    ) -> AgentVersionConfig:
        """为指定 Agent 创建新版本。

        Args:
            agent_name: Agent 名称
            config: 版本配置（不需要填 agent_id 和 id）
            activate: 是否立即激活为新 active 版本

        Returns:
            创建后的完整配置（含 id 和 agent_id）
        """
        definition = self.get_definition(agent_name)
        if definition is None:
            raise ValueError(f"Agent '{agent_name}' 不存在")

        conn = get_conn()

        # 计算下一个版本号
        row = conn.execute(
            "SELECT MAX(version) FROM agent_versions WHERE agent_id = ?",
            (definition.id,),
        ).fetchone()
        next_version = (row[0] or 0) + 1

        steps_json = json.dumps(
            [s.model_dump(exclude_none=True) for s in config.steps], ensure_ascii=False
        )
        model_params_json = json.dumps(config.model_params, ensure_ascii=False)

        status = "active" if activate else (config.status.value if hasattr(config.status, "value") else str(config.status))

        conn.execute(
            """INSERT INTO agent_versions (agent_id, version, status, model, model_params, steps, changelog)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (definition.id, next_version, status, config.model, model_params_json, steps_json, config.changelog),
        )

        # 如果激活，把旧的 active 全部归档
        if activate:
            conn.execute(
                "UPDATE agent_versions SET status = 'archived' WHERE agent_id = ? AND status = 'active'",
                (definition.id,),
            )
            conn.execute(
                "UPDATE agent_versions SET status = 'active' WHERE agent_id = ? AND version = ?",
                (definition.id, next_version),
            )
            _cache.pop(agent_name, None)  # 刷新缓存

        conn.commit()
        logger.info(f"Agent '{agent_name}' 创建版本 v{next_version}, status={status}")

        # 重新查询回完整的配置
        return self.get_version(agent_name, next_version)  # type: ignore

    def activate_version(self, agent_name: str, version: int) -> AgentVersionConfig:
        """切换 active 版本（事务：旧→archived，新→active）。"""
        definition = self.get_definition(agent_name)
        if definition is None:
            raise ValueError(f"Agent '{agent_name}' 不存在")

        target = self.get_version(agent_name, version)
        if target is None:
            raise ValueError(f"Agent '{agent_name}' 版本 v{version} 不存在")

        conn = get_conn()
        conn.execute("BEGIN")
        try:
            # 旧 active → archived
            conn.execute(
                "UPDATE agent_versions SET status = 'archived' WHERE agent_id = ? AND status = 'active'",
                (definition.id,),
            )
            # 目标 → active
            conn.execute(
                "UPDATE agent_versions SET status = 'active' WHERE id = ?",
                (target.id,),
            )
            conn.commit()
            _cache.pop(agent_name, None)  # 刷新缓存
            logger.info(f"Agent '{agent_name}' 切换到 v{version}")
        except Exception:
            conn.rollback()
            raise

        return self.get_version(agent_name, version)  # type: ignore

    # ── 执行日志 ──────────────────────────────────────────────────

    def log_execution(
        self,
        agent_id: int,
        version_id: int,
        input_summary: str = "",
        output_summary: str = "",
        status: str = "success",
        duration_ms: int = 0,
        error_msg: str = "",
        steps_log: list[dict] | None = None,
    ) -> None:
        conn = get_conn()
        conn.execute(
            """INSERT INTO agent_executions (agent_id, version_id, input_summary, output_summary, status, duration_ms, error_msg, steps_log)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                agent_id,
                version_id,
                input_summary[:500],
                output_summary[:500],
                status,
                duration_ms,
                error_msg[:1000],
                json.dumps(steps_log or [], ensure_ascii=False),
            ),
        )
        conn.commit()

    # ── 辅助 ──────────────────────────────────────────────────────

    def _row_to_config(self, row: dict) -> AgentVersionConfig:
        steps_raw = json.loads(row.get("steps", "[]"))
        steps = [AgentStepConfig(**s) for s in steps_raw]
        model_params = json.loads(row.get("model_params", "{}"))
        return AgentVersionConfig(
            id=row["id"],
            agent_id=row["agent_id"],
            version=row["version"],
            status=row.get("status", "draft"),
            model=row.get("model", "gpt-4o-mini"),
            model_params=model_params,
            steps=steps,
            changelog=row.get("changelog", ""),
        )

    def get_executions(self, agent_name: str, limit: int = 20) -> list[dict]:
        conn = get_conn()
        rows = conn.execute(
            """SELECT e.*, v.version
               FROM agent_executions e
               JOIN agent_versions v ON v.id = e.version_id
               JOIN agent_definitions d ON d.id = e.agent_id
               WHERE d.name = ?
               ORDER BY e.created_at DESC
               LIMIT ?""",
            (agent_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
