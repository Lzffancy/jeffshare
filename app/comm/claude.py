"""Comm claude — Claude CLI 子进程调用

封装 process_upload.sh 的调用、超时控制、输出解析。
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass

from app.comm.file_ops import PROJECT_ROOT, SCRIPTS_DIR

logger = logging.getLogger("jeff-api")


@dataclass
class ClaudeResult:
    """Claude CLI 处理结果。"""
    success: bool
    content_type: str = ""       # blog / share / report
    target_path: str = ""        # 最终 content/ 下的相对路径
    raw_output: str = ""         # Claude CLI 原始输出（调试用）


def run(upload_id: str, *, timeout: int = 300) -> ClaudeResult:
    """调用 scripts/process_upload.sh，由 Claude CLI 处理上传内容。

    Args:
        upload_id: source/ 下的上传子目录名
        timeout: 超时秒数（默认 5 分钟）

    Returns:
        ClaudeResult
    """
    script_path = SCRIPTS_DIR / "process_upload.sh"

    if not script_path.exists():
        return ClaudeResult(
            success=True,
            content_type="unknown",
            raw_output="Claude CLI 脚本未安装，文件保持未处理状态",
        )

    logger.info(f"claude: 调用 process_upload.sh 处理 source/{upload_id}/ ...")

    try:
        proc = subprocess.run(
            ["bash", str(script_path), upload_id],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ClaudeResult(
            success=False,
            raw_output=f"处理超时（{timeout}秒）",
        )
    except FileNotFoundError:
        return ClaudeResult(
            success=True,
            content_type="unknown",
            raw_output="claude 命令未安装",
        )

    raw_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    logger.info(f"claude: 返回码={proc.returncode}")

    if proc.returncode != 0:
        return ClaudeResult(
            success=False,
            raw_output=raw_output,
        )

    content_type, target_path = _parse_output(raw_output)
    return ClaudeResult(
        success=True,
        content_type=content_type,
        target_path=target_path,
        raw_output=raw_output,
    )


def _parse_output(output: str) -> tuple[str, str]:
    """从 Claude CLI 输出中解析 JSON 结果。

    期望 Claude 在输出的最后输出一行 JSON:
        {"content_type": "blog", "target_path": "posts/my-article.md"}
    """
    pattern = r'\{[^{}]*"content_type"[^{}]*\}'
    matches = re.findall(pattern, output)
    for match in reversed(matches):
        try:
            data = json.loads(match)
            return data.get("content_type", ""), data.get("target_path", "")
        except json.JSONDecodeError:
            continue
    return "", ""
