from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.errors import ApiBusinessError
from app.db.models.attachment import Attachment
from app.db.models.llm_config import LlmConfigRecord
from app.db.models.qa_session import QaMessageRecord, QaSessionRecord
from app.db.models.standard import Standard
from app.indexing.service import IndexingService
from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, chat_completion
from app.schemas.indexing import ChunkSearchHitDto
from app.schemas.qa import (
    ChatMessageDto,
    CitationDto,
    QaAnswerDto,
    QaSessionDto,
)
from app.services.llm_settings import is_llm_configured, resolve_llm_runtime

logger = logging.getLogger(__name__)

DISCLAIMER = "建议仅供审核参考，最终结论以人工审核为准"

SYSTEM_PROMPT = """你是企业标准知识库问答助手。只能依据提供的「检索片段」回答，不得编造标准条款。

请严格输出 JSON（不要 markdown 代码块），格式：
{
  "conclusion": "一句话结论",
  "basis": ["判断依据1", "判断依据2"],
  "citations": [
    {
      "standardNo": "标准号",
      "standardName": "标准名称",
      "attachment": "附件文件名或空",
      "excerpt": "引用原文摘录（100字内）",
      "position": "章节/条款位置"
    }
  ],
  "scope": "适用范围说明，可空字符串",
  "riskNotice": "风险提示，无则空字符串"
}

规则：
1. 检索片段不足以回答时，conclusion 说明「当前知识库未找到足够依据」，basis 和 citations 为空数组，riskNotice 提示人工复核。
2. citations 必须来自检索片段，不得虚构标准号。
3. 使用简体中文。"""


class QaService:
    def __init__(self, db: Session, llm_config: LlmConfigRecord) -> None:
        self.db = db
        self.llm_config = resolve_llm_runtime(llm_config)

    def list_sessions(self) -> list[QaSessionDto]:
        rows = self.db.scalars(
            select(QaSessionRecord)
            .options(selectinload(QaSessionRecord.messages))
            .order_by(QaSessionRecord.updated_at.desc())
            .limit(50)
        ).all()
        return [self._to_session_dto(row) for row in rows]

    def create_session(self, *, standard_id: uuid.UUID | None = None) -> QaSessionDto:
        if standard_id is not None and self.db.get(Standard, standard_id) is None:
            raise ApiBusinessError("NOT_FOUND", "标准不存在", 404)

        row = QaSessionRecord(
            title="围绕标准提问" if standard_id else "新对话",
            standard_id=standard_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_session_dto(row)

    def send_message(self, session_id: uuid.UUID, content: str) -> QaSessionDto:
        if not is_llm_configured(self.llm_config):
            raise ApiBusinessError(
                "LLM_NOT_CONFIGURED",
                "LLM 未配置，请在系统设置中填写豆包 API Key 与 Endpoint",
                503,
            )

        session = self.db.scalar(
            select(QaSessionRecord)
            .options(selectinload(QaSessionRecord.messages))
            .where(QaSessionRecord.id == session_id)
        )
        if session is None:
            raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

        trimmed = content.strip()
        if not trimmed:
            raise ApiBusinessError("INVALID_INPUT", "消息内容不能为空", 400)

        user_msg = QaMessageRecord(session_id=session.id, role="user", content=trimmed)
        session.messages.append(user_msg)

        answer = self._generate_answer(session, trimmed)
        assistant_msg = QaMessageRecord(
            session_id=session.id,
            role="assistant",
            content=answer.conclusion,
            answer_json=answer.model_dump(),
        )
        session.messages.append(assistant_msg)

        if session.title in {"新对话", "围绕标准提问"} and len(trimmed) <= 30:
            session.title = trimmed
        session.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(session)
        return self._to_session_dto(session)

    def _generate_answer(
        self,
        session: QaSessionRecord,
        question: str,
    ) -> QaAnswerDto:
        kb_updated_at = self._knowledge_base_updated_at()
        hits = self._retrieve_chunks(question, session.standard_id)

        if not hits:
            return QaAnswerDto(
                conclusion="当前知识库未找到足够依据，建议人工复核。",
                basis=[],
                citations=[],
                riskNotice="当前知识库未找到足够依据，建议人工复核",
                disclaimer=DISCLAIMER,
                answeredAt=datetime.now(UTC).isoformat(),
                knowledgeBaseUpdatedAt=kb_updated_at,
            )

        context = self._build_context(hits)
        user_prompt = f"用户问题：{question}\n\n检索片段：\n{context}\n\n请输出 JSON 答案。"

        try:
            raw = chat_completion(
                api_key=self.llm_config.api_key,
                endpoint_id=self.llm_config.endpoint_id,
                base_url=self.llm_config.base_url,
                timeout_seconds=self.llm_config.timeout_seconds,
                messages=[
                    DoubaoChatMessage(role="system", content=SYSTEM_PROMPT),
                    DoubaoChatMessage(role="user", content=user_prompt),
                ],
            )
        except DoubaoClientError as exc:
            logger.exception("Doubao chat failed")
            raise ApiBusinessError("LLM_ERROR", str(exc), 502) from exc

        parsed = self._parse_llm_answer(raw, hits)
        parsed.answeredAt = datetime.now(UTC).isoformat()
        parsed.knowledgeBaseUpdatedAt = kb_updated_at
        parsed.disclaimer = DISCLAIMER
        return parsed

    def _retrieve_chunks(
        self,
        query: str,
        standard_id: uuid.UUID | None,
    ) -> list[ChunkSearchHitDto]:
        indexing = IndexingService(self.db)
        result = indexing.hybrid_search_chunks(
            query,
            standard_id=standard_id,
            top_k=self.llm_config.qa_top_k,
        )
        logger.info(
            "QA hybrid retrieval: query=%r standard_id=%s hits=%d sources=%s",
            query,
            standard_id,
            len(result.hits),
            sorted({hit.source for hit in result.hits if hit.source}),
        )
        return result.hits

    def _build_context(self, hits: list[ChunkSearchHitDto]) -> str:
        lines: list[str] = []
        for index, hit in enumerate(hits, start=1):
            meta = self._resolve_hit_meta(hit)
            excerpt = (hit.content or "").strip().replace("\n", " ")[:500]
            lines.append(
                f"[{index}] 标准号={meta['standard_no']} 标准名={meta['standard_name']} "
                f"附件={meta['attachment']} 位置={hit.positionLabel or '—'}\n{excerpt}"
            )
        return "\n\n".join(lines)

    def _resolve_hit_meta(self, hit: ChunkSearchHitDto) -> dict[str, str]:
        standard_no = ""
        standard_name = ""
        attachment_name = ""

        if hit.standardId:
            standard = self.db.get(Standard, uuid.UUID(hit.standardId))
            if standard:
                standard_no = standard.standard_no or standard.stand_number or ""
                standard_name = standard.name or ""

        if hit.attachmentId:
            attachment = self.db.get(Attachment, uuid.UUID(hit.attachmentId))
            if attachment:
                attachment_name = attachment.display_name or ""

        return {
            "standard_no": standard_no,
            "standard_name": standard_name,
            "attachment": attachment_name,
        }

    def _parse_llm_answer(
        self,
        raw: str,
        hits: list[ChunkSearchHitDto],
    ) -> QaAnswerDto:
        payload = self._extract_json(raw)
        if payload is None:
            return QaAnswerDto(
                conclusion=raw.strip() or "模型未返回有效答案",
                basis=[],
                citations=self._citations_from_hits(hits),
                disclaimer=DISCLAIMER,
                answeredAt="",
                knowledgeBaseUpdatedAt="",
            )

        citations = [
            CitationDto(
                standardNo=str(item.get("standardNo") or ""),
                standardName=str(item.get("standardName") or ""),
                attachment=item.get("attachment") or None,
                excerpt=str(item.get("excerpt") or ""),
                position=item.get("position") or None,
            )
            for item in payload.get("citations") or []
            if isinstance(item, dict)
        ]
        if not citations:
            citations = self._citations_from_hits(hits)
        else:
            citations = self._merge_citation_ids(citations, hits)

        basis = [str(item) for item in payload.get("basis") or [] if str(item).strip()]
        scope = str(payload.get("scope") or "").strip() or None
        risk = str(payload.get("riskNotice") or "").strip() or None

        return QaAnswerDto(
            conclusion=str(payload.get("conclusion") or "").strip() or "未能生成结论",
            basis=basis,
            citations=citations,
            scope=scope,
            riskNotice=risk,
            disclaimer=DISCLAIMER,
            answeredAt="",
            knowledgeBaseUpdatedAt="",
        )

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        text = raw.strip()
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

    def _citations_from_hits(self, hits: list[ChunkSearchHitDto]) -> list[CitationDto]:
        citations: list[CitationDto] = []
        for hit in hits[:5]:
            meta = self._resolve_hit_meta(hit)
            citations.append(
                CitationDto(
                    standardId=hit.standardId,
                    attachmentId=hit.attachmentId or None,
                    chunkId=hit.chunkId or None,
                    standardNo=meta["standard_no"],
                    standardName=meta["standard_name"],
                    attachment=meta["attachment"] or None,
                    excerpt=(hit.content or "")[:200],
                    position=hit.positionLabel,
                )
            )
        return citations

    @staticmethod
    def _merge_citation_ids(
        citations: list[CitationDto],
        hits: list[ChunkSearchHitDto],
    ) -> list[CitationDto]:
        merged: list[CitationDto] = []
        for index, cite in enumerate(citations):
            hit = hits[index] if index < len(hits) else None
            merged.append(
                cite.model_copy(
                    update={
                        "standardId": cite.standardId or (hit.standardId if hit else None),
                        "attachmentId": cite.attachmentId or (hit.attachmentId if hit else None),
                        "chunkId": cite.chunkId or (hit.chunkId if hit else None),
                    }
                )
            )
        return merged

    def _knowledge_base_updated_at(self) -> str:
        latest = self.db.scalar(
            select(Standard.updated_at).order_by(Standard.updated_at.desc()).limit(1)
        )
        if latest is None:
            return datetime.now(UTC).isoformat()
        return latest.isoformat()

    def _to_session_dto(self, session: QaSessionRecord) -> QaSessionDto:
        messages = sorted(session.messages, key=lambda item: item.created_at)
        return QaSessionDto(
            id=str(session.id),
            title=session.title,
            standardId=str(session.standard_id) if session.standard_id else None,
            messages=[self._to_message_dto(item) for item in messages],
            createdAt=session.created_at.isoformat(),
            updatedAt=session.updated_at.isoformat(),
        )

    @staticmethod
    def _to_message_dto(row: QaMessageRecord) -> ChatMessageDto:
        answer = None
        if row.answer_json:
            answer = QaAnswerDto.model_validate(row.answer_json)
        return ChatMessageDto(
            id=str(row.id),
            role=row.role,
            content=row.content,
            answer=answer,
            createdAt=row.created_at.isoformat(),
        )
