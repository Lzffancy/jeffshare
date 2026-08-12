"""Middleware auth — 密码认证 + require_auth 依赖

简单密码登录。ADMIN_PASSWORD 环境变量控制密码。
登录成功后设置 jeff_token cookie，后续请求通过 require_auth 校验。
"""
from __future__ import annotations

import hashlib
import os
import time

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
SESSION_MAX_AGE = 86400 * 7  # 7 天

router = APIRouter()

# 内存: token → expiry_timestamp
_tokens: dict[str, float] = {}


async def require_auth(request: Request) -> dict:
    """FastAPI 依赖：校验 jeff_token cookie.。"""
    token = request.cookies.get("jeff_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="请先登录 /login")
    expiry = _tokens.get(token)
    if expiry is None or time.time() > expiry:
        _tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"user": {"login": "admin"}}


@router.post("/api/login")
async def api_login(request: Request):
    """校验密码，设置 session cookie。"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    password = body.get("password", "")
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")

    token = hashlib.sha256(
        f"{ADMIN_PASSWORD}:{time.time()}:{os.urandom(16).hex()}".encode()
    ).hexdigest()
    _tokens[token] = time.time() + SESSION_MAX_AGE

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
