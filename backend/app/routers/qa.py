from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.qa.service import QaService
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.qa import CreateQaSessionBody, QaSessionDto, SendQaMessageBody
from app.services.llm_settings import get_or_create_llm_config

router = APIRouter(prefix="/api/v1/qibiao/qa", tags=["qibiao-qa"])


def _parse_uuid(value: str, *, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", f"{label}无效", 400) from exc


@router.get("/sessions", response_model=ApiResponse[list[QaSessionDto]])
def list_qa_sessions(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    sessions = QaService(db, llm_config).list_sessions()
    return success(sessions)


@router.post("/sessions", response_model=ApiResponse[QaSessionDto])
def create_qa_session(
    body: CreateQaSessionBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    standard_id = None
    if body.standardId:
        standard_id = _parse_uuid(body.standardId, label="标准 ID")
    session = QaService(db, llm_config).create_session(standard_id=standard_id)
    return success(session)


@router.post("/sessions/{session_id}/messages", response_model=ApiResponse[QaSessionDto])
def send_qa_message(
    session_id: str,
    body: SendQaMessageBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    parsed_id = _parse_uuid(session_id, label="会话 ID")
    session = QaService(db, llm_config).send_message(parsed_id, body.content)
    return success(session)
