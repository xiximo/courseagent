from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.db.models.review_task import ReviewTask, ReviewTaskStatus
from app.review.service import ReviewAssistService
from app.schemas.auth import AuthUserProfile
from app.schemas.review_task import ReviewTaskDto, to_review_task_dto
from app.services.llm_settings import get_or_create_llm_config
from app.storage import get_storage
from app.storage.base import ObjectStorage

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = (".doc", ".docx")


class ReviewTaskService:
    def __init__(
        self,
        db: Session,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.db = db
        self._storage = storage

    @property
    def storage(self) -> ObjectStorage:
        if self._storage is None:
            self._storage = get_storage()
        return self._storage

    def list_tasks(self, limit: int = 100) -> list[ReviewTaskDto]:
        tasks = self.db.scalars(
            select(ReviewTask).order_by(ReviewTask.created_at.desc()).limit(limit)
        ).all()
        return [to_review_task_dto(task) for task in tasks]

    def create_task(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        remark: str | None,
        user: AuthUserProfile,
    ) -> ReviewTaskDto:
        normalized_name = (file_name or "").strip() or "draft.docx"
        lower_name = normalized_name.lower()
        if not lower_name.endswith(ALLOWED_EXTENSIONS):
            raise ApiBusinessError(
                "INVALID_FILE_TYPE",
                "仅支持上传 .doc / .docx 文件",
                400,
            )
        if not file_bytes:
            raise ApiBusinessError("EMPTY_FILE", "上传文件为空", 400)

        task_no = self._next_task_no()
        task_id = uuid.uuid4()
        safe_name = normalized_name.replace("\\", "_").replace("/", "_").strip() or "draft.docx"
        storage_key = f"review/tasks/{task_id}/{safe_name}"

        try:
            self.storage.put_bytes(
                storage_key,
                file_bytes,
                _guess_content_type(normalized_name),
            )
        except Exception as exc:
            logger.exception("Failed to store review task file: %s", task_no)
            raise ApiBusinessError(
                "STORAGE_FAILED",
                f"文档存储失败：{exc}",
                500,
            ) from exc

        task = ReviewTask(
            id=task_id,
            task_no=task_no,
            file_name=normalized_name,
            file_size=len(file_bytes),
            storage_key=storage_key,
            status=ReviewTaskStatus.pending,
            remark=remark.strip() if remark and remark.strip() else None,
            created_by=user.fullName or user.username,
            created_by_user_id=uuid.UUID(user.id) if _is_uuid(user.id) else None,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        from app.review_tasks.runner import enqueue_review_task

        enqueue_review_task(task.id)
        return to_review_task_dto(task)

    def run_task(self, task_id: uuid.UUID) -> None:
        task = self.db.get(ReviewTask, task_id)
        if not task:
            raise ValueError("审核任务不存在")
        if not task.storage_key:
            task.status = ReviewTaskStatus.failed
            task.failure_reason = "未找到上传文档"
            self.db.commit()
            return

        task.status = ReviewTaskStatus.analyzing
        task.failure_reason = None
        self.db.commit()

        try:
            file_bytes = self.storage.get_bytes(task.storage_key)
            llm_config = get_or_create_llm_config(self.db)
            result = ReviewAssistService(self.db, llm_config).analyze(
                file_bytes=file_bytes,
                file_name=task.file_name,
            )
            task.status = ReviewTaskStatus.completed
            task.standard_name = result.basicInfo.name or None
            task.standard_no = result.basicInfo.standardNo or None
            task.summary = result.summary or None
            task.issue_count = len(result.issues or [])
            task.analysis_task_id = result.taskId
            task.failure_reason = None
        except Exception as exc:
            logger.exception("Review task analysis failed: %s", task.task_no)
            task.status = ReviewTaskStatus.failed
            task.failure_reason = str(exc) or "分析失败"
        finally:
            self.db.commit()

    def _next_task_no(self) -> str:
        prefix = datetime.now(UTC).strftime("RA-%Y%m%d")
        existing = self.db.scalars(
            select(ReviewTask.task_no)
            .where(ReviewTask.task_no.like(f"{prefix}%"))
            .order_by(ReviewTask.task_no.desc())
            .limit(1)
        ).first()
        if existing:
            seq = int(existing[-3:]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:03d}"


def _guess_content_type(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".docx"):
        return (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    if lower.endswith(".doc"):
        return "application/msword"
    return "application/octet-stream"


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
