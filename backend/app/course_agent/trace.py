"""对话运行轨迹：思考 / 工具调用 / 工作流节点。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

MAX_TRACE_EVENTS = 120

TOOL_LABELS = {
    "get_user_profile": "读取用户画像",
    "update_user_profile": "更新用户画像",
    "query_course_detail": "查询课程详情",
    "recommend_courses": "推荐适合班型",
    "search_core_nutrition": "检索核心营养知识",
    "search_platform_guide": "检索平台服务资料",
    "search_knowledge": "检索机构知识库",
}

NODE_TYPE_LABELS = {
    "entry": "欢迎分流",
    "identity": "身份澄清",
    "slot_fill": "采集信息",
    "scope": "绑定知识范围",
    "rag_recommend": "检索并推荐",
    "rag_qa": "知识库问答",
    "rag_enroll": "报名引导",
    "rag_platform": "平台介绍",
    "session_control": "会话控制",
    "boundary": "边界处理",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def make_trace(
    event_type: str,
    title: str,
    *,
    detail: str | None = None,
    tool_name: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "id": uuid4().hex[:12],
        "type": event_type,
        "title": title,
        "createdAt": _now_iso(),
    }
    if detail:
        event["detail"] = detail[:4000]
    if tool_name:
        event["toolName"] = tool_name
    if status:
        event["status"] = status
    return event


def tool_label(name: str) -> str:
    key = (name or "").strip()
    return TOOL_LABELS.get(key, key or "未知工具")


def node_label(node: dict[str, Any]) -> str:
    name = str(node.get("name") or "").strip()
    if name:
        return name
    ntype = str(node.get("type") or "").strip()
    return NODE_TYPE_LABELS.get(ntype, ntype or "流程节点")


def format_json_detail(value: Any, *, limit: int = 2000) -> str:
    import json

    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        text = str(value)
    return text[:limit]


def merge_trace_into_constraints(
    constraints: dict[str, Any] | None,
    events: list[dict[str, Any]],
    *,
    max_keep: int = MAX_TRACE_EVENTS,
) -> dict[str, Any]:
    out = dict(constraints or {})
    prev = [item for item in (out.get("_agentTrace") or []) if isinstance(item, dict)]
    merged = prev + [item for item in events if isinstance(item, dict)]
    out["_agentTrace"] = merged[-max_keep:]
    return out


def traces_from_constraints(constraints: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (constraints or {}).get("_agentTrace") or []
    events: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not str(item.get("id") or "").strip() or not str(item.get("title") or "").strip():
            continue
        events.append(item)
    return events
