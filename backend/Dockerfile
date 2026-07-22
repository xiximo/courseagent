# 轻量后端镜像：不含 torch / sentence-transformers，构建快、不易卡死
# 向量检索默认关闭（EMBEDDING_ENABLED=false）；需要 RAG 时用 Dockerfile.ml 或服务器单独装 ML 依赖
ARG PYTHON_IMAGE=docker.1ms.run/library/python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    EMBEDDING_ENABLED=false \
    EMBEDDING_MODE=inline

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --default-timeout=300 -r requirements-api.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

RUN mkdir -p /app/data/attachments /app/data/vector_index

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
