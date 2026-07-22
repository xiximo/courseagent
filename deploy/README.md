# CourseAgent 独立镜像部署（无 compose）

前后端各自构建、各自 `docker run`。数据库用服务器上**已有的 PostgreSQL 容器**。

## 推荐方案（避开 torch 卡住）

后端默认打 **轻量镜像**（无 torch / sentence-transformers），构建通常几分钟内完成。  
向量检索默认关闭（`EMBEDDING_ENABLED=false`），Agent 管理、会话、附件、LLM 对话等 API 可用；**知识库向量索引/RAG 检索**需再上全量镜像或服务器装 ML。

| 方案 | 适用 | 说明 |
|------|------|------|
| A. 轻量 Docker 后端 | 先上线 | `backend/Dockerfile`（默认） |
| B. 本机预下载 wheel 再打全量镜像 | 需要 RAG | `download-ml-wheels.ps1` + `Dockerfile.ml` |
| C. 服务器直接 venv 跑后端 | 完全不打后端镜像 | 见文末 |

## 1. 本机构建导出

```powershell
# 前端
.\deploy\build-and-export.ps1 -Target web

# 后端（轻量，推荐）
.\deploy\build-and-export.ps1 -Target backend
```

全量（含 embedding，易超时）：

```powershell
.\deploy\download-ml-wheels.ps1   # 可反复跑，断点续下
docker build -f backend/Dockerfile.ml -t courseagent-backend:latest .\backend
docker save -o deploy\dist\courseagent-backend-ml.tar courseagent-backend:latest
```

## 2. 服务器启动

```bash
docker network create courseagent 2>/dev/null || true
docker network connect courseagent <你的postgres容器名>

# 环境文件：从 backend/.env.docker.example 复制
# 轻量镜像务必保留 EMBEDDING_ENABLED=false（或显式写上）

docker load -i courseagent-backend-XXXX.tar
docker load -i courseagent-web-XXXX.tar

docker run -d \
  --name courseagent-backend \
  --network courseagent \
  --restart unless-stopped \
  -p 8080:8080 \
  -v courseagent-data:/app/data \
  --env-file /opt/courseagent/backend.env \
  courseagent-backend:latest

docker run -d \
  --name courseagent-web \
  --network courseagent \
  --restart unless-stopped \
  -p 80:80 \
  -e BACKEND_UPSTREAM=courseagent-backend:8080 \
  courseagent-web:latest
```

数据库若只映射宿主机 5432：

```bash
--add-host=host.docker.internal:host-gateway \
-e DATABASE_URL='postgresql+psycopg2://postgres:密码@host.docker.internal:5432/course'
```

## 3. 方案 C：服务器不用 Docker 跑后端

把 `backend` 目录拷到服务器后：

```bash
cd /opt/courseagent/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-api.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# 需要 RAG 时再: pip install -r requirements-ml.txt （同样可能较慢）
cp .env.docker.example .env   # 改 DATABASE_URL 等
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

前端仍用 `courseagent-web` 镜像，把 `BACKEND_UPSTREAM` 改成宿主机地址，例如：

```bash
-e BACKEND_UPSTREAM=172.17.0.1:8080
# 或
--add-host=host.docker.internal:host-gateway -e BACKEND_UPSTREAM=host.docker.internal:8080
```
