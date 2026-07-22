from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReviewTaskStatusDto = Literal["pending", "analyzing", "completed", "failed"]


class ReviewTaskDto(BaseModel):
    id: str
    taskNo: str
    fileName: str
    fileSize: int
    status: ReviewTaskStatusDto
    standardName: str | None = None
    standardNo: str | None = None
    remark: str | None = None
    summary: str | None = None
    issueCount: int | None = None
    failureReason: str | None = None
    createdBy: str
    createdAt: str
    updatedAt: str


def to_review_task_dto(task) -> ReviewTaskDto:
    return ReviewTaskDto(
        id=str(task.id),
        taskNo=task.task_no,
        fileName=task.file_name,
        fileSize=task.file_size,
        status=task.status.value,
        standardName=task.standard_name,
        standardNo=task.standard_no,
        remark=task.remark,
        summary=task.summary,
        issueCount=task.issue_count,
        failureReason=task.failure_reason,
        createdBy=task.created_by,
        createdAt=_iso(task.created_at),
        updatedAt=_iso(task.updated_at),
    )


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""
