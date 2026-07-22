"""Indexing service unit tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.db.models.attachment import Attachment, AttachmentParseStatus, TextChunk
from app.db.models.standard import Standard, StandardSyncStatus
from app.indexing.types import (
    EmbeddingBackendError,
    IndexChunksResult,
    SearchHit,
    SearchResult,
)
from app.indexing.service import IndexingService, maybe_auto_index_after_chunk


def _make_attachment(*, attachment_id: uuid.UUID | None = None) -> Attachment:
    return Attachment(
        id=attachment_id or uuid.uuid4(),
        standard_id=uuid.uuid4(),
        sprs_file_id=f"file-{uuid.uuid4().hex[:8]}",
        display_name="标准正文.pdf",
        file_type="pdf",
        storage_bucket="qibiao",
        storage_key="attachments/sample.pdf",
        parse_status=AttachmentParseStatus.parsed,
    )


def _make_chunk(attachment: Attachment, *, indexed: bool = False) -> TextChunk:
    return TextChunk(
        id=uuid.uuid4(),
        standard_id=attachment.standard_id,
        attachment_id=attachment.id,
        chunk_index=0,
        chunk_type="clause",
        doc_role="body",
        content="5.1.1 轻型汽车 指最大总质量不超过 3500 kg 的 M1 类车辆。",
        position_label="5.1.1",
        index_version=1,
        indexed_at=datetime.now(UTC) if indexed else None,
    )


def test_keyword_search_returns_matching_chunks() -> None:
    db = MagicMock()
    attachment = _make_attachment()
    chunk = _make_chunk(attachment)
    db.scalars.return_value.all.return_value = [chunk]

    hits = IndexingService(db).keyword_search_chunks("轻型汽车")

    assert len(hits) == 1
    assert hits[0].chunkId == str(chunk.id)
    assert hits[0].source == "keyword"


def test_index_attachment_requires_embedding_enabled() -> None:
    get_settings.cache_clear()
    db = MagicMock()
    import os

    os.environ["EMBEDDING_ENABLED"] = "false"
    get_settings.cache_clear()
    try:
        with pytest.raises(EmbeddingBackendError):
            IndexingService(db).index_attachment(uuid.uuid4())
    finally:
        os.environ.pop("EMBEDDING_ENABLED", None)
        get_settings.cache_clear()


@patch("app.indexing.service.index_chunks")
@patch("app.indexing.service.is_embedding_available", return_value=True)
def test_index_attachment_marks_chunks_indexed(
    _configured: MagicMock,
    index_backend: MagicMock,
) -> None:
    db = MagicMock()
    attachment = _make_attachment()
    chunk = _make_chunk(attachment)
    standard = Standard(
        id=attachment.standard_id,
        sprs_id="sprs-1",
        stand_type="national",
        standard_no="GB/T 12345",
        name="测试标准",
        sync_status=StandardSyncStatus.text_parsed,
    )

    db.get.side_effect = lambda model, key: {
        attachment.id: attachment,
        attachment.standard_id: standard,
    }.get(key)
    db.scalars.return_value.all.side_effect = [[chunk], [attachment]]
    db.scalar.side_effect = [1, 1, 1, 1]
    index_backend.return_value = IndexChunksResult(
        job_id="job-1",
        indexed_count=1,
        index_version=1,
        elapsed_sec=0.1,
    )

    count = IndexingService(db).index_attachment(attachment.id)

    assert count == 1
    assert chunk.indexed_at is not None
    assert standard.sync_status == StandardSyncStatus.index_updated
    db.commit.assert_called_once()


@patch("app.indexing.service.IndexingService.index_attachment")
@patch("app.indexing.service.is_embedding_available", return_value=True)
def test_maybe_auto_index_respects_flag(
    _configured: MagicMock,
    index_attachment: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("EMBEDDING_ENABLED", "true")
    monkeypatch.setenv("INDEX_AUTO_ON_CHUNK", "false")
    try:
        maybe_auto_index_after_chunk(MagicMock(), uuid.uuid4())
        index_attachment.assert_not_called()
    finally:
        get_settings.cache_clear()

    get_settings.cache_clear()
    monkeypatch.setenv("EMBEDDING_ENABLED", "true")
    monkeypatch.setenv("INDEX_AUTO_ON_CHUNK", "true")
    try:
        attachment_id = uuid.uuid4()
        maybe_auto_index_after_chunk(MagicMock(), attachment_id)
        index_attachment.assert_called_once_with(attachment_id)
    finally:
        get_settings.cache_clear()


@patch("app.indexing.service.semantic_search")
def test_hybrid_search_merges_keyword_and_semantic(semantic_backend: MagicMock) -> None:
    db = MagicMock()
    attachment = _make_attachment()
    keyword_chunk = _make_chunk(attachment)
    semantic_chunk_id = str(uuid.uuid4())

    db.scalars.return_value.all.return_value = [keyword_chunk]
    semantic_backend.return_value = SearchResult(
        query="测量",
        elapsed_sec=0.05,
        hits=[
            SearchHit(
                chunk_id=semantic_chunk_id,
                score=0.92,
                attachment_id=str(attachment.id),
                standard_id=str(attachment.standard_id),
                chunk_type="clause",
                doc_role="body",
                position_label="5.2.1",
                content="测量设备应经过计量检定。",
                index_version=1,
            )
        ],
    )

    result = IndexingService(db).hybrid_search_chunks("测量", top_k=10)

    assert result.mode == "hybrid"
    assert len(result.hits) == 2
    sources = {hit.source for hit in result.hits}
    assert sources == {"keyword", "semantic"}


@patch("app.indexing.service.semantic_search")
def test_hybrid_search_keeps_keyword_when_semantic_fails(
    semantic_backend: MagicMock,
) -> None:
    db = MagicMock()
    attachment = _make_attachment()
    keyword_chunk = _make_chunk(attachment)

    semantic_backend.side_effect = RuntimeError("milvus unavailable")
    db.scalars.return_value.all.return_value = [keyword_chunk]

    result = IndexingService(db).hybrid_search_chunks("干粉", top_k=5)

    assert result.mode == "hybrid"
    assert len(result.hits) == 1
    assert result.hits[0].source == "keyword"
