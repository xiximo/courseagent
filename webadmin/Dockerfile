ARG NODE_IMAGE=docker.1ms.run/library/node:22-bookworm-slim
ARG NGINX_IMAGE=docker.1ms.run/library/nginx:1.27-alpine

FROM ${NODE_IMAGE} AS build

WORKDIR /app

RUN npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM ${NGINX_IMAGE}

ENV BACKEND_UPSTREAM=courseagent-backend:8080

# 官方 nginx 镜像会把 templates/*.template 经 envsubst 写入 conf.d/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
