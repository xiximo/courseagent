"""向量索引后端门面：inline（进程内）或 worker（HTTP）。"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.indexing.types import (
    EmbeddingBackendError,
    EmbeddingWorkerError,
    IndexChunkPayload,
    IndexChunksResult,
    SearchHit,
    SearchResult,
)

__all__ = [
    "EmbeddingBackendError",
    "EmbeddingWorkerError",
    "IndexChunkPayload",
    "IndexChunksResult",
    "SearchHit",
    "SearchResult",
    "delete_attachment_index",
    "delete_attachment_index_via_worker",
    "index_chunks",
    "index_chunks_via_worker",
    "is_embedding_available",
    "is_embedding_worker_configured",
    "semantic_search",
    "semantic_search_via_worker",
]


def is_embedding_available() -> bool:
    settings = get_settings()
    if not settings.embedding_enabled:
        return False
    if settings.embedding_mode == "worker":
        return bool(settings.embedding_worker_url)
    return True


def is_embedding_worker_configured() -> bool:
    """兼容旧接口。"""
    return is_embedding_available()


def index_chunks(
    *,
    standard_id: str,
    attachment_id: str,
    index_version: int,
    chunks: list[IndexChunkPayload],
    job_id: str | None = None,
) -> IndexChunksResult:
    settings = get_settings()
    if not is_embedding_available():
        raise EmbeddingBackendError("向量索引未启用，请设置 EMBEDDING_ENABLED=true")
    if settings.embedding_mode == "worker":
        return _index_chunks_via_http(
            standard_id=standard_id,
            attachment_id=attachment_id,
            index_version=index_version,
            chunks=chunks,
            job_id=job_id,
        )
    from app.indexing.inline_backend import index_chunks_inline

    return index_chunks_inline(
        standard_id=standard_id,
        attachment_id=attachment_id,
        index_version=index_version,
        chunks=chunks,
        job_id=job_id,
    )


def index_chunks_via_worker(
    *,
    standard_id: str,
    attachment_id: str,
    index_version: int,
    chunks: list[IndexChunkPayload],
    job_id: str | None = None,
) -> IndexChunksResult:
    """兼容旧接口。"""
    return index_chunks(
        standard_id=standard_id,
        attachment_id=attachment_id,
        index_version=index_version,
        chunks=chunks,
        job_id=job_id,
    )


def delete_attachment_index(attachment_id: str) -> int:
    settings = get_settings()
    if not is_embedding_available():
        raise EmbeddingBackendError("向量索引未启用")
    if settings.embedding_mode == "worker":
        return _delete_attachment_index_via_http(attachment_id)
    from app.indexing.inline_backend import delete_attachment_index_inline

    return delete_attachment_index_inline(attachment_id)


def delete_attachment_index_via_worker(attachment_id: str) -> int:
    """兼容旧接口。"""
    return delete_attachment_index(attachment_id)


def semantic_search(
    query: str,
    *,
    top_k: int = 10,
    standard_id: str | None = None,
    attachment_id: str | None = None,
    chunk_type: str | None = None,
    doc_role: str | None = None,
) -> SearchResult:
    settings = get_settings()
    if not is_embedding_available():
        raise EmbeddingBackendError("向量索引未启用")
    if settings.embedding_mode == "worker":
        return _semantic_search_via_http(
            query,
            top_k=top_k,
            standard_id=standard_id,
            attachment_id=attachment_id,
            chunk_type=chunk_type,
            doc_role=doc_role,
        )
    from app.indexing.inline_backend import semantic_search_inline

    return semantic_search_inline(
        query,
        top_k=top_k,
        standard_id=standard_id,
        attachment_id=attachment_id,
        chunk_type=chunk_type,
        doc_role=doc_role,
    )


def semantic_search_via_worker(
    query: str,
    *,
    top_k: int = 10,
    standard_id: str | None = None,
    attachment_id: str | None = None,
    chunk_type: str | None = None,
    doc_role: str | None = None,
) -> SearchResult:
    """兼容旧接口。"""
    return semantic_search(
        query,
        top_k=top_k,
        standard_id=standard_id,
        attachment_id=attachment_id,
        chunk_type=chunk_type,
        doc_role=doc_role,
    )


def _index_chunks_via_http(
    *,
    standard_id: str,
    attachment_id: str,
    index_version: int,
    chunks: list[IndexChunkPayload],
    job_id: str | None = None,
) -> IndexChunksResult:
    settings = get_settings()
    if not chunks:
        raise EmbeddingBackendError("没有可索引的切片")

    base_url = settings.embedding_worker_url.rstrip("/")
    headers = _worker_headers()
    payload = {
        "job_id": job_id,
        "standard_id": standard_id,
        "attachment_id": attachment_id,
        "index_version": index_version,
        "chunks": [
            {
                "chunk_id": item.chunk_id,
                "content": item.content,
                "metadata": item.metadata,
            }
            for item in chunks
        ],
    }

    try:
        with httpx.Client(
            timeout=settings.embedding_worker_timeout_seconds,
            trust_env=False,
        ) as client:
            response = client.post(
                f"{base_url}/v1/index/chunks",
                json=payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise EmbeddingBackendError(
            f"Embedding worker 超时（>{settings.embedding_worker_timeout_seconds}s）"
        ) from exc
    except httpx.HTTPError as exc:
        raise EmbeddingBackendError(f"Embedding worker 连接失败: {exc}") from exc

    if response.status_code >= 400:
        raise EmbeddingBackendError(
            f"Embedding worker 返回错误 ({response.status_code}): {_extract_error_detail(response)}"
        )

    body = response.json()
    return IndexChunksResult(
        job_id=str(body.get("job_id") or ""),
        indexed_count=int(body.get("indexed_count") or 0),
        index_version=int(body.get("index_version") or index_version),
        elapsed_sec=float(body.get("elapsed_sec") or 0.0),
    )


def _delete_attachment_index_via_http(attachment_id: str) -> int:
    settings = get_settings()
    base_url = settings.embedding_worker_url.rstrip("/")
    headers = _worker_headers()

    try:
        with httpx.Client(
            timeout=settings.embedding_worker_timeout_seconds,
            trust_env=False,
        ) as client:
            response = client.delete(
                f"{base_url}/v1/index/attachments/{attachment_id}",
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise EmbeddingBackendError(f"Embedding worker 连接失败: {exc}") from exc

    if response.status_code >= 400:
        raise EmbeddingBackendError(
            f"Embedding worker 返回错误 ({response.status_code}): {_extract_error_detail(response)}"
        )

    body = response.json()
    return int(body.get("deleted_count") or 0)


def _semantic_search_via_http(
    query: str,
    *,
    top_k: int = 10,
    standard_id: str | None = None,
    attachment_id: str | None = None,
    chunk_type: str | None = None,
    doc_role: str | None = None,
) -> SearchResult:
    settings = get_settings()
    base_url = settings.embedding_worker_url.rstrip("/")
    headers = _worker_headers()
    payload = {
        "query": query,
        "top_k": top_k,
        "standard_id": standard_id,
        "attachment_id": attachment_id,
        "chunk_type": chunk_type,
        "doc_role": doc_role,
    }

    try:
        with httpx.Client(
            timeout=settings.embedding_worker_timeout_seconds,
            trust_env=False,
        ) as client:
            response = client.post(
                f"{base_url}/v1/search",
                json=payload,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise EmbeddingBackendError(f"Embedding worker 连接失败: {exc}") from exc

    if response.status_code >= 400:
        raise EmbeddingBackendError(
            f"Embedding worker 返回错误 ({response.status_code}): {_extract_error_detail(response)}"
        )

    body = response.json()
    hits = [
        SearchHit(
            chunk_id=str(item.get("chunk_id") or ""),
            score=item.get("score"),
            attachment_id=item.get("attachment_id"),
            standard_id=item.get("standard_id"),
            chunk_type=item.get("chunk_type"),
            doc_role=item.get("doc_role"),
            position_label=item.get("position_label"),
            content=item.get("content"),
            index_version=item.get("index_version"),
        )
        for item in body.get("hits", [])
    ]
    return SearchResult(
        query=str(body.get("query") or query),
        hits=hits,
        elapsed_sec=float(body.get("elapsed_sec") or 0.0),
    )


def _worker_headers() -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.embedding_worker_token:
        headers["X-Worker-Token"] = settings.embedding_worker_token
    return headers


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    detail = payload.get("detail", response.text)
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)
