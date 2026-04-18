"""Unit tests for orch.rag.qa.QAEngine."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt()."""

    def test_system_prompt_no_module_is_byte_identical_to_pre_change_output(self) -> None:
        """AC5: Verify exact pre-change output when no module context is provided.

        Hard-codes the expected string to guard against textual drift.
        """
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a", "chunk-b"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
        )

        expected = (
            "You are a codebase expert assistant. "
            "Answer questions about the codebase accurately and concisely.\n\n"
            "## Architecture Context\n\n"
            "## Architecture\nBlah\n\n"
            "## Relevant Code Excerpts\n\n"
            "---\nchunk-a\n"
            "---\nchunk-b\n\n\n"
            "Answer the user's question based on the above context. "
            "If the context does not contain enough information, say so clearly."
        )
        assert result == expected

    def test_system_prompt_emits_module_block_when_path_provided(self) -> None:
        """AC3: Module block appears when module_path is set."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a"],
            module_path="orch/daemon/",
            module_name="Orchestration Daemon",
            fallback_triggered=False,
        )

        assert "## Current Focus — Module" in result
        assert "orch/daemon/" in result
        assert "Orchestration Daemon" in result
        assert "Prioritize" in result

    def test_system_prompt_module_block_without_name(self) -> None:
        """Module block renders correctly when module_name is None."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a"],
            module_path="orch/daemon/",
            module_name=None,
            fallback_triggered=False,
        )

        assert "## Current Focus — Module" in result
        assert "orch/daemon/" in result
        assert "(No architecture document available)" not in result
        assert "()" not in result
        assert "( )" not in result

    def test_system_prompt_retrieval_note_only_when_fallback_triggered(self) -> None:
        """AC4 partial: Retrieval Note appears only when fallback_triggered=True."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result_with_fallback = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a"],
            module_path="orch/daemon/",
            module_name="Daemon",
            fallback_triggered=True,
        )
        assert "## Retrieval Note" in result_with_fallback

        result_without_fallback = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a"],
            module_path="orch/daemon/",
            module_name="Daemon",
            fallback_triggered=False,
        )
        assert "## Retrieval Note" not in result_without_fallback

    def test_system_prompt_no_module_block_when_path_empty_string(self) -> None:
        """No module block when module_path is empty string."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        engine = QAEngine(project_id="test-project", config=config)

        result = engine._build_system_prompt(
            context_doc_content="## Architecture\nBlah",
            chunks=["chunk-a"],
            module_path="",
            module_name=None,
            fallback_triggered=False,
        )

        assert "## Current Focus — Module" not in result

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
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

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
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

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

    @pytest.mark.asyncio
    async def test_answer_stream_falls_back_when_module_filter_empty(
        self, mock_config: MagicMock
    ) -> None:
        """AC4: When module filter returns empty, fallback search runs."""
        import pandas as pd

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = AsyncMock(return_value=[0.1] * 128)

        async def mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        class _FakeQuery:
            def __init__(self, rows: list[str]) -> None:
                self._rows = rows

            def to_pandas(self) -> pd.DataFrame:
                return pd.DataFrame({"text": self._rows})

        class _FakeSearch:
            def __init__(self, rows_per_where: dict[str, list[str]]) -> None:
                self._rows_per_where = rows_per_where
                self._last_where: str | None = None

            def where(self, clause: str) -> _FakeSearch:
                self._last_where = clause
                return self

            def limit(self, n: int) -> _FakeQuery:
                return _FakeQuery(self._rows_per_where.get(self._last_where or "", []))

        class _FakeTable:
            def __init__(self, rows_per_where: dict[str, list[str]]) -> None:
                self._rows_per_where = rows_per_where

            def search(self, vec: list[float]) -> _FakeSearch:
                return _FakeSearch(self._rows_per_where)

        filtered_rows: dict[str, list[str]] = {
            "file_path LIKE 'orch/daemon/%' AND file_path != '__iwcore_seed__'": [],
            "file_path != '__iwcore_seed__'": ["chunk-a"],
        }
        mock_table = _FakeTable(filtered_rows)
        mock_db = MagicMock()
        mock_db.open_table.return_value = mock_table

        captured_messages: list = []

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            captured_messages.extend(messages)
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        with (
            patch("lancedb.connect", return_value=mock_db),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            tokens = []
            async for token in engine.answer_stream(
                question="What does this do?",
                context_level="module",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
                module_path="orch/daemon/",
                module_name="Daemon",
            ):
                tokens.append(token)

        system_prompt = captured_messages[0].content
        assert "## Retrieval Note" in system_prompt

    @pytest.mark.asyncio
    async def test_answer_stream_does_not_fall_back_when_module_filter_nonempty(
        self, mock_config: MagicMock
    ) -> None:
        """AC5: When module filter returns results, no fallback and no Retrieval Note."""
        import pandas as pd

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = AsyncMock(return_value=[0.1] * 128)

        async def mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        class _FakeQuery:
            def __init__(self, rows: list[str]) -> None:
                self._rows = rows

            def to_pandas(self) -> pd.DataFrame:
                return pd.DataFrame({"text": self._rows})

        class _FakeSearch:
            def __init__(self, rows_per_where: dict[str, list[str]]) -> None:
                self._rows_per_where = rows_per_where
                self._last_where: str | None = None

            def where(self, clause: str) -> _FakeSearch:
                self._last_where = clause
                return self

            def limit(self, n: int) -> _FakeQuery:
                return _FakeQuery(self._rows_per_where.get(self._last_where or "", []))

        class _FakeTable:
            def __init__(self, rows_per_where: dict[str, list[str]]) -> None:
                self._rows_per_where = rows_per_where

            def search(self, vec: list[float]) -> _FakeSearch:
                return _FakeSearch(self._rows_per_where)

        filtered_rows: dict[str, list[str]] = {
            "file_path LIKE 'orch/daemon/%' AND file_path != '__iwcore_seed__'": ["chunk-a"],
            "file_path != '__iwcore_seed__'": [],
        }
        mock_table = _FakeTable(filtered_rows)
        mock_db = MagicMock()
        mock_db.open_table.return_value = mock_table

        captured_messages: list = []

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            captured_messages.extend(messages)
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        with (
            patch("lancedb.connect", return_value=mock_db),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            tokens = []
            async for token in engine.answer_stream(
                question="What does this do?",
                context_level="module",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
                module_path="orch/daemon/",
                module_name="Daemon",
            ):
                tokens.append(token)

        system_prompt = captured_messages[0].content
        assert "## Retrieval Note" not in system_prompt

    @pytest.mark.asyncio
    async def test_answer_stream_does_not_fall_back_for_architecture_context(
        self, mock_config: MagicMock
    ) -> None:
        """architecture context level uses unfiltered search from the start; no fallback."""
        import pandas as pd

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = AsyncMock(return_value=[0.1] * 128)

        async def mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        class _FakeQuery:
            def __init__(self, rows: list[str]) -> None:
                self._rows = rows

            def to_pandas(self) -> pd.DataFrame:
                return pd.DataFrame({"text": self._rows})

        class _FakeSearch:
            def __init__(self, rows: list[str]) -> None:
                self._rows = rows

            def where(self, clause: str) -> _FakeSearch:
                return self

            def limit(self, n: int) -> _FakeQuery:
                return _FakeQuery(self._rows)

        class _FakeTable:
            def __init__(self, rows: list[str]) -> None:
                self._rows = rows

            def search(self, vec: list[float]) -> _FakeSearch:
                return _FakeSearch(self._rows)

        mock_table = _FakeTable(["chunk-a"])
        mock_db = MagicMock()
        mock_db.open_table.return_value = mock_table

        captured_messages: list = []

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            captured_messages.extend(messages)
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        with (
            patch("lancedb.connect", return_value=mock_db),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
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

        system_prompt = captured_messages[0].content
        assert "## Retrieval Note" not in system_prompt

    @pytest.mark.asyncio
    async def test_answer_stream_handles_lancedb_exception_without_claiming_fallback(
        self, mock_config: MagicMock
    ) -> None:
        """When LanceDB raises, answer_stream still streams and does not claim fallback."""
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        async def mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        captured_messages: list = []

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            captured_messages.extend(messages)
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        with (
            patch(
                "lancedb.connect",
                side_effect=RuntimeError("LanceDB unavailable"),
            ),
            patch(
                "orch.rag.qa.OllamaEmbedding",
                return_value=mock_embedding_instance,
            ),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            tokens = []
            async for token in engine.answer_stream(
                question="What does this do?",
                context_level="module",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
                module_path="orch/daemon/",
                module_name="Daemon",
            ):
                tokens.append(token)

        assert len(tokens) == 1
        assert tokens[0] == "Answer"
        system_prompt = captured_messages[0].content
        assert "## Retrieval Note" not in system_prompt


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
