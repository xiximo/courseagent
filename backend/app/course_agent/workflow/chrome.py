"""对话展示层：去掉上一届课程顾问分流按钮与对应提示语。"""

from __future__ import annotations

COURSE_BRANCH_ACTIONS = frozenset(
    {
        "学生课程",
        "教师培训",
        "平台服务",
        "查看所有课程",
        "了解报名方式",
    }
)

COURSE_WELCOME_MARKERS = (
    "学生课程",
    "教师培训",
    "学生暑期营",
    "学生/家长",
    "OPC 平台",
    "课程顾问",
)

GENERIC_WELCOME = "您好，请问有什么可以帮您？"
GENERIC_IDENTITY_PROMPT = "请问有什么可以帮您？"
GENERIC_OUT_OF_SCOPE = "该问题暂时无法回答，请换一种方式描述您的需求。"


def filter_branch_actions(actions: list[str] | None) -> list[str]:
    out: list[str] = []
    for item in actions or []:
        text = str(item).strip()
        if text and text not in COURSE_BRANCH_ACTIONS and text not in out:
            out.append(text)
    return out


def looks_like_course_copy(text: str) -> bool:
    return any(marker in (text or "") for marker in COURSE_WELCOME_MARKERS)


def sanitize_welcome(text: str) -> str:
    raw = (text or "").strip()
    if not raw or looks_like_course_copy(raw):
        return GENERIC_WELCOME
    return raw


def sanitize_identity_prompt(text: str) -> str:
    raw = (text or "").strip()
    if not raw or looks_like_course_copy(raw):
        return GENERIC_IDENTITY_PROMPT
    return raw


def sanitize_out_of_scope(text: str) -> str:
    raw = (text or "").strip()
    if not raw or looks_like_course_copy(raw):
        return GENERIC_OUT_OF_SCOPE
    return raw
