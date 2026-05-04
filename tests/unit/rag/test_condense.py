"""Unit tests for condense.py — query rewriting (pure logic only)."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.rag.condense import condense_query


class TestCondenseQuery:
    """condense_query() query rewriting logic."""

    def test_short_circuits_below_two_turns(self) -> None:
        """With <2 history turns, returns question verbatim with no LLM call."""
        llm = MagicMock()
        question = "what is F-00077?"
        history = [{"role": "user", "content": "hello"}]

        result = condense_query(history, question, llm)

        assert result == question
        llm.complete.assert_not_called()

    def test_calls_llm_with_history_and_question(self) -> None:
        """With >=2 history turns, calls LLM.complete() with the documented prompt."""
        llm = MagicMock()
        llm.complete.return_value = MagicMock(
            text="what does keep_alive do in orch/daemon/main.py?"
        )

        history = [
            {"role": "user", "content": "what does keep_alive do?"},
            {"role": "assistant", "content": "keep_alive is a function that..."},
        ]
        question = "explain how it works"

        result = condense_query(history, question, llm)

        llm.complete.assert_called_once()
        call_args = llm.complete.call_args
        prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        # Prompt must contain the conversation history and the follow-up question
        assert "what does keep_alive do?" in prompt_arg
        assert "explain how it works" in prompt_arg
        assert result == "what does keep_alive do in orch/daemon/main.py?"

    def test_strips_whitespace_from_llm_output(self) -> None:
        """Returns the LLM output stripped of leading/trailing whitespace."""
        llm = MagicMock()
        llm.complete.return_value = MagicMock(text="  \n  what is keep_alive?\n  ")

        history = [
            {"role": "user", "content": "what is keep_alive?"},
            {"role": "assistant", "content": "keep_alive is..."},
            {"role": "user", "content": "tell me more"},
        ]
        result = condense_query(history, question="what about it?", llm=llm)

        assert result == "what is keep_alive?"
        assert result == result.strip()

    def test_llm_failure_returns_original_question(self) -> None:
        """On LLM exception, returns original question and does not raise."""
        llm = MagicMock()
        llm.complete.side_effect = Exception("Ollama unreachable")

        history = [
            {"role": "user", "content": "first turn"},
            {"role": "assistant", "content": "first response"},
            {"role": "user", "content": "second turn"},
        ]
        result = condense_query(history, question="follow-up?", llm=llm)

        assert result == "follow-up?"

    def test_uses_only_last_four_turns_for_condense(self) -> None:
        """The condense prompt uses at most the last 4 turns (8 messages), dropping older ones."""
        llm = MagicMock()
        llm.complete.return_value = MagicMock(text="  condensed query  ")

        # 12 messages = 6 turns; only the last 4 turns (8 messages) should appear
        history = [
            {"role": "user", "content": "OLDEST_TURN_1"},
            {"role": "assistant", "content": "OLDEST_TURN_2"},
            {"role": "user", "content": "OLD_TURN_3"},
            {"role": "assistant", "content": "OLD_TURN_4"},
            {"role": "user", "content": "recent_turn_5"},
            {"role": "assistant", "content": "recent_turn_6"},
            {"role": "user", "content": "RECENT_TURN_7"},
            {"role": "assistant", "content": "RECENT_TURN_8"},
            {"role": "user", "content": "LATEST_USER"},
            {"role": "assistant", "content": "LATEST_ASSISTANT"},
            {"role": "user", "content": "ACTUAL_RECENT_1"},
            {"role": "assistant", "content": "ACTUAL_RECENT_2"},
        ]
        question = "follow-up?"

        condense_query(history, question, llm)

        call_args = llm.complete.call_args
        prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        # Only the last 4 turns (8 messages) should appear; older turns must not
        assert "OLDEST_TURN_1" not in prompt_arg
        assert "OLDEST_TURN_2" not in prompt_arg
        assert "OLD_TURN_3" not in prompt_arg
        assert "OLD_TURN_4" not in prompt_arg
        assert "recent_turn_5" in prompt_arg
        assert "recent_turn_6" in prompt_arg
        assert "RECENT_TURN_7" in prompt_arg
        assert "RECENT_TURN_8" in prompt_arg
