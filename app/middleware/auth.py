"""Middleware auth — 密码认证 + require_auth 依赖

简单密码登录。ADMIN_PASSWORD 环境变量控制密码。
登录成功后设置 jeff_token cookie，后续请求通过 require_auth 校验。

Session 存储在 SQLite（data/agent.db 的 sessions 表），多 worker 进程共享、
重启不丢失，避免「登录已过期」误判。
"""
from __future__ import annotations

import hashlib
import logging
import os
import time

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from app.repository.persistence.sqlite import get_conn
from app.middleware.tracing import get_trace_id

logger = logging.getLogger("jeff-api")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
SESSION_MAX_AGE = 86400 * 7  # 7 天

# 防暴力破解：同一 IP 连续失败次数阈值与锁定时长
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_SECONDS = 3600  # 1 小时

router = APIRouter()

# 内存缓存: token → expiry_timestamp（只读缓存，真实数据在 SQLite）
_cache: dict[str, float] = {}


def _ensure_sessions_table() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token    TEXT PRIMARY KEY,
            login    TEXT NOT NULL,
            expires  REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            ip         TEXT PRIMARY KEY,
            fail_count INTEGER NOT NULL,
            locked_until REAL NOT NULL
        )
        """
    )
    conn.commit()


def _load_expiry(token: str) -> float | None:
    """从 SQLite 读取 token 过期时间（带内存缓存加速）。"""
    cached = _cache.get(token)
    if cached is not None:
        return cached
    conn = get_conn()
    row = conn.execute(
        "SELECT expires FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    expiry = float(row["expires"])
    _cache[token] = expiry
    return expiry


def _client_ip(request: Request) -> str:
    """提取客户端真实 IP（Caddy 反代后从 X-Forwarded-For 取）。"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # 取最左侧第一个 IP（真实客户端）
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_locked(ip: str) -> bool:
    """检查 IP 是否处于锁定期。"""
    _ensure_sessions_table()
    conn = get_conn()
    row = conn.execute(
        "SELECT locked_until FROM login_attempts WHERE ip = ?", (ip,)
    ).fetchone()
    if row is None:
        return False
    return time.time() < float(row["locked_until"])


def _record_failure(ip: str) -> tuple[bool, int]:
    """记录一次失败。返回 (是否触发锁定, 剩余可尝试次数)。"""
    _ensure_sessions_table()
    conn = get_conn()
    now = time.time()
    row = conn.execute(
        "SELECT fail_count, locked_until FROM login_attempts WHERE ip = ?", (ip,)
    ).fetchone()

    if row is None:
        fail_count = 1
        conn.execute(
            "INSERT INTO login_attempts (ip, fail_count, locked_until) VALUES (?, ?, ?)",
            (ip, fail_count, 0.0),
        )
    else:
        fail_count = int(row["fail_count"]) + 1
        conn.execute(
            "UPDATE login_attempts SET fail_count = ? WHERE ip = ?",
            (fail_count, ip),
        )

    if fail_count >= MAX_FAILED_ATTEMPTS:
        # 触发锁定
        conn.execute(
            "UPDATE login_attempts SET locked_until = ? WHERE ip = ?",
            (now + LOCKOUT_SECONDS, ip),
        )
        conn.commit()
        return True, 0

    conn.commit()
    return False, MAX_FAILED_ATTEMPTS - fail_count


def _clear_failures(ip: str) -> None:
    """登录成功后清除该 IP 的失败记录。"""
    _ensure_sessions_table()
    conn = get_conn()
    conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
    conn.commit()


async def require_auth(request: Request) -> dict:
    """FastAPI 依赖：校验 jeff_token cookie。"""
    token = request.cookies.get("jeff_token", "")
    if not token:
        logger.warning(f"require_auth 拒绝：缺少 token (path={request.url.path})")
        raise HTTPException(status_code=401, detail="请先登录 /login")
    expiry = _load_expiry(token)
    if expiry is None or time.time() > expiry:
        if expiry is not None:
            # 已过期：从库和缓存中清理
            conn = get_conn()
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        _cache.pop(token, None)
        logger.warning(f"require_auth 拒绝：token 无效或已过期 (path={request.url.path})")
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"user": {"login": "admin"}}


@router.get("/api/auth/check")
async def auth_check(session: dict = Depends(require_auth)):
    """校验登录态：返回当前用户信息（供前端判断是否已登录）。"""
    return {"ok": True, "user": session["user"]}


@router.post("/api/login")
async def api_login(request: Request):
    """校验密码，设置 session cookie。"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    ip = _client_ip(request)

    # 检查是否处于锁定期
    if _is_locked(ip):
        logger.warning(f"登录拒绝：IP {ip} 已锁定")
        raise HTTPException(
            status_code=429,
            detail="尝试次数过多，请 1 小时后再试",
        )

    password = body.get("password", "")
    if password != ADMIN_PASSWORD:
        locked, remaining = _record_failure(ip)
        logger.warning(
            f"登录失败：密码错误 (ip={ip}, remaining={remaining}, locked={locked})"
        )
        if locked:
            raise HTTPException(
                status_code=429,
                detail="尝试次数过多，已锁定 1 小时",
            )
        raise HTTPException(
            status_code=401,
            detail=f"密码错误，还可尝试 {remaining} 次",
        )

    # 密码正确：清除失败记录
    _clear_failures(ip)

    token = hashlib.sha256(
        f"{ADMIN_PASSWORD}:{time.time()}:{os.urandom(16).hex()}".encode()
    ).hexdigest()
    _ensure_sessions_table()
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (token, login, expires) VALUES (?, ?, ?)",
        (token, "admin", time.time() + SESSION_MAX_AGE),
    )
    conn.commit()
    _cache[token] = time.time() + SESSION_MAX_AGE

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="jeff_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return response


LOGIN_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>登录 — Jeff 的工作台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f5f5f5}
.card{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);width:100%;max-width:360px}
h1{font-size:1.25rem;margin-bottom:1.5rem;text-align:center;color:#333}
input{width:100%;padding:.75rem;border:1px solid #ddd;border-radius:4px;font-size:1rem;margin-bottom:1rem}
input:focus{outline:none;border-color:#003087}
button{width:100%;padding:.75rem;background:#003087;color:#fff;border:none;border-radius:4px;font-size:1rem;cursor:pointer}
button:hover{background:#002266}
.error{color:#d32f2f;font-size:.875rem;margin-bottom:1rem;display:none;text-align:center}
</style>
</head>
<body>
<div class="card">
<h1>Jeff 的工作台</h1>
<form id="f">
<p class="error" id="err">密码错误，请重试</p>
<input type="password" id="pw" placeholder="请输入密码" autofocus>
<button type="submit">登录</button>
</form>
</div>
<script>
document.getElementById('f').addEventListener('submit',async e=>{
e.preventDefault();
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('pw').value})});
if(r.ok){window.location=new URLSearchParams(window.location.search).get('redirect')||'/'}
else{document.getElementById('err').style.display='block';document.getElementById('pw').value='';document.getElementById('pw').focus()}
});
</script>
</body>
</html>"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面。"""
    return HTMLResponse(LOGIN_PAGE_HTML)
