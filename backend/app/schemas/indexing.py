from typing import Literal

from pydantic import BaseModel, Field


SearchModeDto = Literal["keyword", "semantic", "hybrid"]


class ChunkSearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: SearchModeDto = "hybrid"
    topK: int = Field(default=10, ge=1, le=50)
    standardId: str | None = None
    attachmentId: str | None = None
    chunkType: str | None = None
    docRole: str | None = None


class ChunkSearchHitDto(BaseModel):
    chunkId: str
    attachmentId: str
    standardId: str
    chunkType: str | None = None
    docRole: str | None = None
    positionLabel: str | None = None
    content: str | None = None
    score: float | None = None
    source: str | None = None
    fileName: str | None = None


class ChunkSearchResultDto(BaseModel):
    query: str
    mode: SearchModeDto
    elapsedSec: float = 0.0
    hits: list[ChunkSearchHitDto] = Field(default_factory=list)
