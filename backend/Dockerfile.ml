# 全量后端（含 torch + 本地 embedding 模型）
# 推荐先跑: .\deploy\download-ml-wheels.ps1 再构建
ARG PYTHON_IMAGE=docker.1ms.run/library/python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    EMBEDDING_ENABLED=true \
    EMBEDDING_MODEL=models/bge-small-zh-v1.5

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt requirements-ml.txt ./
COPY wheels/ /wheels/

# 用 find-links 解析依赖，不要一次性 pip install *.whl（会撞上多版本冲突）
RUN set -eux; \
    CPU_TORCH="$(ls /wheels/torch-*+cpu*.whl 2>/dev/null | head -n 1 || true)"; \
    if [ -n "$CPU_TORCH" ]; then \
      pip install --default-timeout=1000 --no-index --find-links=/wheels "$CPU_TORCH"; \
    else \
      pip install --default-timeout=1000 torch --index-url https://download.pytorch.org/whl/cpu \
        || pip install --default-timeout=1000 torch; \
    fi; \
    if ls /wheels/*.whl >/dev/null 2>&1; then \
      pip install --default-timeout=1000 --find-links=/wheels --prefer-binary -r requirements-ml.txt; \
    else \
      pip install --default-timeout=1000 -r requirements-ml.txt; \
    fi

COPY app ./app
COPY models ./models
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

RUN mkdir -p /app/data/attachments /app/data/vector_index

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
