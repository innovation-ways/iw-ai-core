"""Chat conversation repository — thin DB-access layer for chat memory.

All write functions use db.add + db.flush (no commit — caller's responsibility).
The router (S07) owns the commit.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import tiktoken
from sqlalchemy import func, select, update

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

# Module-level cache for tiktoken encodings (one per model name)
_tokenizer_cache: dict[str, tiktoken.Encoding] = {}
_warned_models: set[str] = set()


def count_tokens(text: str, model_name: str | None = None) -> int:
    """Count tokens using tiktoken.

    Uses cl100k_base for unknown model names (fallback: len(text)//4 + 1).
    Logs a warning ONCE per unknown model name.
    """
    if model_name is None:
        model_name = "cl100k_base"

    if model_name in _tokenizer_cache:
        encoding = _tokenizer_cache[model_name]
    else:
        if model_name in _warned_models:
            # Already warned, use cache fallback without retrying tokenizer
            return len(text) // 4 + 1

        try:
            encoding = tiktoken.get_encoding(model_name)
            _tokenizer_cache[model_name] = encoding
        except Exception:
            if model_name not in _warned_models:
                logger.warning(
                    "tiktoken does not support model '%s', using heuristic fallback", model_name
                )
                _warned_models.add(model_name)
            return len(text) // 4 + 1

    try:
        return len(encoding.encode(text))
    except Exception:
        if model_name not in _warned_models:
            logger.warning(
                "tiktoken encode failed for model '%s', using heuristic fallback", model_name
            )
            _warned_models.add(model_name)
        return len(text) // 4 + 1


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------


def get_or_create_conversation(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    conversation_id: str | None,
    module_path: str | None,
    context_level: str,
    first_question: str | None = None,
) -> ChatConversation:
    """Look up a non-archived conversation by (project_id, session_id, conversation_id).

    If conversation_id is None or references a stale/archived/cross-session row,
    create a new ChatConversation.
    The triple filter (project_id, session_id, NOT archived) is mandatory on the
    lookup — see Invariant 7.
    """
    from orch.db.models import ChatConversation

    if conversation_id is not None:
        # Try to find an active conversation matching all three
        conv = db.execute(
            select(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .where(ChatConversation.project_id == project_id)
            .where(ChatConversation.session_id == session_id)
            .where(ChatConversation.archived_at.is_(None))
            .limit(1)
        ).scalar_one_or_none()

        if conv is not None:
            # Found active conversation — bump last_active_at
            conv.last_active_at = datetime.now(UTC)
            db.flush()
            return conv

    # Create new conversation
    title = None
    if first_question:
        title = first_question[:80] if len(first_question) > 80 else first_question

    conv = ChatConversation(
        project_id=project_id,
        session_id=session_id,
        module_path=module_path,
        context_level=context_level,
        title=title,
    )
    db.add(conv)
    db.flush()
    return conv


def append_message(
    db: Session,
    *,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, object] | None = None,
    token_count: int | None = None,
) -> ChatMessage:
    """Insert a chat_messages row. Computes token_count if not supplied.

    Bumps chat_conversations.last_active_at in the same transaction.
    """
    from orch.db.models import ChatMessage

    if token_count is None:
        token_count = count_tokens(content)

    msg = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        token_count=token_count,
        message_metadata=metadata or {},
    )
    db.add(msg)
    db.flush()

    # Bump last_active_at in a single UPDATE (no SELECT)
    from orch.db.models import ChatConversation

    db.execute(
        update(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .values(last_active_at=datetime.now(UTC))
    )
    db.flush()
    return msg


def list_messages_for_context(
    db: Session,
    *,
    conversation_id: str,
    soft_budget_tokens: int,
) -> tuple[list[dict[str, str | int]], str | None]:
    """Return (kept_messages, rolling_summary).

    Loads chat_messages newer than summary_through_message_id (or all if no
    summary yet), drops oldest until cumulative token_count <= soft_budget_tokens
    while ALWAYS preserving the last 2 messages (correctness over budget).
    rolling_summary is the conversation's stored summary (or None).
    """
    from orch.db.models import ChatConversation, ChatMessage

    # Load conversation for rolling_summary + summary_through_message_id
    conv_row = db.execute(
        select(ChatConversation).where(ChatConversation.id == conversation_id)
    ).scalar_one_or_none()
    if conv_row is None:
        return [], None

    rolling_summary = conv_row.rolling_summary
    summary_through_id = conv_row.summary_through_message_id

    # Load messages newer than summary_through_message_id (or all if no summary)
    if summary_through_id is not None:
        # Get boundary message to exclude it; use id-based comparison to handle
        # same-timestamp edge case (multiple messages in same transaction)
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .where(ChatMessage.id != summary_through_id)
            .order_by(ChatMessage.created_at.asc())
        )
    else:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )

    all_rows = db.execute(stmt).scalars().all()
    messages: list[dict[str, str | int]] = [
        {"role": r.role, "content": r.content, "token_count": r.token_count} for r in all_rows
    ]

    # Token-budget truncation: keep within budget, always preserve last 2
    kept = truncate_messages_to_budget(messages, soft_budget_tokens)

    return kept, rolling_summary


def truncate_messages_to_budget(
    messages: list[dict[str, str | int]],
    soft_budget_tokens: int,
) -> list[dict[str, str | int]]:
    """Drop oldest messages until total token_count <= soft_budget_tokens.

    Always preserves the last 2 messages (correctness over budget).
    """
    if not messages:
        return []

    token_counts = [int(msg.get("token_count", 0)) for msg in messages]
    total = sum(token_counts)
    if total <= soft_budget_tokens:
        return list(messages)
    result: list[dict[str, str | int]] = list(messages)
    running_total = total
    while running_total > soft_budget_tokens and len(result) > 2:
        result.pop(0)
        removed_idx = len(messages) - len(result) - 1
        removed_tok = token_counts[removed_idx]
        running_total -= removed_tok
    return result


def list_conversations_for_session(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    limit: int = 50,
) -> list[ChatConversation]:
    """Return non-archived conversations for (project_id, session), ordered by last_active_at."""
    from orch.db.models import ChatConversation

    return list(
        db.execute(
            select(ChatConversation)
            .where(ChatConversation.project_id == project_id)
            .where(ChatConversation.session_id == session_id)
            .where(ChatConversation.archived_at.is_(None))
            .order_by(ChatConversation.last_active_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def get_conversation(
    db: Session,
    *,
    conversation_id: str,
    project_id: str,
    session_id: str,
) -> ChatConversation | None:
    """Strict triple-filter; returns None on any mismatch. Never raises."""
    from orch.db.models import ChatConversation

    return db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .where(ChatConversation.project_id == project_id)
        .where(ChatConversation.session_id == session_id)
        .where(ChatConversation.archived_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()


def archive_conversation(
    db: Session,
    *,
    conversation_id: str,
    project_id: str,
    session_id: str,
) -> datetime | None:
    """Set archived_at = now() if found and not already archived; return the timestamp or None."""
    from orch.db.models import ChatConversation

    conv = db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .where(ChatConversation.project_id == project_id)
        .where(ChatConversation.session_id == session_id)
        .where(ChatConversation.archived_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()

    if conv is None:
        return None

    now = datetime.now(UTC)
    conv.archived_at = now
    db.flush()
    return now


# ---------------------------------------------------------------------------
# Summarization job enqueue helper
# ---------------------------------------------------------------------------

_HISTORY_HARD_BUDGET_TOKENS = 6000


def enqueue_summarization_if_needed(
    db: Session,
    *,
    conversation_id: str,
    hard_budget_tokens: int = _HISTORY_HARD_BUDGET_TOKENS,
) -> ChatSummarizationJob | None:
    """Insert a ChatSummarizationJob if cumulative token budget is exceeded.

    Inspects chat_messages.token_count for messages NEWER than
    chat_conversations.summary_through_message_id (or all if NULL). If the sum
    exceeds hard_budget_tokens AND no job with status IN ('queued', 'running')
    exists for this conversation, inserts a new job and returns it.
    Otherwise returns None.

    Relies on the unique partial index uq_chat_summarization_jobs_one_in_flight
    for race-condition protection: on IntegrityError, returns None gracefully.
    """
    from sqlalchemy.exc import IntegrityError

    from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob

    # 1. Load conversation to find the summary boundary
    conv = db.get(ChatConversation, conversation_id)
    if conv is None:
        return None

    boundary_id = conv.summary_through_message_id

    # 2. Sum token_count for messages newer than the boundary (or all if no summary)
    if boundary_id is not None:
        token_sum = db.execute(
            select(func.coalesce(func.sum(ChatMessage.token_count), 0))
            .where(ChatMessage.conversation_id == conversation_id)
            .where(ChatMessage.id != boundary_id)
        ).scalar_one_or_none()
    else:
        token_sum = db.execute(
            select(func.coalesce(func.sum(ChatMessage.token_count), 0)).where(
                ChatMessage.conversation_id == conversation_id
            )
        ).scalar_one_or_none()

    total_tokens = token_sum or 0
    if total_tokens <= hard_budget_tokens:
        return None

    # 3. Check for in-flight job (queued or running)
    existing = db.execute(
        select(ChatSummarizationJob.id)
        .where(ChatSummarizationJob.conversation_id == conversation_id)
        .where(ChatSummarizationJob.status.in_(["queued", "running"]))
        .limit(1)
    ).scalar_one_or_none()

    if existing is not None:
        return None

    # 4. Insert new job
    job = ChatSummarizationJob(
        conversation_id=conversation_id,
        status="queued",
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        # Race: another request just inserted the same job.
        # The unique partial index prevented the duplicate.
        db.rollback()
        return None

    return job
