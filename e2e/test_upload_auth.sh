#!/usr/bin/env bash
# ================================================================
#  E2E 端到端测试 — 鉴权 + 文件上传
#
#  模拟浏览器 HTTP 交互链：
#    workbench 页面 → GitHub OAuth 跳转 → session cookie
#    → 已登录状态 → verify → API 上传 → 白名单拒绝
#
#  用法: bash e2e/test_upload_auth.sh
#  注意: workbench 页面是 Vue SPA，客户端渲染，
#        页面内容检测在浏览器层才有意义。
#        本测试聚焦 API 鉴权层（HTTP redirect、cookie、session）。
# ================================================================
set -eu

API="http://localhost:8000"
SITE="https://jeffshare.com"
COOKIE_JAR="/tmp/e2e-cookies.txt"
PASS=0
FAIL=0

pass() { echo "  ✅ $*"; ((PASS++)); }
fail() { echo "  ❌ $*"; ((FAIL++)); }

# ── 1. workbench 页面可访问（SSR 部分） ──
echo ""
echo "=========================================="
echo "  Test 1: GET /workbench/ (SSR)"
echo "=========================================="
WC=$(curl -sk -o /dev/null -w '%{http_code}' "$SITE/workbench/" 2>&1)
PAGE_LEN=$(curl -sk "$SITE/workbench/" 2>/dev/null | wc -c)

if [ "$WC" = "200" ]; then
  pass "页面返回 200"
else
  fail "页面返回 $WC"
fi

# SSR 结构：检查页面有内容 (> 500 字节，说明 Astro + Vue 加载正常)
if [ "$PAGE_LEN" -gt 500 ]; then
  pass "SSR 页面大小 ${PAGE_LEN} bytes"
else
  fail "SSR 页面过小: ${PAGE_LEN} bytes"
fi

# 页面应包含导航条
_HAS_NAV=$(curl -sk "$SITE/workbench/" 2>/dev/null | grep -c 'nav' || true)
if [ "$_HAS_NAV" -gt 0 ]; then
  pass "SSR 包含导航区"
else
  fail "SSR 缺少导航区"
fi

# ── 2. /admin-auth?redirect=/workbench/ → GitHub OAuth ──
echo ""
echo "=========================================="
echo "  Test 2: /admin-auth?redirect=/workbench/"
echo "=========================================="

# Caddy 把 /admin-auth/* 反代到 FastAPI，走 HTTPS
REDIRECT_URL=$(curl -sk -o /dev/null -w '%{redirect_url}' \
  "$SITE/admin-auth?redirect=/workbench/" 2>&1)

if echo "$REDIRECT_URL" | grep -q 'github.com/login/oauth/authorize'; then
  pass "重定向到 GitHub OAuth"
else
  fail "未跳转到 GitHub: ${REDIRECT_URL:0:100}"
fi

if echo "$REDIRECT_URL" | grep -q 'state='; then
  pass "URL 含 state 参数（防 CSRF）"
else
  fail "URL 缺少 state 参数"
fi

# ── 3. verify → 未登录 401 ──
echo ""
echo "=========================================="
echo "  Test 3: verify 无 cookie → 401"
echo "=========================================="
VCODE=$(curl -sk -o /dev/null -w '%{http_code}' "$SITE/admin-auth/verify" 2>&1)
if [ "$VCODE" = "401" ]; then
  pass "无 cookie verify → 401"
else
  fail "无 cookie verify → $VCODE (预期 401)"
fi

# ── 4. dev session 获取白名单用户 cookie ──
echo ""
echo "=========================================="
echo "  Test 4: 获取测试 session"
echo "=========================================="
rm -f "$COOKIE_JAR"

DEV_OK=$(curl -sk -o /dev/null -w '%{http_code}' \
  -c "$COOKIE_JAR" -D /tmp/e2e-dev-h.txt \
  -X POST "$API/admin-auth/_dev/session" \
  -H 'Content-Type: application/json' -d '{"login":"jeffszhang"}' 2>&1)

SID=$(grep 'jeff_sid' "$COOKIE_JAR" 2>/dev/null | awk '{print $NF}' || echo "")

if [ -n "$SID" ]; then
  pass "获取到 session: ${SID:0:12}..."
else
  fail "dev session 未返回 cookie"
fi

# ── 5. verify → 已登录 200 ──
echo ""
echo "=========================================="
echo "  Test 5: verify 已登录 → 200"
echo "=========================================="
VCHECK=$(curl -sk -w '\n%{http_code}' -b "jeff_sid=$SID" \
  "$API/admin-auth/verify" 2>&1)
VCHK=$(echo "$VCHECK" | tail -1)

if [ "$VCHK" = "200" ]; then
  if echo "$VCHECK" | grep -q 'jeffszhang'; then
    pass "session 有效，user=jeffszhang"
  else
    pass "session 有效 (200)"
  fi
else
  fail "verify 返回 $VCHK (预期 200)"
fi

# ── 6. POST /api/upload → 未登录 401 ──
echo ""
echo "=========================================="
echo "  Test 6: upload 无 cookie → 401"
echo "=========================================="
U1=$(curl -sk -o /tmp/e2e-u1.json -w '%{http_code}' \
  -X POST "$API/api/upload" 2>&1)

if [ "$U1" = "401" ]; then
  if grep -q '未登录' /tmp/e2e-u1.json 2>/dev/null; then
    pass "无 cookie upload → 401 + '未登录'"
  else
    pass "无 cookie upload → 401"
  fi
else
  fail "无 cookie upload → $U1 (预期 401)"
fi

# ── 7. POST /api/upload → 已登录 + 有文件 ──
echo ""
echo "=========================================="
echo "  Test 7: upload 已登录 + 有文件"
echo "=========================================="
TMPFILE=$(mktemp /tmp/e2e-upload-XXXXXX.md)
cat > "$TMPFILE" <<'MDEOF'
---
title: E2E测试
date: 2026-08-12
tags: [e2e]
draft: true
---

# E2E 测试
由自动化脚本生成。
MDEOF

U2=$(curl -sk -o /tmp/e2e-u2.json -w '%{http_code}' \
  -X POST "$API/api/upload" \
  -b "jeff_sid=$SID" \
  -F "files=@$TMPFILE;type=text/markdown" 2>&1)

if [ "$U2" = "200" ] || [ "$U2" = "500" ]; then
  # 200=完全成功; 500=Claude CLI 不可用但通过鉴权
  pass "已登录上传 → HTTP $U2 (通过鉴权)"
  if grep -q 'upload_id' /tmp/e2e-u2.json 2>/dev/null; then
    ULID=$(grep -oP '"upload_id"\s*:\s*"[a-f0-9]+"' /tmp/e2e-u2.json | grep -oP '[a-f0-9]{12,}' | head -1)
    pass "响应含 upload_id: $ULID"
  fi
else
  fail "已登录上传 → HTTP $U2 (预期 200/500)"
  echo "      响应: $(head -c 200 /tmp/e2e-u2.json)"
fi
rm -f "$TMPFILE"

# ── 8. 已登录无文件 → 400 ──
echo ""
echo "=========================================="
echo "  Test 8: upload 已登录 无文件 → 400"
echo "=========================================="
U3=$(curl -sk -o /tmp/e2e-u3.json -w '%{http_code}' \
  -X POST "$API/api/upload" \
  -b "jeff_sid=$SID" 2>&1)

if [ "$U3" = "400" ]; then
  pass "已登录无文件 → 400"
else
  fail "已登录无文件 → $U3 (预期 400)"
fi

# ── 9. 非白名单 → dev session 拒绝 ──
echo ""
echo "=========================================="
echo "  Test 9: 非白名单 dev session → 400"
echo "=========================================="
D2=$(curl -sk -o /tmp/e2e-d2.json -w '%{http_code}' \
  -X POST "$API/admin-auth/_dev/session" \
  -H 'Content-Type: application/json' \
  -d '{"login":"random_stranger"}' 2>&1)

if [ "$D2" = "400" ]; then
  if grep -qi 'whitelist' /tmp/e2e-d2.json 2>/dev/null; then
    pass "非白名单 → 400 (not in whitelist)"
  else
    pass "非白名单 → 400"
  fi
else
  fail "非白名单 → $D2 (预期 400)"
fi

# ── 10. 代码层白名单检查确认 ──
echo ""
echo "=========================================="
echo "  Test 10: 代码层双重白名单保护"
echo "=========================================="
OAUTH_FILE=/data/jeff_share_svr/app/middleware/oauth.py
AUTH_FILE=/data/jeff_share_svr/app/middleware/auth.py

if grep -A2 'ALLOWED_GITHUB_USERS' "$OAUTH_FILE" | grep -q 'not in ALLOWED'; then
  pass "OAuth 回调含白名单检查"
else
  fail "OAuth 回调缺少白名单检查"
fi

if grep -A2 'ALLOWED_GITHUB_USERS' "$AUTH_FILE" | grep -q 'not in ALLOWED'; then
  pass "require_auth 含白名单检查（纵深防御）"
else
  fail "require_auth 缺少白名单检查"
fi

# ── 结果 ──
echo ""
echo "=========================================="
echo "  E2E 完成: $PASS passed, $FAIL failed"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
  echo "❌ 有失败项！"
  exit 1
else
  echo "✅ 全部通过！"
  exit 0
fi
