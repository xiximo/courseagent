from typing import Literal

from pydantic import BaseModel, Field

SyncStatusDto = Literal[
    "not_synced",
    "synced",
    "attachment_downloaded",
    "text_parsed",
    "index_updated",
    "sync_failed",
]
DownloadStatusDto = Literal["pending", "ready", "failed"]
ParseStatusDto = Literal["pending", "parsed", "failed", "skipped"]
ParseQualityDto = Literal["high", "medium", "low", "ocr"]
ProcessingActionDto = Literal[
    "extract_text",
    "chunk",
    "index",
    "extract_all",
    "chunk_all",
    "index_all",
    "redownload",
]


class ProcessingListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)
    standardNo: str | None = None
    name: str | None = None
    syncStatus: SyncStatusDto | None = None


class AttachmentProcessingDto(BaseModel):
    id: str
    sprsFileId: str
    fileName: str
    fileType: str
    attrField: str | None = None
    downloadStatus: DownloadStatusDto
    parseStatus: ParseStatusDto
    failureReason: str | None = None
    parseEngine: str | None = None
    parseQuality: ParseQualityDto | None = None
    hasTables: bool = False
    hasFigures: bool = False
    pageCount: int | None = None
    charCount: int = 0
    chunkCount: int = 0
    fileSize: int | None = None
    downloadedAt: str | None = None
    isProcessing: bool = False


class StandardProcessingDto(BaseModel):
    id: str
    sprsId: str
    standardNo: str | None
    name: str
    syncStatus: SyncStatusDto
    attachmentCount: int = 0
    downloadedCount: int = 0
    parsedCount: int = 0
    chunkedCount: int = 0
    totalChunks: int = 0
    updatedAt: str | None = None
    isProcessing: bool = False
    attachments: list[AttachmentProcessingDto] = Field(default_factory=list)


class ProcessingPageResult(BaseModel):
    items: list[StandardProcessingDto]
    total: int
    page: int
    pageSize: int


class ProcessingActionResult(BaseModel):
    action: ProcessingActionDto
    targetId: str
    queued: int = 0
    message: str


class ExtractedFigureAssetDto(BaseModel):
    fileName: str
    previewUrl: str
    storageKey: str | None = None
    pageNo: int | None = None
    captions: list[str] = Field(default_factory=list)


class AttachmentExtractedTextDto(BaseModel):
    attachmentId: str
    fileName: str
    fileType: str
    content: str
    contentFormat: Literal["markdown", "plain"] = "markdown"
    charCount: int
    parseEngine: str | None = None
    parseQuality: ParseQualityDto | None = None
    hasTables: bool = False
    hasFigures: bool = False
    pageCount: int | None = None
    figureAssets: list[ExtractedFigureAssetDto] = Field(default_factory=list)
    extractedAt: str | None = None


ChunkTypeDto = Literal["clause", "table", "figure", "appendix", "preamble"]
DocRoleDto = Literal["body", "explanation", "draft"]
ClauseLevelDto = Literal["chapter", "section", "clause", "appendix"]


class TextChunkDto(BaseModel):
    id: str
    chunkIndex: int
    chunkType: ChunkTypeDto
    docRole: DocRoleDto
    content: str
    positionLabel: str | None = None
    clauseLevel: ClauseLevelDto | None = None
    parentLabel: str | None = None
    pageStart: int | None = None
    pageEnd: int | None = None
    tableCaption: str | None = None
    figureCaption: str | None = None
    contentJson: dict | None = None
    tokenCount: int | None = None
    indexVersion: int = 1
    createdAt: str | None = None


class AttachmentChunksDto(BaseModel):
    attachmentId: str
    fileName: str
    total: int
    indexVersion: int | None = None
    byType: dict[str, int] = Field(default_factory=dict)
    chunks: list[TextChunkDto] = Field(default_factory=list)
