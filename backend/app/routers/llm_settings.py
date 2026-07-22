from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.llm import LlmConfigDto, UpdateLlmConfigBody
from app.services.llm_settings import (
    get_or_create_llm_config,
    is_llm_configured,
    mask_secret,
    resolve_llm_runtime,
)

router = APIRouter(prefix="/api/v1/qibiao/settings/llm", tags=["qibiao-settings-llm"])


def _to_dto(record) -> LlmConfigDto:
    resolved = resolve_llm_runtime(record)
    return LlmConfigDto(
        enabled=resolved.enabled,
        provider=resolved.provider,
        modelName=resolved.model_name,
        endpointId=resolved.endpoint_id,
        apiKeyMasked=mask_secret(resolved.api_key),
        baseUrl=resolved.base_url,
        timeoutSeconds=resolved.timeout_seconds,
        qaTopK=resolved.qa_top_k,
        configured=is_llm_configured(resolved),
    )


@router.get("", response_model=ApiResponse[LlmConfigDto])
def get_llm_config(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_llm_config(db)
    return success(_to_dto(record))


@router.put("", response_model=ApiResponse[LlmConfigDto])
def update_llm_config(
    body: UpdateLlmConfigBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_llm_config(db)
    data = body.model_dump(exclude_unset=True)

    field_map = {
        "enabled": "enabled",
        "modelName": "model_name",
        "endpointId": "endpoint_id",
        "apiKey": "api_key",
        "baseUrl": "base_url",
        "timeoutSeconds": "timeout_seconds",
        "qaTopK": "qa_top_k",
    }
    for key, value in data.items():
        setattr(record, field_map[key], value)

    db.commit()
    db.refresh(record)
    return success(_to_dto(record))
