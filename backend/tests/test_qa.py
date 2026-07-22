"""QA service unit tests."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.models.llm_config import LlmConfigRecord
from app.qa.service import QaService
from app.schemas.indexing import ChunkSearchHitDto


def _llm_config() -> LlmConfigRecord:
    return LlmConfigRecord(
        id=1,
        enabled=True,
        provider="doubao",
        model_name="doubao-seed-2-0-pro-260215",
        endpoint_id="ep-test",
        api_key="test-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        timeout_seconds=60,
        qa_top_k=5,
    )


def test_parse_llm_json_answer() -> None:
    db = MagicMock()
    service = QaService(db, _llm_config())
    hits = [
        ChunkSearchHitDto(
            chunkId="c1",
            attachmentId="a1",
            standardId=str(uuid.uuid4()),
            content="5.1 轻型汽车定义",
            positionLabel="5.1",
        )
    ]
    raw = json.dumps(
        {
            "conclusion": "适用轻型汽车条款",
            "basis": ["依据片段 5.1"],
            "citations": [
                {
                    "standardNo": "GB 12345",
                    "standardName": "测试标准",
                    "attachment": "正文.pdf",
                    "excerpt": "5.1 轻型汽车",
                    "position": "5.1",
                }
            ],
            "scope": "M1 类车辆",
            "riskNotice": "",
        },
        ensure_ascii=False,
    )
    answer = service._parse_llm_answer(raw, hits)
    assert answer.conclusion == "适用轻型汽车条款"
    assert answer.basis == ["依据片段 5.1"]
    assert answer.citations[0].standardNo == "GB 12345"


@patch("app.qa.service.chat_completion")
@patch("app.qa.service.IndexingService")
def test_send_message_no_hits_returns_no_evidence(
    indexing_cls: MagicMock,
    chat_completion: MagicMock,
) -> None:
    db = MagicMock()
    session = MagicMock()
    session.id = uuid.uuid4()
    session.title = "新对话"
    session.standard_id = None
    session.messages = []
    session.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    session.updated_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

    db.scalar.return_value = session
    db.get.return_value = None
    db.scalar.side_effect = [session, None]

    indexing_cls.return_value.hybrid_search_chunks.return_value.hits = []

    service = QaService(db, _llm_config())
    with patch.object(service, "_to_session_dto", return_value=MagicMock()):
        service.send_message(session.id, "这个问题没有依据")

    chat_completion.assert_not_called()
    assert len(session.messages) == 2
    assistant = session.messages[-1]
    assert assistant.role == "assistant"
    assert "未找到足够依据" in assistant.content
