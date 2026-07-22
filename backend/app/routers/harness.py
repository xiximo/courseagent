from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.harness import (
    ActivateSkillBody,
    AgentSkillDto,
    ModelRoutingConfigDto,
    OrchestrationConfigDto,
    UpdateModelRoutingConfigBody,
    UpdateOrchestrationConfigBody,
)
from app.services.harness_platform_config import (
    get_or_create_harness_platform_config,
    to_model_routing_dto,
    to_orchestration_dto,
    update_model_routing,
    update_orchestration,
)
from app.services.harness_skills import activate_skill_version, get_skill, list_skills

router = APIRouter(prefix="/api/v1/qibiao/harness", tags=["qibiao-harness"])


@router.get("/defaults", response_model=ApiResponse[OrchestrationConfigDto])
def get_harness_defaults(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_harness_platform_config(db)
    return success(to_orchestration_dto(record))


@router.put("/defaults", response_model=ApiResponse[OrchestrationConfigDto])
def update_harness_defaults(
    body: UpdateOrchestrationConfigBody,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_harness_platform_config(db)
    patch = body.model_dump(exclude_unset=True)
    record = update_orchestration(db, record, patch, updated_by=user.username)
    return success(to_orchestration_dto(record))


@router.get("/models", response_model=ApiResponse[ModelRoutingConfigDto])
def get_harness_models(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_harness_platform_config(db)
    return success(to_model_routing_dto(record))


@router.put("/models", response_model=ApiResponse[ModelRoutingConfigDto])
def update_harness_models(
    body: UpdateModelRoutingConfigBody,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_or_create_harness_platform_config(db)
    patch = body.model_dump(exclude_unset=True)
    record = update_model_routing(db, record, patch, updated_by=user.username)
    return success(to_model_routing_dto(record))


@router.get("/skills", response_model=ApiResponse[list[AgentSkillDto]])
def list_harness_skills(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(list_skills(db))


@router.get("/skills/{skill_id}", response_model=ApiResponse[AgentSkillDto])
def get_harness_skill(
    skill_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(get_skill(db, skill_id))


@router.post("/skills/{skill_id}/activate", response_model=ApiResponse[AgentSkillDto])
def activate_harness_skill(
    skill_id: str,
    body: ActivateSkillBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(activate_skill_version(db, skill_id, body.version))
