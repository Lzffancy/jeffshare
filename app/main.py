"""
Jeff 的工作台 — FastAPI 后端
职责：Decap CMS OAuth 中转 + 未来业务 API 骨架
页面渲染已迁移至 Astro 静态站点
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
from pydantic import BaseModel

# ── logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jeff-api")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

# 关闭 uvicorn 自带 access log
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Jeff 的工作台 — API")


# ── trace-log middleware ──────────────────────────────────────────────
@app.middleware("http")
async def trace_log_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:12]
    trace_id_var.set(trace_id)

    start_ts = time.time()

    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    req_payload = {
        "trace_id": trace_id,
        "method":  request.method,
        "url":     f"{scheme}://{request.headers.get('host', '-')}{request.url.path}",
        "path":    request.url.path,
        "query":   request.url.query or "-",
        "client":  f"{request.client.host}:{request.client.port}" if request.client else "-",
        "user_agent":      request.headers.get("user-agent", "-"),
        "referer":         request.headers.get("referer", "-"),
        "content_type":    request.headers.get("content-type", "-"),
        "content_length":  request.headers.get("content-length", "-"),
        "x_forwarded_for": request.headers.get("x-forwarded-for", "-"),
    }
    logger.info(f"REQ | {json.dumps(req_payload, ensure_ascii=False)}")

    response = await call_next(request)

    duration_ms = round((time.time() - start_ts) * 1000, 1)
    rsp_detail = (
        f"path={request.url.path} "
        f"status={response.status_code} "
        f"content_type={response.headers.get('content-type', '-')} "
        f"size={response.headers.get('content-length', '-')}"
    )
    logger.info(f"RSP | trace_id={trace_id} | {rsp_detail} | duration={duration_ms}ms")

    response.headers["X-Trace-Id"] = trace_id
    return response


# ── health check ──────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Decap CMS GitHub OAuth ───────────────────────────────────────────
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
SITE_URL = os.getenv("SITE_URL", "https://jeffshare.com")


@app.get("/admin-auth/github")
async def github_auth():
    """Redirect user to GitHub OAuth authorize page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(500, detail="GITHUB_CLIENT_ID not configured")
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "scope": "repo,user",
        "redirect_uri": f"{SITE_URL}/admin-auth/github/callback",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{qs}")


@app.get("/admin-auth/github/callback")
async def github_callback(code: str = None, error: str = None, error_description: str = None):
    """GitHub OAuth callback — exchange code for access token."""
    if error:
        raise HTTPException(400, detail=f"GitHub OAuth error: {error} — {error_description}")
    if not code:
        raise HTTPException(400, detail="Missing authorization code")
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(500, detail="GitHub OAuth credentials not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{SITE_URL}/admin-auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise HTTPException(500, detail=f"Token exchange failed: {resp.text}")
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(500, detail=f"No access_token in response: {data}")

    # Decap CMS expects the token posted back to its origin via postMessage
    # Return an HTML page that does this
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body>
<script>
  window.opener.postMessage(
    {{ token: "{access_token}", provider: "github" }},
    "{SITE_URL}"
  );
  window.close();
</script>
<p>登录成功，窗口即将关闭...</p>
</body></html>"""

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


# ── 涂鸦墙 API ─────────────────────────────────────────────────────────
GRAFFITI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "graffiti")


class GraffitiPayload(BaseModel):
    image: str  # base64 data URL (PNG)


def _graffiti_filepath(date_str: str | None = None) -> str:
    """返回指定日期的涂鸦文件路径，默认今天。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(GRAFFITI_DIR, exist_ok=True)
    return os.path.join(GRAFFITI_DIR, f"{date_str}.png")


def _cleanup_old_files(retain_days: int = 7):
    """删除超过 retain_days 天的旧涂鸦文件。"""
    cutoff = datetime.now() - timedelta(days=retain_days)
    if not os.path.isdir(GRAFFITI_DIR):
        return
    for fname in os.listdir(GRAFFITI_DIR):
        fpath = os.path.join(GRAFFITI_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)
            logger.info(f"graffiti cleanup: removed {fname}")


@app.get("/api/graffiti")
def graffiti_get():
    """获取今日涂鸦（base64 PNG），同时清理超过 7 天的旧文件。"""
    _cleanup_old_files()

    filepath = _graffiti_filepath()
    if os.path.isfile(filepath):
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return {"image": f"data:image/png;base64,{data}"}
    return {"image": None}


@app.post("/api/graffiti")
def graffiti_post(payload: GraffitiPayload):
    """保存今日涂鸦（覆盖式写入）。image 必须为 base64 PNG 数据。"""
    if not payload.image:
        raise HTTPException(status_code=400, detail="image 不能为空")

    filepath = _graffiti_filepath()

    # 解析 base64 data URL: "data:image/png;base64,xxxxx"
    raw = payload.image
    if "," in raw:
        raw = raw.split(",", 1)[1]
    img_bytes = base64.b64decode(raw)
    with open(filepath, "wb") as f:
        f.write(img_bytes)
    logger.info(f"graffiti: saved today's drawing ({len(img_bytes)} bytes)")
    return {"status": "saved"}
