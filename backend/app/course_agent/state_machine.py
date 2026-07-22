"""Course Agent 状态机（与前端 state-machine.ts 对齐）."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

CourseAgentRole = Literal["student", "teacher", "org"]
CourseAgentStep = Literal[
    "welcome", "identity", "constraints", "recommend", "qa", "enroll"
]

STUDENT_COURSES = ("北京线下班", "上海线下班", "线上直播班")
TEACHER_COURSES = ("暑期集训班", "周末研修班")
MAX_INPUT_LENGTH = 500


@dataclass
class Citation:
    document: str
    chapter: str
    attachment_id: str | None = None
    chunk_id: str | None = None

    def to_dict(self) -> dict:
        payload: dict = {"document": self.document, "chapter": self.chapter}
        if self.attachment_id:
            payload["attachmentId"] = self.attachment_id
        if self.chunk_id:
            payload["chunkId"] = self.chunk_id
        return payload


@dataclass
class AgentMessage:
    id: str
    role: str
    content: str
    created_at: str
    citations: list[Citation] | None = None
    quick_actions: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "createdAt": self.created_at,
            "citations": [c.to_dict() for c in self.citations] if self.citations else None,
            "quickActions": self.quick_actions,
        }


@dataclass
class SessionState:
    step: CourseAgentStep = "welcome"
    role: CourseAgentRole | None = None
    constraints: dict = field(default_factory=dict)
    recommended_courses: list[str] = field(default_factory=list)
    locked_course: str | None = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "role": self.role,
            "constraints": self.constraints,
            "recommendedCourses": self.recommended_courses,
            "lockedCourse": self.locked_course,
        }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _msg_id() -> str:
    return f"msg-{uuid.uuid4().hex[:12]}"


def _assistant(content: str, **extra) -> AgentMessage:
    return AgentMessage(
        id=_msg_id(),
        role="assistant",
        content=content,
        created_at=_now_iso(),
        citations=extra.get("citations"),
        quick_actions=extra.get("quick_actions"),
    )


def _count_constraints(c: dict) -> int:
    return sum(1 for k in ("city", "date", "format", "goal") if c.get(k))


def _detect_role(text: str) -> CourseAgentRole | None:
    t = text.lower()
    if re.search(r"学生|家长|孩子|报班", t):
        return "student"
    if re.search(r"教师|老师|培训", t):
        return "teacher"
    if re.search(r"机构|企业|平台|会员|合作", t):
        return "org"
    if "学生课程" in t:
        return "student"
    if "教师培训" in t:
        return "teacher"
    if "平台服务" in t:
        return "org"
    return None


def _extract_constraints(text: str, existing: dict) -> dict:
    nxt = dict(existing)
    t = text.lower()
    if not nxt.get("city"):
        if "北京" in t:
            nxt["city"] = "北京"
        elif "上海" in t:
            nxt["city"] = "上海"
        elif re.search(r"线上|直播|远程", t):
            nxt["city"] = "线上"
    if not nxt.get("date"):
        if re.search(r"7月|七月|暑假", t):
            nxt["date"] = "7月"
        elif re.search(r"8月|八月", t):
            nxt["date"] = "8月"
        elif "周末" in t:
            nxt["date"] = "周末"
    if not nxt.get("format"):
        if re.search(r"线下|现场", t):
            nxt["format"] = "offline"
        elif re.search(r"线上|直播|远程", t):
            nxt["format"] = "online"
    if not nxt.get("goal") and re.search(r"ai|人工智能|素养|学习", t):
        nxt["goal"] = "提升 AI 素养"
    return nxt


def _missing_constraint_prompt(c: dict) -> str:
    if not c.get("city"):
        return "请问您倾向哪个城市或地点？（如北京、上海，或线上）"
    if not c.get("date"):
        return "请问您方便的上课时间？（如 7 月、8 月或周末）"
    if not c.get("format"):
        return "您更倾向线上还是线下班型？"
    if not c.get("goal"):
        return "请问您的学习目标是什么？（如提升 AI 素养）"
    return "请补充更多偏好，以便为您推荐合适班型。"


def _pick_courses(role: CourseAgentRole, constraints: dict):
    if role == "student":
        courses: list[str] = []
        reasons: list[str] = []
        if constraints.get("city") == "北京" and constraints.get("format") != "online":
            courses.append("北京线下班")
            reasons.append("您倾向北京线下上课，与北京线下班地点匹配")
        if constraints.get("city") == "上海" and constraints.get("format") != "online":
            courses.append("上海线下班")
            reasons.append("您倾向上海线下上课，与上海线下班地点匹配")
        if (
            constraints.get("format") == "online"
            or constraints.get("city") == "线上"
            or not courses
        ):
            if "线上直播班" not in courses:
                courses.append("线上直播班")
            reasons.append("您接受线上形式，或线下班型与约束不完全匹配时，线上直播班更灵活")
        if constraints.get("date", "").find("7") >= 0:
            reasons.append("7 月档期与夏令营营期安排相符")
        courses = courses[:2]
        reasons = reasons[:3]
        chapter = "第5章「线上直播班安排」"
        if courses and "北京" in courses[0]:
            chapter = "第3章「北京线下班安排」"
        elif courses and "上海" in courses[0]:
            chapter = "第4章「上海线下班安排」"
        return courses, reasons, [Citation("《素材A·暑期AI素养夏令营手册》", chapter)]

    if role == "teacher":
        courses = (
            ["暑期集训班"]
            if "7" in constraints.get("date", "") or constraints.get("format") == "offline"
            else ["周末研修班"]
        )
        reasons = [
            "暑期档期与集训班时间匹配" if "7" in constraints.get("date", "") else "周末研修更适合在职教师持续学习",
            "培训目标聚焦教师 AI 素养提升",
        ]
        chapter = "第2章「暑期集训班」" if courses[0] == "暑期集训班" else "第3章「周末研修班」"
        return courses, reasons, [Citation("《素材B·教师AI素养培训体系介绍》", chapter)]

    return [], [], []


def _answer_detail(question: str, course: str, role: CourseAgentRole):
    q = question.lower()
    kb = (
        "《素材A·暑期AI素养夏令营手册》"
        if role == "student"
        else "《素材B·教师AI素养培训体系介绍》"
    )
    if re.search(r"多少钱|费用|价格", q):
        fees = {
            "北京线下班": "3800 元/期（含材料费）",
            "上海线下班": "3600 元/期",
            "线上直播班": "2800 元/期",
            "暑期集训班": "4200 元/期",
            "周末研修班": "1800 元/期",
        }
        fee = fees.get(course, "详见资料")
        ch = (
            "第3章「费用说明」"
            if "北京" in course
            else "第4章「费用说明」"
            if "上海" in course
            else "第5章「费用说明」"
            if "线上" in course
            else "第2章「费用说明」"
        )
        return f"{course}费用为 {fee}。\n\n来源：{kb}{ch}", [Citation(kb, "费用说明")]
    if re.search(r"什么时候|时间|日程", q):
        return (
            f"{course}主要安排在 7—8 月，具体日程以手册为准。\n\n来源：{kb}对应班型章节「时间安排」"
        ), [Citation(kb, "时间安排")]
    if re.search(r"带什么|准备|物资", q):
        return (
            f"参加{course}建议携带：笔记本电脑、充电器、笔记本；线下班另需携带身份证件。\n\n"
            f"来源：{kb}「学员准备事项」"
        ), [Citation(kb, "学员准备事项")]
    if "报名" in q:
        return (
            f"{course}报名方式：请通过 AI 教育中心官网填写报名表，或拨打资料中公布的咨询热线。"
            f"如需确认余位，请联系人工客服。\n\n来源：{kb}「报名方式」"
        ), [Citation(kb, "报名方式")]
    return (
        f"关于{course}的详情，请具体说明您想了解时间、费用、师资还是大纲。\n\n来源：{kb}"
    ), [Citation(kb, "班型概述")]


def _org_platform_reply(text: str) -> AgentMessage:
    t = text.lower()
    if re.search(r"会员|价格|多少钱", t):
        return _assistant(
            "OPC 平台提供基础版、专业版与企业版会员，权益与定价详见平台白皮书。"
            "请注意：平台会员价格属于平台服务范畴，与学生/教师课程费用不同。\n\n"
            "来源：《素材C·OPC平台产品白皮书》第2章「会员体系与定价」",
            citations=[Citation("《素材C·OPC平台产品白皮书》", "第2章「会员体系与定价」")],
        )
    return _assistant(
        "OPC 平台面向机构提供 SaaS 服务、会员权益、企业合作与定制开发。"
        "如需了解合作模式，请说明您的机构类型与诉求。\n\n"
        "来源：《素材C·OPC平台产品白皮书》第1章「平台概述」",
        citations=[Citation("《素材C·OPC平台产品白皮书》", "第1章「平台概述」")],
        quick_actions=["会员权益", "企业合作"],
    )


def create_initial_state() -> SessionState:
    return SessionState()


def create_welcome_message(conversation: dict | None = None) -> AgentMessage:
    welcome = (conversation or {}).get(
        "welcomeMessage",
        "您好！我是 AI 课程顾问，可为您提供学生夏令营、教师培训或 OPC 平台服务咨询。请问您需要哪类帮助？",
    )
    menu = (conversation or {}).get("menuButtons") or ["学生课程", "教师培训", "平台服务"]
    return _assistant(welcome, quick_actions=list(menu))


def process_message(
    state: SessionState,
    messages: list[AgentMessage],
    user_text: str,
    *,
    conversation: dict | None = None,
) -> tuple[SessionState, list[AgentMessage], str]:
    trimmed = user_text.strip()
    now = _now_iso()
    out_messages = list(messages)
    out_messages.append(
        AgentMessage(id=_msg_id(), role="user", content=trimmed, created_at=now)
    )
    title = "新对话"

    conv = conversation or {}
    empty_msg = conv.get("emptyInputMessage", "请输入您的问题。")
    long_msg = conv.get("tooLongMessage", "输入过长，请精简后重新发送（限 500 字）。")

    if not trimmed:
        out_messages.append(_assistant(empty_msg))
        return state, out_messages, title

    if len(trimmed) > MAX_INPUT_LENGTH:
        out_messages.append(_assistant(long_msg))
        return state, out_messages, title

    if re.search(r"重新开始|重来|取消|重置", trimmed):
        state = create_initial_state()
        reset_msg = conv.get("resetMessage", "已为您重新开始。请问需要学生课程、教师培训还是平台服务？")
        menu = conv.get("menuButtons") or ["学生课程", "教师培训", "平台服务"]
        out_messages.append(_assistant(reset_msg, quick_actions=list(menu)))
        return state, out_messages, title

    if re.search(r"天气|广州线下|深圳班", trimmed):
        if "广州" in trimmed:
            out_messages.append(
                _assistant(
                    "该信息不在现有资料范围内，资料中暂无广州线下班，无法确认。建议联系人工客服。\n\n"
                    "您也可以查看当前身份下的全部班型。",
                    quick_actions=["查看所有课程", "重新开始"],
                )
            )
        else:
            out_scope = conv.get(
                "outOfScopeMessage",
                "抱歉，我仅提供 AI 教育中心课程与平台服务咨询，无法回答该问题。请选择以下服务入口：",
            )
            menu = conv.get("menuButtons") or ["学生课程", "教师培训", "平台服务"]
            out_messages.append(_assistant(out_scope, quick_actions=list(menu)))
        return state, out_messages, title

    if state.role == "student" and re.search(r"会员价|平台会员", trimmed):
        out_messages.append(
            _assistant(
                "平台会员价格属于平台服务范畴，与学生/教师课程费用不同。如需了解平台会员，请切换至「平台服务」入口。",
                quick_actions=["平台服务", "重新开始"],
            )
        )
        return state, out_messages, title
    if state.role == "teacher" and re.search(r"会员价|学生营", trimmed):
        out_messages.append(
            _assistant(
                "平台会员价格属于平台服务范畴，与学生/教师课程费用不同。如需了解平台会员，请切换至「平台服务」入口。",
                quick_actions=["平台服务", "重新开始"],
            )
        )
        return state, out_messages, title

    if state.step in ("welcome", "identity"):
        role = _detect_role(trimmed)
        if not role:
            state.step = "identity"
            out_messages.append(
                _assistant(
                    "请问您是为学生/家长咨询，教师咨询，还是机构/企业了解平台服务？",
                    quick_actions=["我是家长", "我是教师", "机构合作"],
                )
            )
            return state, out_messages, title
        state.role = role
        if role == "org":
            state.step = "qa"
            out_messages.append(_org_platform_reply(trimmed))
            return state, out_messages, title
        state.step = "constraints"
        state.constraints = _extract_constraints(trimmed, state.constraints)
        if _count_constraints(state.constraints) >= 2 and "推荐" in trimmed:
            pass
        else:
            label = "学生/家长" if role == "student" else "教师"
            out_messages.append(
                _assistant(
                    f"已识别您为{label}咨询。{_missing_constraint_prompt(state.constraints)}"
                )
            )
            return state, out_messages, title

    if state.role == "org":
        state.step = "qa"
        out_messages.append(_org_platform_reply(trimmed))
        return state, out_messages, title

    if state.step == "constraints" or (state.step == "identity" and state.role):
        if "推荐" in trimmed and not state.role:
            out_messages.append(_assistant("请先告诉我您的身份（学生/家长、教师或机构），再为您推荐班型。"))
            state.step = "identity"
            return state, out_messages, title

        state.constraints = _extract_constraints(trimmed, state.constraints)
        if _count_constraints(state.constraints) < 2:
            state.step = "constraints"
            out_messages.append(_assistant(_missing_constraint_prompt(state.constraints)))
            return state, out_messages, title

        courses, reasons, citations = _pick_courses(state.role, state.constraints)
        state.step = "recommend"
        state.recommended_courses = courses
        state.locked_course = courses[0] if courses else None
        reason_text = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(reasons))
        course_lines = "\n".join(f"**{c}**" for c in courses)
        out_messages.append(
            _assistant(
                f"根据您的需求，为您推荐以下班型：\n\n{course_lines}\n\n推荐理由：\n{reason_text}\n\n"
                "如需了解费用、时间或报名，请继续提问。",
                citations=citations,
                quick_actions=["这个班什么时候", "多少钱", "需要带什么", "查看所有课程"],
            )
        )
        return state, out_messages, title

    if re.search(r"查看所有课程|全部班型|有哪些班", trimmed) and state.role:
        if state.role == "student":
            listing = "、".join(STUDENT_COURSES)
        elif state.role == "teacher":
            listing = "、".join(TEACHER_COURSES)
        else:
            listing = "平台服务（会员、企业合作、定制开发）"
        out_messages.append(_assistant(f"当前身份下可选内容：{listing}"))
        return state, out_messages, title

    if "报名" in trimmed and state.locked_course and state.role:
        state.step = "enroll"
        content, citations = _answer_detail(trimmed, state.locked_course, state.role)
        out_messages.append(_assistant(content, citations=citations))
        return state, out_messages, title

    if state.locked_course or state.recommended_courses:
        state.step = "qa"
        course = state.locked_course or state.recommended_courses[0]
        state.locked_course = course
        assert state.role is not None
        content, citations = _answer_detail(trimmed, course, state.role)
        out_messages.append(_assistant(content, citations=citations))
        return state, out_messages, title

    menu = conv.get("menuButtons") or ["学生课程", "教师培训", "平台服务"]
    out_messages.append(
        _assistant("请问需要学生课程、教师培训还是平台服务？", quick_actions=list(menu))
    )
    state.step = "welcome"
    return state, out_messages, title
