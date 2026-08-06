# Jeff 工作台 — Astro 构建镜像
# 依赖一次性烤进镜像，运行时直接用，免去每次 npm install
FROM node:20-alpine

WORKDIR /app

# 先只复制依赖清单，利用 Docker 层缓存
COPY package.json package-lock.json .npmrc ./

# 用 lockfile 确定性安装（与宿主机同版本）
RUN npm ci --no-audit --no-fund

# 入口：默认执行构建；挂载源码后由 jeff-build 调用
CMD ["npm", "run", "build"]
