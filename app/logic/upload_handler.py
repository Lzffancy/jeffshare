"""Logic upload_handler — UploadProcessingUseCase（上传处理用例）

接收上传文件 → 保存到 source/ → 调用 Claude CLI 处理 → 返回结果。
"""
from __future__ import annotations

import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("jeff-api")

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = PROJECT_ROOT / "source"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@dataclass
class UploadResult:
    success: bool
    upload_id: str
    content_type: str = ""           # blog / share / report
    target_path: str = ""            # 最终 content/ 下的路径
    message: str = ""
    claude_output: str = ""          # Claude CLI 原始输出（调试用）


class UploadProcessingUseCase:
    """上传处理用例：保存原始文件 → 调用 Claude CLI 智能处理 → 发布到 content/。"""

    def __init__(self, source_dir: str | None = None):
        self._source_dir = Path(source_dir) if source_dir else SOURCE_DIR

    def execute(self, files: list[tuple[str, bytes]]) -> UploadResult:
        """处理上传文件。

        Args:
            files: [(filename, file_bytes), ...] 上传的文件列表

        Returns:
            UploadResult
        """
        upload_id = uuid.uuid4().hex[:12]
        dest_dir = self._source_dir / upload_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 保存原始文件到 source/{upload_id}/
            for filename, content in files:
                safe_name = self._sanitize_filename(filename)
                filepath = dest_dir / safe_name
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(content)
                logger.info(f"UploadProcessing: 保存 {safe_name} → source/{upload_id}/")

            # 2. 调用 Claude CLI 脚本处理
            result = self._run_claude_script(upload_id)

            return result

        except Exception as e:
            logger.error(f"UploadProcessing: 处理失败: {e}")
            return UploadResult(
                success=False,
                upload_id=upload_id,
                message=f"处理失败: {e}",
            )

    def _run_claude_script(self, upload_id: str) -> UploadResult:
        """调用 process_upload.sh 由 Claude CLI 智能处理。"""
        script_path = SCRIPTS_DIR / "process_upload.sh"

        if not script_path.exists():
            # 降级：无 Claude 脚本时，直接返回未处理
            return UploadResult(
                success=True,
                upload_id=upload_id,
                content_type="unknown",
                message=f"文件已保存到 source/{upload_id}/，需手动处理（Claude CLI 脚本未安装）",
            )

        logger.info(f"UploadProcessing: 调用 Claude CLI 处理 source/{upload_id}/ ...")
        try:
            proc = subprocess.run(
                ["bash", str(script_path), upload_id],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300,  # Claude CLI 可能耗时较长
            )

            claude_output = proc.stdout + "\n" + proc.stderr
            logger.info(f"UploadProcessing: Claude CLI 返回码={proc.returncode}")

            if proc.returncode != 0:
                return UploadResult(
                    success=False,
                    upload_id=upload_id,
                    message=f"Claude CLI 处理失败 (exit {proc.returncode})",
                    claude_output=claude_output,
                )

            # 解析 Claude 输出中的结果信息
            content_type, target_path = self._parse_claude_output(claude_output)
            return UploadResult(
                success=True,
                upload_id=upload_id,
                content_type=content_type,
                target_path=target_path,
                message=f"已发布到 content/{target_path}" if target_path else "处理完成",
                claude_output=claude_output,
            )

        except subprocess.TimeoutExpired:
            return UploadResult(
                success=False,
                upload_id=upload_id,
                message="Claude CLI 处理超时（5分钟）",
            )
        except FileNotFoundError:
            return UploadResult(
                success=True,
                upload_id=upload_id,
                content_type="unknown",
                message=f"文件已保存到 source/{upload_id}/，Claude CLI 未安装，需手动处理",
            )

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """清理文件名，防止路径穿越。"""
        # 只取最后一部分，去掉路径
        name = Path(filename).name
        # 替换危险字符
        safe = "".join(c for c in name if c.isalnum() or c in "._-")
        return safe or "untitled"

    @staticmethod
    def _parse_claude_output(output: str) -> tuple[str, str]:
        """从 Claude CLI 输出中解析 content_type 和 target_path。

        期望 Claude 在输出的最后一行输出 JSON:
        {"content_type": "blog", "target_path": "posts/my-article.md"}
        """
        import json
        import re

        # 尝试匹配 JSON 块
        json_pattern = r'\{[^{}]*"content_type"[^{}]*\}'
        matches = re.findall(json_pattern, output)
        for match in reversed(matches):
            try:
                data = json.loads(match)
                return data.get("content_type", ""), data.get("target_path", "")
            except json.JSONDecodeError:
                continue

        return "", ""
