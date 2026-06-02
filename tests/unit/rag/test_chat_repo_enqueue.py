"""Unit tests for orch.rag.chat_repo.enqueue_summarization_if_needed."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.rag.chat_repo import enqueue_summarization_if_needed


class _FakeRow:
    """Fake row mimicking a SQLAlchemy mapped instance.

    Sets arbitrary keyword arguments as instance attributes so tests can
    construct lightweight stand-ins without a real DB session.
    """

    def __init__(self, **attrs: object) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)


class TestEnqueueSummarizationIfNeeded:
    """Tests for enqueue_summarization_if_needed()."""

    def test_below_budget_returns_none(self) -> None:
        """Token sum under hard_budget_tokens → returns None, no row inserted."""
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = 0

        result = enqueue_summarization_if_needed(
            db,
            conversation_id="conv-1",
            hard_budget_tokens=6000,
        )

        assert result is None

    def test_above_budget_no_inflight_job_returns_job(self) -> None:
        """Token sum > budget AND no in-flight job → inserts and returns job."""
        db = MagicMock()
        call_count = [0]

        def execute_side_effect(query: object) -> MagicMock:
            call_count[0] += 1
            result = MagicMock()
            # First call: token sum > budget
            # Second call: no in-flight job
            result.scalar_one_or_none.return_value = 7000 if call_count[0] == 1 else None
            return result

        db.execute.side_effect = execute_side_effect

        # Should have called db.add to insert the job
        enqueue_summarization_if_needed(
            db,
            conversation_id="conv-1",
            hard_budget_tokens=6000,
        )

        assert db.add.called

    def test_above_budget_inflight_job_returns_none(self) -> None:
        """Token sum > budget BUT in-flight job exists → returns None."""
        db = MagicMock()
        # Token sum > budget, in-flight job exists
        db.execute.return_value.scalar_one_or_none.side_effect = [7000, "job-1"]

        result = enqueue_summarization_if_needed(
            db,
            conversation_id="conv-1",
            hard_budget_tokens=6000,
        )

        assert result is None

    def test_integrity_error_handled_gracefully(self) -> None:
        """Two concurrent calls — second raises IntegrityError → returns None gracefully."""
        from sqlalchemy.exc import IntegrityError

        db = MagicMock()
        call_count = [0]

        def execute_side_effect(query: object) -> MagicMock:
            call_count[0] += 1
            result = MagicMock()
            result.scalar_one_or_none.return_value = 7000 if call_count[0] == 1 else None
            return result

        db.execute.side_effect = execute_side_effect
        # First call succeeds, second call gets IntegrityError
        db.flush.side_effect = [None, IntegrityError("unique constraint", "", None)]

        # First call should succeed
        result1 = enqueue_summarization_if_needed(
            db,
            conversation_id="conv-1",
            hard_budget_tokens=6000,
        )
        # Second call hits IntegrityError → returns None (not raised)
        result2 = enqueue_summarization_if_needed(
            db,
            conversation_id="conv-1",
            hard_budget_tokens=6000,
        )

        # First call returned a job (truthy), second returned None
        assert result1 is not None
        assert result2 is None
