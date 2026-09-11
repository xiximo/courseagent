"""Harness 智能体：知识库检索与班型 Skill，结合 Soul 与禁止规则规划问答。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.course_agent.model_runtime import resolve_agent_doubao_runtime
from app.course_agent.course_skills import (
    BUILTIN_COURSE_SKILLS,
    COURSE_SKILL_SCHEMAS,
    OUT_OF_KNOWLEDGE_REPLY,
    execute_query_course_detail,
    execute_recommend_courses,
)
from app.course_agent.profile_tools import (
    execute_get_profile,
    execute_update_profile,
)
from app.course_agent.material_service import MaterialService
from app.course_agent.rag import (
    format_hits_for_prompt,
    hits_to_citations_from_hits,
    retrieve_by_kb_id,
    retrieve_for_agent,
)
from app.course_agent.state_machine import Citation
from app.course_agent.trace import format_json_detail, make_trace, tool_label
from app.db.models.course_agent import CourseAgentSessionRecord
from app.llm.doubao_client import DoubaoClientError, chat_completion_turn

logger = logging.getLogger(__name__)

DEFAULT_SOUL = """你是「AI教育中心」的课程顾问，面向学生、教师与机构提供班型咨询。

你需要：
1. 用户询问某个班型的时间、地点、费用、师资或大纲时，必须先调用 query_course_detail，再据此回答。
2. 用户给出城市、时间偏好等约束（如「我在上海」「我只有周末有空」）时，必须先调用 recommend_courses，返回最匹配的 1–2 个班型及理由。
3. 班型 Skill 返回 SKILL_FALLBACK 时：参数缺失则请用户补充，未找到则说明暂无匹配，不要编造班型。
4. 资料性问答（已上传知识库文档中的内容）必须先检索知识库，并标注来源（文档名称 + 章节标题）。
5. 知识库与班型目录都无法覆盖的问题，明确说明「该问题不在我的知识范围内」，不要猜测。
6. 使用简体中文，语气专业、克制、友好。"""

DEFAULT_PROHIBITION_RULES = f"""禁止规则：
1. 不得编造班型名称、价格、上课地点、师资、联系方式或成功案例。
2. 班型详情与推荐必须来自 query_course_detail / recommend_courses 的返回，禁止用知识库片段拼凑不存在的班型。
3. 资料不足或问题超出知识范围时，必须使用原句「{OUT_OF_KNOWLEDGE_REPLY}」，不要改写。
4. 不得提供医疗诊断或治疗建议。
5. 直接输出回复正文；引用格式示例：来源：《文档名称》· 章节标题。"""

DEFAULT_WELCOME = (
    "您好，我是 AI 教育中心课程顾问。可查询班型详情、按城市和时间偏好推荐课程，"
    "也可以基于已上传资料回答问题。请直接描述您的需求。"
)

DEFAULT_MENU_BUTTONS = [
    "北京线下班详情",
    "上海线下班详情",
    "我在上海，周末有空",
    "只有工作日能上课",
]

MEDICAL_MARKERS = (
    "糖尿病",
    "血糖",
    "血压",
    "高血压",
    "痛风",
    "尿酸",
    "过敏",
    "肾病",
    "妊娠",
    "孕妇",
    "疾病",
    "用药",
    "治疗",
)

DISCLAIMER = "本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师。"

_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")


def sanitize_tool_name(raw: str, fallback: str = "search_kb") -> str:
    text = _TOOL_NAME_RE.sub("_", (raw or "").strip())
    text = text.strip("_")
    if not text:
        text = fallback
    if text[0].isdigit():
        text = f"kb_{text}"
    return text[:64]


def has_knowledge_tools(tools: list[dict[str, Any]] | None) -> bool:
    return any(
        _tool_kind(item) == "kb" and item.get("knowledgeBaseIds")
        for item in (tools or [])
        if isinstance(item, dict)
    )


def default_react_config(
    *,
    agent_name: str = "",
    knowledge_bases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tools = default_tools_from_knowledge_bases(knowledge_bases or [])
    welcome = DEFAULT_WELCOME
    if agent_name.strip() and "课程顾问" not in agent_name:
        welcome = (
            f"您好，我是{agent_name.strip()}。"
            f"{DEFAULT_WELCOME.removeprefix('您好，我是 AI 教育中心课程顾问。').strip()}"
        )
    return {
        "soul": DEFAULT_SOUL,
        "prohibitionRules": DEFAULT_PROHIBITION_RULES,
        "maxToolRounds": 5,
        "tools": tools,
    }


_LEGACY_DEFAULT_TOOL_NAMES = frozenset(
    {"search_core_nutrition", "search_platform_guide"}
)
_AUTO_DEFAULT_KB_TOOL_RE = re.compile(r"^search_kb_\d+$")

TENANT_KB_SEARCH_TOOL = {
    "id": "tool_search_knowledge",
    "name": "search_knowledge",
    "kind": "kb",
    "description": (
        "检索本机构知识库中的课程资料与文档。"
        "资料性问答必须先调用；未绑定具体知识库时自动检索该机构全部知识库。"
        "禁止用模型自身知识编造资料。"
    ),
    "knowledgeBaseIds": [],
    "enabled": True,
}


def default_tools_from_knowledge_bases(
    knowledge_bases: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """默认只保留班型 Skill；知识库检索在对话时按本机构库自动挂上。"""
    _ = knowledge_bases
    return [dict(item) for item in BUILTIN_COURSE_SKILLS]


def _is_auto_default_kb_tool(name: str) -> bool:
    return name in _LEGACY_DEFAULT_TOOL_NAMES or bool(_AUTO_DEFAULT_KB_TOOL_RE.fullmatch(name))


_BUILTIN_KINDS = {
    "profile_get",
    "profile_update",
    "course_detail",
    "course_recommend",
    "kb",
}


def _tool_kind(item: dict[str, Any]) -> str:
    kind = str(item.get("kind") or "").strip()
    name = str(item.get("name") or "")
    if kind in _BUILTIN_KINDS:
        return kind
    if name == "get_user_profile":
        return "profile_get"
    if name == "update_user_profile":
        return "profile_update"
    if name == "query_course_detail":
        return "course_detail"
    if name == "recommend_courses":
        return "course_recommend"
    return "kb"


def _is_runnable_tool(item: dict[str, Any]) -> bool:
    if not item.get("enabled"):
        return False
    kind = _tool_kind(item)
    if kind in ("profile_get", "profile_update", "course_detail", "course_recommend", "kb"):
        return True
    return bool(item.get("knowledgeBaseIds"))


def _tenant_kb_ids(db: Session, agent_id: str) -> list[str]:
    try:
        return MaterialService(db).list_kb_ids_for_agent(agent_id)
    except Exception:
        logger.exception("Failed to list tenant knowledge bases for %s", agent_id)
        return []


def bind_tools_to_tenant_knowledge(
    tools: list[dict[str, Any]],
    kb_ids: list[str],
) -> list[dict[str, Any]]:
    """未绑定知识库的检索工具，运行时落到本机构知识库。"""
    bound: list[dict[str, Any]] = []
    has_kb_tool = False
    for item in tools:
        tool = dict(item)
        if _tool_kind(tool) == "kb":
            has_kb_tool = True
            if not tool.get("knowledgeBaseIds") and kb_ids:
                tool["knowledgeBaseIds"] = list(kb_ids)
        bound.append(tool)
    if not has_kb_tool and kb_ids:
        bound.append({**TENANT_KB_SEARCH_TOOL, "knowledgeBaseIds": list(kb_ids)})
    return bound


def normalize_react_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    tools: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(data.get("tools") or []):
        if not isinstance(item, dict):
            continue
        kind = _tool_kind(item)
        if kind in ("profile_get", "profile_update"):
            continue
        name = sanitize_tool_name(str(item.get("name") or f"search_docs_{index + 1}"))
        if _is_auto_default_kb_tool(name):
            continue
        original = name
        suffix = 2
        while name in seen_names:
            name = f"{original}_{suffix}"[:64]
            suffix += 1
        seen_names.add(name)
        kb_ids = [
            str(kb).strip()
            for kb in (item.get("knowledgeBaseIds") or [])
            if str(kb).strip()
        ]
        enabled = bool(item.get("enabled", True))
        tools.append(
            {
                "id": str(item.get("id") or f"tool_{index + 1}"),
                "name": name,
                "kind": kind,
                "description": str(item.get("description") or f"检索知识库（{name}）").strip(),
                "knowledgeBaseIds": kb_ids,
                "enabled": enabled,
            }
        )
    by_name = {item["name"]: item for item in tools}
    merged: list[dict[str, Any]] = []
    builtin_tools = [dict(item) for item in BUILTIN_COURSE_SKILLS]
    reserved = {item["name"] for item in builtin_tools}
    reserved_kinds = {
        "course_detail",
        "course_recommend",
    }
    for builtin in builtin_tools:
        existing = by_name.get(builtin["name"])
        merged.append(
            {
                **builtin,
                "enabled": existing.get("enabled", True) if existing else True,
                "description": (
                    str(existing.get("description") or "").strip()
                    or builtin["description"]
                    if existing
                    else builtin["description"]
                ),
                "knowledgeBaseIds": (
                    list(existing.get("knowledgeBaseIds") or []) if existing else []
                ),
            }
        )
    for item in tools:
        if item["name"] in reserved or item.get("kind") in reserved_kinds:
            continue
        merged.append(item)
    try:
        max_rounds = int(data.get("maxToolRounds") or 5)
    except (TypeError, ValueError):
        max_rounds = 5
    max_rounds = max(1, min(max_rounds, 8))
    return {
        "soul": str(data.get("soul") or DEFAULT_SOUL).strip() or DEFAULT_SOUL,
        "prohibitionRules": str(
            data.get("prohibitionRules") or DEFAULT_PROHIBITION_RULES
        ).strip()
        or DEFAULT_PROHIBITION_RULES,
        "maxToolRounds": max_rounds,
        "tools": merged,
    }


def build_system_prompt(react_cfg: dict[str, Any], enabled_tools: list[dict[str, Any]]) -> str:
    tool_lines = []
    for tool in enabled_tools:
        kind = _tool_kind(tool)
        extra = ""
        if kind == "kb":
            extra = f"（绑定库：{'、'.join(tool.get('knowledgeBaseIds') or []) or '未绑定'}）"
        tool_lines.append(
            f"- {tool['name']}：{tool.get('description') or ''}{extra}"
        )
    catalog = "\n".join(tool_lines) if tool_lines else "- （尚未配置工具，请不要编造资料）"
    return (
        f"{react_cfg['soul']}\n\n"
        f"{react_cfg['prohibitionRules']}\n\n"
        "你可以通过函数工具查询班型、推荐课程或检索知识库，可多次调用。"
        "班型详情必须先 query_course_detail；约束推荐必须先 recommend_courses。"
        "资料性问答必须先调用知识库检索工具；未绑定具体知识库时，工具会检索本机构全部知识库。"
        "禁止用模型自身知识代替检索结果。"
        "Skill 返回 SKILL_FALLBACK 时按降级策略请用户补充或说明未找到，不要编造。"
        f"资料不足时使用原句「{OUT_OF_KNOWLEDGE_REPLY}」。"
        "先工具后回答。\n"
        f"可用工具：\n{catalog}"
    )


def to_openai_tools(enabled_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tool in enabled_tools:
        kind = _tool_kind(tool)
        if kind == "profile_get":
            parameters: dict[str, Any] = {
                "type": "object",
                "properties": {},
            }
        elif kind in ("course_detail", "course_recommend"):
            parameters = COURSE_SKILL_SCHEMAS.get(tool["name"]) or {
                "type": "object",
                "properties": {},
            }
        elif kind == "profile_update":
            parameters = {
                "type": "object",
                "properties": {
                    "personaLabel": {
                        "type": "string",
                        "description": "减脂塑形 / 增肌强化 / 慢病调理，能判断时填写",
                    },
                    "summary": {
                        "type": "string",
                        "description": "更新后的用户画像综述",
                    },
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本轮新识别的目标，追加写入",
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "忌口、生活限制、不可接受的做法",
                    },
                    "conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "疾病或健康状况，如肾病、血糖偏高、痛风",
                    },
                    "allergies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "食物过敏",
                    },
                    "newFacts": {
                        "type": "string",
                        "description": "本轮用户提到的新事实摘要，可选；工具仍会读取数据库中的用户发言并用模型归纳",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["current", "all_users"],
                        "description": "current=当前用户；all_users=读取所有目标用户的历史发言并批量刷新",
                    },
                    "fromHistory": {
                        "type": "boolean",
                        "description": "是否从数据库读取用户发送的消息并用大模型归纳，默认 true",
                    },
                    "lookbackHours": {
                        "type": "number",
                        "description": "只使用最近若干小时内的用户发言；定时任务可按配置传入",
                    },
                },
            }
        else:
            parameters = {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索用的具体问题或关键词，尽量包含人群、食材或服务名称",
                    }
                },
                "required": ["query"],
            }
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "parameters": parameters,
                },
            }
        )
    return specs


def execute_named_tool(
    db: Session,
    *,
    tool: dict[str, Any],
    args: dict[str, Any],
    user_text: str,
    user_id: UUID | None,
    session: CourseAgentSessionRecord | None,
    agent_id: str | None = None,
) -> tuple[str, list[Citation]]:
    kind = _tool_kind(tool)
    if kind == "profile_get":
        return execute_get_profile(db, user_id=user_id, session=session), []
    if kind == "profile_update":
        return (
            execute_update_profile(
                db,
                user_id=user_id,
                session=session,
                args=args,
                agent_id=agent_id or (session.agent_id if session is not None else None),
            ),
            [],
        )
    if kind == "course_detail":
        return execute_query_course_detail(args), []
    if kind == "course_recommend":
        return execute_recommend_courses(args), []
    query = str(args.get("query") or user_text)
    return execute_kb_tool(db, tool=tool, query=query, agent_id=agent_id)


def execute_kb_tool(
    db: Session,
    *,
    tool: dict[str, Any],
    query: str,
    top_k: int = 6,
    agent_id: str | None = None,
) -> tuple[str, list[Citation]]:
    kb_ids = [str(item).strip() for item in (tool.get("knowledgeBaseIds") or []) if str(item).strip()]
    q = (query or "").strip()
    if not q:
        return "检索词为空。", []

    merged: dict[str, Any] = {}
    if kb_ids:
        for kb_id in kb_ids:
            for hit in retrieve_by_kb_id(
                db, kb_id=kb_id, query=q, top_k=top_k, agent_id=agent_id
            ):
                existing = merged.get(hit.chunkId)
                if existing is None or (hit.score or 0) > (existing.score or 0):
                    merged[hit.chunkId] = hit
    elif agent_id:
        for hit in retrieve_for_agent(db, agent_id=agent_id, query=q, top_k=top_k):
            existing = merged.get(hit.chunkId)
            if existing is None or (hit.score or 0) > (existing.score or 0):
                merged[hit.chunkId] = hit
    else:
        return "该工具未绑定知识库。", []
    hits = sorted(merged.values(), key=lambda item: item.score or 0.0, reverse=True)[:top_k]
    if not hits:
        return (
            f"知识库「{tool['name']}」未检索到与「{q}」相关的资料。"
            f"{OUT_OF_KNOWLEDGE_REPLY}",
            [],
        )
    citations = hits_to_citations_from_hits(hits)
    body = format_hits_for_prompt(hits)
    return f"工具 {tool['name']} 检索结果：\n{body}", citations


def _needs_disclaimer(user_text: str, reply: str) -> bool:
    blob = f"{user_text}\n{reply}"
    if not any(marker in blob for marker in MEDICAL_MARKERS):
        return False
    return DISCLAIMER not in (reply or "")


def _append_disclaimer(reply: str) -> str:
    text = (reply or "").rstrip()
    if not text:
        return DISCLAIMER
    return f"{text}\n\n{DISCLAIMER}"


def iter_react_turn(
    db: Session,
    *,
    agent_id: str,
    react_cfg: dict[str, Any],
    user_text: str,
    history: list[tuple[str, str]],
    user_id: UUID | None = None,
    session: CourseAgentSessionRecord | None = None,
) -> Iterator[tuple[str, Any]]:
    """产出 trace / delta / result 事件。"""
    cfg = normalize_react_config(react_cfg)
    tenant_kb_ids = _tenant_kb_ids(db, agent_id)
    cfg["tools"] = bind_tools_to_tenant_knowledge(cfg["tools"], tenant_kb_ids)
    enabled = [t for t in cfg["tools"] if _is_runnable_tool(t)]
    runtime = resolve_agent_doubao_runtime(db, agent_id)
    if not runtime.is_configured:
        yield (
            "trace",
            make_trace("reply", "LLM 未配置，无法继续", status="done"),
        )
        yield (
            "result",
            {
                "content": "LLM 未配置。请先在智能体中绑定并启用模型后再试。",
                "citations": [],
            },
        )
        return

    system = build_system_prompt(cfg, enabled)
    messages: list[dict] = [{"role": "system", "content": system}]
    for role, content in history[-12:]:
        if role not in ("user", "assistant") or not (content or "").strip():
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    tools_spec = to_openai_tools(enabled)
    tools_by_name = {t["name"]: t for t in enabled}
    citations: list[Citation] = []
    seen_cite: set[str] = set()

    yield (
        "trace",
        make_trace("turn", "开始处理用户问题", detail=user_text.strip()[:400], status="running"),
    )

    try:
        for round_index in range(int(cfg["maxToolRounds"])):
            yield (
                "trace",
                make_trace(
                    "thinking",
                    f"第 {round_index + 1} 轮：模型规划中",
                    status="running",
                ),
            )
            completion = chat_completion_turn(
                api_key=runtime.api_key,
                endpoint_id=runtime.endpoint_id,
                base_url=runtime.base_url,
                timeout_seconds=runtime.timeout_seconds,
                temperature=runtime.temperature,
                messages=messages,
                tools=tools_spec or None,
            )
            thought = (completion.reasoning or completion.content or "").strip()
            if completion.tool_calls and thought:
                yield (
                    "trace",
                    make_trace("thinking", "模型思考", detail=thought, status="done"),
                )
            if not completion.tool_calls:
                if completion.reasoning:
                    yield (
                        "trace",
                        make_trace(
                            "thinking",
                            "模型思考",
                            detail=completion.reasoning,
                            status="done",
                        ),
                    )
                yield ("trace", make_trace("reply", "生成最终回答", status="running"))
                reply = completion.content
                if _needs_disclaimer(user_text, reply):
                    reply = _append_disclaimer(reply)
                if reply:
                    yield ("delta", {"text": reply})
                yield ("trace", make_trace("reply", "回答完成", status="done"))
                yield ("result", {"content": reply, "citations": citations})
                return

            messages.append(completion.assistant_message)
            for call in completion.tool_calls:
                tool = tools_by_name.get(call.name)
                try:
                    args = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                label = tool_label(call.name)
                yield (
                    "trace",
                    make_trace(
                        "tool",
                        f"调用 {label}",
                        detail=format_json_detail(args),
                        tool_name=call.name,
                        status="running",
                    ),
                )
                if tool is None:
                    result_text = f"未知工具：{call.name}"
                else:
                    result_text, new_cites = execute_named_tool(
                        db,
                        tool=tool,
                        args=args,
                        user_text=user_text,
                        user_id=user_id,
                        session=session,
                        agent_id=agent_id,
                    )
                    for cite in new_cites:
                        key = f"{cite.document}:{cite.chapter}"
                        if key in seen_cite:
                            continue
                        seen_cite.add(key)
                        citations.append(cite)
                yield (
                    "trace",
                    make_trace(
                        "tool_result",
                        f"{label} 返回",
                        detail=result_text[:2000],
                        tool_name=call.name,
                        status="done",
                    ),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result_text[:6000],
                    }
                )

        # 达到轮次上限：强制不再给工具，生成最终回答
        yield (
            "trace",
            make_trace("thinking", "工具轮次已达上限，改为直接作答", status="running"),
        )
        completion = chat_completion_turn(
            api_key=runtime.api_key,
            endpoint_id=runtime.endpoint_id,
            base_url=runtime.base_url,
            timeout_seconds=runtime.timeout_seconds,
            temperature=runtime.temperature,
            messages=messages
            + [
                {
                    "role": "user",
                    "content": "请根据已检索资料给出最终中文回答，不要再调用工具。",
                }
            ],
            tools=None,
        )
        if completion.reasoning:
            yield (
                "trace",
                make_trace("thinking", "模型思考", detail=completion.reasoning, status="done"),
            )
        yield ("trace", make_trace("reply", "生成最终回答", status="running"))
        reply = completion.content
        if _needs_disclaimer(user_text, reply):
            reply = _append_disclaimer(reply)
        if reply:
            yield ("delta", {"text": reply})
        yield ("trace", make_trace("reply", "回答完成", status="done"))
        yield ("result", {"content": reply, "citations": citations})
    except DoubaoClientError as exc:
        logger.warning("Harness turn failed: %s", exc)
        fallback = "服务繁忙，请稍后重试。"
        if citations:
            fallback = (
                "模型暂时不可用，以下为已检索到的资料摘要：\n\n"
                + "\n".join(f"- {c.document} · {c.chapter}" for c in citations[:5])
            )
        yield ("trace", make_trace("reply", "模型调用失败，已回退", detail=str(exc)[:400], status="done"))
        yield ("result", {"content": fallback, "citations": citations})
