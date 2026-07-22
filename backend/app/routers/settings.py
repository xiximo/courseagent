from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.settings import SprsConfigDto, UpdateSprsConfigBody
from app.services.sprs_settings import (
    get_or_create_sprs_config,
    mask_secret,
)

router = APIRouter(prefix="/api/v1/qibiao/settings", tags=["qibiao-settings"])


def _to_dto(record) -> SprsConfigDto:
    return SprsConfigDto(
        baseUrl=record.base_url,
        authType=record.auth_type,
        authSecretMasked=mask_secret(record.auth_secret),
        timeoutSeconds=record.timeout_seconds,
        pageSize=record.page_size,
        maxPages=record.max_pages or 0,
        syncCron=record.sync_cron,
        indexBatchSize=record.index_batch_size,
        defaultStandType=record.default_stand_type,
        downloadAttachments=record.download_attachments,
    )


@router.get("", response_model=ApiResponse[SprsConfigDto])
def get_settings_config(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_sprs_config(db)
    return success(_to_dto(record))


@router.put("", response_model=ApiResponse[SprsConfigDto])
def update_settings_config(
    body: UpdateSprsConfigBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_sprs_config(db)
    data = body.model_dump(exclude_unset=True)

    field_map = {
        "baseUrl": "base_url",
        "authType": "auth_type",
        "authSecret": "auth_secret",
        "timeoutSeconds": "timeout_seconds",
        "pageSize": "page_size",
        "maxPages": "max_pages",
        "syncCron": "sync_cron",
        "indexBatchSize": "index_batch_size",
        "defaultStandType": "default_stand_type",
        "downloadAttachments": "download_attachments",
    }
    for key, value in data.items():
        if key == "maxPages" and value == 0:
            value = None
        setattr(record, field_map[key], value)

    db.commit()
    db.refresh(record)
    return success(_to_dto(record))
