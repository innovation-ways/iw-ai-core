"""Integration tests for F-00077 — hard-budget enqueues exactly one job (AC6).

Verifies that enqueue_summarization_if_needed creates exactly one
ChatSummarizationJob even when called twice for the same conversation,
and that the unique partial index prevents duplicates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


class TestHardBudgetEnqueueIdempotency:
    """AC6: hard-budget overflow enqueues exactly one job; duplicate call is no-op."""

    def test_overflow_enqueues_one_job(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Token count > HARD_BUDGET creates exactly one ChatSummarizationJob."""
        from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob
        from orch.rag.chat_repo import enqueue_summarization_if_needed
        from orch.rag.qa import HISTORY_HARD_BUDGET_TOKENS

        # Create conversation
        conv = ChatConversation(
            project_id=test_project.id,
            session_id="test-session-budget",
            context_level="architecture",
        )
        db_session.add(conv)
        db_session.flush()
        conv_id = conv.id

        # Add messages totaling > 6000 tokens
        for i in range(10):
            msg = ChatMessage(
                conversation_id=conv_id,
                role="user",
                content=f"message content token count high {i}" * 50,
                token_count=800,  # 10 * 800 = 8000 > 6000
                message_metadata={},
            )
            db_session.add(msg)
        db_session.flush()

        # Enqueue
        job = enqueue_summarization_if_needed(
            db_session,
            conversation_id=conv_id,
            hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
        )
        db_session.commit()

        assert job is not None, "Expected a job to be enqueued"
        assert job.status == "queued"

        # Verify exactly one job
        jobs = (
            db_session.execute(
                select(ChatSummarizationJob).where(ChatSummarizationJob.conversation_id == conv_id)
            )
            .scalars()
            .all()
        )
        assert len(jobs) == 1, f"Expected exactly 1 job, got {len(jobs)}"

    def test_second_enqueue_is_no_op(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Calling enqueue_summarization_if_needed twice returns None the second time."""
        from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob
        from orch.rag.chat_repo import enqueue_summarization_if_needed
        from orch.rag.qa import HISTORY_HARD_BUDGET_TOKENS

        # Create conversation
        conv = ChatConversation(
            project_id=test_project.id,
            session_id="test-session-budget-2",
            context_level="architecture",
        )
        db_session.add(conv)
        db_session.flush()
        conv_id = conv.id

        # Add messages totaling > 6000 tokens
        for i in range(10):
            msg = ChatMessage(
                conversation_id=conv_id,
                role="user",
                content=f"message {i}" * 100,
                token_count=800,
                message_metadata={},
            )
            db_session.add(msg)
        db_session.flush()

        # First enqueue
        job1 = enqueue_summarization_if_needed(
            db_session,
            conversation_id=conv_id,
            hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
        )
        db_session.commit()
        assert job1 is not None

        # Second enqueue — should return None (already queued)
        job2 = enqueue_summarization_if_needed(
            db_session,
            conversation_id=conv_id,
            hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
        )
        db_session.commit()

        assert job2 is None, "Second enqueue should return None (already queued)"

        # Verify only one job in DB
        jobs = (
            db_session.execute(
                select(ChatSummarizationJob).where(ChatSummarizationJob.conversation_id == conv_id)
            )
            .scalars()
            .all()
        )
        assert len(jobs) == 1, f"Expected exactly 1 job, got {len(jobs)}"

    def test_idempotent_despite_integrity_error(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The unique partial index blocks duplicate jobs; no exception bubbles up."""
        from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob
        from orch.rag.chat_repo import enqueue_summarization_if_needed
        from orch.rag.qa import HISTORY_HARD_BUDGET_TOKENS

        # Create conversation
        conv = ChatConversation(
            project_id=test_project.id,
            session_id="test-session-integrity",
            context_level="architecture",
        )
        db_session.add(conv)
        db_session.flush()
        conv_id = conv.id

        # Add messages totaling > 6000 tokens
        for i in range(10):
            msg = ChatMessage(
                conversation_id=conv_id,
                role="user",
                content=f"message {i}" * 100,
                token_count=800,
                message_metadata={},
            )
            db_session.add(msg)
        db_session.flush()

        # First enqueue — succeeds
        job1 = enqueue_summarization_if_needed(
            db_session,
            conversation_id=conv_id,
            hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
        )
        # Note: we intentionally do NOT call commit() here. The test fixture
        # wraps everything in a transaction that is rolled back at teardown.
        # Calling commit() then rollback() would undo the committed job.
        # Instead, we verify the job was created within the current transaction.
        assert job1 is not None

        # Verify one job exists within the current transaction
        jobs_before = (
            db_session.execute(
                select(ChatSummarizationJob).where(ChatSummarizationJob.conversation_id == conv_id)
            )
            .scalars()
            .all()
        )
        assert len(jobs_before) == 1, (
            f"Expected exactly 1 job before duplicate insert, got {len(jobs_before)}"
        )

        # Attempt to directly insert a second job (simulating race) — should be blocked
        dup_job = ChatSummarizationJob(
            conversation_id=conv_id,
            status="queued",
        )
        db_session.add(dup_job)
        from sqlalchemy.exc import IntegrityError

        # The flush should raise IntegrityError due to unique partial index
        with pytest.raises(IntegrityError):
            db_session.flush()

        # Note: we do NOT rollback here. Rolling back would undo the first job too
        # since it's the same transaction. We only verify the IntegrityError was raised.
        # The fixture's outer transaction will be rolled back at test teardown anyway.
