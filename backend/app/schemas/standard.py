from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.processing import DownloadStatusDto, ParseStatusDto, SyncStatusDto

StandardStatusDto = Literal["active", "obsolete", "draft"]
StandardTypeDto = Literal["domestic", "foreign"]


class StandardSummaryDto(BaseModel):
    id: str
    sprsId: str
    standardNo: str
    name: str
    englishName: str | None = None
    standardType: StandardTypeDto
    country: str
    category: str
    status: StandardStatusDto
    partCode: str
    partName: str
    publishDate: str
    effectiveDate: str
    syncStatus: SyncStatusDto
    updatedAt: str


class StandardAttachmentDto(BaseModel):
    id: str
    fileName: str
    fileType: str
    downloadStatus: DownloadStatusDto
    parseStatus: ParseStatusDto | None = None
    charCount: int | None = None
    chunkCount: int | None = None


class StandardDetailDto(StandardSummaryDto):
    textStatus: str
    source: Literal["SPRS"] = "SPRS"
    attachments: list[StandardAttachmentDto] = Field(default_factory=list)
    attrInfo: dict[str, str] | None = None


class StandardSearchPageResult(BaseModel):
    items: list[StandardSummaryDto]
    total: int
    page: int
    pageSize: int
