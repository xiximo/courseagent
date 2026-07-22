from typing import Literal

from pydantic import BaseModel, Field

AuthTypeDto = Literal["token", "basic"]


class SprsConfigDto(BaseModel):
    baseUrl: str
    authType: AuthTypeDto
    authSecretMasked: str
    timeoutSeconds: int = Field(ge=5, le=300)
    pageSize: int = Field(ge=1, le=200)
    maxPages: int = Field(
        default=0,
        ge=0,
        le=9999,
        description="0 表示不限制，拉取 SPRS 返回的全部页数",
    )
    syncCron: str
    indexBatchSize: int = Field(ge=50, le=1000)
    defaultStandType: str = "INLAND"
    downloadAttachments: bool = True


class UpdateSprsConfigBody(BaseModel):
    baseUrl: str | None = None
    authType: AuthTypeDto | None = None
    authSecret: str | None = None
    timeoutSeconds: int | None = Field(default=None, ge=5, le=300)
    pageSize: int | None = Field(default=None, ge=1, le=200)
    maxPages: int | None = Field(default=None, ge=0, le=9999)
    syncCron: str | None = None
    indexBatchSize: int | None = Field(default=None, ge=50, le=1000)
    defaultStandType: str | None = None
    downloadAttachments: bool | None = None
