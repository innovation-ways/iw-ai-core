"""ChatSummarizationJob poller — daemon component for rolling-summary compaction.

Polls chat_summarization_jobs WHERE status='queued' and processes them:
  1. Lock with FOR UPDATE SKIP LOCKED.
  2. Transition status → 'running'.
  3. Load messages newer than summary_through_message_id.
  4. Load existing rolling_summary as 'previous_summary'.
  5. Call summarize_history(messages, llm, previous_summary).
  6. Update chat_conversations.rolling_summary and summary_through_message_id.
  7. Transition status → 'completed'.
  8. On exception: status → 'failed', error_message set.

Runs as part of the main daemon poll loop.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    ChatConversation,
    ChatMessage,
    ChatSummarizationJob,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.rag.summarize import BaseLLM

logger = logging.getLogger(__name__)


def poll_chat_summarization_jobs(
    db: Session,
    *,
    llm: BaseLLM,
    max_jobs_per_cycle: int = 5,
) -> int:
    """Poll and process up to max_jobs_per_cycle queued ChatSummarizationJobs.

    Returns the number of jobs processed.
    """

    # Find queued jobs, oldest first, up to limit
    stmt = (
        select(ChatSummarizationJob)
        .where(ChatSummarizationJob.status == "queued")
        .order_by(ChatSummarizationJob.triggered_at.asc())
        .limit(max_jobs_per_cycle)
        .with_for_update(skip_locked=True)
    )
    rows = db.execute(stmt).scalars().all()
    if not rows:
        logger.debug("No queued chat summarization jobs")
        return 0

    processed = 0
    for job in rows:
        _process_one_job(db, job, llm)
        processed += 1

    return processed


def _process_one_job(
    db: Session,
    job: ChatSummarizationJob,
    llm: BaseLLM,
) -> None:
    """Process a single ChatSummarizationJob end-to-end."""
    from orch.rag.summarize import summarize_history

    conversation_id = job.conversation_id

    # Transition queued → running
    job.status = "running"
    job.started_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "chat_summarization job %s: queued→running (conversation_id=%s)",
        job.id,
        conversation_id,
    )

    try:
        # ---- Load conversation ----
        conv = db.get(ChatConversation, conversation_id)
        if conv is None:
            _fail_job(db, job, "conversation_not_found")
            return

        # ---- Load messages newer than summary_through_message_id ----
        if conv.summary_through_message_id is not None:
            msgs_stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .where(ChatMessage.id != conv.summary_through_message_id)
                .order_by(ChatMessage.created_at.asc())
            )
        else:
            msgs_stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at.asc())
            )

        messages = db.execute(msgs_stmt).scalars().all()

        if not messages:
            # Nothing to summarise — mark complete immediately
            _complete_job(db, job, messages_summarized=0)
            return

        # ---- Load previous rolling_summary ----
        previous_summary: str | None = conv.rolling_summary

        # ---- Call LLM ----
        summary_text = summarize_history(list(messages), llm, previous_summary)

        # ---- Update conversation ----
        latest_msg_id = messages[-1].id if messages else None
        conv.rolling_summary = summary_text
        if latest_msg_id is not None:
            conv.summary_through_message_id = latest_msg_id

        # ---- Mark job completed ----
        _complete_job(db, job, messages_summarized=len(messages))

    except Exception as exc:  # noqa: BLE001
        logger.exception("chat_summarization job %s failed", job.id)
        _fail_job(db, job, str(exc)[:500])


def _complete_job(db: Session, job: ChatSummarizationJob, messages_summarized: int) -> None:
    """Transition job to completed and commit."""
    job.status = "completed"
    job.completed_at = datetime.now(UTC)
    job.messages_summarized = messages_summarized
    if job.summary_through_message_id is None:
        job.summary_through_message_id = None
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "chat_summarization job %s: running→completed (%d messages)",
        job.id,
        messages_summarized,
    )


def _fail_job(db: Session, job: ChatSummarizationJob, error_message: str) -> None:
    """Transition job to failed and commit."""
    job.status = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.error(
        "chat_summarization job %s: running→failed (%s)",
        job.id,
        error_message,
    )
