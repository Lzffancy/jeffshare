"""
Jeff 的工作台 — FastAPI 后端
职责：依赖组装 + FastAPI 创建

DDD 四层架构：
  presentation → application → domain ← infrastructure
"""
import json
import uuid
import time
import logging
import contextvars
import os
import base64
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.presentation.routes import router as agent_router
from app.seed import seed_all

# ── 日志 ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jeff-api")

# ── FastAPI 应用 ───────────────────────────────────────────────────
app = FastAPI(
    title="Jeff 工作台 API",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 Agent 路由
app.include_router(agent_router)


# ── 启动事件 ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """写入种子数据。"""
    seed_all()
    logger.info("DDD 四层架构启动完成")


# ── Decap CMS OAuth 中转 ───────────────────────────────────────────
OAUTH_CLIENT_ID = "b9ebf70e04c8bc275523"
OAUTH_CLIENT_SECRET = "ac91c75d7ae77c4a6c6e20ba4d5cf2002fcf9f34"
SESSION_EXPIRE_SECONDS = 3600
OAUTH_STATE_TTL = 600

oauth_states: dict[str, float] = {}
sessions: dict[str, dict] = {}
sid_ctx: contextvars.ContextVar = contextvars.ContextVar("sid", default="")


@app.get("/")
async def root():
    return {"status": "ok", "service": "jeff-share-api"}


@app.get("/admin-auth")
async def admin_auth(request: Request):
    provider = request.query_params.get("provider", "github")
    if provider == "github":
        state = uuid.uuid4().hex
        oauth_states[state] = time.time()
        return RedirectResponse(
            f"https://github.com/login/oauth/authorize"
            f"?client_id={OAUTH_CLIENT_ID}&scope=repo,user&state={state}"
        )
    raise HTTPException(status_code=400, detail=f"unsupported provider: {provider}")


@app.get("/admin-auth/callback")
async def github_callback(code: str = "", state: str = ""):
    now = time.time()
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="invalid state")
    if now - oauth_states.pop(state) > OAUTH_STATE_TTL:
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

    sid = uuid.uuid4().hex
    sessions[sid] = {
        "user": user_info,
        "token": access_token,
        "created_at": now,
    }

    site_url = os.getenv("SITE_URL", "https://jeffshare.com")
    response = RedirectResponse(f"{site_url}/admin/")
    response.set_cookie(
        key="jeff_sid", value=sid, httponly=True,
        secure=True, samesite="lax", max_age=SESSION_EXPIRE_SECONDS,
    )
    return response


@app.post("/admin-auth/exchange")
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


@app.get("/admin-auth/verify")
async def admin_verify(request: Request):
    sid = request.cookies.get("jeff_sid", "")
    session = sessions.get(sid)
    if session is None or time.time() - session["created_at"] > SESSION_EXPIRE_SECONDS:
        raise HTTPException(status_code=401, detail="session expired")
    return {"user": session["user"]}


# ── 涂鸦墙 API ─────────────────────────────────────────────────────
GRAFFITI_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "graffiti",
)


class GraffitiPayload(BaseModel):
    content: str


@app.get("/api/graffiti")
async def get_graffiti():
    os.makedirs(GRAFFITI_DIR, exist_ok=True)
    f = os.path.join(GRAFFITI_DIR, "latest.json")
    if not os.path.exists(f):
        return {"content": ""}
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return {"content": data.get("content", "")}


@app.post("/api/graffiti")
async def post_graffiti(payload: GraffitiPayload):
    os.makedirs(GRAFFITI_DIR, exist_ok=True)
    f = os.path.join(GRAFFITI_DIR, "latest.json")
    with open(f, "w", encoding="utf-8") as fp:
        json.dump({"content": payload.content}, fp, ensure_ascii=False)
    return {"success": True}
