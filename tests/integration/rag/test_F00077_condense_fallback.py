"""Integration test: condense fallback when LLM unavailable (AC3).

Verifies that `condense_query` returns the original question verbatim
when the LLM raises a ConnectionError, and that a daemon_event of type
'condense_failed' is inserted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


class TestCondenseFallback:
    """AC3: condense_query falls back to original question on LLM failure."""

    def test_connection_error_returns_original_question(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """On ConnectionError, condense_query returns the original question."""
        from orch.rag.condense import condense_query

        # History with >= 2 turns (would normally trigger LLM call)
        history = [
            {"role": "user", "content": "what does keep_alive do?"},
            {"role": "assistant", "content": "keep_alive is a function that..."},
            {"role": "user", "content": "explain how it works"},
        ]
        question = "tell me more"

        # Stub LLM that raises ConnectionError
        class FailingLLM:
            def complete(self, prompt, **kwargs):  # type: ignore[no-untyped-def]
                raise ConnectionError("Ollama unreachable")

        failing_llm = FailingLLM()

        result = condense_query(
            history,
            question,
            failing_llm,
            db_session=db_session,
            conversation_id=None,
        )

        assert result == question, (
            f"Expected fallback to return original question '{question}', got '{result}'"
        )

    def test_connection_error_emits_condense_failed_event(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """On ConnectionError, a daemon_event of type 'condense_failed' is inserted."""
        from orch.db.models import DaemonEvent
        from orch.rag.condense import condense_query

        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
        ]
        question = "follow-up?"

        class FailingLLM:
            def complete(self, prompt, **kwargs):  # type: ignore[no-untyped-def]
                raise ConnectionError("Ollama unreachable")

        failing_llm = FailingLLM()

        result = condense_query(
            history,
            question,
            failing_llm,
            db_session=db_session,
            conversation_id="test-conv-condense-fail",
        )
        db_session.flush()

        assert result == question

        # Check daemon_event was inserted
        events = (
            db_session.execute(
                select(DaemonEvent)
                .where(DaemonEvent.event_type == "condense_failed")
                .order_by(DaemonEvent.created_at.desc())
            )
            .scalars()
            .all()
        )
        assert len(events) >= 1, f"Expected at least one condense_failed event, got {len(events)}"
        latest_event = events[0]
        assert latest_event.event_metadata.get("conversation_id") == "test-conv-condense-fail"

    def test_other_exception_also_falls_back(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Any LLM exception (not just ConnectionError) triggers fallback."""
        from orch.rag.condense import condense_query

        history = [
            {"role": "user", "content": "what is F-00077?"},
            {"role": "assistant", "content": "F-00077 is a feature."},
            {"role": "user", "content": "tell me more"},
        ]
        question = "more details"

        class GenericErrorLLM:
            def complete(self, prompt, **kwargs):  # type: ignore[no-untyped-def]
                raise RuntimeError("some other error")

        result = condense_query(
            history,
            question,
            GenericErrorLLM(),
            db_session=db_session,
            conversation_id=None,
        )

        assert result == question, "Any LLM exception should trigger fallback"

    def test_short_circuit_below_two_turns(
        self,
        db_session: Session,
    ) -> None:
        """With < 2 history turns, condense returns question without LLM call."""
        from orch.rag.condense import condense_query

        history = [{"role": "user", "content": "hello"}]
        question = "what is keep_alive?"

        llm = MagicMock()
        result = condense_query(history, question, llm)

        assert result == question
        llm.complete.assert_not_called()
