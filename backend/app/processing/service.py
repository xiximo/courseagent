from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.attachment import (
    Attachment,
    AttachmentDownloadStatus,
    AttachmentParseStatus,
    AttachmentText,
    TextChunk,
)
from app.db.models.standard import Standard, StandardSyncStatus
from app.processing.chunker import chunk_attachment_text
from app.indexing.service import maybe_auto_index_after_chunk
from app.processing.figure_assets import (
    FigureAssetInput,
    list_figure_assets,
    persist_figure_assets,
    remove_figure_assets,
)
from app.processing.parser import extract_attachment_text
from app.processing.state import is_attachment_running, is_standard_running
from app.schemas.processing import (
    AttachmentChunksDto,
    AttachmentExtractedTextDto,
    AttachmentProcessingDto,
    ProcessingPageResult,
    StandardProcessingDto,
    TextChunkDto,
)
from app.storage import get_storage
from app.storage.base import ObjectStorage


class ProcessingService:
    def __init__(
        self,
        db: Session,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.db = db
        self.storage = storage or get_storage()

    def list_standards(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        standard_no: str | None = None,
        name: str | None = None,
        sync_status: str | None = None,
        include_attachments: bool = True,
    ) -> ProcessingPageResult:
        filters = []
        if standard_no:
            filters.append(Standard.standard_no.ilike(f"%{standard_no.strip()}%"))
        if name:
            filters.append(Standard.name.ilike(f"%{name.strip()}%"))
        if sync_status:
            filters.append(Standard.sync_status == sync_status)

        total = self.db.scalar(
            select(func.count()).select_from(Standard).where(*filters)
        ) or 0

        query = (
            select(Standard)
            .where(*filters)
            .order_by(Standard.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if include_attachments:
            query = query.options(selectinload(Standard.attachments))

        standards = self.db.scalars(query).all()
        standard_ids = [item.id for item in standards]

        chunk_counts: dict[uuid.UUID, int] = {}
        if standard_ids:
            rows = self.db.execute(
                select(TextChunk.standard_id, func.count())
                .where(TextChunk.standard_id.in_(standard_ids))
                .group_by(TextChunk.standard_id)
            ).all()
            chunk_counts = {row[0]: row[1] for row in rows}

        items = [
            self._to_standard_dto(
                standard,
                total_chunks=chunk_counts.get(standard.id, 0),
                include_attachments=include_attachments,
            )
            for standard in standards
        ]

        return ProcessingPageResult(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    def get_standard(self, standard_id: uuid.UUID) -> StandardProcessingDto | None:
        standard = self.db.scalar(
            select(Standard)
            .where(Standard.id == standard_id)
            .options(selectinload(Standard.attachments))
        )
        if standard is None:
            return None

        total_chunks = self.db.scalar(
            select(func.count())
            .select_from(TextChunk)
            .where(TextChunk.standard_id == standard_id)
        ) or 0

        return self._to_standard_dto(
            standard,
            total_chunks=total_chunks,
            include_attachments=True,
        )

    def extract_text(self, attachment_id: uuid.UUID) -> None:
        attachment = self._get_attachment(attachment_id)
        if attachment.download_status != AttachmentDownloadStatus.ready:
            attachment.parse_status = AttachmentParseStatus.failed
            attachment.failure_reason = "附件尚未下载完成，无法抽取文本"
            self.db.commit()
            return

        attachment.parse_status = AttachmentParseStatus.pending
        attachment.failure_reason = None
        self.db.execute(delete(TextChunk).where(TextChunk.attachment_id == attachment.id))
        self._delete_attachment_index_quiet(attachment.id)
        self.db.commit()

        try:
            payload = self.storage.get_bytes(attachment.storage_key)
            result = extract_attachment_text(
                payload,
                attachment.file_type or "",
                attachment.display_name or attachment.sprs_file_id,
            )
            content = result.content
            if result.figure_assets:
                figure_inputs = [
                    FigureAssetInput(
                        file_name=str(item.get("file_name") or f"fig-{index:03d}.png"),
                        content_base64=str(item.get("content_base64") or ""),
                        page_no=item.get("page_no"),
                        captions=[
                            str(caption) for caption in item.get("captions", []) if caption
                        ],
                    )
                    for index, item in enumerate(result.figure_assets, start=1)
                    if item.get("content_base64")
                ]
                if figure_inputs:
                    content, _records = persist_figure_assets(
                        self.storage,
                        attachment.id,
                        content,
                        figure_inputs,
                    )
                    result = replace(
                        result,
                        content=content,
                        has_figures=True,
                        char_count=len(content),
                        figure_assets=[],
                    )
            self._upsert_attachment_text(attachment, result)
            attachment.parse_status = AttachmentParseStatus.parsed
            attachment.failure_reason = None
            self._refresh_standard_sync_status(attachment.standard_id)
            self.db.commit()
        except Exception as exc:
            attachment.parse_status = AttachmentParseStatus.failed
            attachment.failure_reason = str(exc)
            self.db.commit()
            raise

    def chunk_attachment(self, attachment_id: uuid.UUID) -> None:
        attachment = self._get_attachment(attachment_id)
        if attachment.parse_status != AttachmentParseStatus.parsed:
            raise ValueError("请先完成文本抽取，再进行结构切片")

        text_row = self.db.scalar(
            select(AttachmentText).where(AttachmentText.attachment_id == attachment.id)
        )
        if text_row is None or not text_row.content.strip():
            raise ValueError("附件文本为空，无法切片")

        doc_role = self._guess_doc_role(attachment)
        parse_quality = text_row.parse_quality
        drafts = chunk_attachment_text(
            text_row.content,
            doc_role=doc_role,
            parse_quality=parse_quality,
        )

        existing_version = (
            self.db.scalar(
                select(func.max(TextChunk.index_version)).where(
                    TextChunk.attachment_id == attachment.id
                )
            )
            or 0
        )
        index_version = existing_version + 1

        self.db.execute(delete(TextChunk).where(TextChunk.attachment_id == attachment.id))
        for draft in drafts:
            chunk = TextChunk(
                attachment_id=attachment.id,
                standard_id=attachment.standard_id,
                chunk_index=draft.chunk_index,
                chunk_type=draft.chunk_type,
                doc_role=draft.doc_role,
                content=draft.content,
                position_label=draft.position_label,
                clause_level=draft.clause_level,
                parent_label=draft.parent_label,
                page_start=draft.page_start,
                page_end=draft.page_end,
                table_caption=draft.table_caption,
                figure_caption=draft.figure_caption,
                content_json=draft.content_json,
                token_count=draft.token_count,
                index_version=index_version,
            )
            self.db.add(chunk)
            self.db.flush()
            chunk.embedding_id = str(chunk.id)

        self._refresh_standard_sync_status(attachment.standard_id)
        self.db.commit()
        maybe_auto_index_after_chunk(self.db, attachment.id)

    def extract_all_for_standard(self, standard_id: uuid.UUID) -> int:
        attachments = self.db.scalars(
            select(Attachment).where(
                Attachment.standard_id == standard_id,
                Attachment.download_status == AttachmentDownloadStatus.ready,
                Attachment.parse_status.in_(
                    [AttachmentParseStatus.pending, AttachmentParseStatus.failed]
                ),
            )
        ).all()

        count = 0
        for attachment in attachments:
            try:
                self.extract_text(attachment.id)
                count += 1
            except Exception:
                continue
        return count

    def chunk_all_for_standard(self, standard_id: uuid.UUID) -> int:
        attachments = self.db.scalars(
            select(Attachment).where(
                Attachment.standard_id == standard_id,
                Attachment.parse_status == AttachmentParseStatus.parsed,
            )
        ).all()

        count = 0
        for attachment in attachments:
            try:
                self.chunk_attachment(attachment.id)
                count += 1
            except Exception:
                continue
        return count

    def redownload_attachment(self, attachment_id: uuid.UUID) -> None:
        if is_attachment_running(attachment_id):
            raise ValueError("该附件正在处理中，请稍后再试")

        attachment = self._get_attachment(attachment_id)
        from app.sync.attachment_parser import AttachmentRef
        from app.sync.service import SyncService

        ref = AttachmentRef(
            sprs_file_id=attachment.sprs_file_id,
            attr_field=attachment.attr_field or "",
            display_name=attachment.display_name,
        )

        sync = SyncService(self.db, storage=self.storage)
        try:
            sync._download_attachment(attachment, [ref])
        except Exception as exc:
            self.db.commit()
            raise ValueError(str(exc)) from exc

        if attachment.download_status != AttachmentDownloadStatus.ready:
            self.db.commit()
            raise ValueError(attachment.failure_reason or "附件重新下载失败")

        remove_figure_assets(self.storage, attachment.id)
        self.db.execute(
            delete(AttachmentText).where(AttachmentText.attachment_id == attachment.id)
        )
        self.db.execute(
            delete(TextChunk).where(TextChunk.attachment_id == attachment.id)
        )
        attachment.parse_status = AttachmentParseStatus.pending
        attachment.failure_reason = None
        self._refresh_standard_sync_status(attachment.standard_id)
        self.db.commit()

    def get_extracted_text(
        self, attachment_id: uuid.UUID
    ) -> AttachmentExtractedTextDto | None:
        attachment = self._get_attachment(attachment_id)
        if attachment.parse_status != AttachmentParseStatus.parsed:
            return None

        row = self.db.scalar(
            select(AttachmentText).where(AttachmentText.attachment_id == attachment.id)
        )
        if row is None or not row.content.strip():
            return None

        return AttachmentExtractedTextDto(
            attachmentId=str(attachment.id),
            fileName=attachment.display_name or attachment.sprs_file_id,
            fileType=attachment.file_type or "bin",
            content=row.content,
            contentFormat="markdown",
            charCount=row.char_count,
            parseEngine=row.parse_engine,
            parseQuality=row.parse_quality,
            hasTables=row.has_tables,
            hasFigures=row.has_figures,
            pageCount=row.page_count,
            figureAssets=list_figure_assets(self.storage, attachment.id),
            extractedAt=row.extracted_at.isoformat() if row.extracted_at else None,
        )

    def get_attachment_chunks(
        self,
        attachment_id: uuid.UUID,
        *,
        chunk_type: str | None = None,
    ) -> AttachmentChunksDto | None:
        attachment = self._get_attachment(attachment_id)
        query = (
            select(TextChunk)
            .where(TextChunk.attachment_id == attachment.id)
            .order_by(TextChunk.chunk_index)
        )
        if chunk_type:
            query = query.where(TextChunk.chunk_type == chunk_type)

        rows = self.db.scalars(query).all()
        if not rows:
            return None

        by_type: dict[str, int] = {}
        for row in rows:
            by_type[row.chunk_type] = by_type.get(row.chunk_type, 0) + 1

        index_version = max(row.index_version for row in rows)
        chunks = [self._to_chunk_dto(row) for row in rows]

        return AttachmentChunksDto(
            attachmentId=str(attachment.id),
            fileName=attachment.display_name or attachment.sprs_file_id,
            total=len(chunks),
            indexVersion=index_version,
            byType=by_type,
            chunks=chunks,
        )

    def get_extracted_asset_bytes(
        self,
        attachment_id: uuid.UUID,
        asset_name: str,
    ) -> tuple[bytes, str]:
        from app.processing.figure_assets import get_figure_asset_bytes

        attachment = self._get_attachment(attachment_id)
        if attachment.parse_status != AttachmentParseStatus.parsed:
            raise ValueError("附件尚未完成文本抽取")
        return get_figure_asset_bytes(self.storage, attachment_id, asset_name)

    def get_attachment_bytes(self, attachment_id: uuid.UUID) -> tuple[bytes, str, str]:
        attachment = self._get_attachment(attachment_id)
        if attachment.download_status != AttachmentDownloadStatus.ready:
            raise ValueError("附件尚未下载完成")
        payload = self.storage.get_bytes(attachment.storage_key)
        file_name = attachment.display_name or f"{attachment.sprs_file_id}.bin"
        content_type = self._guess_content_type(attachment.file_type, file_name)
        return payload, file_name, content_type

    def _get_attachment(self, attachment_id: uuid.UUID) -> Attachment:
        attachment = self.db.get(Attachment, attachment_id)
        if attachment is None:
            raise ValueError("附件不存在")
        return attachment

    def _upsert_attachment_text(self, attachment: Attachment, result) -> None:
        row = self.db.scalar(
            select(AttachmentText).where(AttachmentText.attachment_id == attachment.id)
        )
        if row is None:
            row = AttachmentText(
                attachment_id=attachment.id,
                content=result.content,
                char_count=result.char_count,
                parse_engine=result.parse_engine,
                parse_quality=result.parse_quality,
                has_tables=result.has_tables,
                has_figures=result.has_figures,
                page_count=result.page_count,
            )
            self.db.add(row)
        else:
            row.content = result.content
            row.char_count = result.char_count
            row.parse_engine = result.parse_engine
            row.parse_quality = result.parse_quality
            row.has_tables = result.has_tables
            row.has_figures = result.has_figures
            row.page_count = result.page_count
            row.extracted_at = datetime.now(UTC)

        attachment.file_type = attachment.file_type or self._guess_file_type(
            attachment.display_name
        )

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

        if parsed_count > 0:
            standard.sync_status = StandardSyncStatus.text_parsed

    def _to_standard_dto(
        self,
        standard: Standard,
        *,
        total_chunks: int,
        include_attachments: bool,
    ) -> StandardProcessingDto:
        attachments = list(standard.attachments) if include_attachments else []
        attachment_ids = [item.id for item in attachments]

        text_rows: dict[uuid.UUID, AttachmentText] = {}
        chunk_counts: dict[uuid.UUID, int] = {}
        if attachment_ids:
            for row in self.db.scalars(
                select(AttachmentText).where(
                    AttachmentText.attachment_id.in_(attachment_ids)
                )
            ).all():
                text_rows[row.attachment_id] = row

            for row in self.db.execute(
                select(TextChunk.attachment_id, func.count())
                .where(TextChunk.attachment_id.in_(attachment_ids))
                .group_by(TextChunk.attachment_id)
            ).all():
                chunk_counts[row[0]] = row[1]

        downloaded_count = sum(
            1
            for item in attachments
            if item.download_status == AttachmentDownloadStatus.ready
        )
        parsed_count = sum(
            1
            for item in attachments
            if item.parse_status == AttachmentParseStatus.parsed
        )
        chunked_count = sum(1 for count in chunk_counts.values() if count > 0)

        attachment_dtos: list[AttachmentProcessingDto] = []
        for item in attachments:
            text_row = text_rows.get(item.id)
            attachment_dtos.append(
                AttachmentProcessingDto(
                    id=str(item.id),
                    sprsFileId=item.sprs_file_id,
                    fileName=item.display_name or item.sprs_file_id,
                    fileType=item.file_type or "bin",
                    attrField=item.attr_field,
                    downloadStatus=item.download_status.value,
                    parseStatus=item.parse_status.value,
                    failureReason=item.failure_reason,
                    parseEngine=text_row.parse_engine if text_row else None,
                    parseQuality=text_row.parse_quality if text_row else None,
                    hasTables=text_row.has_tables if text_row else False,
                    hasFigures=text_row.has_figures if text_row else False,
                    pageCount=text_row.page_count if text_row else None,
                    charCount=text_row.char_count if text_row else 0,
                    chunkCount=chunk_counts.get(item.id, 0),
                    fileSize=item.file_size,
                    downloadedAt=(
                        item.downloaded_at.isoformat() if item.downloaded_at else None
                    ),
                    isProcessing=is_attachment_running(item.id),
                )
            )

        return StandardProcessingDto(
            id=str(standard.id),
            sprsId=standard.sprs_id,
            standardNo=standard.standard_no,
            name=standard.name,
            syncStatus=standard.sync_status.value,
            attachmentCount=len(attachments),
            downloadedCount=downloaded_count,
            parsedCount=parsed_count,
            chunkedCount=chunked_count,
            totalChunks=total_chunks,
            updatedAt=standard.updated_at.isoformat() if standard.updated_at else None,
            isProcessing=is_standard_running(standard.id),
            attachments=attachment_dtos,
        )

    @staticmethod
    def _to_chunk_dto(row: TextChunk) -> TextChunkDto:
        return TextChunkDto(
            id=str(row.id),
            chunkIndex=row.chunk_index,
            chunkType=row.chunk_type,
            docRole=row.doc_role,
            content=row.content,
            positionLabel=row.position_label,
            clauseLevel=row.clause_level,
            parentLabel=row.parent_label,
            pageStart=row.page_start,
            pageEnd=row.page_end,
            tableCaption=row.table_caption,
            figureCaption=row.figure_caption,
            contentJson=row.content_json,
            tokenCount=row.token_count,
            indexVersion=row.index_version,
            createdAt=row.created_at.isoformat() if row.created_at else None,
        )

    @staticmethod
    def _delete_attachment_index_quiet(attachment_id: uuid.UUID) -> None:
        try:
            from app.indexing.embedding_client import (
                delete_attachment_index,
                is_embedding_available,
            )

            if is_embedding_available():
                delete_attachment_index(str(attachment_id))
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to delete attachment index: %s", attachment_id
            )

    @staticmethod
    def _guess_doc_role(attachment: Attachment) -> str:
        name = (attachment.display_name or "").lower()
        field = (attachment.attr_field or "").lower()
        if "编制说明" in name or "jdwj" in field:
            return "explanation"
        if "征求意见" in name or "draft" in name:
            return "draft"
        return "body"

    @staticmethod
    def _guess_file_type(file_name: str | None) -> str:
        name = (file_name or "").lower()
        for ext in ("pdf", "docx", "doc", "txt", "md", "markdown"):
            if name.endswith(f".{ext}"):
                return ext
        return "bin"

    @staticmethod
    def _guess_content_type(file_type: str | None, file_name: str) -> str:
        mapping = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": (
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            "txt": "text/plain",
            "md": "text/markdown",
            "markdown": "text/markdown",
        }
        normalized = (file_type or ProcessingService._guess_file_type(file_name)).lower()
        return mapping.get(normalized, "application/octet-stream")
