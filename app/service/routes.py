"""Service routes — FastAPI Agent 路由 + 组合根(DI)

依赖注入：通过懒加载单例组装 repository 实现并注入 use case。
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth import require_auth
from app.logic.dtos import SummarizeInput, SaveMarkdownInput
from app.logic.summarize import SummarizeUseCase
from app.logic.save_markdown import SaveMarkdownUseCase
from app.repository.persistence.repositories import SqliteAgentConfigRepo
from app.repository.llm.openai_client import OpenAIClient
from app.repository.workflow.langgraph_engine import LangGraphWorkflowEngine

from .schemas import SummarizeRequest, SaveRequest

logger = logging.getLogger("jeff-api")

router = APIRouter(prefix="/api/agent")

# ── 依赖（懒加载单例） ─────────────────────────────────────────────

_repo: SqliteAgentConfigRepo | None = None
_llm: OpenAIClient | None = None
_engine: LangGraphWorkflowEngine | None = None
_summarize_uc: SummarizeUseCase | None = None
_save_uc: SaveMarkdownUseCase | None = None


def _get_summarize_uc() -> SummarizeUseCase:
    global _repo, _llm, _engine, _summarize_uc
    if _summarize_uc is None:
        _repo = SqliteAgentConfigRepo()
        _llm = OpenAIClient()
        _engine = LangGraphWorkflowEngine()
        _summarize_uc = SummarizeUseCase(repo=_repo, llm=_llm, engine=_engine)
    return _summarize_uc


def _get_save_uc() -> SaveMarkdownUseCase:
    global _save_uc
    if _save_uc is None:
        _save_uc = SaveMarkdownUseCase(
            content_dir=os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "content", "posts",
            )
        )
    return _save_uc


# ── 路由 ──────────────────────────────────────────────────────────


@router.post("/summarize")
async def summarize(payload: SummarizeRequest, session: dict = Depends(require_auth)):
    """AI 会话总结：粘贴对话 → 返回 Markdown。"""
    if not payload.conversation.strip():
        raise HTTPException(status_code=400, detail="对话内容不能为空")

    try:
        output = _get_summarize_uc().execute(
            SummarizeInput(conversation=payload.conversation.strip())
        )
        return {"success": True, "result": {
            "title": output.title,
            "slug": output.slug,
            "tags": output.tags,
            "markdown": output.markdown,
            "summary": output.summary,
        }}
    except ValueError as e:
        logger.error(f"/api/agent/summarize: 配置错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        logger.error(f"/api/agent/summarize: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"/api/agent/summarize: unexpected: {e}")
        raise HTTPException(status_code=500, detail="总结失败，请稍后重试")


@router.post("/save")
async def save_markdown(payload: SaveRequest, session: dict = Depends(require_auth)):
    """保存编辑后的 Markdown 到 content/posts/。"""
    if not payload.slug or not payload.markdown:
        raise HTTPException(status_code=400, detail="slug 和 markdown 不能为空")

    try:
        filepath = _get_save_uc().execute(
            SaveMarkdownInput(slug=payload.slug, markdown=payload.markdown)
        )
        return {
            "success": True,
            "path": filepath,
            "message": "已保存，git commit + push 后即可上线",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
