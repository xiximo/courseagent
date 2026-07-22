from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models.llm_config import LlmConfigRecord


def get_or_create_llm_config(db: Session) -> LlmConfigRecord:
    record = db.get(LlmConfigRecord, 1)
    if record is not None:
        return record

    env = get_settings()
    record = LlmConfigRecord(
        id=1,
        enabled=env.llm_enabled,
        provider="doubao",
        model_name=env.doubao_model_name,
        endpoint_id=env.doubao_endpoint_id,
        api_key=env.doubao_api_key,
        base_url=env.doubao_base_url,
        timeout_seconds=env.llm_timeout_seconds,
        qa_top_k=env.qa_retrieval_top_k,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def mask_secret(secret: str) -> str:
    if not secret:
        return "（未配置）"
    if len(secret) <= 4:
        return "****"
    return f"{secret[:2]}****{secret[-2:]}"


def is_llm_configured(record: LlmConfigRecord) -> bool:
    return bool(record.enabled and record.api_key.strip() and record.endpoint_id.strip())


def resolve_llm_runtime(record: LlmConfigRecord, env: Settings | None = None) -> LlmConfigRecord:
    """空字段回落到环境变量。"""
    env = env or get_settings()
    if not record.model_name.strip():
        record.model_name = env.doubao_model_name
    if not record.endpoint_id.strip():
        record.endpoint_id = env.doubao_endpoint_id
    if not record.api_key.strip():
        record.api_key = env.doubao_api_key
    if not record.base_url.strip():
        record.base_url = env.doubao_base_url
    if record.timeout_seconds <= 0:
        record.timeout_seconds = env.llm_timeout_seconds
    if record.qa_top_k <= 0:
        record.qa_top_k = env.qa_retrieval_top_k
    return record
