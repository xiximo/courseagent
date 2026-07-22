"""平台知识库（course_agent_knowledge_base + Standard/Attachment），与 Agent 解耦。"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.course_agent.data_migration import (
    LEGACY_BUILTIN_MATERIAL_LABELS,
    migrate_agent_from_config_json,
)
from app.db.models.attachment import (
    Attachment,
    AttachmentDownloadStatus,
    AttachmentParseStatus,
    TextChunk,
)
from app.db.models.course_agent import CourseAgentRecord
from app.db.models.course_agent_resources import CourseAgentKnowledgeBaseRecord
from app.db.models.standard import Standard, StandardSyncStatus
from app.processing.figure_assets import remove_figure_assets
from app.processing.runner import enqueue_index_all
from app.processing.service import ProcessingService
from app.processing.state import (
    is_attachment_running,
    is_standard_running,
    mark_attachment_running,
    unmark_attachment_running,
)
from app.schemas.course_agent import CourseAgentKnowledgeBaseDto
from app.storage import get_storage
from app.storage.base import ObjectStorage
from app.sync.attachment_parser import guess_file_type

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PLATFORM_OWNER = "platform"


def _owner_key(agent_id: str | None) -> str:
    return agent_id or PLATFORM_OWNER


class MaterialService:
    def __init__(self, db: Session, storage: ObjectStorage | None = None) -> None:
        self.db = db
        self.storage = storage or get_storage()

    def ensure_agent_materials(self, agent_id: str) -> list[CourseAgentKnowledgeBaseDto]:
        """兼容旧逻辑：返回曾归属该 Agent 的知识库；平台库请用 list_all。"""
        self._ensure_migrated(agent_id)
        self._purge_legacy_builtin(agent_id)
        rows = self._list_kb_rows(agent_id)
        return [self._kb_to_dto(row) for row in rows]

    def create_knowledge_base(
        self,
        *,
        name: str,
        description: str = "",
        agent_id: str | None = None,
    ) -> CourseAgentKnowledgeBaseDto:
        material_label = f"material_{uuid.uuid4().hex[:8]}"
        while self._material_label_exists(material_label):
            material_label = f"material_{uuid.uuid4().hex[:8]}"

        owner = _owner_key(agent_id)
        standard = self._get_or_create_standard(owner, material_label, name)
        total = self.db.scalar(select(func.count()).select_from(CourseAgentKnowledgeBaseRecord)) or 0
        record = CourseAgentKnowledgeBaseRecord(
            id=f"kb_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            material_label=material_label,
            name=name,
            description=description,
            role="",
            standard_id=standard.id,
            status="ready",
            sort_order=int(total),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._kb_to_dto(record)

    def get_knowledge_base(self, kb_id: str) -> CourseAgentKnowledgeBaseDto:
        return self._kb_to_dto(self._get_kb_by_id(kb_id))

    def update_knowledge_base(
        self,
        kb_id: str,
        *,
        name: str,
        description: str = "",
    ) -> CourseAgentKnowledgeBaseDto:
        record = self._get_kb_by_id(kb_id)
        record.name = name
        record.description = description
        record.updated_at = datetime.now(UTC)

        standard = self.db.get(Standard, record.standard_id)
        if standard is not None:
            standard.name = name

        self.db.commit()
        self.db.refresh(record)
        return self._kb_to_dto(record)

    def delete_knowledge_base(self, kb_id: str) -> None:
        record = self._get_kb_by_id(kb_id)
        material_label = record.material_label
        standard_id = record.standard_id
        owner = _owner_key(record.agent_id)
        self.db.delete(record)
        self.db.flush()
        self._purge_standard_material(owner, material_label, standard_id)
        self.db.commit()

    def list_material_documents(self, material_label: str) -> list[dict]:
        record = self._get_kb_by_material_label(material_label)
        attachments = self.db.scalars(
            select(Attachment)
            .where(Attachment.standard_id == record.standard_id)
            .order_by(Attachment.created_at.desc())
        ).all()

        documents: list[dict] = []
        for attachment in attachments:
            chunk_count = self.db.scalar(
                select(func.count())
                .select_from(TextChunk)
                .where(TextChunk.attachment_id == attachment.id)
            ) or 0
            indexed_count = self.db.scalar(
                select(func.count())
                .select_from(TextChunk)
                .where(
                    TextChunk.attachment_id == attachment.id,
                    TextChunk.indexed_at.is_not(None),
                )
            ) or 0
            uploaded_at = attachment.downloaded_at or attachment.created_at
            documents.append(
                {
                    "id": str(attachment.id),
                    "fileName": attachment.display_name or attachment.sprs_file_id,
                    "fileType": attachment.file_type or "",
                    "fileSize": attachment.file_size,
                    "parseStatus": attachment.parse_status.value,
                    "chunkCount": chunk_count,
                    "indexedChunkCount": indexed_count,
                    "uploadedAt": uploaded_at.isoformat() if uploaded_at else "",
                    "failureReason": attachment.failure_reason,
                }
            )
        return documents

    def upload_material(
        self,
        material_label: str,
        *,
        file_name: str,
        file_bytes: bytes,
    ) -> CourseAgentKnowledgeBaseDto:
        record = self._get_kb_by_material_label(material_label)
        if not file_bytes:
            raise ApiBusinessError("EMPTY_FILE", "上传文件为空", 400)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ApiBusinessError("FILE_TOO_LARGE", "文件过大（上限 20MB）", 400)

        ext = _file_extension(file_name)
        if ext not in ALLOWED_EXTENSIONS:
            raise ApiBusinessError(
                "UNSUPPORTED_FILE",
                f"不支持的文件类型，允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}",
                400,
            )

        self._set_material_status(record, "indexing")
        owner = _owner_key(record.agent_id)

        attachment_id = uuid.uuid4()
        sprs_file_id = f"course-agent:{owner}:{material_label}:{attachment_id.hex[:12]}"
        safe_name = file_name.replace("\\", "_").replace("/", "_").strip() or "document"
        storage_key = (
            f"course-agent/{owner}/{material_label}/{attachment_id.hex[:12]}_{safe_name}"
        )
        content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        self.storage.put_bytes(storage_key, file_bytes, content_type=content_type)

        attachment = Attachment(
            id=attachment_id,
            standard_id=record.standard_id,
            sprs_file_id=sprs_file_id,
            attr_field=material_label,
            display_name=safe_name,
            file_type=guess_file_type(safe_name, sprs_file_id),
            storage_backend=(get_settings().storage_backend or "local").strip().lower(),
            storage_bucket=self.storage.bucket,
            storage_key=storage_key,
            file_size=len(file_bytes),
            content_hash=hashlib.sha256(file_bytes).hexdigest(),
            download_status=AttachmentDownloadStatus.ready,
            parse_status=AttachmentParseStatus.pending,
            downloaded_at=datetime.now(UTC),
        )
        self.db.add(attachment)
        self.db.commit()

        queued = enqueue_material_pipeline(attachment.id, material_label)
        if not queued:
            self._set_material_status(record, "error")
            raise ApiBusinessError("PROCESSING_BUSY", "该素材正在处理中，请稍后再试", 409)

        self.db.refresh(record)
        return self._kb_to_dto(record)

    def reindex_material(self, material_label: str) -> CourseAgentKnowledgeBaseDto:
        record = self._get_kb_by_material_label(material_label)
        self._set_material_status(record, "indexing")
        queued = enqueue_index_all(record.standard_id)
        if not queued:
            raise ApiBusinessError("PROCESSING_BUSY", "该素材正在批量索引中", 409)

        thread = threading.Thread(
            target=_wait_standard_index_then_refresh,
            args=(record.standard_id, material_label),
            name=f"material-reindex-{material_label}",
            daemon=True,
        )
        thread.start()
        self.db.refresh(record)
        return self._kb_to_dto(record)

    def delete_material_document(
        self,
        material_label: str,
        attachment_id: uuid.UUID,
    ) -> CourseAgentKnowledgeBaseDto:
        if is_attachment_running(attachment_id):
            raise ApiBusinessError(
                "PROCESSING_BUSY", "该文档正在处理中，请稍后再试", 409
            )

        record = self._get_kb_by_material_label(material_label)
        attachment = self.db.get(Attachment, attachment_id)
        if attachment is None or attachment.standard_id != record.standard_id:
            raise ApiBusinessError("NOT_FOUND", "文档不存在", 404)

        self._purge_attachment(attachment)
        self.db.commit()
        self.db.refresh(record)
        return self._kb_to_dto(record)

    def resolve_standard_id(self, agent_id: str, role: str) -> uuid.UUID | None:
        """优先：绑定知识库中 role 匹配；其次：遗留 agent_id+role；再次：绑定库第一项。"""
        bound_ids = []
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is not None:
            cfg = dict(row.config_json or {})
            bound_ids = [
                str(item)
                for item in (cfg.get("boundKnowledgeBaseIds") or [])
                if str(item).strip()
            ]

        if bound_ids:
            role_match = self.db.scalar(
                select(CourseAgentKnowledgeBaseRecord).where(
                    CourseAgentKnowledgeBaseRecord.id.in_(bound_ids),
                    CourseAgentKnowledgeBaseRecord.role == role,
                )
            )
            if role_match is not None:
                return role_match.standard_id

        owned = self.db.scalar(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.agent_id == agent_id,
                CourseAgentKnowledgeBaseRecord.role == role,
            )
        )
        if owned is not None:
            return owned.standard_id

        if bound_ids:
            first = self.db.scalar(
                select(CourseAgentKnowledgeBaseRecord).where(
                    CourseAgentKnowledgeBaseRecord.id == bound_ids[0]
                )
            )
            if first is not None:
                return first.standard_id
        return None

    def list_standard_ids(self, agent_id: str) -> list[uuid.UUID]:
        self._ensure_migrated(agent_id)
        row = self._get_agent(agent_id)
        cfg = dict(row.config_json or {})
        bound_ids = [
            str(item)
            for item in (cfg.get("boundKnowledgeBaseIds") or [])
            if str(item).strip()
        ]
        if bound_ids:
            return self.list_standard_ids_by_kb_ids(bound_ids)
        return [
            kb.standard_id
            for kb in self._list_kb_rows(agent_id)
            if kb.standard_id is not None
        ]

    def list_standard_ids_by_kb_ids(self, kb_ids: list[str]) -> list[uuid.UUID]:
        if not kb_ids:
            return []
        rows = self.db.scalars(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.id.in_(kb_ids)
            )
        ).all()
        by_id = {row.id: row.standard_id for row in rows}
        return [by_id[kb_id] for kb_id in kb_ids if kb_id in by_id]

    def list_all_knowledge_bases(self) -> list[CourseAgentKnowledgeBaseDto]:
        rows = self.db.scalars(
            select(CourseAgentKnowledgeBaseRecord).order_by(
                CourseAgentKnowledgeBaseRecord.updated_at.desc()
            )
        ).all()
        return [self._kb_to_dto(row) for row in rows]

    def get_kb_name_for_role(self, agent_id: str, role: str) -> str | None:
        record = self.db.scalar(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.agent_id == agent_id,
                CourseAgentKnowledgeBaseRecord.role == role,
            )
        )
        return record.name if record else None

    def _kb_to_dto(self, record: CourseAgentKnowledgeBaseRecord) -> CourseAgentKnowledgeBaseDto:
        stats = self._material_stats(record.standard_id)
        computed_status = stats.pop("status")
        status = record.status if record.status == "indexing" else computed_status
        return CourseAgentKnowledgeBaseDto.model_validate(
            {
                "id": record.id,
                "role": record.role or "",
                "name": record.name,
                "description": record.description or "",
                "materialLabel": record.material_label,
                "standardId": str(record.standard_id),
                "status": status,
                **stats,
            }
        )

    def _ensure_migrated(self, agent_id: str) -> None:
        migrate_agent_from_config_json(self.db, agent_id)
        self.db.commit()

    def _list_kb_rows(self, agent_id: str) -> list[CourseAgentKnowledgeBaseRecord]:
        return list(
            self.db.scalars(
                select(CourseAgentKnowledgeBaseRecord)
                .where(CourseAgentKnowledgeBaseRecord.agent_id == agent_id)
                .order_by(
                    CourseAgentKnowledgeBaseRecord.sort_order,
                    CourseAgentKnowledgeBaseRecord.created_at,
                )
            ).all()
        )

    def _get_kb_by_id(self, kb_id: str) -> CourseAgentKnowledgeBaseRecord:
        record = self.db.get(CourseAgentKnowledgeBaseRecord, kb_id)
        if record is None:
            raise ApiBusinessError("NOT_FOUND", "知识库不存在", 404)
        return record

    def _get_kb_by_material_label(
        self, material_label: str
    ) -> CourseAgentKnowledgeBaseRecord:
        record = self.db.scalar(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.material_label == material_label,
            )
        )
        if record is None:
            raise ApiBusinessError(
                "INVALID_MATERIAL",
                f"知识库 {material_label} 不存在",
                404,
            )
        return record

    def _material_label_exists(self, material_label: str) -> bool:
        existing = self.db.scalar(
            select(CourseAgentKnowledgeBaseRecord.id).where(
                CourseAgentKnowledgeBaseRecord.material_label == material_label,
            )
        )
        return existing is not None

    def _purge_legacy_builtin(self, agent_id: str) -> None:
        rows = self.db.scalars(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.agent_id == agent_id,
                CourseAgentKnowledgeBaseRecord.material_label.in_(
                    LEGACY_BUILTIN_MATERIAL_LABELS
                ),
            )
        ).all()
        for row in rows:
            material_label = row.material_label
            standard_id = row.standard_id
            owner = _owner_key(row.agent_id)
            try:
                self.db.delete(row)
                self.db.flush()
                self._purge_standard_material(owner, material_label, standard_id)
            except ApiBusinessError as exc:
                logger.warning("Skip purging legacy builtin KB: %s", exc.message)
            except Exception:
                logger.exception(
                    "Failed to purge legacy builtin KB: %s", material_label
                )
        if rows:
            self.db.commit()

    def _get_or_create_standard(
        self, owner: str, material_label: str, name: str
    ) -> Standard:
        sprs_id = f"course-agent:{owner}:{material_label}"
        standard = self.db.scalar(select(Standard).where(Standard.sprs_id == sprs_id))
        if standard is not None:
            return standard

        standard = Standard(
            sprs_id=sprs_id,
            stand_type="COURSE_AGENT",
            name=name,
            sync_status=StandardSyncStatus.not_synced,
        )
        self.db.add(standard)
        self.db.flush()
        return standard

    def _material_stats(self, standard_id: uuid.UUID) -> dict:
        doc_count = self.db.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.standard_id == standard_id,
                Attachment.download_status == AttachmentDownloadStatus.ready,
            )
        ) or 0
        chunk_count = self.db.scalar(
            select(func.count())
            .select_from(TextChunk)
            .where(TextChunk.standard_id == standard_id)
        ) or 0
        indexed_count = self.db.scalar(
            select(func.count())
            .select_from(TextChunk)
            .where(
                TextChunk.standard_id == standard_id,
                TextChunk.indexed_at.is_not(None),
            )
        ) or 0
        last_indexed = self.db.scalar(
            select(func.max(TextChunk.indexed_at)).where(
                TextChunk.standard_id == standard_id
            )
        )

        status = "ready"
        if doc_count > 0 and chunk_count > 0 and indexed_count < chunk_count:
            status = "indexing"
        elif doc_count > 0 and chunk_count == 0:
            status = "indexing"

        return {
            "documentCount": doc_count,
            "chunkCount": chunk_count,
            "lastIndexedAt": (
                last_indexed.isoformat() if last_indexed else datetime.now(UTC).isoformat()
            ),
            "status": status,
        }

    def _set_material_status(
        self, record: CourseAgentKnowledgeBaseRecord, status: str
    ) -> None:
        record.status = status
        record.updated_at = datetime.now(UTC)
        self.db.commit()

    def _set_material_status_by_label(self, material_label: str, status: str) -> None:
        record = self._get_kb_by_material_label(material_label)
        self._set_material_status(record, status)

    def _get_agent(self, agent_id: str) -> CourseAgentRecord:
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is None:
            raise ApiBusinessError("NOT_FOUND", f"Agent {agent_id} 不存在", 404)
        return row

    def _purge_attachment(self, attachment: Attachment) -> None:
        ProcessingService._delete_attachment_index_quiet(attachment.id)

        if attachment.storage_key:
            try:
                self.storage.remove_object(attachment.storage_key)
            except Exception:
                logger.exception(
                    "Failed to remove uploaded file: %s", attachment.storage_key
                )

        try:
            remove_figure_assets(self.storage, attachment.id)
        except Exception:
            logger.exception(
                "Failed to remove extracted assets: attachment=%s", attachment.id
            )

        self.db.delete(attachment)

    def _purge_standard_material(
        self,
        owner: str,
        material_label: str,
        standard_id: uuid.UUID,
    ) -> None:
        if is_standard_running(standard_id):
            raise ApiBusinessError(
                "PROCESSING_BUSY", "该知识库正在批量处理中，请稍后再试", 409
            )

        attachments = self.db.scalars(
            select(Attachment).where(Attachment.standard_id == standard_id)
        ).all()
        for attachment in attachments:
            if is_attachment_running(attachment.id):
                raise ApiBusinessError(
                    "PROCESSING_BUSY", "知识库中有文档正在处理中，请稍后再试", 409
                )

        for attachment in attachments:
            self._purge_attachment(attachment)

        for prefix in (
            f"course-agent/{owner}/{material_label}/",
            f"course-agent/{PLATFORM_OWNER}/{material_label}/",
        ):
            try:
                self.storage.remove_prefix(prefix)
            except Exception:
                logger.exception("Failed to remove material prefix: %s", prefix)

        standard = self.db.get(Standard, standard_id)
        if standard is not None:
            self.db.delete(standard)
        self.db.flush()


def enqueue_material_pipeline(
    attachment_id: uuid.UUID, material_label: str
) -> bool:
    if not mark_attachment_running(attachment_id):
        return False

    thread = threading.Thread(
        target=_execute_material_pipeline,
        args=(attachment_id, material_label),
        name=f"material-pipeline-{attachment_id}",
        daemon=True,
    )
    thread.start()
    return True


def _execute_material_pipeline(
    attachment_id: uuid.UUID, material_label: str
) -> None:
    from app.db.session import SessionLocal
    from app.indexing.service import IndexingService

    db = SessionLocal()
    try:
        processing = ProcessingService(db)
        processing.extract_text(attachment_id)
        processing.chunk_attachment(attachment_id)
        IndexingService(db).index_attachment(attachment_id)
        MaterialService(db)._set_material_status_by_label(material_label, "ready")
    except Exception:
        logger.exception(
            "Material pipeline failed: material=%s attachment=%s",
            material_label,
            attachment_id,
        )
        try:
            MaterialService(db)._set_material_status_by_label(material_label, "error")
        except Exception:
            logger.exception("Failed to mark material error status")
    finally:
        db.close()
        unmark_attachment_running(attachment_id)


def _wait_standard_index_then_refresh(
    standard_id: uuid.UUID, material_label: str
) -> None:
    from app.db.session import SessionLocal
    from app.processing.state import is_standard_running

    import time

    deadline = time.time() + 3600
    while is_standard_running(standard_id) and time.time() < deadline:
        time.sleep(1.0)

    db = SessionLocal()
    try:
        MaterialService(db)._set_material_status_by_label(material_label, "ready")
    except Exception:
        logger.exception("Failed to refresh KB stats after reindex")
    finally:
        db.close()


def _file_extension(file_name: str) -> str:
    dot = file_name.rfind(".")
    if dot < 0:
        return ""
    return file_name[dot:].lower()
