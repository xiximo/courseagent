# CourseAgent 服务器 Docker 部署

推荐用 **docker compose + Caddy**：Caddy 会向 Let's Encrypt（失败时自动试 ZeroSSL）申请**免费 HTTPS 证书**，并自动续期。

## 上线前检查

1. 域名 A 记录已指向服务器公网 IP（不要只配 CNAME 到未解析的地址）。
2. 云安全组 / 防火墙放行 **80** 和 **443**（申请证书必须能从公网访问 80）。
3. 服务器已安装 Docker 与 Compose v2（`docker compose version`）。
4. 宿主机上不要再占用 80/443（例如已有 nginx/apache 要先停掉或改端口）。
5. 若同时有 AAAA（IPv6）记录，服务器也必须能走 IPv6，否则申请证书会失败；不确定就先只留 A 记录。

## 1. 配置

在仓库的 `deploy/` 目录：

```bash
cp .env.example .env
cp backend.env.example backend.env
```

编辑 `.env`：

| 变量 | 说明 |
|------|------|
| `DOMAIN` | 已解析到本机的域名，不要带 `https://`。同时支持 www 时写成 `example.com, www.example.com` |
| `CORS_ORIGINS` | 浏览器访问地址，须带 `https://`，例如 `https://example.com` |
| `ACME_EMAIL` | 证书到期提醒邮箱 |
| `POSTGRES_PASSWORD` | 数据库密码 |
| `JWT_SECRET` | 随机长字符串，可用 `openssl rand -hex 32` |
| `EMBEDDING_MODELS_DIR` | 宿主机向量模型目录，默认 `./models`，挂到容器 `/app/models` |

编辑 `backend.env`：改掉 `INIT_ADMIN_PASSWORD`，填入 `DOUBAO_API_KEY` 等。

`DATABASE_URL` / `CORS_ORIGINS` / `JWT_SECRET` 由 compose 根据 `.env` 自动注入，一般不用在 `backend.env` 里再写。

## 2. 上传向量模型

镜像只含 torch 运行时，**模型文件不打进镜像**。把本机 `backend/models/bge-small-zh-v1.5` 整目录传到服务器：

```bash
scp -r backend/models/bge-small-zh-v1.5 root@你的服务器:/opt/courseagent/deploy/models/
```

目录说明见 `deploy/models/README.md`。应能读到 `deploy/models/bge-small-zh-v1.5/config.json`。换路径则改 `.env` 里的 `EMBEDDING_MODELS_DIR`。

## 3. 启动（服务器上构建）

把代码放到服务器后：

```bash
cd /opt/courseagent/deploy
docker compose up -d --build
docker compose ps
docker compose logs -f caddy
```

首次启动 Caddy 会申请证书，日志里出现 `certificate obtained successfully` 即成功。随后用浏览器打开：

`https://agent.rebuilder.com.cn`

默认管理员账号见 `backend.env` 的 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD`。

常用命令：

```bash
docker compose logs -f backend
docker compose restart backend
docker compose down          # 停服务，数据卷保留
```

数据卷：`courseagent-pg`（数据库）、`courseagent-data`（附件）、`caddy-data`（证书，勿删）。

## 4. Windows 本机构建再上传（服务器不编译）

Dockerfile 默认用本机已有镜像，**不会 pull**：`python:3.12-slim`、`node:22-alpine`、`nginx:latest`。

前端：

```powershell
docker build -t courseagent-web:latest .\webadmin
docker save -o deploy\dist\courseagent-web.tar courseagent-web:latest
```

后端（线上 embedding，含 torch，不含向量模型）：

```powershell
docker build -f backend\Dockerfile.ml -t courseagent-backend:ml .\backend
docker save -o deploy\dist\courseagent-backend-ml.tar courseagent-backend:ml
```

轻量后端（不开 embedding）：

```powershell
docker build -t courseagent-backend:latest .\backend
```

可选：只导出已构建镜像 `.\deploy\build-and-export.ps1 -Target web`

把 tar 拷到服务器后：

```bash
docker load -i courseagent-backend-ml.tar
docker load -i courseagent-web.tar
cd /opt/courseagent/deploy
docker compose up -d
```

compose 使用 `courseagent-backend:ml` 和 `courseagent-web:latest`。向量模型另传到 `deploy/models/`。

## 5. 证书说明（免费）

Caddy 默认使用 **Let's Encrypt**，拿不到时会再试 **ZeroSSL**，均为免费 DV 证书，约 90 天一签，Caddy 会自动续期。

申请失败常见原因：

- 域名还没指到这台机器，或指到了旧 IP
- 80 端口没放行，或被本机其它进程占用
- 只配了 IPv6 但机器不通 IPv6

查看：

```bash
docker compose logs caddy
```

证书缓存在 Docker 卷 `caddy-data` 中。换域名后执行 `docker compose restart caddy` 即可重新申请。

## 6. 使用已有 PostgreSQL

1. 在 `docker-compose.yml` 中删除（或注释）`postgres` 服务，以及 backend 的 `depends_on`。
2. 把已有数据库容器加入网络：`docker network connect courseagent <postgres容器名>`
3. 在 compose 的 backend `environment.DATABASE_URL` 中改成该容器名与真实密码。

若数据库只映射在宿主机 5432：

```yaml
environment:
  DATABASE_URL: postgresql+psycopg2://postgres:密码@host.docker.internal:5432/course
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## 7. 轻量镜像 vs 全量 ML

| 方案 | 适用 | 说明 |
|------|------|------|
| A. 轻量 Docker 后端 | 不要 RAG | `backend/Dockerfile`，`EMBEDDING_ENABLED=false` |
| B. 全量镜像 + 挂载模型 | 线上 embedding | `Dockerfile.ml`（含 torch）+ 宿主机 `models/bge-small-zh-v1.5` |

当前 compose 默认走方案 B。模型不进镜像，构建前建议 `.\deploy\download-ml-wheels.ps1` 预下载 Linux wheel，避免构建时拉 torch 超时。

## 8. 无 compose 的独立 `docker run`

仅当前端走 HTTP、或证书由外部网关处理时使用。数据库用已有 PostgreSQL 容器。

```bash
docker network create courseagent 2>/dev/null || true
docker network connect courseagent <你的postgres容器名>

docker run -d \
  --name courseagent-backend \
  --network courseagent \
  --restart unless-stopped \
  -v courseagent-data:/app/data \
  -v /opt/courseagent/deploy/models:/app/models:ro \
  --env-file /opt/courseagent/backend.env \
  courseagent-backend:ml

docker run -d \
  --name courseagent-web \
  --network courseagent \
  --restart unless-stopped \
  -p 80:80 \
  -e BACKEND_UPSTREAM=courseagent-backend:8080 \
  courseagent-web:latest
```

生产环境请用第 3 节的 Caddy，不要把 80 直接暴露给公网。
