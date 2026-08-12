"""Jeff 的工作台 — FastAPI 后端
职责：依赖组装 + FastAPI 创建

Clean Architecture 分层：
  service → logic → entity ← repository
       ← middleware（横切关注点）
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.service.routes import router as agent_router
from app.service.graffiti import router as graffiti_router
from app.service.upload import router as upload_router
from app.middleware.oauth import router as oauth_router
from app.repository.persistence.seed import seed_all

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

# 注册路由
app.include_router(agent_router)
app.include_router(graffiti_router)
app.include_router(upload_router)
app.include_router(oauth_router)


# ── 启动事件 ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """写入种子数据。"""
    seed_all()
    logger.info("Clean Architecture 启动完成")


# ── 根路由 ─────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "service": "jeff-share-api"}
