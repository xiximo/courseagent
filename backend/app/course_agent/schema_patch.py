"""运行时补丁：知识库 / 模型表与 Agent 解耦（agent_id 可空、去掉外键）。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _drop_agent_fk_and_nullable(engine: Engine, table: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            if "agent_id" not in (fk.get("constrained_columns") or []):
                continue
            name = fk.get("name")
            if not name:
                continue
            conn.execute(
                text(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')
            )
            logger.info("Dropped FK %s on %s", name, table)

        conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN agent_id DROP NOT NULL"))


def ensure_platform_knowledge_base_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "course_agent_knowledge_base" not in inspector.get_table_names():
        return

    _drop_agent_fk_and_nullable(engine, "course_agent_knowledge_base")

    inspector = inspect(engine)
    with engine.begin() as conn:
        uniques = inspector.get_unique_constraints("course_agent_knowledge_base")
        has_material_unique = any(
            u.get("column_names") == ["material_label"] for u in uniques
        )
        if not has_material_unique:
            try:
                conn.execute(
                    text(
                        "ALTER TABLE course_agent_knowledge_base "
                        "ADD CONSTRAINT uq_cakb_material_label UNIQUE (material_label)"
                    )
                )
            except Exception:
                logger.exception(
                    "Could not add uq_cakb_material_label; continuing without it"
                )

    logger.info("Platform knowledge base schema ensured")


def ensure_platform_model_schema(engine: Engine) -> None:
    _drop_agent_fk_and_nullable(engine, "course_agent_model")
    logger.info("Platform model schema ensured")


def ensure_platform_resource_schema(engine: Engine) -> None:
    ensure_platform_knowledge_base_schema(engine)
    ensure_platform_model_schema(engine)
    ensure_lead_schema(engine)


def ensure_lead_schema(engine: Engine) -> None:
    """为已有库补齐线索表字段（create_all 后仍可能缺 lead_id）。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "course_agent_message" in tables:
            cols = {c["name"] for c in inspector.get_columns("course_agent_message")}
            if "lead_id" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE course_agent_message "
                        "ADD COLUMN IF NOT EXISTS lead_id UUID NULL"
                    )
                )
                logger.info("Added course_agent_message.lead_id")
        if "course_agent_lead" in tables and "course_agent_message" in tables:
            fks = inspector.get_foreign_keys("course_agent_message")
            has_lead_fk = any(
                "lead_id" in (fk.get("constrained_columns") or []) for fk in fks
            )
            if not has_lead_fk:
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE course_agent_message "
                            "ADD CONSTRAINT fk_course_agent_message_lead "
                            "FOREIGN KEY (lead_id) REFERENCES course_agent_lead(id) "
                            "ON DELETE SET NULL"
                        )
                    )
                    logger.info("Added FK course_agent_message.lead_id")
                except Exception:
                    logger.exception(
                        "Could not add lead_id FK; continuing without it"
                    )
    logger.info("Course agent lead schema ensured")
