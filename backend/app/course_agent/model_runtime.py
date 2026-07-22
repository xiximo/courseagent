"""解析 Agent 模型 Profile 的运行时豆包连接参数（独立表 → 平台配置 → 环境变量）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.course_agent.model_service import ModelService
from app.db.models.course_agent import CourseAgentRecord
from app.db.models.llm_config import LlmConfigRecord
from app.services.llm_settings import get_or_create_llm_config, resolve_llm_runtime


@dataclass(frozen=True)
class AgentDoubaoRuntime:
    api_key: str
    endpoint_id: str
    base_url: str
    model_name: str
    stream: bool
    timeout_seconds: int
    temperature: float = 0.3

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip() and self.endpoint_id.strip())


def resolve_agent_doubao_runtime(
    db: Session,
    agent_id: str,
    *,
    env: Settings | None = None,
) -> AgentDoubaoRuntime:
    env = env or get_settings()
    platform: LlmConfigRecord = resolve_llm_runtime(get_or_create_llm_config(db), env)
    profile = ModelService(db).get_active_profile_dict(agent_id)

    agent = db.get(CourseAgentRecord, agent_id)
    cfg = dict((agent.config_json if agent else None) or {})
    temperature = float(
        cfg.get("temperature") if cfg.get("temperature") is not None else 0.3
    )

    api_key = (
        str(profile.get("apiKey") or "").strip()
        or platform.api_key.strip()
        or env.doubao_api_key.strip()
    )
    endpoint_id = (
        str(profile.get("endpointId") or "").strip()
        or platform.endpoint_id.strip()
        or env.doubao_endpoint_id.strip()
    )
    base_url = (
        str(profile.get("baseUrl") or "").strip()
        or platform.base_url.strip()
        or env.doubao_base_url.strip()
    )
    model_name = (
        str(profile.get("modelName") or "").strip()
        or platform.model_name.strip()
        or env.doubao_model_name.strip()
    )
    stream = bool(profile.get("stream"))
    timeout_seconds = (
        platform.timeout_seconds if platform.timeout_seconds > 0 else env.llm_timeout_seconds
    )

    return AgentDoubaoRuntime(
        api_key=api_key,
        endpoint_id=endpoint_id,
        base_url=base_url,
        model_name=model_name,
        stream=stream,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
