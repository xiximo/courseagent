from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.attachment import AttachmentText, TextChunk
from app.db.models.standard import Standard, StandardSyncStatus
from app.schemas.standard import (
    StandardAttachmentDto,
    StandardDetailDto,
    StandardSearchPageResult,
    StandardStatusDto,
    StandardSummaryDto,
    StandardTypeDto,
)


def map_standard_type(stand_type: str | None, country: str | None) -> StandardTypeDto:
    if stand_type == "OUTLAND":
        return "foreign"
    if stand_type == "INLAND":
        return "domestic"
    normalized = (country or "").strip().upper()
    if normalized and normalized not in {"CN", "CHINA", "中国"}:
        return "foreign"
    return "domestic"


def map_standard_status(
    stand_state_show: str | None,
    text_status_show: str | None,
) -> StandardStatusDto:
    combined = f"{stand_state_show or ''}{text_status_show or ''}"
    if any(token in combined for token in ("废止", "作废", "失效")):
        return "obsolete"
    if any(token in combined for token in ("草案", "征求意见", "制订中")):
        return "draft"
    return "active"


def status_filter(status: StandardStatusDto):
    if status == "obsolete":
        return or_(
            Standard.stand_state_show.ilike("%废止%"),
            Standard.stand_state_show.ilike("%作废%"),
            Standard.text_status_show.ilike("%废止%"),
            Standard.text_status_show.ilike("%作废%"),
        )
    if status == "draft":
        return or_(
            Standard.stand_state_show.ilike("%草案%"),
            Standard.stand_state_show.ilike("%征求%"),
            Standard.text_status_show.ilike("%草案%"),
            Standard.text_status_show.ilike("%征求%"),
        )
    return or_(
        Standard.stand_state_show.ilike("%现行%"),
        Standard.text_status_show.ilike("%现行%"),
        Standard.stand_state_show.is_(None),
        Standard.text_status_show.is_(None),
    )


def type_filter(standard_type: StandardTypeDto):
    if standard_type == "foreign":
        return Standard.stand_type == "OUTLAND"
    return or_(
        Standard.stand_type == "INLAND",
        Standard.stand_type.is_(None),
    )


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _display_standard_no(standard: Standard) -> str:
    return standard.standard_no or standard.sprs_id


def _display_text_status(standard: Standard) -> str:
    if standard.text_status_show:
        return standard.text_status_show
    labels = {
        StandardSyncStatus.not_synced: "未同步",
        StandardSyncStatus.synced: "已同步",
        StandardSyncStatus.attachment_downloaded: "附件已下载",
        StandardSyncStatus.text_parsed: "文本已解析",
        StandardSyncStatus.index_updated: "索引已更新",
        StandardSyncStatus.sync_failed: "同步失败",
    }
    return labels.get(standard.sync_status, "未知")


def _flatten_attr_info(raw: dict | None) -> dict[str, str] | None:
    if not raw:
        return None
    result: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            result[str(key)] = text
    return result or None


def to_summary_dto(standard: Standard) -> StandardSummaryDto:
    return StandardSummaryDto(
        id=str(standard.id),
        sprsId=standard.sprs_id,
        standardNo=_display_standard_no(standard),
        name=standard.name,
        englishName=standard.english_name,
        standardType=map_standard_type(standard.stand_type, standard.country),
        country=standard.country or "",
        category=standard.stand_sort or "",
        status=map_standard_status(
            standard.stand_state_show,
            standard.text_status_show,
        ),
        partCode=standard.part_code or "",
        partName=standard.part_name or "",
        publishDate=_format_date(standard.publish_date),
        effectiveDate=_format_date(standard.effective_date),
        syncStatus=standard.sync_status.value,
        updatedAt=_format_datetime(standard.updated_at or standard.synced_at),
    )


class StandardsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        standard_no: str | None = None,
        name: str | None = None,
        standard_type: StandardTypeDto | None = None,
        status: StandardStatusDto | None = None,
        part_code: str | None = None,
        country: str | None = None,
    ) -> StandardSearchPageResult:
        filters = self._build_filters(
            standard_no=standard_no,
            name=name,
            standard_type=standard_type,
            status=status,
            part_code=part_code,
            country=country,
        )

        total = self.db.scalar(
            select(func.count()).select_from(Standard).where(*filters)
        ) or 0

        standards = self.db.scalars(
            select(Standard)
            .where(*filters)
            .order_by(Standard.updated_at.desc(), Standard.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return StandardSearchPageResult(
            items=[to_summary_dto(item) for item in standards],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def get_detail(self, standard_id: uuid.UUID) -> StandardDetailDto | None:
        standard = self.db.scalar(
            select(Standard)
            .where(Standard.id == standard_id)
            .options(selectinload(Standard.attachments))
        )
        if standard is None:
            return None

        attachment_ids = [item.id for item in standard.attachments]
        char_counts: dict[uuid.UUID, int] = {}
        chunk_counts: dict[uuid.UUID, int] = {}
        if attachment_ids:
            char_rows = self.db.execute(
                select(AttachmentText.attachment_id, AttachmentText.char_count)
                .where(AttachmentText.attachment_id.in_(attachment_ids))
            ).all()
            char_counts = {row[0]: row[1] or 0 for row in char_rows}

            chunk_rows = self.db.execute(
                select(TextChunk.attachment_id, func.count())
                .where(TextChunk.attachment_id.in_(attachment_ids))
                .group_by(TextChunk.attachment_id)
            ).all()
            chunk_counts = {row[0]: row[1] for row in chunk_rows}

        summary = to_summary_dto(standard)
        return StandardDetailDto(
            **summary.model_dump(),
            textStatus=_display_text_status(standard),
            attachments=[
                StandardAttachmentDto(
                    id=str(item.id),
                    fileName=item.display_name or item.sprs_file_id,
                    fileType=item.file_type or "bin",
                    downloadStatus=item.download_status.value,
                    parseStatus=item.parse_status.value,
                    charCount=char_counts.get(item.id),
                    chunkCount=chunk_counts.get(item.id),
                )
                for item in standard.attachments
            ],
            attrInfo=_flatten_attr_info(standard.attr_info_map),
        )

    @staticmethod
    def _build_filters(
        *,
        standard_no: str | None,
        name: str | None,
        standard_type: StandardTypeDto | None,
        status: StandardStatusDto | None,
        part_code: str | None,
        country: str | None,
    ) -> list:
        filters = []
        if standard_no:
            token = standard_no.strip()
            filters.append(
                or_(
                    Standard.standard_no.ilike(f"%{token}%"),
                    Standard.sprs_id.ilike(f"%{token}%"),
                )
            )
        if name:
            filters.append(Standard.name.ilike(f"%{name.strip()}%"))
        if standard_type:
            filters.append(type_filter(standard_type))
        if status:
            filters.append(status_filter(status))
        if part_code:
            filters.append(Standard.part_code.ilike(f"%{part_code.strip()}%"))
        if country:
            filters.append(Standard.country.ilike(f"%{country.strip()}%"))
        return filters
