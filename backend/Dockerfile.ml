# 全量后端（含 CPU torch / sentence-transformers）
# 只用本机已有的 python:3.12-slim，不拉 docker/dockerfile 前端镜像
# builder 里的 wheels 不会进入最终镜像
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /app

COPY requirements-api.txt requirements-ml.txt ./
COPY wheels/ /wheels/

RUN set -eux; \
    CPU_TORCH="$(ls /wheels/torch-*+cpu*.whl 2>/dev/null | head -n 1 || true)"; \
    if [ -n "$CPU_TORCH" ]; then \
      pip install --default-timeout=1000 --no-index --find-links=/wheels "$CPU_TORCH"; \
    else \
      pip install --default-timeout=1000 torch --index-url https://download.pytorch.org/whl/cpu; \
    fi; \
    if ls /wheels/*.whl >/dev/null 2>&1; then \
      pip install --default-timeout=1000 --find-links=/wheels --prefer-binary \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements-ml.txt; \
    else \
      pip install --default-timeout=1000 \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements-ml.txt; \
    fi; \
    rm -rf /wheels

FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    EMBEDDING_ENABLED=true \
    EMBEDDING_MODEL=models/bge-small-zh-v1.5

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

RUN mkdir -p /app/data/attachments /app/data/vector_index /app/models \
    && ldconfig

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
