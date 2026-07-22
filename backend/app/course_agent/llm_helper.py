"""Course Agent 豆包 LLM 增强（qa / recommend / enroll 步骤）。"""



from __future__ import annotations



import logging



from sqlalchemy.orm import Session



from app.course_agent.model_runtime import resolve_agent_doubao_runtime

from app.course_agent.state_machine import AgentMessage, SessionState

from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, chat_completion



logger = logging.getLogger(__name__)



SYSTEM_PROMPT = """你是 AI 教育中心的课程顾问助手。只能依据提供的「资料摘要」和「会话上下文」回答。

规则：
1. 优先依据「检索到的资料片段」组织推荐与问答；规则引擎草稿仅作参考，不得与资料矛盾。
2. 不得编造班型名称、费用、时间、报名方式或师资信息。
3. 资料摘要不足以回答时，明确说明「现有资料中未找到相关信息」，并建议联系人工客服；此时不要保留草稿中的假想来源。
4. 平台会员价格属于平台服务范畴，与学生/教师课程费用不同；跨身份问题需引导切换入口。
5. 使用简体中文，语气友好、简洁；可提及资料中的文档名与章节。
6. 直接输出回复正文，不要 JSON 或 markdown 代码块。"""


def resolve_system_prompt(conversation: dict | None = None) -> str:
    """优先使用 Agent 配置中的 systemPrompt，否则回落到默认提示词。"""
    custom = str((conversation or {}).get("systemPrompt") or "").strip()
    return custom or SYSTEM_PROMPT


class CourseAgentLlmHelper:
    def __init__(self, db: Session, agent_id: str) -> None:
        self.db = db
        self.agent_id = agent_id
        self.runtime = resolve_agent_doubao_runtime(db, agent_id)

    def is_available(self) -> bool:
        return self.runtime.is_configured

    def enhance_reply(
        self,
        *,
        user_text: str,
        state: SessionState,
        draft: AgentMessage,
        retrieval_context: str | None = None,
    ) -> AgentMessage | None:
        if not self.is_available():
            return None
        if state.step not in ("recommend", "qa", "enroll"):
            return None
        if draft.role != "assistant":
            return None

        context = self._build_context(state, draft, retrieval_context)
        user_prompt = (
            f"用户问题：{user_text}\n\n"
            f"会话上下文：\n{context}\n\n"
            f"规则引擎草稿回复（可参考结构，但事实必须以资料片段为准）：\n{draft.content}"
        )

        try:
            raw = chat_completion(
                api_key=self.runtime.api_key,
                endpoint_id=self.runtime.endpoint_id,
                base_url=self.runtime.base_url,
                timeout_seconds=self.runtime.timeout_seconds,
                temperature=self.runtime.temperature,
                stream=self.runtime.stream,
                messages=[
                    DoubaoChatMessage(role="system", content=SYSTEM_PROMPT),
                    DoubaoChatMessage(role="user", content=user_prompt),
                ],
            )
        except DoubaoClientError as exc:
            logger.warning("Course agent LLM enhance failed: %s", exc)
            return None

        text = raw.strip()
        if not text:
            return None

        return AgentMessage(
            id=draft.id,
            role=draft.role,
            content=text,
            created_at=draft.created_at,
            citations=draft.citations,
            quick_actions=draft.quick_actions,
        )



    def _build_context(

        self,

        state: SessionState,

        draft: AgentMessage,

        retrieval_context: str | None = None,

    ) -> str:

        role_label = {

            "student": "学生/家长",

            "teacher": "教师",

            "org": "机构/企业",

        }.get(state.role or "", "未识别")

        lines = [

            f"当前步骤：{state.step}",

            f"用户身份：{role_label}",

            f"约束条件：{state.constraints or '无'}",

        ]

        if state.recommended_courses:

            lines.append(f"已推荐班型：{', '.join(state.recommended_courses)}")

        if state.locked_course:

            lines.append(f"当前聚焦班型：{state.locked_course}")

        if draft.citations:

            cites = "; ".join(f"{c.document} {c.chapter}" for c in draft.citations)

            lines.append(f"引用章节：{cites}")

        if retrieval_context:

            lines.append(f"检索到的资料片段：\n{retrieval_context}")

        return "\n".join(lines)



    def generate_preview_reply(

        self,

        *,

        user_text: str,

        retrieval_context: str | None,

        history: list[AgentMessage] | None = None,

        system_prompt: str | None = None,

    ) -> AgentMessage | None:

        if not self.is_available():

            return None



        from app.course_agent.state_machine import _msg_id, _now_iso



        history_lines: list[str] = []

        for msg in (history or [])[-8:]:

            role_label = "用户" if msg.role == "user" else "助手"

            snippet = (msg.content or "").strip().replace("\n", " ")

            if len(snippet) > 240:

                snippet = snippet[:240] + "…"

            history_lines.append(f"{role_label}：{snippet}")



        context_parts = []

        if history_lines:

            context_parts.append("近期对话：\n" + "\n".join(history_lines))

        if retrieval_context:

            context_parts.append(f"检索到的资料片段：\n{retrieval_context}")

        context = "\n\n".join(context_parts) if context_parts else "（无额外上下文）"



        user_prompt = (

            f"用户问题：{user_text}\n\n"

            f"上下文：\n{context}\n\n"

            "请依据资料片段回答；资料不足时明确说明未找到相关信息。"

        )

        prompt = (system_prompt or "").strip() or SYSTEM_PROMPT



        try:

            raw = chat_completion(
                api_key=self.runtime.api_key,
                endpoint_id=self.runtime.endpoint_id,
                base_url=self.runtime.base_url,
                timeout_seconds=self.runtime.timeout_seconds,
                temperature=self.runtime.temperature,
                stream=self.runtime.stream,

                messages=[

                    DoubaoChatMessage(role="system", content=prompt),

                    DoubaoChatMessage(role="user", content=user_prompt),

                ],

            )

        except DoubaoClientError as exc:

            logger.warning("Course agent preview LLM failed: %s", exc)

            return None



        text = raw.strip()

        if not text:

            return None



        return AgentMessage(

            id=_msg_id(),

            role="assistant",

            content=text,

            created_at=_now_iso(),

        )

