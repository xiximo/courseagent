"""Embedding 引擎（sentence-transformers）。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sentence_transformers import SentenceTransformer

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_HF_MODEL = "BAAI/bge-small-zh-v1.5"
_DEFAULT_LOCAL_MODEL = _BACKEND_ROOT / "models" / "bge-small-zh-v1.5"


def resolve_embedding_model_path(model_name: str) -> tuple[str, bool]:
    """解析模型路径；若本机目录存在则优先离线加载。"""
    raw = (model_name or "").strip() or _DEFAULT_HF_MODEL
    candidate = Path(raw)

    if candidate.is_dir():
        return str(candidate.resolve()), True

    if not candidate.is_absolute():
        relative = (_BACKEND_ROOT / raw).resolve()
        if relative.is_dir():
            return str(relative), True

    if raw in {_DEFAULT_HF_MODEL, "bge-small-zh-v1.5"} and _DEFAULT_LOCAL_MODEL.is_dir():
        return str(_DEFAULT_LOCAL_MODEL.resolve()), True

    return raw, False


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str) -> SentenceTransformer:
    resolved, is_local = resolve_embedding_model_path(model_name)
    if is_local:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        return SentenceTransformer(
            resolved,
            model_kwargs={"local_files_only": True},
            tokenizer_kwargs={"local_files_only": True},
        )
    return SentenceTransformer(resolved)


def embed_texts(texts: list[str], *, model_name: str) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model(model_name)
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embedding_dimension(model_name: str) -> int:
    model = get_embedding_model(model_name)
    if hasattr(model, "get_embedding_dimension"):
        return int(model.get_embedding_dimension())
    return int(model.get_sentence_embedding_dimension())
