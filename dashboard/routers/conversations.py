"""Conversations router — session-scoped chat conversation CRUD.

Four endpoints:
- GET  /api/projects/{project_id}/conversations                  — list recent
- POST /api/projects/{project_id}/conversations                — create new
- GET  /api/projects/{project_id}/conversations/{id}/messages   — replay
- POST /api/projects/{project_id}/conversations/{id}/archive    — soft-delete

All DB reads are triple-filtered by (project_id, session_id, conversation_id).
A mismatch returns 404 (not 403) to avoid leaking conversation existence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from dashboard.dependencies import get_db, get_session_id
from orch.db.models import ChatConversation, ChatMessage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


router = APIRouter(
    prefix="/api/projects/{project_id}/conversations",
    tags=["conversations"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConversationListItem(BaseModel):
    conversation_id: str
    title: str | None
    last_active_at: datetime
    module_path: str | None
    context_level: str
    message_count: int


class NewConversationRequest(BaseModel):
    module_path: str | None = None
    context_level: str = "architecture"


class NewConversationResponse(BaseModel):
    conversation_id: str


class ConversationMessageView(BaseModel):
    role: str
    content: str
    created_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    title: str | None
    rolling_summary: str | None
    last_active_at: datetime
    messages: list[ConversationMessageView]


class ArchiveResponse(BaseModel):
    archived_at: datetime | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _message_count(db: Session, conversation_id: str) -> int:
    """Return count of chat_messages for a conversation."""
    return db.execute(
        select(func.count()).where(ChatMessage.conversation_id == conversation_id)
    ).scalar_one()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ConversationListItem])
def list_conversations(
    project_id: str,
    _: Request,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
) -> list[ConversationListItem]:
    """Return up to 50 non-archived conversations for (project_id, session_id),
    ordered by last_active_at DESC."""
    conversations = (
        db.execute(
            select(ChatConversation)
            .where(ChatConversation.project_id == project_id)
            .where(ChatConversation.session_id == session_id)
            .where(ChatConversation.archived_at.is_(None))
            .order_by(ChatConversation.last_active_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    items = []
    for conv in conversations:
        items.append(
            ConversationListItem(
                conversation_id=conv.id,
                title=conv.title,
                last_active_at=conv.last_active_at,
                module_path=conv.module_path,
                context_level=conv.context_level,
                message_count=_message_count(db, conv.id),
            )
        )
    return items


@router.post("", response_model=NewConversationResponse, status_code=201)
def new_conversation(
    project_id: str,
    body: NewConversationRequest,
    _: Request,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
) -> NewConversationResponse:
    """Create a fresh ChatConversation and return its id."""
    conv = ChatConversation(
        project_id=project_id,
        session_id=session_id,
        module_path=body.module_path,
        context_level=body.context_level,
    )
    db.add(conv)
    db.flush()
    return NewConversationResponse(conversation_id=conv.id)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def get_messages(
    project_id: str,
    conversation_id: str,
    _: Request,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
) -> ConversationMessagesResponse:
    """Return full message replay for a conversation.

    404 if not found, cross-session, cross-project, or archived.
    Does NOT include rolling_summary as a synthetic message —
    returns it as a separate field for client-side rendering.
    """
    conv = db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .where(ChatConversation.project_id == project_id)
        .where(ChatConversation.session_id == session_id)
        .where(ChatConversation.archived_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        .scalars()
        .all()
    )

    return ConversationMessagesResponse(
        conversation_id=conv.id,
        title=conv.title,
        rolling_summary=conv.rolling_summary,
        last_active_at=conv.last_active_at,
        messages=[
            ConversationMessageView(
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.message_metadata or {},
            )
            for msg in messages
        ],
    )


@router.post("/{conversation_id}/archive", response_model=ArchiveResponse)
def archive(
    project_id: str,
    conversation_id: str,
    _: Request,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
) -> ArchiveResponse:
    """Soft-delete a conversation by setting archived_at.

    Idempotent: subsequent calls return the same archived_at timestamp.
    """
    conv = db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .where(ChatConversation.project_id == project_id)
        .where(ChatConversation.session_id == session_id)
        .where(ChatConversation.archived_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()

    if conv is None:
        # Check if it exists but is already archived
        existing = db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id).limit(1)
        ).scalar_one_or_none()
        if existing is not None and existing.archived_at is not None:
            # Idempotent — already archived, return the same timestamp
            return ArchiveResponse(archived_at=existing.archived_at)
        raise HTTPException(status_code=404, detail="Conversation not found")

    now = datetime.now(UTC)
    conv.archived_at = now
    db.flush()
    return ArchiveResponse(archived_at=now)
