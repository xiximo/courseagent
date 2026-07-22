from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.harness_platform_config import HarnessPlatformConfigRecord
from app.schemas.harness import ModelRoutingConfigDto, OrchestrationConfigDto

DEFAULT_ORCHESTRATION: dict = {
    "maxIterations": 5,
    "turnTimeoutSeconds": 10,
    "parallelTools": True,
    "citationGateEnabled": True,
    "noEvidenceTemplate": "当前知识库未找到足够依据，建议人工复核",
}

DEFAULT_FAST_PATH_RULES: list[str] = [
    "单句 FAQ 且无草案上下文",
    "意图分类 confidence > 0.85",
    "仅涉及单一标准编号查询",
]

DEFAULT_PROFILE_OVERRIDES: dict[str, str] = {
    "employee-review": "gpt-4.1",
    "employee-fast": "gpt-4.1-nano",
}


def _default_model_routing() -> dict:
    env = get_settings()
    default_model = env.doubao_model_name or "gpt-4.1-mini"
    return {
        "defaultModel": default_model,
        "fastPathModel": "gpt-4.1-nano",
        "fastPathRules": list(DEFAULT_FAST_PATH_RULES),
        "profileOverrides": dict(DEFAULT_PROFILE_OVERRIDES),
    }


def get_or_create_harness_platform_config(db: Session) -> HarnessPlatformConfigRecord:
    record = db.get(HarnessPlatformConfigRecord, 1)
    if record is not None:
        return record

    record = HarnessPlatformConfigRecord(
        id=1,
        orchestration=dict(DEFAULT_ORCHESTRATION),
        model_routing=_default_model_routing(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _merge_defaults(stored: dict, defaults: dict) -> dict:
    merged = dict(defaults)
    merged.update(stored or {})
    return merged


def to_orchestration_dto(record: HarnessPlatformConfigRecord) -> OrchestrationConfigDto:
    data = _merge_defaults(record.orchestration or {}, DEFAULT_ORCHESTRATION)
    return OrchestrationConfigDto.model_validate(data)


def to_model_routing_dto(record: HarnessPlatformConfigRecord) -> ModelRoutingConfigDto:
    data = _merge_defaults(record.model_routing or {}, _default_model_routing())
    return ModelRoutingConfigDto.model_validate(data)


def update_orchestration(
    db: Session,
    record: HarnessPlatformConfigRecord,
    patch: dict,
    updated_by: str | None = None,
) -> HarnessPlatformConfigRecord:
    current = _merge_defaults(record.orchestration or {}, DEFAULT_ORCHESTRATION)
    current.update(patch)
    record.orchestration = current
    if updated_by:
        record.updated_by = updated_by
    db.commit()
    db.refresh(record)
    return record


def update_model_routing(
    db: Session,
    record: HarnessPlatformConfigRecord,
    patch: dict,
    updated_by: str | None = None,
) -> HarnessPlatformConfigRecord:
    current = _merge_defaults(record.model_routing or {}, _default_model_routing())
    current.update(patch)
    record.model_routing = current
    if updated_by:
        record.updated_by = updated_by
    db.commit()
    db.refresh(record)
    return record
