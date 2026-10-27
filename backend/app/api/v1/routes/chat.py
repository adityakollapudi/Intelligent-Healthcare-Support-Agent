from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.rag.embeddings import Embedder, get_embedder
from app.rag.generation import Generator, get_generator
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse, SessionDetail, SessionPage
from app.schemas.common import ErrorResponse
from app.services import chat_service, feedback_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/chat", tags=["chat"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
ChatUser = Annotated[Principal, Depends(require_any_permission(Permission.CHAT_USE))]
_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "", response_model=ChatResponse, summary="Ask the assistant (document-grounded answers)", responses=_ERRORS
)
def post_chat(
    body: ChatRequest,
    db: Db,
    audit: Audit,
    principal: ChatUser,
    settings: Annotated[Settings, Depends(get_settings)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    generator: Annotated[Generator, Depends(get_generator)],
) -> ChatResponse:
    return chat_service.handle_message(db, settings, audit, embedder, generator, principal, body)


@router.get("/sessions", response_model=SessionPage, summary="My recent conversations", responses=_ERRORS)
def list_sessions(db: Db, principal: ChatUser, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> SessionPage:
    return chat_service.list_sessions(db, principal, limit)


@router.get(
    "/sessions/{session_id}", response_model=SessionDetail, summary="One of my conversations", responses=_ERRORS
)
def get_session(session_id: UUID, db: Db, audit: Audit, principal: ChatUser) -> SessionDetail:
    return chat_service.get_session(db, audit, principal, session_id)

@router.post(
    "/messages/{message_id}/feedback", response_model=FeedbackResponse, responses=_ERRORS,
    summary="Rate one of my assistant answers (helpful / not helpful)",
)
def post_feedback(
    message_id: UUID, body: FeedbackRequest, db: Db, audit: Audit,
    principal: Annotated[Principal, Depends(require_any_permission(Permission.FEEDBACK_CREATE))],
) -> FeedbackResponse:
    return feedback_service.rate(db, audit, principal, message_id, body)
