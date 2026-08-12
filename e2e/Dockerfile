# Jeff 工作台 — Playwright E2E 测试镜像
# 基于 node:20 (Debian)，不能用 Alpine，因为 Playwright Chromium 需要 glibc
FROM node:20

# 支持通过 --build-arg 注入代理（加速 apt/npm/playwright 下载）
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ARG NO_PROXY
ARG no_proxy
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    NO_PROXY=${NO_PROXY} \
    no_proxy=${no_proxy}

WORKDIR /app

# 先复制依赖清单，利用 Docker 层缓存
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install

# 配置 apt 代理（apt 不认 HTTP_PROXY 环境变量，需要写 apt.conf.d）
RUN if [ -n "${HTTP_PROXY}" ]; then \
      echo "Acquire::http::Proxy \"${HTTP_PROXY}\";" > /etc/apt/apt.conf.d/99proxy ; \
      echo "Acquire::https::Proxy \"${HTTPS_PROXY}\";" >> /etc/apt/apt.conf.d/99proxy ; \
      echo "[apt proxy] ${HTTP_PROXY}" ; \
    fi

# 安装 Chromium 所需的系统依赖（libatk, libnss 等 .deb 包）
RUN npx playwright install-deps chromium

# 下载 Chromium 浏览器（~177MB，烤进镜像避免每次下载）
RUN npx playwright install chromium

# 复制测试文件
COPY . .

CMD ["npx", "playwright", "test"]
