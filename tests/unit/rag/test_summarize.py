"""RED phase: tests for summarize.py — conversation compaction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orch.rag.summarize import summarize_history


class TestSummarizeHistory:
    """summarize_history() produces compact prose preserving entities."""

    def test_produces_non_empty_text(self) -> None:
        """Given a fixture conversation, produces non-empty summary text."""
        messages = [
            MagicMock(role="user", content="my name is sergio"),
            MagicMock(role="assistant", content="Hello Sergio!"),
            MagicMock(role="user", content="I am working on F-00055"),
            MagicMock(role="assistant", content="F-00055 is the chat memory feature"),
        ]
        llm = MagicMock()
        llm.chat.return_value = MagicMock(
            message=MagicMock(content="Sergio is working on F-00055.")
        )

        result = summarize_history(messages, llm)

        assert result
        assert isinstance(result, str)

    def test_injects_entities_into_prompt(self) -> None:
        """Named entities from conversation appear in the rendered prompt."""
        messages = [
            MagicMock(role="user", content="my name is sergio"),
            MagicMock(role="assistant", content="Hi Sergio!"),
        ]
        llm = MagicMock()
        llm.chat.return_value = MagicMock(message=MagicMock(content="Summary."))

        summarize_history(messages, llm)

        call_args = llm.chat.call_args
        # Get messages passed to chat
        llm_messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
        prompt_text = str(llm_messages)
        assert "sergio" in prompt_text or "Sergio" in prompt_text

    def test_previous_summary_included_in_prompt(self) -> None:
        """When previous_summary is provided, it is injected into the prompt."""
        messages = [
            MagicMock(role="user", content="hello"),
            MagicMock(role="assistant", content="hi there"),
        ]
        llm = MagicMock()
        llm.chat.return_value = MagicMock(message=MagicMock(content="Updated summary."))

        summarize_history(messages, llm, previous_summary="Earlier we discussed project X.")

        call_args = llm.chat.call_args
        llm_messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
        prompt_text = str(llm_messages)
        assert "Earlier we discussed project X" in prompt_text

    def test_llm_raises_propagates(self) -> None:
        """If LLM raises, summarize_history re-raises (caller handles as failed job)."""
        messages = [MagicMock(role="user", content="hello")]
        llm = MagicMock()
        llm.chat.side_effect = Exception("Ollama error")

        with pytest.raises(Exception, match="Ollama error"):
            summarize_history(messages, llm)

    def test_preserves_named_entities_workitem_ids(self) -> None:
        """Work-item IDs like F-00055 appear in the summary."""
        messages = [
            MagicMock(role="user", content="I am working on F-00055 in orch/daemon/main.py"),
            MagicMock(role="assistant", content="Good progress on F-00055."),
        ]
        llm = MagicMock()
        llm.chat.return_value = MagicMock(
            message=MagicMock(content="Summary of F-00055 work in orch/daemon/main.py.")
        )

        result = summarize_history(messages, llm)

        assert "F-00055" in result or "orch/daemon/main.py" in result
