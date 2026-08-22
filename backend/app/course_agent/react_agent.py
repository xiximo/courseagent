"""Harness 智能体：知识库检索 + 用户画像工具，结合 Soul 与禁止规则规划问答。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.course_agent.model_runtime import resolve_agent_doubao_runtime
from app.course_agent.profile_tools import (
    BUILTIN_PROFILE_TOOLS,
    execute_get_profile,
    execute_update_profile,
)
from app.course_agent.rag import (
    format_hits_for_prompt,
    hits_to_citations_from_hits,
    retrieve_by_kb_id,
)
from app.course_agent.state_machine import Citation
from app.course_agent.trace import format_json_detail, make_trace, tool_label
from app.db.models.course_agent import CourseAgentSessionRecord
from app.llm.doubao_client import DoubaoClientError, chat_completion_turn

logger = logging.getLogger(__name__)

DEFAULT_SOUL = """你是「健康优选」平台的 AI 智能膳食顾问，面向 25–45 岁都市白领，7×24 提供个性化膳食建议。

你需要：
1. 识别用户倾向：减脂塑形 / 增肌强化 / 慢病调理；也可根据「想减重」「在健身」「血糖偏高」等描述判断。
2. 回答任何膳食方案、蛋白质、热量或食材问题前，必须先调用 get_user_profile，核对该用户的目标、约束、疾病与过敏。
3. 用户新提到目标、疾病、过敏、忌口时，先调用 update_user_profile 写入画像，再检索资料回答。
4. 从核心营养资料中推荐 1–2 个最匹配的膳食方案或食材组合，并给出 1–2 句推荐理由；推荐必须服从画像约束（例如肾病禁止高蛋白增肌方案）。
5. 回答食材营养、搭配原则、禁忌、热量/蛋白质/GI 等问题时，必须依据工具返回的资料，并标注来源（文档名 + 章节）。
6. 平台介绍、会员、企业合作问题，只使用平台资料工具，不要夹带膳食方案推荐。
7. 使用简体中文，语气专业、克制、友好。"""

DEFAULT_PROHIBITION_RULES = """禁止规则：
1. 不得编造营养数据、热量、GI 值、方案名称、价格、联系方式或 succeess case。
2. 核心营养问题（推荐、食材、禁忌、膳食方案）禁止使用平台白皮书中的会员价格/企业合作信息。
3. 平台介绍问题禁止输出膳食方案/食材推荐，避免两类资料混淆。
4. 不得提供医疗诊断或治疗建议。用户提到疾病、血糖、血压、痛风、过敏时，必须附加：「本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师」。
5. 资料不足时明确说明「现有资料中未找到相关信息」，不要猜测。
6. 未调用 get_user_profile 前，不得给出具体膳食方案或蛋白质/热量数字建议。
7. 画像约束与知识库建议冲突时，以用户健康约束为准，并说明原因。
8. 直接输出回复正文；引用格式示例：来源：《2026秋季健康膳食指南》· 秋季时令食材。"""

DEFAULT_WELCOME = (
    "您好，我是健康优选 AI 膳食顾问。可咨询减脂、增肌或慢病调理怎么吃，"
    "也可以了解平台会员与企业服务。请直接描述您的情况和问题。"
)

DEFAULT_MENU_BUTTONS = [
    "减脂怎么吃",
    "增肌蛋白质怎么补",
    "血糖高饮食注意",
    "了解平台服务",
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
    if agent_name.strip() and "膳食" not in agent_name:
        welcome = f"您好，我是{agent_name.strip()}。{DEFAULT_WELCOME.removeprefix('您好，我是健康优选 AI 膳食顾问。').strip()}"
    return {
        "soul": DEFAULT_SOUL,
        "prohibitionRules": DEFAULT_PROHIBITION_RULES,
        "maxToolRounds": 5,
        "tools": tools,
    }


def default_tools_from_knowledge_bases(
    knowledge_bases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    core_ids: list[str] = []
    platform_ids: list[str] = []
    others: list[dict[str, Any]] = []
    for kb in knowledge_bases:
        kb_id = str(kb.get("id") or "").strip()
        if not kb_id:
            continue
        label = str(kb.get("materialLabel") or kb.get("material_label") or "").lower()
        name = str(kb.get("name") or "")
        blob = f"{label} {name}"
        if any(token in blob for token in ("material_c", "白皮书", "平台服务", "会员")):
            platform_ids.append(kb_id)
        elif any(
            token in blob
            for token in ("material_a", "material_b", "膳食指南", "饮食计划", "营养")
        ):
            core_ids.append(kb_id)
        else:
            others.append(kb)

    tools: list[dict[str, Any]] = [dict(item) for item in BUILTIN_PROFILE_TOOLS]
    if core_ids:
        tools.append(
            {
                "id": "tool_core_nutrition",
                "name": "search_core_nutrition",
                "description": (
                    "检索核心营养知识库（膳食指南、个性化饮食计划）。"
                    "用于减脂/增肌/调理推荐、食材营养成分、搭配原则、禁忌与替换。"
                    "禁止用于会员价格、企业合作或平台套餐介绍。"
                ),
                "knowledgeBaseIds": core_ids,
                "enabled": True,
            }
        )
    if platform_ids:
        tools.append(
            {
                "id": "tool_platform",
                "name": "search_platform_guide",
                "description": (
                    "检索健康优选平台白皮书。仅用于平台介绍、会员订阅、企业健康管理、合作方案。"
                    "禁止用于膳食方案推荐或营养成分问答。"
                ),
                "knowledgeBaseIds": platform_ids,
                "enabled": True,
            }
        )
    for index, kb in enumerate(others, start=1):
        kb_id = str(kb.get("id") or "").strip()
        kb_name = str(kb.get("name") or f"知识库{index}")
        tools.append(
            {
                "id": f"tool_kb_{index}",
                "name": sanitize_tool_name(f"search_{kb_name}", f"search_kb_{index}"),
                "description": f"检索知识库「{kb_name}」。仅在问题与该库主题相关时调用。",
                "knowledgeBaseIds": [kb_id],
                "enabled": True,
            }
        )
    return tools


def _tool_kind(item: dict[str, Any]) -> str:
    kind = str(item.get("kind") or "").strip()
    name = str(item.get("name") or "")
    if kind in ("profile_get", "profile_update", "kb"):
        return kind
    if name == "get_user_profile":
        return "profile_get"
    if name == "update_user_profile":
        return "profile_update"
    return "kb"


def _is_runnable_tool(item: dict[str, Any]) -> bool:
    if not item.get("enabled"):
        return False
    kind = _tool_kind(item)
    if kind in ("profile_get", "profile_update"):
        return True
    return bool(item.get("knowledgeBaseIds"))


def normalize_react_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    tools: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(data.get("tools") or []):
        if not isinstance(item, dict):
            continue
        kind = _tool_kind(item)
        name = sanitize_tool_name(str(item.get("name") or f"search_kb_{index + 1}"))
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
        if kind in ("profile_get", "profile_update"):
            kb_ids = []
        enabled = bool(item.get("enabled", True))
        if kind == "kb":
            enabled = enabled and bool(kb_ids)
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
    reserved = {item["name"] for item in BUILTIN_PROFILE_TOOLS}
    for builtin in BUILTIN_PROFILE_TOOLS:
        existing = by_name.get(builtin["name"])
        merged.append(
            {
                **builtin,
                "enabled": existing.get("enabled", True) if existing else True,
            }
        )
    for item in tools:
        if item["name"] in reserved or item.get("kind") in ("profile_get", "profile_update"):
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
        "你可以通过函数工具检索知识库，或读写用户画像，可多次调用。"
        "回答膳食/蛋白质/热量问题前必须先 get_user_profile；"
        "用户提到新的目标、疾病、过敏或忌口时调用 update_user_profile。"
        "update_user_profile 会自行读取该用户在数据库中的发言并用模型归纳，不必在参数里复述全部对话。"
        "先工具后回答；不要在没有资料时给出具体数字或方案名称。\n"
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
    query = str(args.get("query") or user_text)
    return execute_kb_tool(db, tool=tool, query=query)


def execute_kb_tool(
    db: Session,
    *,
    tool: dict[str, Any],
    query: str,
    top_k: int = 6,
) -> tuple[str, list[Citation]]:
    kb_ids = [str(item).strip() for item in (tool.get("knowledgeBaseIds") or []) if str(item).strip()]
    if not kb_ids:
        return "该工具未绑定知识库。", []
    q = (query or "").strip()
    if not q:
        return "检索词为空。", []

    merged: dict[str, Any] = {}
    for kb_id in kb_ids:
        for hit in retrieve_by_kb_id(db, kb_id=kb_id, query=q, top_k=top_k):
            existing = merged.get(hit.chunkId)
            if existing is None or (hit.score or 0) > (existing.score or 0):
                merged[hit.chunkId] = hit
    hits = sorted(merged.values(), key=lambda item: item.score or 0.0, reverse=True)[:top_k]
    if not hits:
        return f"知识库「{tool['name']}」未检索到与「{q}」相关的资料。", []
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
