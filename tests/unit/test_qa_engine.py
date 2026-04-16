"""Unit tests for orch.rag.qa.QAEngine."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt()."""

    def test_build_system_prompt_includes_context_doc(self) -> None:
        """Given: context_doc_content = "MyApp is a web app", chunks = ["def foo(): pass"]
        When: engine._build_system_prompt(context_doc_content, chunks) is called
        Then: returned string contains "MyApp is a web app"
        And: returned string contains "def foo(): pass"
        And: returned string contains "Architecture Context"
        And: returned string contains "Relevant Code Excerpts"
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt("MyApp is a web app", ["def foo(): pass"])

        assert "MyApp is a web app" in result
        assert "def foo(): pass" in result
        assert "Architecture Context" in result
        assert "Relevant Code Excerpts" in result

    def test_build_system_prompt_empty_context_doc(self) -> None:
        """Given: context_doc_content = "", chunks = ["def bar(): ..."]
        When: engine._build_system_prompt("", chunks) is called
        Then: returned string contains "(No architecture document available)"
        And: returned string contains "def bar(): ..."
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt("", ["def bar(): ..."])

        assert "(No architecture document available)" in result
        assert "def bar(): ..." in result


class TestTruncateHistory:
    """Tests for _truncate_history()."""

    def test_truncate_history_within_limit(self) -> None:
        """Given: history with 4 messages (2 turns)
        When: engine._truncate_history(history) is called
        Then: all 4 messages are returned unchanged (within MAX_HISTORY_TURNS)
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well"},
        ]

        result = engine._truncate_history(history)
        assert result == history
        assert len(result) == 4

    def test_truncate_history_at_limit(self) -> None:
        """Given: history with exactly 10 messages (5 turns = MAX_HISTORY_TURNS)
        When: engine._truncate_history(history) is called
        Then: all 10 messages returned unchanged
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        history = [
            {"role": "user", "content": f"Message {i}"}
            if i % 2 == 0
            else {"role": "assistant", "content": f"Response {i}"}
            for i in range(10)
        ]

        result = engine._truncate_history(history)
        assert result == history
        assert len(result) == 10

    def test_truncate_history_exceeds_limit(self) -> None:
        """Given: history with 12 messages (6 turns)
        When: engine._truncate_history(history) is called
        Then: only the last 10 messages are returned
        And: len(result) == 10
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        history = [
            {"role": "user", "content": f"Old message {i}"}
            if i % 2 == 0
            else {"role": "assistant", "content": f"Old response {i}"}
            for i in range(12)
        ]

        result = engine._truncate_history(history)
        assert len(result) == 10
        assert result == history[-10:]

    def test_truncate_history_empty(self) -> None:
        """Given: history = []
        When: engine._truncate_history([]) is called
        Then: [] is returned
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._truncate_history([])
        assert result == []


class TestAnswerStream:
    """Tests for answer_stream()."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock CodeUnderstandingConfig."""
        config = MagicMock()
        config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = Path(tempfile.mkdtemp())
        return config

    def test_answer_stream_returns_async_generator(self, mock_config: MagicMock) -> None:
        """Given: QAEngine initialized with a mock config and mocked LanceDB/Ollama dependencies
        When: answer_stream() is called
        Then: the return type is an AsyncGenerator (has __aiter__ and __anext__)
        """
        import types

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_pandas.return_value = MagicMock()  # empty df
        mock_table.search.return_value = mock_search

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = AsyncMock(return_value=[0.1] * 128)

        mock_chunks = [
            {"text": "def foo(): pass"},
            {"text": "def bar(): pass"},
        ]
        mock_search.to_pandas.return_value = MagicMock(__iter__=lambda _: iter(mock_chunks))

        def mock_search_method(vec):
            return mock_search

        mock_table.search = mock_search_method

        mock_llm = MagicMock()
        mock_chat_response = MagicMock()
        mock_chat_response.delta = "Hello"
        mock_astream = AsyncMock(return_value=mock_chat_response)
        mock_llm.astream_chat = mock_astream

        with (
            patch(
                "lancedb.connect",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=mock_table), __exit__=MagicMock()
                ),
            ),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
        ):

            async def consume():
                result = engine.answer_stream(
                    question="What does this do?",
                    context_level="architecture",
                    context_doc_id=None,
                    conversation_history=[],
                    session=mock_session,
                )
                assert isinstance(result, types.AsyncGeneratorType)
                # Consume to verify it's an async generator
                async for _ in result:
                    pass

            asyncio.run(consume())

    @pytest.mark.asyncio
    async def test_answer_stream_error_token_on_ollama_down(self, mock_config: MagicMock) -> None:
        """Given: OllamaLLM.astream_chat raises httpx.ConnectError
        When: answer_stream() is consumed
        Then: the first yielded token starts with "__ERROR__:"
        """
        import httpx

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_df = MagicMock()
        mock_df.__iter__ = lambda _: iter([])
        mock_search.to_pandas.return_value = mock_df

        def mock_search_method(vec):
            return mock_search

        mock_table.search = mock_search_method

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = AsyncMock(return_value=[0.1] * 128)

        async def mock_astream_chat_error(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat_error

        with (
            patch(
                "lancedb.connect",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=mock_table), __exit__=MagicMock()
                ),
            ),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
        ):
            tokens = []
            async for token in engine.answer_stream(
                question="What does this do?",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
            ):
                tokens.append(token)

            assert len(tokens) > 0
            assert tokens[0].startswith("__ERROR__:")


class TestQAEngineConstants:
    """Tests for QAEngine class constants."""

    def test_top_k_is_8(self) -> None:
        """Verify TOP_K is set to 8."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)
        assert engine.TOP_K == 8

    def test_max_history_turns_is_5(self) -> None:
        """Verify MAX_HISTORY_TURNS is set to 5."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)
        assert engine.MAX_HISTORY_TURNS == 5
