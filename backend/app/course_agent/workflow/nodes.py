"""各节点执行逻辑。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.course_agent.llm_helper import CourseAgentLlmHelper
from app.course_agent.rag import (
    format_hits_for_prompt,
    hits_to_citations_from_hits,
    retrieve_by_kb_id,
)
from app.course_agent.workflow.conditions import guess_intent_from_text
from app.course_agent.workflow.types import (
    AssistantOut,
    CitationOut,
    Intent,
    NodeOutput,
    TurnInput,
    WorkflowRuntimeState,
)
from app.llm.doubao_client import (
    DoubaoChatMessage,
    DoubaoClientError,
    chat_completion,
    iter_chat_completion,
)
from app.services.llm_settings import get_or_create_llm_config, resolve_llm_runtime

logger = logging.getLogger(__name__)

# RAG 节点在 stream=True 时可能返回生成器：产出 str 增量，最后产出 NodeOutput
NodeExecResult = NodeOutput | Iterator[str | NodeOutput]


def execute_node(
    *,
    db: Session,
    agent_id: str,
    node: dict[str, Any],
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
    bootstrap: bool = False,
    stream: bool = False,
) -> NodeExecResult:
    ntype = node.get("type") or ""
    config = node.get("config") if isinstance(node.get("config"), dict) else {}

    if ntype == "entry":
        return _entry(config, turn, bootstrap=bootstrap)
    if ntype == "identity":
        return _identity(db, agent_id, config, state, turn)
    if ntype == "slot_fill":
        return _slot_fill(db, agent_id, config, state, turn)
    if ntype == "scope":
        return _scope(config, state)
    if ntype in ("rag_recommend", "rag_qa", "rag_enroll", "rag_platform"):
        return _rag_generate(
            db, agent_id, ntype, config, state, turn, stream=stream
        )
    if ntype == "session_control":
        return _session_control(db, agent_id, config, state, turn)
    if ntype == "boundary":
        return _boundary(config, turn)
    return NodeOutput(
        messages=[AssistantOut(content="未知节点类型，请检查流程配置。")],
        intent="other",
        wait_for_user=True,
    )


def _entry(config: dict, turn: TurnInput | None, *, bootstrap: bool) -> NodeOutput:
    welcome = str(config.get("welcomeText") or "您好，我是课程顾问。")
    # 快捷按钮完全来自画布节点 config.quickActions
    actions = [str(a).strip() for a in (config.get("quickActions") or []) if str(a).strip()]
    if bootstrap or turn is None:
        return NodeOutput(
            messages=[AssistantOut(content=welcome, quick_actions=actions or None)],
            wait_for_user=True,
        )
    # 用户在入口发话：静默转出，由边条件分流
    text = (turn.text or "").strip()
    guessed = guess_intent_from_text(text)
    intent: Intent = guessed or "choose_role"
    if turn.quick_action or text in actions or text in (
        "学生课程",
        "教师培训",
        "平台服务",
    ):
        intent = "choose_role"
        if text in ("重新开始",) or turn.quick_action == "重新开始":
            intent = "restart"
    return NodeOutput(messages=[], intent=intent, wait_for_user=False)


def _identity(
    db: Session,
    agent_id: str,
    config: dict,
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
) -> NodeOutput:
    if state.role_status == "confirmed" and state.role:
        return NodeOutput(messages=[], intent="other", wait_for_user=False)

    prompt = str(config.get("promptWhenUnknown") or "请问您的身份是？")
    actions = ["学生课程", "教师培训", "平台服务"]
    text = (turn.text if turn else "") or ""
    guessed = guess_intent_from_text(text)
    if guessed == "restart":
        return NodeOutput(messages=[], intent="restart", wait_for_user=False)
    if guessed == "out_of_scope":
        return NodeOutput(messages=[], intent="out_of_scope", wait_for_user=False)

    role = _detect_role_rule(text) or _detect_role_from_quick(turn)
    if role:
        return NodeOutput(
            messages=[],
            intent="choose_role",
            wait_for_user=False,
            state_patch={"role": role, "roleStatus": "confirmed"},
        )

    # LLM 轻量分类
    parsed = _llm_json(
        db,
        agent_id,
        system=(
            "你是身份分类器。根据用户话判断 student/teacher/org，或无法判断。"
            '只输出 JSON：{"role":"student|teacher|org|null","confirmed":bool,"reply":"中文追问","intent":"choose_role|out_of_scope|restart|other"}'
        ),
        user=f"用户说：{text}",
    )
    if parsed:
        intent = parsed.get("intent") or "other"
        if intent not in (
            "choose_role",
            "out_of_scope",
            "restart",
            "other",
        ):
            intent = "other"
        if parsed.get("confirmed") and parsed.get("role") in (
            "student",
            "teacher",
            "org",
        ):
            return NodeOutput(
                messages=[],
                intent="choose_role",
                wait_for_user=False,
                state_patch={
                    "role": parsed["role"],
                    "roleStatus": "confirmed",
                },
            )
        reply = str(parsed.get("reply") or prompt)
        return NodeOutput(
            messages=[AssistantOut(content=reply, quick_actions=actions)],
            intent=intent,  # type: ignore[arg-type]
            wait_for_user=True,
        )

    return NodeOutput(
        messages=[AssistantOut(content=prompt, quick_actions=actions)],
        intent="other",
        wait_for_user=True,
    )


def _slot_fill(
    db: Session,
    agent_id: str,
    config: dict,
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
) -> NodeOutput:
    text = (turn.text if turn else "") or ""
    guessed = guess_intent_from_text(text)
    if guessed in ("restart", "list_courses", "out_of_scope"):
        return NodeOutput(messages=[], intent=guessed, wait_for_user=False)

    slots = config.get("slots") if isinstance(config.get("slots"), list) else []
    ask_one = bool(config.get("askOneMissingAtATime", True))

    # 入口快捷身份按钮同轮穿行到采集：不把按钮文案当约束
    role_buttons = {"学生课程", "教师培训", "平台服务"}
    skip_extract = (not text.strip()) or text.strip() in role_buttons

    patch_constraints: dict[str, str] = {}
    llm_patch = None
    if not skip_extract:
        # 用户表示没有更多要求：把仍空的槽填成「无特殊要求」，避免反复追问
        if _is_soft_decline(text):
            for key in ("city", "date", "format", "goal"):
                if key not in state.constraint_slots():
                    patch_constraints[key] = "无特殊要求"
        else:
            _rule_fill_slots(text, patch_constraints)
            llm_patch = _llm_json(
                db,
                agent_id,
                system=(
                    "从用户话中抽取课程约束。只输出 JSON："
                    '{"city":str|null,"date":str|null,"format":str|null,"goal":str|null,'
                    '"reply":"若还需追问则给出一句中文","intent":"provide_constraint|ask_recommend|restart|out_of_scope|other"}'
                    "若用户明确说没有要求/没有了，对应字段填「无特殊要求」。"
                ),
                user=(
                    f"已有约束：{state.constraint_slots()}\n用户说：{text}\n"
                    f"可抽取字段：city/date/format/goal"
                ),
            )
            if isinstance(llm_patch, dict):
                for key in ("city", "date", "format", "goal"):
                    val = llm_patch.get(key)
                    if val:
                        patch_constraints[key] = str(val)

    merged = dict(state.constraint_slots())
    merged.update(patch_constraints)
    filled_count = len(merged)

    state_patch = {"constraints": {**state.constraints, **patch_constraints}}

    if filled_count >= 2 and not skip_extract:
        return NodeOutput(
            messages=[],
            intent="ask_recommend",
            wait_for_user=False,
            state_patch=state_patch,
        )

    # 按槽位定义顺序追问（城市→日期→形式→目标）
    missing_prompt = None
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        key = slot.get("key")
        if key in merged:
            continue
        missing_prompt = str(slot.get("askPrompt") or f"请补充{slot.get('label')}")
        if ask_one:
            break

    reply = None
    if isinstance(llm_patch, dict) and llm_patch.get("reply") and not skip_extract:
        reply = str(llm_patch["reply"])
    if not reply:
        reply = missing_prompt or "请再补充一些偏好（城市、时间、线上线下或学习目标）。"

    return NodeOutput(
        messages=[
            AssistantOut(
                content=reply,
                quick_actions=["查看所有课程", "没有特殊要求", "重新开始"],
            )
        ],
        intent="provide_constraint",
        wait_for_user=True,
        state_patch=state_patch,
    )


def _is_soft_decline(text: str) -> bool:
    t = text.strip()
    return t in (
        "没有了",
        "没有",
        "无",
        "都行",
        "随意",
        "无所谓",
        "没有要求",
        "无要求",
        "都可以",
        "暂无",
        "不知道",
    ) or t.startswith("没有") and len(t) <= 12


def _scope(config: dict, state: WorkflowRuntimeState) -> NodeOutput:
    binding = config.get("binding") if isinstance(config.get("binding"), dict) else {}
    missing = str(
        config.get("missingKbText")
        or "当前身份对应的知识库尚未配置，请联系人工客服。"
    )
    if state.role_status != "confirmed" or not state.role:
        return NodeOutput(
            messages=[AssistantOut(content="请先确认身份后再继续。")],
            intent="other",
            wait_for_user=True,
        )
    kb_id = binding.get(state.role)
    if not kb_id or str(kb_id).startswith("kb_material_"):
        return NodeOutput(
            messages=[AssistantOut(content=missing, quick_actions=["重新开始"])],
            intent="other",
            wait_for_user=True,
            state_patch={"activeKnowledgeBaseId": None},
        )
    return NodeOutput(
        messages=[],
        intent="other",
        wait_for_user=False,
        state_patch={"activeKnowledgeBaseId": str(kb_id)},
    )


def _rag_generate(
    db: Session,
    agent_id: str,
    ntype: str,
    config: dict,
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
    *,
    stream: bool = False,
) -> NodeExecResult:
    text = (turn.text if turn else "") or ""
    guessed = guess_intent_from_text(text)
    actions = list(config.get("quickActions") or [])

    if turn and turn.quick_action:
        qa = turn.quick_action
        if qa == "重新开始":
            return NodeOutput(messages=[], intent="restart", wait_for_user=False)
        if qa == "查看所有课程":
            return NodeOutput(messages=[], intent="list_courses", wait_for_user=False)
        # 已在报名节点时不要再把「了解报名方式」当成跳转信号（否则 enroll↔qa 死循环）
        if qa == "了解报名方式" and ntype != "rag_enroll":
            return NodeOutput(messages=[], intent="ask_enroll", wait_for_user=False)

    # 推荐已完成：本轮用户输入用于跳转（追问/报名等），不再重复推荐
    if ntype == "rag_recommend" and state.recommended_courses and text:
        intent: Intent = guessed or "ask_detail"
        if text.strip() == "了解报名方式" or guessed == "ask_enroll":
            intent = "ask_enroll"
        elif intent in ("provide_constraint", "choose_role", "other", "ask_recommend"):
            intent = "ask_detail"
        locked = _resolve_course_from_user_text(text, state)
        patch = {"lockedCourse": locked} if locked else None
        return NodeOutput(
            messages=[],
            intent=intent,
            wait_for_user=False,
            state_patch=patch,
        )

    if guessed in ("restart", "list_courses", "out_of_scope") and ntype != "rag_recommend":
        return NodeOutput(messages=[], intent=guessed, wait_for_user=False)
    if (
        guessed == "ask_enroll"
        and ntype in ("rag_qa", "rag_platform", "rag_recommend")
        and text
    ):
        locked = _resolve_course_from_user_text(text, state)
        return NodeOutput(
            messages=[],
            intent="ask_enroll",
            wait_for_user=False,
            state_patch={"lockedCourse": locked} if locked else None,
        )

    # 追问/报名前：根据用户话刷新聚焦班型（如「我考虑 L1…」「这个班」沿用已锁定）
    if ntype in ("rag_qa", "rag_enroll") and text:
        locked = _resolve_course_from_user_text(text, state)
        if locked:
            state.locked_course = locked

    kb_id = state.active_knowledge_base_id
    if not kb_id:
        return NodeOutput(
            messages=[
                AssistantOut(
                    content="尚未绑定可用知识库，无法检索资料。请在流程「知识范围」节点配置后重试。",
                    quick_actions=["重新开始"],
                )
            ],
            intent="other",
            wait_for_user=True,
        )

    llm_cfg = resolve_llm_runtime(get_or_create_llm_config(db))
    query = _build_query(ntype, state, text)
    hits = retrieve_by_kb_id(db, kb_id=kb_id, query=query, top_k=llm_cfg.qa_top_k)
    citations = [
        CitationOut(
            document=c.document,
            chapter=c.chapter,
            attachment_id=c.attachment_id,
            chunk_id=c.chunk_id,
        )
        for c in hits_to_citations_from_hits(hits)
    ]
    context = format_hits_for_prompt(hits)
    state.last_retrieval = {
        "knowledgeBaseId": kb_id,
        "chunkIds": [h.chunkId for h in hits],
        "query": query,
    }

    if not hits:
        return NodeOutput(
            messages=[
                AssistantOut(
                    content=(
                        "当前绑定知识库中暂未检索到与您问题直接相关的资料片段。"
                        "请确认文档已完成索引，或联系人工客服。"
                    ),
                    quick_actions=actions or ["重新开始"],
                )
            ],
            intent="other",
            wait_for_user=True,
        )

    system_extra = str(config.get("systemExtra") or "")
    task = {
        "rag_recommend": (
            "根据资料推荐 1–2 个真实班型，给出关键安排，并逐条对应约束说明理由。"
            "每个班型请使用完整产品名（如「L1暑期集训班」「北京线下班」），"
            "不要只用「暑期集训班」等笼统名称。"
        ),
        "rag_qa": (
            "仅针对「聚焦班型」回答用户追问，事实必须来自资料。"
            "若已聚焦某一具体班型/等级，只回答该班型；不要罗列其他等级或全部班型的费用、课时、报名信息，"
            "除非用户明确要求对比或查看全部。"
        ),
        "rag_enroll": "仅说明资料中「聚焦班型」的报名方式；没有则说明需人工确认。禁止虚构链接/电话/余位。",
        "rag_platform": "介绍平台/会员/合作服务；禁止推荐学生或教师班型，勿混淆会员价与课程价。",
    }.get(ntype, "依据资料回答。")

    system = (
        "你是 AI 教育中心课程顾问。只能依据「资料摘要」回答，不得编造。"
        f"\n任务：{task}\n{system_extra}\n"
        "使用简体中文；直接输出回复正文。"
    )
    focus_hint = ""
    if ntype in ("rag_qa", "rag_enroll") and state.locked_course:
        focus_hint = (
            f"\n重要：当前用户关注的班型是「{state.locked_course}」。"
            "请只围绕该班型作答。"
        )
    user = (
        f"用户身份：{state.role}\n"
        f"约束：{state.constraint_slots()}\n"
        f"已推荐：{state.recommended_courses}\n"
        f"聚焦班型：{state.locked_course}\n"
        f"{focus_hint}"
        f"用户说：{text or '（请基于约束给出推荐）'}\n\n"
        f"资料摘要：\n{context}"
    )

    def _finish(content: str) -> NodeOutput:
        body = content.strip() if content else ""
        if not body:
            body = "模型暂时不可用，请稍后重试。"

        state_patch: dict[str, Any] | None = None
        if ntype == "rag_recommend":
            courses = _extract_course_names(body, state.role)
            if not courses and hits:
                courses = _extract_bracket_names(body)[
                    : int(config.get("maxCourses") or 2)
                ]
            if courses:
                state_patch = {"recommendedCourses": courses}
                # 推荐多个时不默认锁第一个笼统名；有明确产品名时锁第一个
                if config.get("lockFirstCourse", True):
                    state_patch["lockedCourse"] = courses[0]
        elif ntype in ("rag_qa", "rag_enroll"):
            locked = state.locked_course
            if not locked and state.recommended_courses:
                locked = state.recommended_courses[0]
            if locked:
                state_patch = {"lockedCourse": locked}

        return NodeOutput(
            messages=[
                AssistantOut(
                    content=body,
                    citations=citations or None,
                    quick_actions=actions or None,
                )
            ],
            intent="other",
            wait_for_user=True,
            state_patch=state_patch,
        )

    if stream:
        def _gen() -> Iterator[str | NodeOutput]:
            parts: list[str] = []
            for delta in _iter_llm_text(db, agent_id, system=system, user=user):
                parts.append(delta)
                yield delta
            yield _finish("".join(parts))

        return _gen()

    content = _llm_text(db, agent_id, system=system, user=user)
    return _finish(content or "")


def _session_control(
    db: Session,
    agent_id: str,
    config: dict,
    state: WorkflowRuntimeState,
    turn: TurnInput | None,
) -> NodeOutput:
    text = (turn.text if turn else "") or ""
    actions = [
        str(a).strip()
        for a in (
            config.get("quickActions")
            or ["学生课程", "教师培训", "平台服务"]
        )
        if str(a).strip()
    ]

    if turn and (
        turn.quick_action == "重新开始"
        or text.strip() in ("重新开始", "重来", "reset", "restart")
    ):
        restart_text = str(config.get("restartText") or "已为您重新开始。")
        return NodeOutput(
            messages=[AssistantOut(content=restart_text, quick_actions=actions)],
            intent="restart",
            wait_for_user=False,
        )

    # 在控制节点点选三大入口：确认身份后交由边回到流程，绝不当成重启
    role = _detect_role_from_quick(turn) or _detect_role_rule(text)
    if role:
        return NodeOutput(
            messages=[],
            intent="choose_role",
            wait_for_user=False,
            state_patch={"role": role, "roleStatus": "confirmed"},
        )

    intent = guess_intent_from_text(text) or "other"
    if intent == "list_courses" or "查看所有" in text or (
        turn and turn.quick_action == "查看所有课程"
    ):
        intro = str(config.get("listCoursesIntro") or "当前可了解：")
        kb_id = state.active_knowledge_base_id
        role_label = {
            "student": "学生/家长",
            "teacher": "教师",
            "org": "机构/企业",
        }.get(state.role or "", "当前身份")
        list_query = {
            "student": "班型 课程 安排 目录 夏令营",
            "teacher": "教师培训 集训 研修 班型 安排 目录",
            "org": "平台模块 会员权益 企业合作 服务 产品介绍",
        }.get(state.role or "", "班型 课程 安排 目录 服务")
        if state.role_status == "confirmed" and state.role and kb_id:
            hits = retrieve_by_kb_id(
                db, kb_id=kb_id, query=list_query, top_k=6
            )
            if hits:
                body = f"{intro}（{role_label}）\n\n" + format_hits_for_prompt(hits)
            else:
                body = (
                    f"{intro}（{role_label}）\n"
                    "资料中暂未检索到可列出的目录内容，请继续提问或联系人工客服。"
                )
        elif state.role_status == "confirmed" and state.role:
            body = (
                f"已确认您为{role_label}，但该身份对应的知识库尚未绑定或未索引完成，"
                "暂时无法列出内容。请在流程「知识范围」节点完成绑定后重试。"
            )
        else:
            body = (
                "尚未确认身份，无法按资料列出内容。"
                "请先选择「学生课程 / 教师培训 / 平台服务」。"
            )
        # 列出后回到角色对应节点，避免下一轮卡在控制节点
        resume_node: str | None = None
        if state.role == "org":
            resume_node = "n_platform"
        elif state.role in ("student", "teacher"):
            if state.locked_course or state.recommended_courses:
                resume_node = "n_qa"
            else:
                resume_node = "n_slots"
        return NodeOutput(
            messages=[AssistantOut(content=body, quick_actions=actions)],
            intent="other",
            wait_for_user=True,
            state_patch={"currentNodeId": resume_node} if resume_node else None,
        )

    if intent == "restart":
        restart_text = str(config.get("restartText") or "已为您重新开始。")
        return NodeOutput(
            messages=[AssistantOut(content=restart_text, quick_actions=actions)],
            intent="restart",
            wait_for_user=False,
        )

    # 未识别输入：提示继续选择，禁止默认当成「重新开始」
    return NodeOutput(
        messages=[
            AssistantOut(
                content="请选择「学生课程 / 教师培训 / 平台服务」继续，或点击页头「重新开始」清空会话。",
                quick_actions=actions,
            )
        ],
        intent="other",
        wait_for_user=True,
    )


def _boundary(config: dict, turn: TurnInput | None) -> NodeOutput:
    templates = config.get("templates") if isinstance(config.get("templates"), dict) else {}
    actions = list(config.get("quickActions") or ["学生课程", "教师培训", "平台服务", "重新开始"])
    text = (turn.text if turn else "") or ""
    key = "outOfScope"
    if "会员" in text or "平台价" in text:
        key = "crossMaterial"
    content = str(templates.get(key) or templates.get("outOfScope") or "超出服务范围。")
    return NodeOutput(
        messages=[AssistantOut(content=content, quick_actions=actions)],
        intent="other",
        wait_for_user=True,
    )


def _detect_role_rule(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in ("学生", "家长", "孩子", "报班", "夏令营")):
        return "student"
    if any(k in t for k in ("教师", "老师", "教研", "培训师资")):
        return "teacher"
    if any(k in t for k in ("机构", "企业", "公司", "平台", "会员", "opc")):
        return "org"
    return None


def _detect_role_from_quick(turn: TurnInput | None) -> str | None:
    if not turn:
        return None
    mapping = {
        "学生课程": "student",
        "教师培训": "teacher",
        "平台服务": "org",
    }
    key = turn.quick_action or turn.text.strip()
    return mapping.get(key)


def _rule_fill_slots(text: str, out: dict[str, str]) -> None:
    if re.search(r"北京|上海|广州|深圳|杭州|线上", text):
        if "线上" in text and "线下" not in text:
            out.setdefault("format", "线上")
        if "线下" in text:
            out.setdefault("format", "线下")
        for city in ("北京", "上海", "广州", "深圳", "杭州"):
            if city in text:
                out.setdefault("city", city)
                break
    if re.search(r"7\s*月|8\s*月|周末|暑假", text):
        out.setdefault("date", text.strip()[:40])
    if re.search(r"编程|素养|竞赛|入门|进阶", text):
        out.setdefault("goal", text.strip()[:40])


def _normalize_course_label(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("暑假", "暑期")
    s = re.sub(r"[，,。．;；:：]+$", "", s)
    return s


def _build_query(ntype: str, state: WorkflowRuntimeState, text: str) -> str:
    parts = [text.strip()]
    parts.extend(state.constraint_slots().values())
    # 追问/报名：优先按已锁定班型检索，避免把全部推荐班型塞进 query 拉回全系列费用
    if ntype in ("rag_qa", "rag_enroll"):
        if state.locked_course:
            parts.append(state.locked_course)
        elif state.recommended_courses:
            parts.append(state.recommended_courses[0])
    else:
        if state.locked_course:
            parts.append(state.locked_course)
        parts.extend(state.recommended_courses)
    if ntype == "rag_recommend":
        parts.append("班型 课程安排 推荐")
    elif ntype == "rag_enroll":
        parts.append("报名 联系方式 报名流程")
    elif ntype == "rag_platform":
        parts.append("平台 会员 企业合作")
    elif ntype == "rag_qa" and any(k in text for k in ("费用", "多少钱", "价格", "学费")):
        parts.append("费用 价格")
    return " ".join(p for p in parts if p)


def _extract_course_names(content: str, role: str | None) -> list[str]:
    """从推荐回复中抽取具体班型名（优先 L1/L2 等完整产品名）。"""
    found: list[str] = []

    def _add(raw: str) -> None:
        name = _normalize_course_label(raw)
        if len(name) < 2 or len(name) > 40:
            return
        # 过滤明显不是班型的片段
        if any(x in name for x in ("理由", "安排", "以下", "如下", "适配")):
            return
        for existing in found:
            if _normalize_course_label(existing) == name:
                return
        found.append(name)

    # 1) 「推荐班型1：L1暑期集训班」
    for m in re.finditer(
        r"推荐班型\s*\d+\s*[:：]\s*([^\n（(【]{2,40})", content
    ):
        _add(m.group(1))

    # 2) 教师产品：L1/L2/L3 + 暑期集训班 / 周末研修班
    for m in re.finditer(
        r"L\s*[123]\s*暑[假期]集训班|L\s*[123]\s*周末研修班", content, flags=re.I
    ):
        _add(m.group(0))

    if found:
        return found[:2]

    # 3) 角色目录（学生班型或教师笼统名）
    catalog = {
        "student": ["北京线下班", "上海线下班", "线上直播班"],
        "teacher": ["暑期集训班", "周末研修班"],
    }.get(role or "", [])
    # 长名优先，避免「暑期集训班」抢在「L1暑期集训班」之前（此处 catalog 已无 L 级）
    for name in sorted(catalog, key=len, reverse=True):
        if name in content:
            _add(name)
    if found:
        return found[:2]

    # 4) 书名号等兜底
    return _extract_bracket_names(content)[:2]


def _resolve_course_from_user_text(
    text: str, state: WorkflowRuntimeState
) -> str | None:
    """根据用户输入在已推荐/已锁定班型中选定聚焦班型。"""
    raw = (text or "").strip()
    if not raw:
        return state.locked_course

    candidates: list[str] = []
    for c in list(state.recommended_courses or []):
        if c and c not in candidates:
            candidates.append(c)
    if state.locked_course and state.locked_course not in candidates:
        candidates.append(state.locked_course)

    norm_text = _normalize_course_label(raw)
    scored: list[tuple[int, str]] = []

    for c in candidates:
        cn = _normalize_course_label(c)
        if not cn:
            continue
        score = 0
        if cn == norm_text or cn in norm_text or norm_text in cn:
            score = 100 + len(cn)
        else:
            # L1 / L2 等级线索
            lvl = re.search(r"L\s*([123])", c, flags=re.I)
            if lvl and re.search(rf"L\s*{lvl.group(1)}\b", raw, flags=re.I):
                score = 80 + len(cn)
            # 「集训班」「研修班」粗匹配：仅当候选唯一含该关键词时
            elif "集训" in cn and "集训" in norm_text and "研修" not in norm_text:
                same = [x for x in candidates if "集训" in _normalize_course_label(x)]
                if len(same) == 1:
                    score = 40 + len(cn)
            elif "研修" in cn and "研修" in norm_text:
                same = [x for x in candidates if "研修" in _normalize_course_label(x)]
                if len(same) == 1:
                    score = 40 + len(cn)
        if score > 0:
            scored.append((score, c))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    # 用户话里直接出现 Lx暑期集训班，即使还不在推荐列表
    m = re.search(r"L\s*[123]\s*暑[假期]集训班|L\s*[123]\s*周末研修班", raw, flags=re.I)
    if m:
        return _normalize_course_label(m.group(0))

    # 「这个班/该班」等指代：沿用当前锁定
    if re.search(r"这个班|该班|这门课|上述|刚才", raw) and state.locked_course:
        return state.locked_course

    return state.locked_course


def _extract_bracket_names(content: str) -> list[str]:
    names = re.findall(r"「([^」]{2,20})」|【([^】]{2,20})】|《([^》]{2,20})》", content)
    flat = [a or b or c for a, b, c in names]
    return [_normalize_course_label(x) for x in flat if x]


def _llm_json(db: Session, agent_id: str, *, system: str, user: str) -> dict | None:
    helper = CourseAgentLlmHelper(db, agent_id)
    if not helper.is_available():
        return None
    try:
        raw = chat_completion(
            api_key=helper.runtime.api_key,
            endpoint_id=helper.runtime.endpoint_id,
            base_url=helper.runtime.base_url,
            timeout_seconds=helper.runtime.timeout_seconds,
            temperature=0.1,
            stream=False,
            messages=[
                DoubaoChatMessage(role="system", content=system),
                DoubaoChatMessage(role="user", content=user),
            ],
        )
    except DoubaoClientError as exc:
        logger.warning("workflow llm json failed: %s", exc)
        return None
    return _parse_json_object(raw)


def _llm_text(db: Session, agent_id: str, *, system: str, user: str) -> str | None:
    parts = list(_iter_llm_text(db, agent_id, system=system, user=user))
    text = "".join(parts).strip()
    return text or None


def _iter_llm_text(
    db: Session, agent_id: str, *, system: str, user: str
) -> Iterator[str]:
    helper = CourseAgentLlmHelper(db, agent_id)
    if not helper.is_available():
        return
    try:
        yield from iter_chat_completion(
            api_key=helper.runtime.api_key,
            endpoint_id=helper.runtime.endpoint_id,
            base_url=helper.runtime.base_url,
            timeout_seconds=helper.runtime.timeout_seconds,
            temperature=helper.runtime.temperature,
            messages=[
                DoubaoChatMessage(role="system", content=system),
                DoubaoChatMessage(role="user", content=user),
            ],
        )
    except DoubaoClientError as exc:
        logger.warning("workflow llm text failed: %s", exc)
        return


def _parse_json_object(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None
