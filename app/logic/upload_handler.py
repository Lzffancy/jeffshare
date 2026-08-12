"""Logic upload_handler — UploadProcessingUseCase（上传处理用例）

业务编排层：保存文件（comm.file_ops）→ Claude CLI 处理（comm.claude）→ 返回结果。
基础设施已抽象到 app/comm/ 通用模块中。
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.comm.file_ops import SOURCE_DIR, save_uploaded_files
from app.comm.claude import run as run_claude, ClaudeResult

logger = logging.getLogger("jeff-api")


@dataclass
class UploadResult:
    """上传处理结果 DTO。"""
    success: bool
    upload_id: str
    content_type: str = ""       # blog / share / report
    target_path: str = ""        # 最终 content/ 下的路径
    message: str = ""
    claude_output: str = ""      # Claude CLI 原始输出（调试用）


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

        try:
            save_uploaded_files(files, dest_dir)
            claude_result = run_claude(upload_id)
            return self._to_upload_result(upload_id, claude_result)
        except Exception as e:
            logger.error(f"UploadProcessing: 处理失败: {e}")
            return UploadResult(
                success=False,
                upload_id=upload_id,
                message=f"处理失败: {e}",
            )

    @staticmethod
    def _to_upload_result(upload_id: str, cr: ClaudeResult) -> UploadResult:
        """将 ClaudeResult 转换为 UploadResult。"""
        if cr.success:
            return UploadResult(
                success=True,
                upload_id=upload_id,
                content_type=cr.content_type,
                target_path=cr.target_path,
                message=f"已发布到 content/{cr.target_path}" if cr.target_path else "处理完成",
                claude_output=cr.raw_output,
            )
        return UploadResult(
            success=False,
            upload_id=upload_id,
            message="Claude CLI 处理失败",
            claude_output=cr.raw_output,
        )
