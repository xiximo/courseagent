"""Course Agent RAG 检索（按 role 硬隔离素材库）。"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.course_agent.material_service import MaterialService
from app.course_agent.state_machine import Citation
from app.db.models.attachment import Attachment
from app.indexing.service import IndexingService
from app.schemas.indexing import ChunkSearchHitDto


def _normalize_doc_label(label: str) -> str:
    text = label.strip()
    for ch in "《》":
        text = text.replace(ch, "")
    text = re.sub(r"^素材[A-C]·", "", text)
    return text.strip().lower()


def _list_agent_attachments(db: Session, agent_id: str) -> list[Attachment]:
    standard_ids = list_standard_ids_for_agent(db, agent_id)
    if not standard_ids:
        return []
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.standard_id.in_(standard_ids))
            .order_by(Attachment.created_at.desc())
        ).all()
    )


def _match_attachment(document: str, attachments: list[Attachment]) -> Attachment | None:
    needle = _normalize_doc_label(document)
    if not needle:
        return None

    best: Attachment | None = None
    best_score = 0
    for attachment in attachments:
        name = (attachment.display_name or attachment.sprs_file_id or "").lower()
        if not name:
            continue
        if needle == name or needle in name or name in needle:
            return attachment

        score = 0
        for part in re.split(r"[·\s_\-/（）()「」\[\]]+", needle):
            part = part.strip()
            if len(part) >= 2 and part in name:
                score += len(part)
        if score > best_score:
            best_score = score
            best = attachment

    if best_score >= 4:
        return best
    return None


def enrich_citations_with_attachments(
    db: Session,
    agent_id: str,
    citations: list[Citation] | None,
) -> list[Citation] | None:
    if not citations:
        return citations

    attachments = _list_agent_attachments(db, agent_id)
    if not attachments:
        return citations

    fallback = attachments[0] if len(attachments) == 1 else None
    enriched: list[Citation] = []

    for citation in citations:
        if citation.attachment_id:
            enriched.append(citation)
            continue

        matched = _match_attachment(citation.document, attachments) or fallback
        if matched is None:
            enriched.append(citation)
            continue

        display = (matched.display_name or citation.document).strip()
        enriched.append(
            Citation(
                document=display,
                chapter=citation.chapter,
                attachment_id=str(matched.id),
                chunk_id=citation.chunk_id,
            )
        )

    return enriched


def list_standard_ids_for_agent(db: Session, agent_id: str) -> list[uuid.UUID]:
    return MaterialService(db).list_standard_ids(agent_id)


def retrieve_for_agent(
    db: Session,
    *,
    agent_id: str,
    query: str,
    top_k: int = 8,
) -> list[ChunkSearchHitDto]:
    standard_ids = list_standard_ids_for_agent(db, agent_id)
    if not standard_ids:
        return []

    indexing = IndexingService(db)
    merged: dict[str, ChunkSearchHitDto] = {}
    per_kb_k = max(3, top_k // len(standard_ids) + 1)

    for standard_id in standard_ids:
        try:
            result = indexing.hybrid_search_chunks(
                query,
                standard_id=standard_id,
                top_k=per_kb_k,
            )
        except Exception:
            continue
        for hit in result.hits:
            existing = merged.get(hit.chunkId)
            if existing is None or (hit.score or 0) > (existing.score or 0):
                merged[hit.chunkId] = hit

    hits = sorted(merged.values(), key=lambda item: item.score or 0.0, reverse=True)
    return hits[:top_k]


def retrieve_by_kb_id(
    db: Session,
    *,
    kb_id: str,
    query: str,
    top_k: int = 8,
) -> list[ChunkSearchHitDto]:
    """仅在指定知识库（平台 KB id）内检索，禁止跨库。"""
    if not kb_id or str(kb_id).startswith("kb_material_"):
        return []
    ids = MaterialService(db).list_standard_ids_by_kb_ids([str(kb_id)])
    if not ids:
        return []
    try:
        result = IndexingService(db).hybrid_search_chunks(
            query,
            standard_id=ids[0],
            top_k=top_k,
        )
        return result.hits
    except Exception:
        return []


def retrieve_for_role(
    db: Session,
    *,
    agent_id: str,
    role: str,
    query: str,
    top_k: int = 8,
) -> list[ChunkSearchHitDto]:
    """按身份优先检索；若无 role 专属库，则回退到 Agent 已绑定知识库。"""
    material = MaterialService(db)
    standard_id = material.resolve_standard_id(agent_id, role)
    if standard_id is not None:
        try:
            result = IndexingService(db).hybrid_search_chunks(
                query,
                standard_id=standard_id,
                top_k=top_k,
            )
            if result.hits:
                return result.hits
        except Exception:
            pass

    # 平台知识库多为独立资源且未必填写 role，回退绑定库检索
    return retrieve_for_agent(db, agent_id=agent_id, query=query, top_k=top_k)

def hits_to_citations_from_hits(hits: list[ChunkSearchHitDto]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for hit in hits:
        document_name = (hit.fileName or "资料").strip()
        chapter = (hit.positionLabel or "相关章节").strip()
        key = f"{document_name}:{chapter}"
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document=document_name,
                chapter=chapter,
                attachment_id=hit.attachmentId or None,
                chunk_id=hit.chunkId or None,
            )
        )
    return citations[:3]


def hits_to_citations(
    hits: list[ChunkSearchHitDto],
    *,
    document_name: str,
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for hit in hits:
        chapter = (hit.positionLabel or "相关章节").strip()
        key = f"{document_name}:{chapter}"
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document=document_name,
                chapter=chapter,
                attachment_id=hit.attachmentId or None,
                chunk_id=hit.chunkId or None,
            )
        )
    return citations[:3]


def document_name_for_role(db: Session, agent_id: str, role: str) -> str:
    name = MaterialService(db).get_kb_name_for_role(agent_id, role)
    return name or "资料"


def format_hits_for_prompt(hits: list[ChunkSearchHitDto]) -> str:
    if not hits:
        return "（未检索到相关资料片段）"

    lines: list[str] = []
    for index, hit in enumerate(hits[:8], start=1):
        label = hit.positionLabel or f"片段{index}"
        content = (hit.content or "").strip().replace("\n", " ")
        if len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"[{index}] {label}\n{content}")
    return "\n\n".join(lines)
