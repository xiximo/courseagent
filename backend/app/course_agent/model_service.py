"""平台模型配置（独立表 course_agent_model），与 Agent 解耦。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.course_agent.data_migration import migrate_agent_from_config_json
from app.db.models.course_agent import CourseAgentRecord
from app.db.models.course_agent_resources import CourseAgentModelRecord
from app.schemas.course_agent import (
    CourseAgentModelProfileDto,
    CreateCourseModelBody,
    UpdateCourseModelBody,
)
from app.services.llm_settings import mask_secret

RUNTIME_MODEL_KEYS = (
    "provider",
    "stream",
    "modelName",
    "endpointId",
    "baseUrl",
)


def _new_model_id() -> str:
    return f"mdl_{secrets.token_hex(4)}"


def _doubao_defaults() -> dict[str, Any]:
    env = get_settings()
    return {
        "provider": "doubao",
        "stream": False,
        "modelName": env.doubao_model_name,
        "endpointId": env.doubao_endpoint_id,
        "apiKey": "",
        "baseUrl": env.doubao_base_url,
    }


def _default_runtime_model() -> dict[str, Any]:
    defaults = _doubao_defaults()
    return {k: defaults[k] for k in RUNTIME_MODEL_KEYS if k in defaults}


def _record_to_profile_dict(record: CourseAgentModelRecord, *, masked: bool) -> dict:
    key = (record.api_key or "").strip()
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description or "",
        "provider": record.provider,
        "stream": record.stream,
        "modelName": record.model_name,
        "endpointId": record.endpoint_id,
        "apiKey": mask_secret(key) if masked and key else (key if not masked else ""),
        "apiKeyConfigured": bool(key),
        "baseUrl": record.base_url,
        "isActive": bool(record.is_active),
    }


def _profile_from_record(
    record: CourseAgentModelRecord, *, masked: bool = True
) -> CourseAgentModelProfileDto:
    return CourseAgentModelProfileDto.model_validate(
        _record_to_profile_dict(record, masked=masked)
    )


class ModelService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_models(self, agent_id: str) -> list[CourseAgentModelProfileDto]:
        """兼容旧逻辑：仅返回曾归属该 Agent 的模型。"""
        self._ensure_migrated(agent_id)
        rows = self._list_model_rows(agent_id)
        return [_profile_from_record(row) for row in rows]

    def list_all_models(self) -> list[CourseAgentModelProfileDto]:
        rows = self.db.scalars(
            select(CourseAgentModelRecord).order_by(
                CourseAgentModelRecord.updated_at.desc()
            )
        ).all()
        return [_profile_from_record(row) for row in rows]

    def create_model(
        self, body: CreateCourseModelBody, *, agent_id: str | None = None
    ) -> CourseAgentModelProfileDto:
        defaults = _doubao_defaults()
        total = self.db.scalar(select(func.count()).select_from(CourseAgentModelRecord)) or 0
        set_active = body.setAsActive or int(total) == 0

        if set_active:
            self._deactivate_all()

        record = CourseAgentModelRecord(
            id=_new_model_id(),
            agent_id=agent_id,
            name=body.name.strip(),
            description=body.description.strip(),
            provider=body.provider or defaults["provider"],
            stream=body.stream if body.stream is not None else defaults["stream"],
            model_name=body.modelName or defaults["modelName"],
            endpoint_id=body.endpointId or defaults["endpointId"],
            api_key=(body.apiKey or "").strip(),
            base_url=body.baseUrl or defaults["baseUrl"],
            is_active=set_active,
            sort_order=int(total),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return _profile_from_record(record)

    def update_model(
        self, model_id: str, body: UpdateCourseModelBody
    ) -> CourseAgentModelProfileDto:
        record = self._get_model_by_id(model_id)
        if body.name is not None:
            record.name = body.name.strip()
        if body.description is not None:
            record.description = body.description.strip()
        if body.provider is not None:
            record.provider = body.provider
        if body.stream is not None:
            record.stream = body.stream
        if body.modelName is not None:
            record.model_name = body.modelName
        if body.endpointId is not None:
            record.endpoint_id = body.endpointId
        if body.baseUrl is not None:
            record.base_url = body.baseUrl
        if body.apiKey is not None and body.apiKey.strip():
            record.api_key = body.apiKey.strip()
        if body.setAsActive:
            self._deactivate_all()
            record.is_active = True

        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return _profile_from_record(record)

    def delete_model(self, model_id: str) -> dict[str, str]:
        record = self._get_model_by_id(model_id)
        was_active = record.is_active
        self.db.delete(record)
        self.db.flush()

        if was_active:
            remaining = self.db.scalars(
                select(CourseAgentModelRecord).order_by(
                    CourseAgentModelRecord.sort_order,
                    CourseAgentModelRecord.created_at,
                )
            ).first()
            if remaining is not None:
                remaining.is_active = True

        self.db.commit()
        return {"message": "模型配置已删除"}

    def set_active_model(self, model_id: str) -> CourseAgentModelProfileDto:
        record = self._get_model_by_id(model_id)
        self._deactivate_all()
        record.is_active = True
        record.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(record)
        return _profile_from_record(record)

    def get_active_profile_dict(self, agent_id: str) -> dict[str, Any]:
        self._ensure_migrated(agent_id)
        row = self._get_agent(agent_id)
        cfg = dict(row.config_json or {})
        bound_ids = [
            str(item)
            for item in (cfg.get("boundModelIds") or [])
            if str(item).strip()
        ]
        record = None
        if bound_ids:
            for model_id in bound_ids:
                candidate = self.db.get(CourseAgentModelRecord, model_id)
                if candidate is not None:
                    record = candidate
                    break
        if record is None:
            record = self._get_active_model_row(agent_id)
        if record is None:
            record = self.db.scalar(
                select(CourseAgentModelRecord).where(
                    CourseAgentModelRecord.is_active.is_(True)
                )
            )
        if record is None:
            return {**_default_runtime_model(), "apiKey": ""}
        return _record_to_profile_dict(record, masked=False)

    def get_active_model_id(self, agent_id: str) -> str | None:
        record = self._get_active_model_row(agent_id)
        if record is not None:
            return record.id
        global_active = self.db.scalar(
            select(CourseAgentModelRecord).where(
                CourseAgentModelRecord.is_active.is_(True)
            )
        )
        return global_active.id if global_active else None

    def get_runtime_model(self, agent_id: str) -> dict[str, Any]:
        profile = self.get_active_profile_dict(agent_id)
        return {k: profile[k] for k in RUNTIME_MODEL_KEYS if k in profile}

    def sync_runtime_snapshot(self, agent_id: str) -> None:
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is None:
            return
        cfg = dict(row.config_json or {})
        cfg["model"] = self.get_runtime_model(agent_id)
        cfg["activeModelId"] = self.get_active_model_id(agent_id)
        cfg.pop("models", None)
        row.config_json = cfg
        row.updated_at = datetime.now(UTC)
        self.db.commit()

    def _ensure_migrated(self, agent_id: str) -> None:
        migrate_agent_from_config_json(self.db, agent_id)
        self.db.commit()

    def _list_model_rows(self, agent_id: str) -> list[CourseAgentModelRecord]:
        return list(
            self.db.scalars(
                select(CourseAgentModelRecord)
                .where(CourseAgentModelRecord.agent_id == agent_id)
                .order_by(
                    CourseAgentModelRecord.sort_order,
                    CourseAgentModelRecord.created_at,
                )
            ).all()
        )

    def _get_active_model_row(self, agent_id: str) -> CourseAgentModelRecord | None:
        active = self.db.scalar(
            select(CourseAgentModelRecord).where(
                CourseAgentModelRecord.agent_id == agent_id,
                CourseAgentModelRecord.is_active.is_(True),
            )
        )
        if active is not None:
            return active
        rows = self._list_model_rows(agent_id)
        return rows[0] if rows else None

    def _get_model_by_id(self, model_id: str) -> CourseAgentModelRecord:
        record = self.db.get(CourseAgentModelRecord, model_id)
        if record is None:
            raise ApiBusinessError("NOT_FOUND", "模型配置不存在", 404)
        return record

    def _deactivate_all(self) -> None:
        rows = self.db.scalars(select(CourseAgentModelRecord)).all()
        for row in rows:
            row.is_active = False

    def _get_agent(self, agent_id: str) -> CourseAgentRecord:
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is None:
            raise ApiBusinessError("NOT_FOUND", f"Agent {agent_id} 不存在", 404)
        return row
