"""Repository persistence — SQLite 连接 + DDL"""
from __future__ import annotations

import os
import sqlite3
import threading

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "agent.db",
)

_local = threading.local()

DDL = """
CREATE TABLE IF NOT EXISTS agent_definitions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    display_name  TEXT    NOT NULL,
    description   TEXT    DEFAULT '',
    workflow_type TEXT    NOT NULL DEFAULT 'linear_chain',
    agent_class   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id     INTEGER NOT NULL REFERENCES agent_definitions(id),
    version      INTEGER NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'draft',
    model        TEXT    NOT NULL DEFAULT 'gpt-4o-mini',
    model_params TEXT    NOT NULL DEFAULT '{}',
    steps        TEXT    NOT NULL DEFAULT '[]',
    changelog    TEXT    DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(agent_id, version)
);

CREATE TABLE IF NOT EXISTS agent_executions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id       INTEGER NOT NULL,
    version_id     INTEGER NOT NULL,
    input_summary  TEXT,
    output_summary TEXT,
    status         TEXT    NOT NULL,
    duration_ms    INTEGER,
    error_msg      TEXT,
    steps_log      TEXT    DEFAULT '[]',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(DDL)
        conn.commit()
        _local.conn = conn
    return _local.conn


def close_conn():
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None
