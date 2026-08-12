"""Comm file_ops — 通用文件操作

路径常量、文件名清理、文件落地等可复用基础能力。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("jeff-api")

# ── 路径常量 ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = PROJECT_ROOT / "source"
CONTENT_DIR = PROJECT_ROOT / "content"
IMAGES_DIR = PROJECT_ROOT / "site" / "public" / "images"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径穿越。

    只保留字母数字和 . _ -，移除路径分隔符等危险字符。
    返回空字符串时兜底为 "untitled"。
    """
    name = Path(filename).name
    safe = "".join(c for c in name if c.isalnum() or c in "._-")
    return safe or "untitled"


def save_uploaded_files(
    files: list[tuple[str, bytes]],
    dest_dir: Path,
) -> list[str]:
    """保存上传文件到目标目录。

    Args:
        files: [(filename, file_bytes), ...]
        dest_dir: 目标目录（自动创建）

    Returns:
        保存后的相对路径列表（相对于 dest_dir）
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    for filename, content in files:
        safe_name = sanitize_filename(filename)
        filepath = dest_dir / safe_name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(content)
        saved.append(safe_name)
        logger.info(f"file_ops: 保存 {safe_name} → {dest_dir.name}/")

    return saved
