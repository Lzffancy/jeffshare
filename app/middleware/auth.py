"""Middleware auth — 认证依赖函数

从 OAuth session 抽取 require_auth，供所有需要鉴权的路由复用。
"""
from __future__ import annotations

import time

from fastapi import Request, HTTPException

from app.middleware.oauth import sessions, SESSION_EXPIRE_SECONDS


async def require_auth(request: Request) -> dict:
    """FastAPI 依赖：校验 jeff_sid cookie，返回 session 信息。

    用法:
        @router.post("/api/upload")
        async def upload(request: Request, session=Depends(require_auth)):
            ...
    """
    sid = request.cookies.get("jeff_sid", "")
    if not sid:
        raise HTTPException(status_code=401, detail="未登录，请先访问 /admin/ 进行 GitHub OAuth 登录")

    session = sessions.get(sid)
    if session is None:
        raise HTTPException(status_code=401, detail="会话不存在，请重新登录")

    if time.time() - session["created_at"] > SESSION_EXPIRE_SECONDS:
        sessions.pop(sid, None)
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    return session
