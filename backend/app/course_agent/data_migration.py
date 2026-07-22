"""将 config_json 中的知识库 / 模型配置迁移到独立表。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.course_agent import CourseAgentRecord
from app.db.models.course_agent_resources import (
    CourseAgentKnowledgeBaseRecord,
    CourseAgentModelRecord,
)
from app.db.models.standard import Standard, StandardSyncStatus

logger = logging.getLogger(__name__)

LEGACY_BUILTIN_MATERIAL_LABELS = frozenset(
    {"material_a", "material_b", "material_c"}
)


def migrate_all_agents_from_config_json(db: Session) -> None:
    rows = db.scalars(select(CourseAgentRecord)).all()
    for row in rows:
        migrate_agent_from_config_json(db, row.agent_id)
    db.commit()


def migrate_agent_from_config_json(db: Session, agent_id: str) -> None:
    row = db.get(CourseAgentRecord, agent_id)
    if row is None:
        return

    cfg = dict(row.config_json or {})
    changed = False

    if _migrate_knowledge_bases(db, row, cfg):
        changed = True
    if _migrate_models(db, row, cfg):
        changed = True

    if changed:
        cfg.pop("knowledgeBases", None)
        cfg.pop("models", None)
        cfg.pop("activeModelId", None)
        # 保留 runtime 快照 cfg["model"]，但不再据此落表
        row.config_json = cfg
        row.updated_at = datetime.now(UTC)
        db.flush()


def _migrate_knowledge_bases(db: Session, row: CourseAgentRecord, cfg: dict) -> bool:
    raw_kbs = cfg.get("knowledgeBases")
    if not raw_kbs:
        return False

    existing_ids = set(
        db.scalars(
            select(CourseAgentKnowledgeBaseRecord.id).where(
                CourseAgentKnowledgeBaseRecord.agent_id == row.agent_id
            )
        ).all()
    )
    migrated = False

    for index, kb in enumerate(raw_kbs):
        if not isinstance(kb, dict):
            continue
        material_label = str(kb.get("materialLabel") or "").strip()
        if not material_label or material_label in LEGACY_BUILTIN_MATERIAL_LABELS:
            continue

        kb_id = str(kb.get("id") or f"kb_{material_label}")
        if kb_id in existing_ids:
            continue

        standard_id = _resolve_standard_id(db, row.agent_id, material_label, kb)
        if standard_id is None:
            continue

        db.add(
            CourseAgentKnowledgeBaseRecord(
                id=kb_id,
                agent_id=row.agent_id,
                material_label=material_label,
                name=str(kb.get("name") or material_label),
                description=str(kb.get("description") or ""),
                role=str(kb.get("role") or ""),
                standard_id=standard_id,
                status=str(kb.get("status") or "ready"),
                sort_order=index,
            )
        )
        existing_ids.add(kb_id)
        migrated = True

    return migrated


def _resolve_standard_id(
    db: Session, agent_id: str, material_label: str, kb: dict
) -> uuid.UUID | None:
    raw = kb.get("standardId")
    if raw:
        try:
            standard_id = uuid.UUID(str(raw))
            if db.get(Standard, standard_id) is not None:
                return standard_id
        except ValueError:
            pass

    sprs_id = f"course-agent:{agent_id}:{material_label}"
    standard = db.scalar(select(Standard).where(Standard.sprs_id == sprs_id))
    if standard is not None:
        return standard.id

    name = str(kb.get("name") or material_label)
    standard = Standard(
        sprs_id=sprs_id,
        stand_type="COURSE_AGENT",
        name=f"{agent_id} · {name}",
        sync_status=StandardSyncStatus.not_synced,
    )
    db.add(standard)
    db.flush()
    return standard.id


def _migrate_models(db: Session, row: CourseAgentRecord, cfg: dict) -> bool:
    """仅迁移显式的 models 列表；不再把运行时 model 快照落成「默认模型」。"""
    raw_models = cfg.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        return False

    items = [m for m in raw_models if isinstance(m, dict)]
    if not items:
        return False

    active_id = cfg.get("activeModelId")
    existing_ids = set(
        db.scalars(
            select(CourseAgentModelRecord.id).where(
                CourseAgentModelRecord.agent_id == row.agent_id
            )
        ).all()
    )
    # 同时按全局 id 去重，避免删库后因同一 id 反复插入
    global_ids = set(db.scalars(select(CourseAgentModelRecord.id)).all())
    migrated = False

    for index, item in enumerate(items):
        model_id = str(item.get("id") or f"mdl_{uuid.uuid4().hex[:8]}")
        if model_id in existing_ids or model_id in global_ids:
            continue

        is_active = model_id == active_id or (
            active_id is None and index == 0 and len(items) == 1
        )
        db.add(
            CourseAgentModelRecord(
                id=model_id,
                agent_id=None,  # 平台资源，不挂靠 Agent
                name=str(item.get("name") or "模型配置"),
                description=str(item.get("description") or ""),
                provider=str(item.get("provider") or "doubao"),
                stream=bool(item.get("stream", False)),
                model_name=str(item.get("modelName") or ""),
                endpoint_id=str(item.get("endpointId") or ""),
                api_key=str(item.get("apiKey") or ""),
                base_url=str(item.get("baseUrl") or ""),
                is_active=is_active,
                sort_order=index,
            )
        )
        existing_ids.add(model_id)
        global_ids.add(model_id)
        migrated = True

    if migrated and active_id:
        db.flush()
        _ensure_single_active_model(db, str(active_id))

    return migrated


def _ensure_single_active_model(db: Session, active_id: str) -> None:
    rows = db.scalars(select(CourseAgentModelRecord)).all()
    found = False
    for row in rows:
        row.is_active = row.id == active_id
        if row.is_active:
            found = True
    if not found and rows:
        rows[0].is_active = True
