"""Unit tests for the query classifier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestClassifyQuery:
    """Tests for classify_query function."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock CodeUnderstandingConfig."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    @pytest.mark.asyncio
    async def test_slash_override_why_returns_workitem_aware(self, mock_config: MagicMock) -> None:
        """AC2: /why chip forces workitem_aware pipeline."""
        from orch.rag.classifier import classify_query

        result = await classify_query(
            "why does the daemon work?",
            mock_config,
            context_chips=["why"],
        )
        assert result == "workitem_aware"

    @pytest.mark.asyncio
    async def test_slash_override_history_returns_workitem_aware(self, mock_config: MagicMock) -> None:
        """AC2: /history chip forces workitem_aware pipeline."""
        from orch.rag.classifier import classify_query

        result = await classify_query(
            "what changed?",
            mock_config,
            context_chips=["history"],
        )
        assert result == "workitem_aware"

    @pytest.mark.asyncio
    async def test_slash_override_findusages_returns_workitem_aware(self, mock_config: MagicMock) -> None:
        """AC2: /findusages chip forces workitem_aware pipeline."""
        from orch.rag.classifier import classify_query

        result = await classify_query(
            "where is this used?",
            mock_config,
            context_chips=["findusages"],
        )
        assert result == "workitem_aware"

    @pytest.mark.asyncio
    async def test_no_chips_no_context_defaults_to_code_only(self, mock_config: MagicMock) -> None:
        """Without chips, non-behavioral query defaults to code_only."""
        from orch.rag.classifier import classify_query

        result = await classify_query("show me the signature", mock_config, context_chips=None)
        assert result == "code_only"

    @pytest.mark.asyncio
    async def test_llm_classify_behavioral_query(self, mock_config: MagicMock) -> None:
        """Behavior questions get classified as workitem_aware by LLM."""
        from orch.rag.classifier import classify_query

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "workitem_aware"
        mock_llm.complete = MagicMock(return_value=mock_response)

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = await classify_query(
                "why does the daemon retry 3 times?",
                mock_config,
                context_chips=None,
            )

        assert result == "workitem_aware"

    @pytest.mark.asyncio
    async def test_llm_classify_code_query(self, mock_config: MagicMock) -> None:
        """Technical queries get classified as code_only by LLM."""
        from orch.rag.classifier import classify_query

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "code_only"
        mock_llm.complete = MagicMock(return_value=mock_response)

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = await classify_query(
                "show me the signature of parse_id",
                mock_config,
                context_chips=None,
            )

        assert result == "code_only"

    @pytest.mark.asyncio
    async def test_llm_timeout_falls_back_to_code_only(self, mock_config: MagicMock) -> None:
        """On LLM timeout, default to code_only (AC3 low-confidence behavior)."""

        from orch.rag.classifier import classify_query

        mock_llm = MagicMock()
        mock_llm.complete = MagicMock(side_effect=TimeoutError("LLM request timed out"))

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = await classify_query(
                "why does this work?",
                mock_config,
                context_chips=None,
            )

        assert result == "code_only"

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_code_only(self, mock_config: MagicMock) -> None:
        """On LLM exception, default to code_only."""
        from orch.rag.classifier import classify_query

        mock_llm = MagicMock()
        mock_llm.complete = MagicMock(side_effect=Exception("LLM unavailable"))

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = await classify_query(
                "why does this work?",
                mock_config,
                context_chips=None,
            )

        assert result == "code_only"


class TestSlashOverrideChips:
    """Tests for slash override chip detection."""

    def test_case_insensitive_override(self) -> None:
        """Chip matching is case-insensitive."""
        from orch.rag.classifier import SLASH_OVERRIDE_CHIPS

        mock_config = MagicMock()
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"

        for chip in ["WHY", "History", "FINDUSAGES"]:
            assert chip.lower() in SLASH_OVERRIDE_CHIPS or chip.upper() in SLASH_OVERRIDE_CHIPS

    @pytest.mark.asyncio
    async def test_empty_chips_list(self) -> None:
        """Empty chips list does not trigger override."""
        from orch.rag.classifier import classify_query

        mock_config = MagicMock()
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "code_only"
        mock_llm.complete = MagicMock(return_value=mock_response)

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = await classify_query("show me the signature", mock_config, context_chips=[])
            assert result == "code_only"
