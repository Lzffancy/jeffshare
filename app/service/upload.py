"""Service upload — 文件上传路由

POST /api/upload → 保存到 source/ → Claude CLI 处理 → 发布到 content/。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile, HTTPException

from app.middleware.auth import require_auth
from app.logic.upload_handler import UploadProcessingUseCase, UploadResult

logger = logging.getLogger("jeff-api")

router = APIRouter(prefix="/api/upload")

_upload_uc: UploadProcessingUseCase | None = None


def _get_upload_uc() -> UploadProcessingUseCase:
    global _upload_uc
    if _upload_uc is None:
        _upload_uc = UploadProcessingUseCase()
    return _upload_uc


@router.post("")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    session: dict = Depends(require_auth),
):
    """上传文件到 source/，自动处理并发布到 content/。

    支持：
    - 单个 .md / .html 文件
    - 多个文件（含图片附件）
    - .zip 包（待扩展）

    鉴权：需要 GitHub OAuth 登录（jeff_sid cookie）。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请选择要上传的文件")

    # 读取文件内容
    raw_files: list[tuple[str, bytes]] = []
    total_size = 0
    for f in files:
        content = await f.read()
        total_size += len(content)
        if total_size > 50 * 1024 * 1024:  # 50MB 上限
            raise HTTPException(status_code=400, detail="上传文件总大小不能超过 50MB")
        raw_files.append((f.filename or "untitled", content))

    logger.info(
        f"Upload: 收到 {len(raw_files)} 个文件，总大小 {total_size} 字节，"
        f"用户 {session.get('user', {}).get('login', 'unknown')}"
    )

    uc = _get_upload_uc()
    result = uc.execute(raw_files)

    return _format_response(result)


def _format_response(result: UploadResult) -> dict:
    """将 UploadResult 格式化 API 响应。"""
    body = {
        "success": result.success,
        "upload_id": result.upload_id,
        "content_type": result.content_type,
        "target_path": result.target_path,
        "message": result.message,
    }
    # 仅在失败时暴露 Claude 输出便于排查
    if not result.success and result.claude_output:
        body["detail"] = result.claude_output[-2000:]  # 截断
    return body
