"""Middleware oauth — Decap CMS OAuth 中转

从 app.main 抽出，使用独立 APIRouter。
"""
from __future__ import annotations

import os
import time
import uuid
import contextvars

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter()

OAUTH_CLIENT_ID = "b9ebf70e04c8bc275523"
OAUTH_CLIENT_SECRET = "ac91c75d7ae77c4a6c6e20ba4d5cf2002fcf9f34"
SESSION_EXPIRE_SECONDS = 3600
OAUTH_STATE_TTL = 600
# 只允许这些 GitHub 用户登录（白名单）
ALLOWED_GITHUB_USERS: set[str] = set(
    os.getenv("ALLOWED_GITHUB_USERS", "jeffszhang").split(",")
)

oauth_states: dict[str, dict] = {}  # {state: {created_at, redirect}}
sessions: dict[str, dict] = {}
sid_ctx: contextvars.ContextVar = contextvars.ContextVar("sid", default="")


@router.get("/admin-auth")
async def admin_auth(request: Request):
    provider = request.query_params.get("provider", "github")
    redirect_to = request.query_params.get("redirect", "/admin/")
    if provider == "github":
        state = uuid.uuid4().hex
        oauth_states[state] = {
            "created_at": time.time(),
            "redirect": redirect_to,
        }
        return RedirectResponse(
            f"https://github.com/login/oauth/authorize"
            f"?client_id={OAUTH_CLIENT_ID}&scope=repo,user&state={state}"
        )
    raise HTTPException(status_code=400, detail=f"unsupported provider: {provider}")


@router.get("/admin-auth/callback")
async def github_callback(code: str = "", state: str = ""):
    now = time.time()
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="invalid state")
    state_data = oauth_states.pop(state)
    if now - state_data["created_at"] > OAUTH_STATE_TTL:
        raise HTTPException(status_code=400, detail="state expired")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="token exchange failed")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_resp.json()

        # ── 用户白名单校验：只有 ALLOWED_GITHUB_USERS 中的人才能登录 ──
        login = user_info.get("login", "")
        if login not in ALLOWED_GITHUB_USERS:
            raise HTTPException(
                status_code=403,
                detail=f"用户 {login} 不在允许列表中",
            )

    sid = uuid.uuid4().hex
    sessions[sid] = {
        "user": user_info,
        "token": access_token,
        "created_at": now,
    }

    site_url = os.getenv("SITE_URL", "https://jeffshare.com")
    redirect_to = state_data.get("redirect", "/admin/")
    response = RedirectResponse(f"{site_url}{redirect_to}")
    response.set_cookie(
        key="jeff_sid", value=sid, httponly=True,
        secure=True, samesite="lax", max_age=SESSION_EXPIRE_SECONDS,
    )
    return response


@router.post("/admin-auth/exchange")
async def admin_exchange(request: Request):
    body = await request.json()
    provider = body.get("provider", "github")
    if provider != "github":
        raise HTTPException(status_code=400, detail=f"unsupported provider: {provider}")

    token = body.get("token")
    if not token:
        sid = request.cookies.get("jeff_sid", "")
        session = sessions.get(sid, {})
        token = session.get("token", "")

    if not token:
        raise HTTPException(status_code=401, detail="no token")

    return {
        "token": token,
        "backendName": "github",
        "user": sessions.get(request.cookies.get("jeff_sid", ""), {}).get("user", {}),
    }


@router.get("/admin-auth/verify")
async def admin_verify(request: Request):
    sid = request.cookies.get("jeff_sid", "")
    session = sessions.get(sid)
    if session is None or time.time() - session["created_at"] > SESSION_EXPIRE_SECONDS:
        raise HTTPException(status_code=401, detail="session expired")
    return {"user": session["user"]}



