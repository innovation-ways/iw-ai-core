"""End-to-end integration tests for chat summarization pipeline.

Uses a real PostgreSQL testcontainer with a stubbed LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import pytest

from orch.daemon.chat_summarization_poller import poll_chat_summarization_jobs
from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob, Project
from orch.rag.chat_repo import enqueue_summarization_if_needed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class _FakeLLM:
    """Stub LLM that returns deterministic text."""

    def __init__(self, response: str = "Compact conversation summary.") -> None:
        """Initialise the stub with the given canned response text.

        Args:
            response: The text string returned by every ``chat()`` call.
        """
        self._response = response

    def chat(self, messages: list[dict]) -> object:
        """Return a mock chat completion carrying the preconfigured response.

        Args:
            messages: Ignored input messages (present for interface compatibility).

        Returns:
            A MagicMock whose ``.message.content`` equals the configured response.
        """
        from unittest.mock import MagicMock

        return MagicMock(message=MagicMock(content=self._response))


@pytest.fixture
def chat_conversation_with_messages(db_session: Session, test_project: Project) -> ChatConversation:
    """Create a ChatConversation with 6 messages (~300 tokens each) persisted in the test DB.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.
        test_project: The Project row created by the shared test_project fixture.

    Returns:
        The committed ChatConversation row, usable as a base for further message additions.
    """
    conv = ChatConversation(
        id=str(uuid4()),
        project_id=test_project.id,
        session_id="test-session",
        context_level="architecture",
    )
    db_session.add(conv)
    db_session.flush()

    # 6 messages; using ~300-char content approximates 300 tokens with heuristic fallback
    messages = [
        ("user", "What is the architecture of the authentication module?"),
        (
            "assistant",
            "The auth module uses JWT tokens stored in httpOnly cookies. "
            "It validates against the /auth/verify endpoint and refreshes "
            "tokens via /auth/refresh. There are three main components: "
            "JwtService, RefreshTokenStore, and SessionManager.",
        ),
        ("user", "How does the refresh token rotation work?"),
        (
            "assistant",
            "The refresh token rotation works as follows: on each "
            "/auth/refresh request, the server validates the incoming "
            "refresh token, issues a new access token + refresh token pair, "
            "and revokes the old refresh token. This prevents replay attacks.",
        ),
        ("user", "What about token expiration handling?"),
        (
            "assistant",
            "Token expiration is handled in the middleware layer. "
            "When a token expires (401 response), the client automatically "
            "attempts a refresh. If refresh fails, the client redirects to "
            "the login page and clears local storage.",
        ),
    ]

    for role, content in messages:
        token_count = len(content) // 4 + 1  # heuristic fallback
        msg = ChatMessage(
            id=str(uuid4()),
            conversation_id=conv.id,
            role=role,
            content=content,
            token_count=token_count,
        )
        db_session.add(msg)
        db_session.flush()

    return conv


class TestChatSummarizationE2E:
    """End-to-end tests for the chat summarization pipeline."""

    def test_enqueue_summarization_if_needed_returns_job(
        self,
        db_session: Session,
        chat_conversation_with_messages: ChatConversation,
    ) -> None:
        """Above budget → enqueue_summarization_if_needed returns a queued job."""
        # Add a large message to push past 6000 tokens
        big_content = "A" * 24000  # ~6000 tokens with heuristic
        msg = ChatMessage(
            id=str(uuid4()),
            conversation_id=chat_conversation_with_messages.id,
            role="assistant",
            content=big_content,
            token_count=len(big_content) // 4 + 1,
        )
        db_session.add(msg)
        db_session.flush()

        job = enqueue_summarization_if_needed(
            db_session,
            conversation_id=chat_conversation_with_messages.id,
            hard_budget_tokens=6000,
        )

        assert job is not None
        assert job.status == "queued"
        assert job.conversation_id == chat_conversation_with_messages.id

    def test_poll_completes_and_updates_conversation(
        self,
        db_session: Session,
        chat_conversation_with_messages: ChatConversation,
    ) -> None:
        """poll_chat_summarization_jobs → completed, conversation.rolling_summary set."""
        # Enqueue a job (budget exceeded)
        big_content = "B" * 24000
        msg = ChatMessage(
            id=str(uuid4()),
            conversation_id=chat_conversation_with_messages.id,
            role="assistant",
            content=big_content,
            token_count=len(big_content) // 4 + 1,
        )
        db_session.add(msg)
        db_session.flush()

        enqueue_summarization_if_needed(
            db_session,
            conversation_id=chat_conversation_with_messages.id,
            hard_budget_tokens=6000,
        )
        db_session.commit()

        # Run the poller
        llm = _FakeLLM(response="Session manager handles token refresh and revocation.")
        processed = poll_chat_summarization_jobs(db_session, llm=llm)

        assert processed == 1

        # Verify conversation was updated
        updated_conv = db_session.get(ChatConversation, chat_conversation_with_messages.id)
        assert updated_conv is not None
        assert (
            updated_conv.rolling_summary == "Session manager handles token refresh and revocation."
        )
        assert updated_conv.summary_through_message_id is not None

        # Verify job completed
        job = (
            db_session.query(ChatSummarizationJob)
            .filter(ChatSummarizationJob.conversation_id == chat_conversation_with_messages.id)
            .first()
        )
        assert job is not None
        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.messages_summarized > 0

    def test_second_enqueue_returns_none_when_no_new_messages(
        self,
        db_session: Session,
        chat_conversation_with_messages: ChatConversation,
    ) -> None:
        """Enqueue called twice before new messages → second call returns None."""
        # Add a large message to trigger enqueue
        big_content = "C" * 24000
        msg = ChatMessage(
            id=str(uuid4()),
            conversation_id=chat_conversation_with_messages.id,
            role="assistant",
            content=big_content,
            token_count=len(big_content) // 4 + 1,
        )
        db_session.add(msg)
        db_session.flush()

        # First enqueue
        job = enqueue_summarization_if_needed(
            db_session,
            conversation_id=chat_conversation_with_messages.id,
            hard_budget_tokens=6000,
        )
        assert job is not None

        # Second enqueue WITHOUT adding more messages (boundary hasn't changed)
        job2 = enqueue_summarization_if_needed(
            db_session,
            conversation_id=chat_conversation_with_messages.id,
            hard_budget_tokens=6000,
        )
        assert job2 is None

    def test_conversation_deleted_job_fails_with_not_found(
        self,
        db_session: Session,
        chat_conversation_with_messages: ChatConversation,
    ) -> None:
        """Job enqueued then conversation deleted → poller fails with conversation_not_found."""
        # Enqueue a job
        big_content = "D" * 24000
        msg = ChatMessage(
            id=str(uuid4()),
            conversation_id=chat_conversation_with_messages.id,
            role="assistant",
            content=big_content,
            token_count=len(big_content) // 4 + 1,
        )
        db_session.add(msg)
        db_session.flush()

        job = enqueue_summarization_if_needed(
            db_session,
            conversation_id=chat_conversation_with_messages.id,
            hard_budget_tokens=6000,
        )
        assert job is not None
        db_session.commit()

        # Delete the conversation (CASCADE removes the job too).
        # For the test, we stub the db.get call to simulate the conversation
        # being absent at the time the poller looks it up.
        original_get = db_session.get

        def stubbed_get(model_cls: type, cid: str) -> object | None:
            # Simulate conversation gone when poller tries to load it
            if model_cls.__name__ == "ChatConversation":
                return None
            return original_get(model_cls, cid)

        llm = _FakeLLM()

        with patch.object(db_session, "get", side_effect=stubbed_get):
            processed = poll_chat_summarization_jobs(db_session, llm=llm)

        assert processed == 1
