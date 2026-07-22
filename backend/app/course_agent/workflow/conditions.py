"""边条件求值。"""

from __future__ import annotations

from typing import Any

from app.course_agent.workflow.types import Intent, NodeOutput, TurnInput, WorkflowRuntimeState


def eval_condition(
    when: dict[str, Any] | None,
    *,
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
    output: NodeOutput | None,
    min_constraints_fallback: int = 2,
) -> bool:
    if not when:
        return True
    ctype = when.get("type") or "always"

    if ctype == "always":
        return True
    if ctype == "quick_action":
        action = str(when.get("action") or "")
        if not action:
            return False
        qa = (turn.quick_action if turn else None) or ""
        text = (turn.text if turn else "") or ""
        return qa == action or text.strip() == action
    if ctype == "role_eq":
        return state.role == when.get("role")
    if ctype == "role_status":
        return state.role_status == when.get("status")
    if ctype == "constraints_ready":
        minimum = int(when.get("min") or min_constraints_fallback)
        return state.effective_constraint_count() >= minimum
    if ctype == "intent":
        want = when.get("intent")
        got = output.intent if output else None
        return got == want
    if ctype == "state_flag":
        path = str(when.get("path") or "")
        expected = when.get("equals")
        actual = _read_path(state, path)
        return actual == expected
    if ctype == "and":
        items = when.get("items") or []
        return all(
            eval_condition(
                item,
                state=state,
                turn=turn,
                output=output,
                min_constraints_fallback=min_constraints_fallback,
            )
            for item in items
            if isinstance(item, dict)
        )
    if ctype == "or":
        items = when.get("items") or []
        return any(
            eval_condition(
                item,
                state=state,
                turn=turn,
                output=output,
                min_constraints_fallback=min_constraints_fallback,
            )
            for item in items
            if isinstance(item, dict)
        )
    if ctype == "not":
        item = when.get("item")
        if not isinstance(item, dict):
            return True
        return not eval_condition(
            item,
            state=state,
            turn=turn,
            output=output,
            min_constraints_fallback=min_constraints_fallback,
        )
    return False


def _read_path(state: WorkflowRuntimeState, path: str) -> Any:
    cur: Any = state
    for part in path.split("."):
        if not part:
            continue
        if isinstance(cur, WorkflowRuntimeState):
            cur = getattr(cur, part, None)
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def guess_intent_from_text(text: str) -> Intent | None:
    t = text.strip().lower()
    if not t:
        return "empty"
    if t in ("重新开始", "重来", "取消", "reset", "restart"):
        return "restart"
    if "查看所有" in t or "全部班型" in t or "所有课程" in t:
        return "list_courses"
    if any(k in t for k in ("报名", "怎么报", "如何报名", "报名方式")):
        return "ask_enroll"
    if any(k in t for k in ("天气", "笑话", "股票", "八卦")):
        return "out_of_scope"
    return None
