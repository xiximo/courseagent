"""Workflow 运行时类型（对齐 docs/agent-runtime-spec.md）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["student", "teacher", "org"]
RoleStatus = Literal["unknown", "confirmed"]
Intent = Literal[
    "choose_role",
    "provide_constraint",
    "ask_recommend",
    "ask_detail",
    "ask_enroll",
    "restart",
    "list_courses",
    "out_of_scope",
    "empty",
    "too_long",
    "other",
]

WORKFLOW_META_KEY = "_workflow"


@dataclass
class CitationOut:
    document: str
    chapter: str
    attachment_id: str | None = None
    chunk_id: str | None = None


@dataclass
class AssistantOut:
    content: str
    citations: list[CitationOut] | None = None
    quick_actions: list[str] | None = None


@dataclass
class TurnInput:
    text: str
    quick_action: str | None = None
    is_empty: bool = False
    too_long: bool = False
    char_count: int = 0


@dataclass
class WorkflowRuntimeState:
    current_node_id: str
    role: Role | None = None
    role_status: RoleStatus = "unknown"
    constraints: dict[str, str | None] = field(default_factory=dict)
    recommended_courses: list[str] = field(default_factory=list)
    locked_course: str | None = None
    active_knowledge_base_id: str | None = None
    last_retrieval: dict[str, Any] | None = None
    awaiting_input: bool = True
    last_error: str | None = None
    is_preview: bool = False

    def constraint_slots(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key in ("city", "date", "format", "goal"):
            val = self.constraints.get(key)
            if val and str(val).strip():
                out[key] = str(val).strip()
        return out

    def effective_constraint_count(self) -> int:
        return len(self.constraint_slots())


@dataclass
class NodeOutput:
    messages: list[AssistantOut] = field(default_factory=list)
    intent: Intent | None = None
    wait_for_user: bool = True
    state_patch: dict[str, Any] | None = None
    # 若节点已自行推进 current_node_id，引擎仍以边跳转为准


@dataclass
class TurnResult:
    state: WorkflowRuntimeState
    user_text: str
    assistant_messages: list[AssistantOut]
    title_hint: str | None = None
