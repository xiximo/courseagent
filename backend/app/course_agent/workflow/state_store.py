"""Session ↔ WorkflowRuntimeState 序列化。"""

from __future__ import annotations

from typing import Any

from app.course_agent.workflow.types import (
    WORKFLOW_META_KEY,
    Role,
    RoleStatus,
    WorkflowRuntimeState,
)


def state_to_session_fields(state: WorkflowRuntimeState) -> dict[str, Any]:
    constraints = {
        k: v
        for k, v in (state.constraints or {}).items()
        if k in ("city", "date", "format", "goal") and v is not None
    }
    constraints[WORKFLOW_META_KEY] = {
        "roleStatus": state.role_status,
        "activeKnowledgeBaseId": state.active_knowledge_base_id,
        "lastRetrieval": state.last_retrieval,
        "awaitingInput": state.awaiting_input,
        "lastError": state.last_error,
        "isPreview": state.is_preview,
    }
    return {
        "step": state.current_node_id,
        "role": state.role,
        "constraints_json": constraints,
        "recommended_courses": list(state.recommended_courses or []),
        "locked_course": state.locked_course,
    }


def state_from_session(
    *,
    step: str,
    role: str | None,
    constraints_json: dict | None,
    recommended_courses: list | None,
    locked_course: str | None,
    entry_node_id: str,
    is_preview: bool = False,
) -> WorkflowRuntimeState:
    raw = dict(constraints_json or {})
    meta = raw.pop(WORKFLOW_META_KEY, None)
    if not isinstance(meta, dict):
        meta = {}

    slots = {
        k: (str(raw[k]) if raw.get(k) is not None else None)
        for k in ("city", "date", "format", "goal")
        if k in raw
    }

    role_status: RoleStatus = meta.get("roleStatus") or "unknown"
    if role_status not in ("unknown", "confirmed"):
        role_status = "unknown"
    if role and role_status == "unknown":
        # 兼容旧会话：有 role 视为已确认
        role_status = "confirmed"

    typed_role: Role | None = None
    if role in ("student", "teacher", "org"):
        typed_role = role  # type: ignore[assignment]

    current = step if step and step not in ("welcome", "preview", "identity", "constraints", "recommend", "qa", "enroll") else entry_node_id
    # 旧状态机 step 名 → 落到入口，避免卡死
    if step in ("welcome", "preview", "identity", "constraints", "recommend", "qa", "enroll"):
        current = entry_node_id

    return WorkflowRuntimeState(
        current_node_id=current or entry_node_id,
        role=typed_role,
        role_status=role_status,
        constraints=slots,
        recommended_courses=list(recommended_courses or []),
        locked_course=locked_course,
        active_knowledge_base_id=meta.get("activeKnowledgeBaseId"),
        last_retrieval=meta.get("lastRetrieval"),
        awaiting_input=bool(meta.get("awaitingInput", True)),
        last_error=meta.get("lastError"),
        is_preview=bool(meta.get("isPreview", is_preview)),
    )


def apply_state_patch(state: WorkflowRuntimeState, patch: dict[str, Any] | None) -> None:
    if not patch:
        return
    if patch.get("clearSession"):
        state.constraints = {}
        state.recommended_courses = []
        state.locked_course = None
        state.active_knowledge_base_id = None
        state.last_retrieval = None
        state.last_error = None
    if patch.get("clearRole"):
        state.role = None
        state.role_status = "unknown"
        state.active_knowledge_base_id = None

    if "role" in patch:
        role = patch.get("role")
        state.role = role if role in ("student", "teacher", "org") else None
    if "roleStatus" in patch:
        status = patch.get("roleStatus")
        if status in ("unknown", "confirmed"):
            state.role_status = status
    if "constraints" in patch and isinstance(patch["constraints"], dict):
        for key, value in patch["constraints"].items():
            if key in ("city", "date", "format", "goal"):
                state.constraints[key] = None if value is None else str(value)
    if "recommendedCourses" in patch and isinstance(patch["recommendedCourses"], list):
        state.recommended_courses = [str(x) for x in patch["recommendedCourses"]]
    if "lockedCourse" in patch:
        lc = patch.get("lockedCourse")
        state.locked_course = None if lc is None else str(lc)
    if "activeKnowledgeBaseId" in patch:
        kb = patch.get("activeKnowledgeBaseId")
        state.active_knowledge_base_id = None if kb is None else str(kb)
    if "currentNodeId" in patch and patch.get("currentNodeId"):
        state.current_node_id = str(patch["currentNodeId"])
    if patch.get("currentNodeId"):
        state.current_node_id = str(patch["currentNodeId"])
