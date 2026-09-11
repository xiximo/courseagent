"""Harness 定时任务：调用 update_user_profile 从历史发言归纳画像。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.course_agent import CourseAgentRecord

logger = logging.getLogger(__name__)

DEFAULT_TASK_PROMPT = (
    "只根据用户自己发送的消息归纳目标、疾病、过敏、忌口；"
    "没有新事实不要改画像，不要编造未提及的健康状况。"
)


def _as_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if number != number:
        number = default
    return max(min_value, min(number, max_value))


def normalize_schedule(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    run_mode = data.get("runMode") if data.get("runMode") in ("chat", "scheduled") else "chat"
    visible = data.get("visibleInChat")
    if visible is None:
        visible = run_mode != "scheduled"
    target = data.get("target") if data.get("target") in ("all_users", "members") else "all_users"
    prompt = str(data.get("taskPrompt") or DEFAULT_TASK_PROMPT).strip() or DEFAULT_TASK_PROMPT
    last_run = data.get("lastRunAt")
    last_note = str(data.get("lastRunNote") or "").strip() or None
    return {
        "enabled": bool(data.get("enabled")),
        "intervalHours": _as_float(data.get("intervalHours"), 2, 0.05, 168),
        "runMode": run_mode,
        "visibleInChat": bool(visible),
        "target": target,
        "onlyIfNewMessages": bool(data.get("onlyIfNewMessages", True)),
        "lookbackHours": _as_float(data.get("lookbackHours"), 24, 1, 720),
        "taskPrompt": prompt,
        "lastRunAt": str(last_run).strip() if last_run else None,
        "lastRunNote": last_note,
    }


def is_visible_in_chat(cfg: dict[str, Any] | None) -> bool:
    schedule = normalize_schedule((cfg or {}).get("schedule"))
    return bool(schedule["visibleInChat"])


def force_chat_only_schedule(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Harness 不再提供定时任务配置，统一为对话可见、不自动执行。"""
    data = normalize_schedule(raw)
    data["enabled"] = False
    data["runMode"] = "chat"
    data["visibleInChat"] = True
    return data


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _due(schedule: dict[str, Any], now: datetime) -> bool:
    last = _parse_iso(schedule.get("lastRunAt"))
    if last is None:
        return True
    delta = timedelta(hours=float(schedule["intervalHours"]))
    return now >= last + delta


def run_scheduled_agent(
    db: Session, agent: CourseAgentRecord, *, now: datetime | None = None
) -> dict[str, Any]:
    from app.course_agent.profile_tools import execute_update_profile

    cfg = dict(agent.config_json or {})
    schedule = normalize_schedule(cfg.get("schedule"))
    now = now or datetime.now(UTC)
    note = execute_update_profile(
        db,
        user_id=None,
        session=None,
        agent_id=agent.agent_id,
        args={
            "scope": "all_users",
            "fromHistory": True,
            "lookbackHours": schedule["lookbackHours"],
            "target": schedule["target"],
            "onlyIfNewMessages": schedule["onlyIfNewMessages"],
            "instruction": schedule["taskPrompt"],
        },
    )
    schedule["lastRunAt"] = now.isoformat()
    schedule["lastRunNote"] = note.split("\n", 1)[0][:240]
    cfg["schedule"] = schedule
    agent.config_json = cfg
    db.add(agent)
    db.commit()
    logger.info("Scheduled harness %s finished: %s", agent.agent_id, schedule["lastRunNote"])
    return schedule


def run_due_harness_jobs(db: Session, *, now: datetime | None = None) -> int:
    del db, now
    return 0
