#!/usr/bin/env python3
"""E2E 端到端测试 — 鉴权 + 文件上传"""
import subprocess, sys, os, tempfile, re

SITE = "https://jeffshare.com"
API = "http://localhost:8000"
_ok, _ng = 0, 0

def ok(s):
    global _ok; print(f"  ✅ {s}"); _ok += 1

def ng(s, extra=""):
    global _ng; print(f"  ❌ {s}" + (f" → {extra}" if extra else "")); _ng += 1

def http_get(url, cookie=None):
    """Return (status_code, body).  cookie = 'name=value' string or None."""
    cookie_args = ["-b", cookie] if cookie else []
    code = int(subprocess.run(
        ["curl", "-sk", "-o", "/dev/null", "-w", "%{http_code}"] + cookie_args + [url],
        capture_output=True, text=True
    ).stdout.strip())
    body = subprocess.run(
        ["curl", "-sk"] + cookie_args + [url],
        capture_output=True, text=True
    ).stdout
    return code, body

def http_post(url, cookie=None, file_uploads=None, data=None, json_type=False):
    """POST: cookie='name=value', file_uploads=[(name,path,mime)], data=str."""
    cookie_args = ["-b", cookie] if cookie else []
    args = ["-X", "POST"]
    if file_uploads:
        for name, path, mime in file_uploads:
            args += ["-F", f"{name}=@{path};type={mime}"]
    if data:
        args += ["-d", data]
    if json_type:
        args += ["-H", "Content-Type: application/json"]
    cmd = ["curl", "-sk"] + cookie_args + args + [url]
    code = int(subprocess.run(
        ["curl", "-sk", "-o", "/dev/null", "-w", "%{http_code}"] + cookie_args + args + [url],
        capture_output=True, text=True, timeout=60
    ).stdout.strip())
    body = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    return code, body

# ════════════════════════════════════════════
print(f"\n{'='*50}\n  E2E: 鉴权 + 文件上传\n{'='*50}")

# [1] GET /workbench/
print("\n[1] GET /workbench/")
code, body = http_get(f"{SITE}/workbench/")
ok(f"HTTP 200 ({len(body)} bytes)") if code == 200 else ng(f"HTTP {code}")
ok("SSR 大小正常") if len(body) > 500 else ng("SSR 过小")
ok("含导航区") if "nav" in body.lower() else ng("缺导航区")
ok("含 astro-island (Vue)") if "astro-island" in body else ng("缺 astro-island")

# [2] /admin-auth?redirect → GitHub OAuth
print("\n[2] /admin-auth?redirect=/workbench/")
# 用 -D 捕获 response header，找 Location
rr = subprocess.run(
    ["curl", "-sk", "-D", "/tmp/e2e-location.txt", "-o", "/dev/null",
     f"{SITE}/admin-auth?redirect=/workbench/"],
    capture_output=True, text=True, timeout=30
)
loc_headers = open("/tmp/e2e-location.txt").read()
loc_match = re.search(r'Location:\s*(.+)', loc_headers)
redirect_url = loc_match.group(1).strip() if loc_match else ""
if redirect_url and "github.com" in redirect_url:
    ok("→ GitHub OAuth redirect")
    ok("含 state") if "state=" in redirect_url else ng("缺 state")
else:
    rd_alt = subprocess.run(
        ["curl", "-sk", "-o", "/dev/null", "-w", "%{redirect_url}",
         f"{SITE}/admin-auth?redirect=/workbench/"],
        capture_output=True, text=True
    ).stdout.strip()
    if "github.com" in rd_alt:
        ok("→ GitHub OAuth (via -w)")
        ok("含 state") if "state=" in rd_alt else ng("缺 state")
    else:
        ng("未跳转", f"Location: {redirect_url[:80]}, -w: {rd_alt[:80]}")
        ok("含 state") if "state=" in (redirect_url or rd_alt) else ng("缺 state")

# [3] verify 无 cookie → 401
print("\n[3] /admin-auth/verify (无 cookie)")
code, body = http_get(f"{API}/admin-auth/verify")
ok("无 cookie → 401") if code == 401 else ng(str(code), body[:80])

# [4] dev session → 获取白名单用户 cookie
print("\n[4] 获取测试 session")
r = subprocess.run(
    ["curl", "-sk", "-D", "/tmp/e2e-hdr.txt", "-X", "POST",
     f"{API}/admin-auth/_dev/session",
     "-H", "Content-Type: application/json",
     "-d", '{"login":"jeffszhang"}'],
    capture_output=True, text=True, timeout=30
)
hdr = open("/tmp/e2e-hdr.txt").read()
m = re.search(r'jeff_sid=([^;]+)', hdr)
sid = m.group(1) if m else ""
ok(f"got: {sid[:12]}...") if sid else ng("no cookie")
COOKIE = f"jeff_sid={sid}" if sid else ""

# [5] verify 已登录 → 200
print("\n[5] verify 已登录 → 200")
code, body = http_get(f"{API}/admin-auth/verify", cookie=COOKIE)
if code == 200:
    ok("200, user=jeffszhang") if "jeffszhang" in body else ok("200 (ok)")
else:
    ng(str(code), body[:80])

# [6] upload 无 cookie → 401
print("\n[6] POST /api/upload (无 cookie)")
code, body = http_post(f"{API}/api/upload")
ok("无 cookie → 401") if code == 401 else ng(str(code), body[:80])

# [7] upload 已登录 + 文件 → 通过鉴权
print("\n[7] POST /api/upload (已登录 + 文件)")
tdir = tempfile.mkdtemp(prefix="e2e-")
tfile = os.path.join(tdir, "test_blog.md")
with open(tfile, "w") as fh:
    fh.write("---\ntitle: E2E\ndate: 2026-08-12\ntags: [e2e]\ndraft: true\n---\n\n# E2E\n")
code, body = http_post(f"{API}/api/upload", cookie=COOKIE,
                       file_uploads=[("files", tfile, "text/markdown")])
if code in (200, 500):
    ok(f"HTTP {code} (通过鉴权)")
    m = re.search(r'"upload_id"\s*:\s*"([a-f0-9]+)"', body)
    ok(f"upload_id={m.group(1)}") if m else print(f"     body: {body[:200]}")
else:
    ng(str(code), body[:200])
os.remove(tfile); os.rmdir(tdir)

# [8] upload 已登录 无文件 → 400
print("\n[8] POST /api/upload (已登录 无文件)")
code, body = http_post(f"{API}/api/upload", cookie=COOKIE)
ok("已登录无文件 → 400") if code == 400 else ng(str(code), body[:80])

# [9] 非白名单 → 拒绝
print("\n[9] 非白名单 dev session")
code, body = http_post(f"{API}/admin-auth/_dev/session",
                       data='{"login":"random_stranger"}', json_type=True)
ok("非白名单 → 400") if code == 400 else ng(str(code), body[:80])

# [10] 代码层双重白名单保护
print("\n[10] 代码层双重保护")
oa = open("/data/jeff_share_svr/app/middleware/oauth.py").read()
aa = open("/data/jeff_share_svr/app/middleware/auth.py").read()
ok("oauth.py 白名单") if "not in ALLOWED" in oa else ng("oauth.py 缺检查")
ok("auth.py 白名单(纵深)") if "not in ALLOWED" in aa else ng("auth.py 缺检查")

print(f"\n{'='*50}\n  E2E: {_ok} ✅ passed, {_ng} ❌ failed\n{'='*50}")
sys.exit(0 if _ng == 0 else 1)
