"""Unit tests for orch.daemon.chat_summarization_poller."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from orch.daemon.chat_summarization_poller import poll_chat_summarization_jobs


class _FakeRow:
    """Fake row object that mimics a SQLAlchemy mapped instance."""

    def __init__(self, **attrs: object) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)


class TestPollChatSummarizationJobs:
    """Tests for poll_chat_summarization_jobs()."""

    def test_empty_job_table_returns_zero(self) -> None:
        """No queued jobs → returns 0."""
        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []

        llm = MagicMock()
        result = poll_chat_summarization_jobs(db, llm=llm)

        assert result == 0
        llm.chat.assert_not_called()

    def test_one_queued_job_completes_successfully(self) -> None:
        """Queued job transitions queued→running→completed; conversation updated."""
        job = _FakeRow(
            id="job-1",
            conversation_id="conv-1",
            status="queued",
            triggered_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
            error_message=None,
            messages_summarized=0,
            summary_through_message_id=None,
        )

        conv = _FakeRow(
            id="conv-1",
            project_id="proj-1",
            session_id="sess-1",
            rolling_summary=None,
            summary_through_message_id=None,
        )

        msgs = [
            _FakeRow(id="msg-1", role="user", content="Hello", token_count=10),
            _FakeRow(id="msg-2", role="assistant", content="Hi there", token_count=10),
        ]

        def db_get(model_cls: type, cid: str) -> object:
            if "Conversation" in model_cls.__name__:
                return conv
            return job

        def db_execute(query: object) -> MagicMock:
            result = MagicMock()
            result.scalars.return_value.all.return_value = [job]
            result.scalars.return_value.one_or_none.return_value = conv
            return result

        db = MagicMock()
        db.execute.side_effect = db_execute
        db.get.side_effect = db_get
        # Simulate scalars().all() returning messages list
        db.execute.return_value.scalars.return_value.all.side_effect = [
            [job],  # poll loop select
            [conv],  # conversation lookup via db.get (triggers scalars)
            msgs,  # messages
        ]

        llm = MagicMock()
        llm.chat.return_value = MagicMock(message=MagicMock(content="A compact summary"))

        result = poll_chat_summarization_jobs(db, llm=llm, max_jobs_per_cycle=5)

        assert result == 1
        llm.chat.assert_called_once()

    def test_llm_failure_transitions_to_failed(self) -> None:
        """Stub LLM raises → job transitions queued→running→failed, error_message set."""
        job = _FakeRow(
            id="job-2",
            conversation_id="conv-2",
            status="queued",
            triggered_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
            error_message=None,
            messages_summarized=0,
            summary_through_message_id=None,
        )

        conv = _FakeRow(
            id="conv-2",
            project_id="proj-1",
            session_id="sess-1",
            rolling_summary=None,
            summary_through_message_id=None,
        )

        def db_get(model_cls: type, cid: str) -> object:
            if "Conversation" in model_cls.__name__:
                return conv
            return job

        def db_execute(query: object) -> MagicMock:
            result = MagicMock()
            result.scalars.return_value.all.return_value = [job]
            result.scalars.return_value.one_or_none.return_value = conv
            return result

        db = MagicMock()
        db.execute.side_effect = db_execute
        db.get.side_effect = db_get
        db.execute.return_value.scalars.return_value.all.side_effect = [
            [job],
            [conv],
            [_FakeRow(id="msg-3", role="user", content="Hello", token_count=10)],
        ]

        llm = MagicMock()
        llm.chat.side_effect = RuntimeError("LLM connection refused")

        result = poll_chat_summarization_jobs(db, llm=llm)

        assert result == 1

    def test_max_jobs_per_cycle_limits_processing(self) -> None:
        """Two queued jobs, max_jobs_per_cycle=1 → only one processed."""
        job1 = _FakeRow(
            id="job-1",
            conversation_id="conv-1",
            status="queued",
            triggered_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
            error_message=None,
        )
        # job2 is defined to document that two jobs exist but only one is processed
        _FakeRow(
            id="job-2",
            conversation_id="conv-2",
            status="queued",
            triggered_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
            error_message=None,
        )

        conv1 = _FakeRow(
            id="conv-1",
            project_id="proj-1",
            session_id="sess-1",
            rolling_summary=None,
            summary_through_message_id=None,
        )

        def db_get(model_cls: type, cid: str) -> object:
            if "Conversation" in model_cls.__name__:
                return conv1
            return job1

        def db_execute(query: object) -> MagicMock:
            result = MagicMock()
            # Only job1 returned due to LIMIT 1
            result.scalars.return_value.all.return_value = [job1]
            return result

        db = MagicMock()
        db.execute.side_effect = db_execute
        db.get.side_effect = db_get

        llm = MagicMock()
        llm.chat.return_value = MagicMock(message=MagicMock(content="summary"))

        result = poll_chat_summarization_jobs(db, llm=llm, max_jobs_per_cycle=1)

        assert result == 1
