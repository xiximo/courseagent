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
    _ensure_kb_chunk_columns(engine)

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


def _ensure_kb_chunk_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "course_agent_knowledge_base" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("course_agent_knowledge_base")}
    statements = []
    if "chunk_mode" not in cols:
        statements.append(
            "ALTER TABLE course_agent_knowledge_base "
            "ADD COLUMN IF NOT EXISTS chunk_mode VARCHAR(16) DEFAULT 'size'"
        )
    if "chunk_max_chars" not in cols:
        statements.append(
            "ALTER TABLE course_agent_knowledge_base "
            "ADD COLUMN IF NOT EXISTS chunk_max_chars INTEGER DEFAULT 1800"
        )
    if "chunk_overlap_chars" not in cols:
        statements.append(
            "ALTER TABLE course_agent_knowledge_base "
            "ADD COLUMN IF NOT EXISTS chunk_overlap_chars INTEGER DEFAULT 200"
        )
    if not statements:
        return
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
    logger.info("Knowledge base chunk columns ensured")


def ensure_platform_model_schema(engine: Engine) -> None:
    _drop_agent_fk_and_nullable(engine, "course_agent_model")
    logger.info("Platform model schema ensured")


def ensure_platform_resource_schema(engine: Engine) -> None:
    ensure_platform_knowledge_base_schema(engine)
    ensure_platform_model_schema(engine)
    ensure_lead_schema(engine)
    ensure_user_profile_schema(engine)
    ensure_session_owner_schema(engine)
    ensure_billing_schema(engine)
    ensure_tenant_schema(engine)
    ensure_resource_tenant_schema(engine)


def ensure_tenant_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "user_account" not in tables:
        return
    with engine.begin() as conn:
        if "tenant" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tenant (
                        id UUID PRIMARY KEY,
                        name VARCHAR(128) NOT NULL,
                        slug VARCHAR(64) NOT NULL UNIQUE,
                        plan_code VARCHAR(16) NOT NULL DEFAULT 'free',
                        plan_upgraded_at TIMESTAMPTZ NULL,
                        chat_count INTEGER NOT NULL DEFAULT 0,
                        usage_year_month VARCHAR(7) NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
            )
            logger.info("Created tenant table")
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("user_account")}
        if "tenant_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_account "
                    "ADD COLUMN IF NOT EXISTS tenant_id UUID NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_account_tenant_id "
                    "ON user_account (tenant_id)"
                )
            )
            try:
                conn.execute(
                    text(
                        "ALTER TABLE user_account "
                        "ADD CONSTRAINT fk_user_account_tenant "
                        "FOREIGN KEY (tenant_id) REFERENCES tenant(id) "
                        "ON DELETE SET NULL"
                    )
                )
            except Exception:
                logger.exception("Could not add user_account.tenant_id FK")
            logger.info("Added user_account.tenant_id")
    _ensure_tenant_plan_columns(engine)
    logger.info("Tenant schema ensured")


def _ensure_tenant_plan_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "tenant" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tenant")}
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "plan_code" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE tenant "
                    "ADD COLUMN IF NOT EXISTS plan_code VARCHAR(16) "
                    "DEFAULT 'free'"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_tenant_plan_code "
                    "ON tenant (plan_code)"
                )
            )
            logger.info("Added tenant.plan_code")
        if "plan_upgraded_at" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE tenant "
                    "ADD COLUMN IF NOT EXISTS plan_upgraded_at TIMESTAMPTZ NULL"
                )
            )
            logger.info("Added tenant.plan_upgraded_at")
        if "chat_count" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE tenant "
                    "ADD COLUMN IF NOT EXISTS chat_count INTEGER DEFAULT 0"
                )
            )
            logger.info("Added tenant.chat_count")
        if "usage_year_month" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE tenant "
                    "ADD COLUMN IF NOT EXISTS usage_year_month VARCHAR(7) NULL"
                )
            )
            logger.info("Added tenant.usage_year_month")
        if "user_account" in tables:
            conn.execute(
                text(
                    """
                    UPDATE tenant t
                    SET plan_code = 'pro',
                        plan_upgraded_at = COALESCE(
                            t.plan_upgraded_at,
                            (
                                SELECT MAX(u.plan_upgraded_at)
                                FROM user_account u
                                WHERE u.tenant_id = t.id
                                  AND u.plan_code = 'pro'
                            )
                        )
                    WHERE COALESCE(t.plan_code, 'free') <> 'pro'
                      AND EXISTS (
                        SELECT 1
                        FROM user_account u
                        WHERE u.tenant_id = t.id
                          AND u.plan_code = 'pro'
                      )
                    """
                )
            )
        if "usage_monthly" in tables and "user_account" in tables:
            conn.execute(
                text(
                    """
                    UPDATE tenant t
                    SET chat_count = src.used,
                        usage_year_month = to_char(timezone('UTC', now()), 'YYYY-MM')
                    FROM (
                        SELECT u.tenant_id AS tenant_id,
                               COALESCE(SUM(um.chat_count), 0) AS used
                        FROM usage_monthly um
                        JOIN user_account u ON u.id = um.user_id
                        WHERE u.tenant_id IS NOT NULL
                          AND um.year_month = to_char(timezone('UTC', now()), 'YYYY-MM')
                        GROUP BY u.tenant_id
                    ) src
                    WHERE t.id = src.tenant_id
                      AND t.usage_year_month IS NULL
                      AND COALESCE(t.chat_count, 0) = 0
                      AND src.used > 0
                    """
                )
            )
    logger.info("Tenant plan columns ensured")


def ensure_resource_tenant_schema(engine: Engine) -> None:
    for table in ("course_agent", "course_agent_knowledge_base"):
        _ensure_tenant_id_column(engine, table)
    logger.info("Resource tenant schema ensured")


def _ensure_tenant_id_column(engine: Engine, table: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(table)}
    if "tenant_id" in cols:
        return
    fk_name = f"fk_{table}_tenant"
    with engine.begin() as conn:
        conn.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id UUID NULL")
        )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
                f"ON {table} (tenant_id)"
            )
        )
        try:
            conn.execute(
                text(
                    f'ALTER TABLE {table} ADD CONSTRAINT {fk_name} '
                    f"FOREIGN KEY (tenant_id) REFERENCES tenant(id) "
                    "ON DELETE SET NULL"
                )
            )
        except Exception:
            logger.exception("Could not add %s.tenant_id FK", table)
        logger.info("Added %s.tenant_id", table)


def ensure_billing_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "user_account" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("user_account")}
    with engine.begin() as conn:
        if "plan_code" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_account "
                    "ADD COLUMN IF NOT EXISTS plan_code VARCHAR(16) "
                    "DEFAULT 'free'"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_account_plan_code "
                    "ON user_account (plan_code)"
                )
            )
            logger.info("Added user_account.plan_code")
        if "plan_upgraded_at" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_account "
                    "ADD COLUMN IF NOT EXISTS plan_upgraded_at TIMESTAMPTZ NULL"
                )
            )
            logger.info("Added user_account.plan_upgraded_at")
        if "billing_order" in inspector.get_table_names():
            order_cols = {c["name"] for c in inspector.get_columns("billing_order")}
            if "channel" not in order_cols:
                conn.execute(
                    text(
                        "ALTER TABLE billing_order "
                        "ADD COLUMN IF NOT EXISTS channel VARCHAR(16) "
                        "DEFAULT 'alipay'"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_billing_order_channel "
                        "ON billing_order (channel)"
                    )
                )
                logger.info("Added billing_order.channel")
            if "provider_trade_no" not in order_cols:
                conn.execute(
                    text(
                        "ALTER TABLE billing_order "
                        "ADD COLUMN IF NOT EXISTS provider_trade_no VARCHAR(64) NULL"
                    )
                )
                logger.info("Added billing_order.provider_trade_no")
    logger.info("Billing schema ensured")


def ensure_session_owner_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "course_agent_session" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("course_agent_session")}
    if "user_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE course_agent_session "
                "ADD COLUMN IF NOT EXISTS user_id UUID NULL"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_course_agent_session_user_id "
                "ON course_agent_session (user_id)"
            )
        )
        try:
            conn.execute(
                text(
                    "ALTER TABLE course_agent_session "
                    "ADD CONSTRAINT fk_course_agent_session_user "
                    "FOREIGN KEY (user_id) REFERENCES user_account(id) "
                    "ON DELETE SET NULL"
                )
            )
        except Exception:
            logger.exception(
                "Could not add course_agent_session.user_id FK; continuing without it"
            )
    logger.info("Added course_agent_session.user_id")


def ensure_user_profile_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "user_account" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("user_account")}
    if "profile_json" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE user_account "
                "ADD COLUMN IF NOT EXISTS profile_json JSONB DEFAULT '{}'::jsonb"
            )
        )
    logger.info("Added user_account.profile_json")


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
