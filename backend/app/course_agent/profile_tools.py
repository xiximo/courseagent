"""登录用户的膳食画像：供 Harness 工具读写。"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.course_agent import (
    CourseAgentMessageRecord,
    CourseAgentSessionRecord,
)
from app.db.models.user import AccountStatus, User
from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, chat_completion

logger = logging.getLogger(__name__)

PROFILE_GET_NAME = "get_user_profile"
PROFILE_UPDATE_NAME = "update_user_profile"
SESSION_PROFILE_KEY = "_userProfile"
ADMIN_ROLES = {"sys_admin", "system_admin", "admin"}

PROFILE_GET_TOOL = {
    "id": "tool_get_profile",
    "name": PROFILE_GET_NAME,
    "kind": "profile_get",
    "description": (
        "获取当前登录用户的画像、目标与约束（疾病、过敏、忌口）。"
        "回答任何膳食方案、蛋白质、热量或食材推荐前必须先调用。"
        "若存在肾病、痛风、过敏等，回答必须避开冲突建议。"
    ),
    "knowledgeBaseIds": [],
    "enabled": True,
}

PROFILE_UPDATE_TOOL = {
    "id": "tool_update_profile",
    "name": PROFILE_UPDATE_NAME,
    "kind": "profile_update",
    "description": (
        "从数据库读取用户发送的消息，调用大模型归纳目标/疾病/过敏/忌口后写入画像。"
        "对话中用户提到新健康事实时必须调用（默认刷新当前用户）。"
        "定时任务可设 scope=all_users，批量刷新全部目标用户。"
        "不要编造用户未说过的疾病或过敏。"
    ),
    "knowledgeBaseIds": [],
    "enabled": True,
}

BUILTIN_PROFILE_TOOLS = [PROFILE_GET_TOOL, PROFILE_UPDATE_TOOL]

EXTRACT_SYSTEM = """你是用户画像归纳器，不是膳食顾问。
根据「用户发送的原话」和当前画像，提取需要写入的增量事实。
只输出一个 JSON 对象，不要 Markdown、不要解释。

字段：
- hasUpdate: 是否有新事实需要写入
- personaLabel: 减脂塑形 / 增肌强化 / 慢病调理，无法判断则省略
- summary: 更新后的画像综述
- goals / constraints / conditions / allergies: 字符串数组，只含本批新识别项（系统会与旧画像合并）
- newFacts: 本批事实的一句话摘要

规则：
1. 只使用用户明确说过的内容，不得编造疾病、过敏、用药。
2. 没有新事实时输出 {"hasUpdate": false}。
3. 不要给出膳食方案或营养建议。"""


def empty_profile() -> dict[str, Any]:
    return {
        "persona": "",
        "personaLabel": "",
        "summary": "",
        "goals": [],
        "constraints": [],
        "conditions": [],
        "allergies": [],
        "sampleQuestions": [],
        "notes": [],
    }


def normalize_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = empty_profile()
    if not isinstance(raw, dict):
        return data
    data["persona"] = str(raw.get("persona") or "").strip()
    data["personaLabel"] = str(raw.get("personaLabel") or "").strip()
    data["summary"] = str(raw.get("summary") or "").strip()
    for key in ("goals", "constraints", "conditions", "allergies", "sampleQuestions", "notes"):
        values = raw.get(key) or []
        if isinstance(values, str):
            values = [values]
        cleaned: list[str] = []
        for item in values:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        data[key] = cleaned
    return data


def _list_arg(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
        return out
    return []


def merge_profile(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    next_profile = normalize_profile(current)
    label = str(patch.get("personaLabel") or "").strip()
    if label:
        next_profile["personaLabel"] = label
        mapping = {
            "减脂": "fat_loss",
            "塑形": "fat_loss",
            "增肌": "muscle_gain",
            "力量": "muscle_gain",
            "慢病": "chronic_care",
            "调理": "chronic_care",
            "血糖": "chronic_care",
            "肾病": "chronic_care",
        }
        for token, persona in mapping.items():
            if token in label:
                next_profile["persona"] = persona
                break
    summary = str(patch.get("summary") or "").strip()
    if summary:
        next_profile["summary"] = summary
    for key in ("goals", "constraints", "conditions", "allergies"):
        added = _list_arg(patch.get(key))
        existing = list(next_profile.get(key) or [])
        for item in added:
            if item not in existing:
                existing.append(item)
        next_profile[key] = existing
    note = str(patch.get("newFacts") or patch.get("notes") or "").strip()
    if note:
        notes = list(next_profile.get("notes") or [])
        if note not in notes:
            notes.append(note)
        next_profile["notes"] = notes[-12:]
    return next_profile


def read_profile(
    db: Session,
    *,
    user_id: UUID | None,
    session: CourseAgentSessionRecord | None = None,
) -> dict[str, Any]:
    if user_id is not None:
        user = db.get(User, user_id)
        if user is not None:
            return normalize_profile(
                user.profile_json if isinstance(user.profile_json, dict) else {}
            )
    if session is not None:
        raw = (session.constraints_json or {}).get(SESSION_PROFILE_KEY)
        return normalize_profile(raw if isinstance(raw, dict) else {})
    return empty_profile()


def write_profile(
    db: Session,
    profile: dict[str, Any],
    *,
    user_id: UUID | None,
    session: CourseAgentSessionRecord | None = None,
) -> None:
    normalized = normalize_profile(profile)
    if user_id is not None:
        user = db.get(User, user_id)
        if user is not None:
            user.profile_json = normalized
            db.add(user)
            db.flush()
            return
    if session is None:
        return
    constraints = dict(session.constraints_json or {})
    constraints[SESSION_PROFILE_KEY] = normalized
    session.constraints_json = constraints
    db.add(session)
    db.flush()


def format_profile_for_tool(
    profile: dict[str, Any],
    *,
    display_name: str = "",
    persisted: bool,
) -> str:
    data = normalize_profile(profile)
    lines = ["当前用户画像："]
    if display_name:
        lines.append(f"- 用户：{display_name}")
    lines.append(f"- 画像类型：{data['personaLabel'] or '未标注'}")
    lines.append(f"- 综述：{data['summary'] or '暂无'}")
    lines.append(f"- 目标：{'；'.join(data['goals']) or '暂无'}")
    lines.append(f"- 约束：{'；'.join(data['constraints']) or '暂无'}")
    lines.append(f"- 健康状况：{'；'.join(data['conditions']) or '未记录'}")
    lines.append(f"- 过敏：{'；'.join(data['allergies']) or '未记录'}")
    if data["notes"]:
        lines.append("- 近期对话摘要：" + "；".join(data["notes"][-4:]))
    if not persisted:
        lines.append("- 说明：当前未登录，画像仅保存在本会话，刷新后不会带到其他账号。")
    blob = " ".join(
        [
            data["personaLabel"],
            data["summary"],
            *data["constraints"],
            *data["conditions"],
            *data["allergies"],
        ]
    )
    warnings: list[str] = []
    if any(token in blob for token in ("肾", "蛋白尿", "透析")):
        warnings.append("肾病相关：禁止推荐高蛋白增肌方案或大量动物蛋白，优先咨询医师。")
    if any(token in blob for token in ("痛风", "尿酸")):
        warnings.append("痛风/高尿酸：避免高嘌呤食材（动物内脏、浓汤、大量海鲜）。")
    if data["allergies"]:
        warnings.append("必须排除过敏原：" + "、".join(data["allergies"]))
    if any(token in blob for token in ("血糖", "糖尿")):
        warnings.append("血糖相关：优先低 GI，避免高糖饮料与精制甜食。")
    if warnings:
        lines.append("安全提示：")
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("安全提示：回答前仍须核对约束，资料不足时不要编造。")
    return "\n".join(lines)


def execute_get_profile(
    db: Session,
    *,
    user_id: UUID | None,
    session: CourseAgentSessionRecord | None,
) -> str:
    display_name = ""
    persisted = False
    if user_id is not None:
        user = db.get(User, user_id)
        if user is not None:
            display_name = user.full_name or user.username
            persisted = True
    profile = read_profile(db, user_id=user_id, session=session)
    return format_profile_for_tool(profile, display_name=display_name, persisted=persisted)


def _is_preview_session(
    *, title: str | None, step: str | None, constraints: dict[str, Any] | None
) -> bool:
    if title == "对话预览" or step == "preview":
        return True
    meta = (constraints or {}).get("_workflow") or {}
    return bool(meta.get("isPreview"))


def _is_admin_user(user: User) -> bool:
    codes = {str(code).lower() for code in (user.role_codes or [])}
    return bool(codes & ADMIN_ROLES)


def _bool_arg(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _has_manual_patch(args: dict[str, Any]) -> bool:
    if str(args.get("personaLabel") or args.get("summary") or args.get("newFacts") or "").strip():
        return True
    for key in ("goals", "constraints", "conditions", "allergies"):
        if _list_arg(args.get(key)):
            return True
    return False


def parse_profile_extract_payload(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {"hasUpdate": False}
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {"hasUpdate": False}
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {"hasUpdate": False}
    if not isinstance(data, dict):
        return {"hasUpdate": False}
    if data.get("hasUpdate") is False:
        return {"hasUpdate": False}
    return data


def load_user_utterances(
    db: Session,
    user_id: UUID,
    *,
    since: datetime | None = None,
    limit: int = 80,
) -> list[str]:
    stmt = (
        select(
            CourseAgentMessageRecord.content,
            CourseAgentSessionRecord.title,
            CourseAgentSessionRecord.step,
            CourseAgentSessionRecord.constraints_json,
        )
        .join(
            CourseAgentSessionRecord,
            CourseAgentSessionRecord.id == CourseAgentMessageRecord.session_id,
        )
        .where(
            CourseAgentSessionRecord.user_id == user_id,
            CourseAgentMessageRecord.role == "user",
        )
        .order_by(CourseAgentMessageRecord.created_at.desc())
        .limit(limit * 2)
    )
    if since is not None:
        stmt = stmt.where(CourseAgentMessageRecord.created_at >= since)
    kept: list[str] = []
    for content, title, step, constraints in db.execute(stmt).all():
        if _is_preview_session(title=title, step=step, constraints=constraints):
            continue
        text = " ".join(str(content or "").split())
        if not text:
            continue
        kept.append(text[:800])
        if len(kept) >= limit:
            break
    kept.reverse()
    return kept


def list_profile_target_users(db: Session, target: str) -> list[User]:
    users = list(
        db.scalars(
            select(User)
            .where(User.status == AccountStatus.enabled)
            .order_by(User.created_at.asc())
        )
    )
    if target == "members":
        return [user for user in users if not _is_admin_user(user)]
    return users


def extract_profile_patch_with_llm(
    db: Session,
    *,
    agent_id: str | None,
    current: dict[str, Any],
    utterances: list[str],
    instruction: str = "",
) -> dict[str, Any]:
    from app.course_agent.model_runtime import resolve_agent_doubao_runtime

    if not utterances:
        return {"hasUpdate": False}
    if not agent_id:
        return {"hasUpdate": False}
    runtime = resolve_agent_doubao_runtime(db, agent_id)
    if not runtime.is_configured:
        logger.warning("Skip profile extract: LLM is not configured")
        return {"hasUpdate": False}

    extra = str(instruction or "").strip()
    system = EXTRACT_SYSTEM
    if extra:
        system += "\n\n额外要求：\n" + extra
    user_blob = "\n".join(f"- {item}" for item in utterances[-80:])
    prompt = (
        "当前画像：\n"
        f"{json.dumps(normalize_profile(current), ensure_ascii=False)}\n\n"
        "用户发送的消息（按时间）：\n"
        f"{user_blob}"
    )
    try:
        text = chat_completion(
            api_key=runtime.api_key,
            endpoint_id=runtime.endpoint_id,
            base_url=runtime.base_url,
            timeout_seconds=runtime.timeout_seconds,
            temperature=min(0.2, runtime.temperature),
            messages=[
                DoubaoChatMessage(role="system", content=system),
                DoubaoChatMessage(role="user", content=prompt),
            ],
        )
    except DoubaoClientError:
        logger.exception("Profile extract LLM failed")
        return {"hasUpdate": False}
    return parse_profile_extract_payload(text)


def _refresh_one_user(
    db: Session,
    *,
    user: User | None,
    session: CourseAgentSessionRecord | None,
    args: dict[str, Any],
    agent_id: str | None,
    utterances: list[str],
    from_history: bool,
    instruction: str,
) -> tuple[str, bool]:
    user_id = user.id if user is not None else None
    current = read_profile(db, user_id=user_id, session=session)
    patch: dict[str, Any] = {}
    if from_history and utterances:
        extracted_payload = extract_profile_patch_with_llm(
            db,
            agent_id=agent_id,
            current=current,
            utterances=utterances,
            instruction=instruction,
        )
        if extracted_payload.get("hasUpdate") is not False:
            patch = extracted_payload
    if _has_manual_patch(args):
        patch = {**patch, **{k: v for k, v in args.items() if k in {
            "personaLabel", "summary", "goals", "constraints", "conditions", "allergies", "newFacts"
        } and v not in (None, "", [])}}
    if not patch:
        display = (user.full_name or user.username) if user else ""
        return (
            f"{display}：无新事实，画像未改。\n"
            + format_profile_for_tool(current, display_name=display, persisted=user is not None),
            False,
        )
    updated = merge_profile(current, patch)
    if normalize_profile(updated) == normalize_profile(current):
        display = (user.full_name or user.username) if user else ""
        return (
            f"{display}：归纳结果与现有画像相同。\n"
            + format_profile_for_tool(current, display_name=display, persisted=user is not None),
            False,
        )
    write_profile(db, updated, user_id=user_id, session=session)
    persisted = user is not None
    display = (user.full_name or user.username) if user else ""
    prefix = (
        f"{display}：已根据历史发言归纳并写入账号。"
        if persisted
        else "已根据历史发言更新本会话画像。"
    )
    return prefix + "\n" + format_profile_for_tool(
        updated, display_name=display, persisted=persisted
    ), True


def execute_update_profile(
    db: Session,
    *,
    user_id: UUID | None,
    session: CourseAgentSessionRecord | None,
    args: dict[str, Any],
    agent_id: str | None = None,
) -> str:
    args = dict(args or {})
    agent_id = agent_id or (session.agent_id if session is not None else None)
    scope = str(args.get("scope") or "current").strip().lower()
    if scope in {"all", "all_users"}:
        scope = "all_users"
    else:
        scope = "current"
    from_history = _bool_arg(args.get("fromHistory"), True)
    instruction = str(args.get("instruction") or args.get("taskPrompt") or "").strip()
    lookback = args.get("lookbackHours")
    since: datetime | None = None
    if lookback not in (None, ""):
        try:
            hours = max(1.0, min(float(lookback), 720.0))
            since = datetime.now(UTC) - timedelta(hours=hours)
        except (TypeError, ValueError):
            since = None
    only_if_new = _bool_arg(args.get("onlyIfNewMessages"), True)
    target = str(args.get("target") or "all_users")

    if scope == "all_users":
        users = list_profile_target_users(db, target)
        processed = 0
        updated = 0
        skipped = 0
        lines: list[str] = []
        for user in users:
            utterances = load_user_utterances(db, user.id, since=since)
            if only_if_new and not utterances:
                skipped += 1
                continue
            processed += 1
            text, changed = _refresh_one_user(
                db,
                user=user,
                session=None,
                args={},
                agent_id=agent_id,
                utterances=utterances,
                from_history=True,
                instruction=instruction,
            )
            if changed:
                updated += 1
            lines.append(text.split("\n", 1)[0])
            db.commit()
        summary = f"批量画像刷新完成：处理 {processed} 人，更新 {updated} 人，跳过 {skipped} 人。"
        if lines:
            summary += "\n" + "\n".join(lines[:40])
        return summary

    user = db.get(User, user_id) if user_id is not None else None
    if user is not None:
        utterances = load_user_utterances(db, user.id, since=since)
    elif session is not None:
        utterances = [
            " ".join(str(m.content or "").split())
            for m in (session.messages or [])
            if m.role == "user" and str(m.content or "").strip()
        ]
        utterances = [item[:800] for item in utterances if item][-80:]
    else:
        utterances = []
    text, _changed = _refresh_one_user(
        db,
        user=user,
        session=session,
        args=args,
        agent_id=agent_id,
        utterances=utterances,
        from_history=from_history,
        instruction=instruction,
    )
    return text
