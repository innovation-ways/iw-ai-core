"""Query rewriting — CondensePlusContext pattern.

condense_query(history, question, llm) rewrites a follow-up question into
a self-contained search query using the last 4 conversation turns.
On LLM failure, falls back to the original question (graceful degradation).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

CONDENSE_PROMPT = """\
Given the conversation below and a follow-up question, rephrase the follow-up
question into a self-contained search query that captures the user's full
intent including any implicit references to earlier turns. Return ONLY the
rewritten query, no preamble, no quotes.

Conversation history:
{history}

Follow-up question: {question}

Standalone search query:"""


def condense_query(
    history: list[dict[str, str]],
    question: str,
    llm: Any,
    *,
    db_session: Session | None = None,
    conversation_id: str | None = None,
    max_tokens: int = 256,
) -> str:
    """Rewrite a follow-up question using conversation history.

    If len(history) < 2, returns question unchanged (no LLM call).
    Otherwise calls llm.complete() with CONDENSE_PROMPT.
    On any LLM exception, logs a daemon_event of type 'condense_failed'
    via orch.db.session and returns the original question.

    Args:
        history: List of message dicts with 'role' and 'content' keys.
        question: The follow-up question to rewrite.
        llm: LLM instance with a .complete() method.
        db_session: Optional SQLAlchemy session for daemon_event persistence.
        conversation_id: Optional conversation ID to include in the failure event.
        max_tokens: Max tokens for the LLM completion (default 256).
    """
    if len(history) < 2:
        return question

    # Use last 4 turns at most
    recent = history[-(4 * 2) :]
    history_lines = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in recent
    )

    prompt = CONDENSE_PROMPT.format(history=history_lines, question=question)

    try:
        response = llm.complete(prompt, max_tokens=max_tokens)
        text = getattr(response, "text", "") or ""
        return text.strip()
    except Exception:
        _emit_condense_failed_event(db_session, conversation_id=conversation_id)
        logger.warning("condense_query LLM call failed, falling back to original question")
        return question


def _emit_condense_failed_event(
    db_session: Session | None, conversation_id: str | None = None
) -> None:
    """Write a daemon_event of type 'condense_failed' to the DB if session available."""
    if db_session is None:
        return
    try:
        from orch.db.models import DaemonEvent

        metadata = {}
        if conversation_id is not None:
            metadata["conversation_id"] = conversation_id
        event = DaemonEvent(
            project_id="internal",
            event_type="condense_failed",
            event_metadata=metadata,
        )
        db_session.add(event)
        db_session.flush()
    except Exception:
        logger.warning("Failed to write condense_failed daemon_event")
