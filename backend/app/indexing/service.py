from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.attachment import Attachment, AttachmentParseStatus, TextChunk
from app.db.models.standard import Standard, StandardSyncStatus
from app.indexing.embedding_client import (
    EmbeddingBackendError,
    IndexChunkPayload,
    SearchHit,
    delete_attachment_index,
    index_chunks,
    is_embedding_available,
    semantic_search,
)
from app.schemas.indexing import ChunkSearchHitDto, ChunkSearchResultDto

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def index_attachment(self, attachment_id: uuid.UUID) -> int:
        if not is_embedding_available():
            raise EmbeddingBackendError(
                "向量索引未启用，请设置 EMBEDDING_ENABLED=true"
            )

        attachment = self._get_attachment(attachment_id)
        chunks = self.db.scalars(
            select(TextChunk)
            .where(TextChunk.attachment_id == attachment.id)
            .order_by(TextChunk.chunk_index)
        ).all()
        if not chunks:
            raise ValueError("附件尚未完成结构切片，无法建立向量索引")

        index_version = max(chunk.index_version for chunk in chunks)
        payloads = [
            IndexChunkPayload(
                chunk_id=str(chunk.id),
                content=chunk.content,
                metadata={
                    "chunk_type": chunk.chunk_type,
                    "doc_role": chunk.doc_role,
                    "position_label": chunk.position_label or "",
                    "parent_label": chunk.parent_label or "",
                    "chunk_index": chunk.chunk_index,
                },
            )
            for chunk in chunks
        ]

        result = index_chunks(
            standard_id=str(attachment.standard_id),
            attachment_id=str(attachment.id),
            index_version=index_version,
            chunks=payloads,
        )

        now = datetime.now(UTC)
        for chunk in chunks:
            chunk.embedding_id = str(chunk.id)
            chunk.indexed_at = now

        self._refresh_standard_sync_status(attachment.standard_id)
        self.db.commit()
        return result.indexed_count

    def keyword_search_chunks(
        self,
        query: str,
        *,
        standard_id: uuid.UUID | None = None,
        attachment_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        doc_role: str | None = None,
        top_k: int = 10,
    ) -> list[ChunkSearchHitDto]:
        keyword = query.strip()
        if not keyword:
            return []

        stmt = select(TextChunk).where(TextChunk.content.ilike(f"%{keyword}%"))
        if standard_id:
            stmt = stmt.where(TextChunk.standard_id == standard_id)
        if attachment_id:
            stmt = stmt.where(TextChunk.attachment_id == attachment_id)
        if chunk_type:
            stmt = stmt.where(TextChunk.chunk_type == chunk_type)
        if doc_role:
            stmt = stmt.where(TextChunk.doc_role == doc_role)

        rows = self.db.scalars(stmt.order_by(TextChunk.chunk_index).limit(top_k)).all()
        return self._enrich_hits_from_db([self._to_keyword_hit(row) for row in rows])

    def semantic_search_chunks(
        self,
        query: str,
        *,
        standard_id: uuid.UUID | None = None,
        attachment_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        doc_role: str | None = None,
        top_k: int = 10,
    ) -> ChunkSearchResultDto:
        result = semantic_search(
            query,
            top_k=top_k,
            standard_id=str(standard_id) if standard_id else None,
            attachment_id=str(attachment_id) if attachment_id else None,
            chunk_type=chunk_type,
            doc_role=doc_role,
        )
        hits = self._enrich_hits_from_db(
            [self._to_semantic_hit(item) for item in result.hits]
        )
        return ChunkSearchResultDto(
            query=result.query,
            mode="semantic",
            elapsedSec=result.elapsed_sec,
            hits=hits,
        )

    def hybrid_search_chunks(
        self,
        query: str,
        *,
        standard_id: uuid.UUID | None = None,
        attachment_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        doc_role: str | None = None,
        top_k: int = 10,
    ) -> ChunkSearchResultDto:
        semantic_hits: list[ChunkSearchHitDto] = []
        elapsed_sec = 0.0
        try:
            semantic = self.semantic_search_chunks(
                query,
                standard_id=standard_id,
                attachment_id=attachment_id,
                chunk_type=chunk_type,
                doc_role=doc_role,
                top_k=top_k,
            )
            semantic_hits = semantic.hits
            elapsed_sec = semantic.elapsedSec or 0.0
        except Exception as exc:
            logger.warning(
                "Hybrid semantic leg failed, continuing with keyword leg: %s",
                exc,
                exc_info=True,
            )

        keyword_hits = self.keyword_search_chunks(
            query,
            standard_id=standard_id,
            attachment_id=attachment_id,
            chunk_type=chunk_type,
            doc_role=doc_role,
            top_k=top_k,
        )

        merged: dict[str, ChunkSearchHitDto] = {}
        for hit in semantic_hits:
            merged[hit.chunkId] = hit
        for hit in keyword_hits:
            if hit.chunkId not in merged:
                merged[hit.chunkId] = hit

        hits = self._enrich_hits_from_db(list(merged.values())[:top_k])
        return ChunkSearchResultDto(
            query=query.strip(),
            mode="hybrid",
            elapsedSec=elapsed_sec,
            hits=hits,
        )

    def delete_attachment_index(self, attachment_id: uuid.UUID) -> int:
        if not is_embedding_available():
            return 0
        attachment = self._get_attachment(attachment_id)
        deleted = delete_attachment_index(str(attachment.id))
        rows = self.db.scalars(
            select(TextChunk).where(TextChunk.attachment_id == attachment.id)
        ).all()
        for row in rows:
            row.indexed_at = None
        self._refresh_standard_sync_status(attachment.standard_id)
        self.db.commit()
        return deleted

    def index_all_for_standard(self, standard_id: uuid.UUID) -> int:
        attachments = self.db.scalars(
            select(Attachment).where(
                Attachment.standard_id == standard_id,
                Attachment.parse_status == AttachmentParseStatus.parsed,
            )
        ).all()

        total = 0
        for attachment in attachments:
            chunk_count = self.db.scalar(
                select(func.count())
                .select_from(TextChunk)
                .where(TextChunk.attachment_id == attachment.id)
            ) or 0
            if chunk_count <= 0:
                continue
            try:
                total += self.index_attachment(attachment.id)
            except Exception:
                continue
        return total

    def _get_attachment(self, attachment_id: uuid.UUID) -> Attachment:
        attachment = self.db.get(Attachment, attachment_id)
        if attachment is None:
            raise ValueError("附件不存在")
        return attachment

    def _refresh_standard_sync_status(self, standard_id: uuid.UUID) -> None:
        standard = self.db.get(Standard, standard_id)
        if standard is None:
            return

        attachments = self.db.scalars(
            select(Attachment).where(Attachment.standard_id == standard_id)
        ).all()
        if not attachments:
            return

        parsed_count = sum(
            1 for item in attachments if item.parse_status == AttachmentParseStatus.parsed
        )
        if parsed_count <= 0:
            return

        standard.sync_status = StandardSyncStatus.text_parsed

        attachment_ids = [item.id for item in attachments]
        chunk_total = self.db.scalar(
            select(func.count())
            .select_from(TextChunk)
            .where(TextChunk.standard_id == standard_id)
        ) or 0
        indexed_total = self.db.scalar(
            select(func.count())
            .select_from(TextChunk)
            .where(
                TextChunk.standard_id == standard_id,
                TextChunk.indexed_at.is_not(None),
            )
        ) or 0

        attachments_with_chunks = self.db.scalar(
            select(func.count(func.distinct(TextChunk.attachment_id))).where(
                TextChunk.attachment_id.in_(attachment_ids)
            )
        ) or 0

        attachments_indexed = self.db.scalar(
            select(func.count(func.distinct(TextChunk.attachment_id))).where(
                TextChunk.attachment_id.in_(attachment_ids),
                TextChunk.indexed_at.is_not(None),
            )
        ) or 0

        if (
            chunk_total > 0
            and indexed_total == chunk_total
            and attachments_with_chunks > 0
            and attachments_indexed == attachments_with_chunks
        ):
            standard.sync_status = StandardSyncStatus.index_updated

    @staticmethod
    def _to_keyword_hit(row: TextChunk) -> ChunkSearchHitDto:
        return ChunkSearchHitDto(
            chunkId=str(row.id),
            attachmentId=str(row.attachment_id),
            standardId=str(row.standard_id),
            chunkType=row.chunk_type,
            docRole=row.doc_role,
            positionLabel=row.position_label,
            content=row.content,
            score=None,
            source="keyword",
        )

    @staticmethod
    def _to_semantic_hit(item: SearchHit) -> ChunkSearchHitDto:
        return ChunkSearchHitDto(
            chunkId=item.chunk_id,
            attachmentId=item.attachment_id or "",
            standardId=item.standard_id or "",
            chunkType=item.chunk_type,
            docRole=item.doc_role,
            positionLabel=item.position_label,
            content=item.content,
            score=item.score,
            source="semantic",
        )

    def _enrich_hits_from_db(
        self,
        hits: list[ChunkSearchHitDto],
    ) -> list[ChunkSearchHitDto]:
        if not hits:
            return hits

        chunk_ids: list[uuid.UUID] = []
        for hit in hits:
            try:
                chunk_ids.append(uuid.UUID(hit.chunkId))
            except ValueError:
                continue
        if not chunk_ids:
            return hits

        rows = self.db.scalars(
            select(TextChunk).where(TextChunk.id.in_(chunk_ids))
        ).all()
        row_map = {str(row.id): row for row in rows}

        attachment_ids = {row.attachment_id for row in rows}
        if not attachment_ids:
            attachment_ids = {
                uuid.UUID(hit.attachmentId)
                for hit in hits
                if hit.attachmentId
            }
        attachment_names: dict[str, str] = {}
        if attachment_ids:
            attachments = self.db.scalars(
                select(Attachment).where(Attachment.id.in_(attachment_ids))
            ).all()
            attachment_names = {
                str(item.id): item.display_name or item.sprs_file_id or "未知文件"
                for item in attachments
            }

        enriched: list[ChunkSearchHitDto] = []
        for hit in hits:
            row = row_map.get(hit.chunkId)
            if row is None:
                file_name = attachment_names.get(hit.attachmentId)
                enriched.append(
                    hit.model_copy(update={"fileName": file_name or hit.fileName})
                )
                continue
            attachment_id = str(row.attachment_id)
            enriched.append(
                ChunkSearchHitDto(
                    chunkId=hit.chunkId,
                    attachmentId=attachment_id,
                    standardId=str(row.standard_id),
                    fileName=attachment_names.get(attachment_id),
                    chunkType=row.chunk_type,
                    docRole=row.doc_role,
                    positionLabel=row.position_label or hit.positionLabel,
                    content=(row.content or hit.content or "").strip() or hit.content,
                    score=hit.score,
                    source=hit.source,
                )
            )
        return enriched


def maybe_auto_index_after_chunk(db: Session, attachment_id: uuid.UUID) -> None:
    settings = get_settings()
    if not settings.index_auto_on_chunk or not is_embedding_available():
        return
    try:
        IndexingService(db).index_attachment(attachment_id)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Auto index after chunk failed: %s", attachment_id
        )
