from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndexChunkPayload:
    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexChunksResult:
    job_id: str
    indexed_count: int
    index_version: int
    elapsed_sec: float


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    score: float | None
    attachment_id: str | None
    standard_id: str | None
    chunk_type: str | None
    doc_role: str | None
    position_label: str | None
    content: str | None
    index_version: int | None


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: list[SearchHit]
    elapsed_sec: float


class EmbeddingBackendError(RuntimeError):
    pass


# 兼容旧命名
EmbeddingWorkerError = EmbeddingBackendError
