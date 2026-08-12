#!/bin/bash
# run.sh — 构建 Playwright 镜像并运行 E2E 测试
#
# 用法:
#   ./run.sh                  # 运行全部测试
#   ./run.sh tests/smoke.spec.ts   # 指定测试文件
#   ./run.sh --grep "博客"    # 按名称过滤测试
#   BASE_URL=http://localhost ./run.sh   # 覆盖目标 URL
#
# 前提: 服务必须在宿主机上运行（Caddy :443 + FastAPI :8000）

set -euo pipefail
cd "$(dirname "$0")"

IMAGE="jeff-playwright"
BASE_URL="${BASE_URL:-https://localhost}"

echo "=== 构建 Playwright 镜像（首次需下载 Chromium ~177MB，约 2-3 分钟）==="
# 构建时用 --network host + 宿主机 Clash 代理加速 apt/npm/playwright 下载
docker build \
  --network host \
  --build-arg HTTP_PROXY=http://127.0.0.1:7890 \
  --build-arg HTTPS_PROXY=http://127.0.0.1:7890 \
  --build-arg http_proxy=http://127.0.0.1:7890 \
  --build-arg https_proxy=http://127.0.0.1:7890 \
  -t "$IMAGE" -f Dockerfile .

echo ""
echo "=== 运行 E2E 测试（目标: $BASE_URL）==="
exec docker run --rm \
  --network host \
  -v "$(pwd)/tests:/app/tests" \
  -v "$(pwd)/playwright.config.ts:/app/playwright.config.ts" \
  -v "$(pwd)/package.json:/app/package.json" \
  -v "$(pwd)/playwright-report:/app/playwright-report" \
  -v "$(pwd)/test-results:/app/test-results" \
  -w /app \
  -e "BASE_URL=$BASE_URL" \
  "$IMAGE" \
  npx playwright test "$@"
