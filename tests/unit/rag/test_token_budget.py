"""RED phase: tests for token-budget truncation."""

from __future__ import annotations

from orch.rag.qa import _truncate_messages_to_budget


class TestTruncateMessagesToBudget:
    """Token-budget truncation that drops oldest messages first."""

    def test_drops_oldest_first(self) -> None:
        """When total exceeds budget, oldest messages are removed first."""
        messages = [
            {"role": "user", "content": "Hello", "token_count": 1000},
            {"role": "assistant", "content": "Hi", "token_count": 1000},
            {"role": "user", "content": "Tell me about X", "token_count": 1000},
            {"role": "assistant", "content": "X is ...", "token_count": 1000},
            {"role": "user", "content": "What about Y?", "token_count": 1000},
        ]
        # Budget that would keep only last 2 if we have 5 messages
        result = _truncate_messages_to_budget(messages, soft_budget_tokens=100)
        # With budget=100, only the newest 2 (correctness over budget) survive
        assert len(result) == 2
        assert result[-1] == messages[-1]  # last message preserved
        assert result[-2] == messages[-2]  # second-to-last preserved

    def test_preserves_last_two_even_if_they_exceed_budget(self) -> None:
        """The last 2 messages are always kept, even if they alone exceed the budget."""
        messages = [
            {"role": "user", "content": "old message 1", "token_count": 5000},
            {"role": "assistant", "content": "old response 1", "token_count": 5000},
            {
                "role": "user",
                "content": "recent question that is very long and exceeds budget alone",
                "token_count": 5000,
            },
            {
                "role": "assistant",
                "content": "recent answer that is also very long and exceeds budget",
                "token_count": 5000,
            },
        ]
        result = _truncate_messages_to_budget(messages, soft_budget_tokens=1)
        # The last 2 messages must be preserved regardless of budget
        assert result[-1] == messages[-1]
        assert result[-2] == messages[-2]
        assert len(result) == 2

    def test_empty_input_returns_empty(self) -> None:
        """Empty list returns empty list."""
        result = _truncate_messages_to_budget([], soft_budget_tokens=3000)
        assert result == []

    def test_below_budget_returns_unchanged(self) -> None:
        """Messages that fit within budget are returned unchanged."""
        messages = [
            {"role": "user", "content": "short", "token_count": 5},
            {"role": "assistant", "content": "also short", "token_count": 5},
        ]
        result = _truncate_messages_to_budget(messages, soft_budget_tokens=3000)
        assert result == messages
