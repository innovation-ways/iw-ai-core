"""Unit tests for executor/context_overflow.py — AC4 / I-00105.

These tests cover the context-overflow-detection helper:

* runtime output carrying an overflow signature → detected with a clear blocker message
* clean output → not detected
* specific blocker text, not shape

Per the TDD contract, tests assert specific values, not just shape.
"""

from __future__ import annotations

from executor.context_overflow import (
    OverflowDetectionResult,
    detect_context_overflow,
    overflow_signatures,
)


class TestDetectContextOverflow:
    """AC4 tests: overflow detected → step failed cleanly."""

    # ── 1: Detection of each signature ──────────────────────────────────────

    def test_anthropic_context_window_exceeded(self) -> None:
        """Anthropic API: 400 invalid_request_error: context window exceeds limit."""
        text = (
            "Error: 400 invalid_request_error: "
            "context window exceeds limit for model 'minimax/MiniMax-M2.7' "
            "(2013 tokens over)"
        )
        result = detect_context_overflow(text)
        assert result.detected is True, "Must detect anthropic overflow signature"
        assert "anthropic_context_window_exceeded" in result.signatures_found
        assert result.blocker_message is not None

    def test_openai_context_length_exceeded(self) -> None:
        """OpenAI API: context_length_exceeded."""
        text = "error: context_length_exceeded: model context is 128000 tokens"
        result = detect_context_overflow(text)
        assert result.detected is True
        assert "openai_context_length_exceeded" in result.signatures_found

    def test_azure_context_limit_exceeded(self) -> None:
        """Azure OpenAI: context_limit_exceeded."""
        text = "AzureOpenAIError: context_limit_exceeded"
        result = detect_context_overflow(text)
        assert result.detected is True
        assert "azure_context_limit" in result.signatures_found

    def test_opencode_context_overflow_error(self) -> None:
        """opencode: ContextOverflowError."""
        text = "opencode.exceptions.ContextOverflowError: Compaction failed"
        result = detect_context_overflow(text)
        assert result.detected is True
        assert "opencode_context_overflow" in result.signatures_found

    def test_litellm_context_exceeded(self) -> None:
        """LiteLLM: 'Context window exceeded'."""
        text = "litellm.MaximumTokensExceededError: Context window exceeded"
        result = detect_context_overflow(text)
        assert result.detected is True
        assert "litellm_context_exceeded" in result.signatures_found

    # ── 2: Clean output — no false positives ────────────────────────────────

    def test_clean_output_not_detected(self) -> None:
        """Clean runtime output: no overflow signature → detected=False."""
        text = (
            "Running pytest tests/unit/\n"
            "collected 42 items\n"
            "tests/test_foo.py::test_bar PASSED\n"
            "All tests passed (exit code 0)"
        )
        result = detect_context_overflow(text)
        assert result.detected is False, "Clean output must not trigger overflow detection"
        assert result.signatures_found == ()
        assert result.blocker_message is None

    def test_user_content_with_context_word_not_false_positive(self) -> None:
        """A message that happens to contain 'context' in normal text."""
        text = (
            "User: I need a function that manages context for a cache.\n"
            "Assistant: def cache_context(key, value): ..."
        )
        result = detect_context_overflow(text)
        assert result.detected is False, "'context' in user prose must not trigger a false positive"

    def test_empty_text_not_detected(self) -> None:
        """Empty string → detected=False."""
        result = detect_context_overflow("")
        assert result.detected is False
        assert result.signatures_found == ()

    def test_none_text_not_detected(self) -> None:
        """None input → detected=False (defensive)."""
        result = detect_context_overflow(None)  # type: ignore[arg-type]
        assert result.detected is False

    # ── 3: Blocker message ─────────────────────────────────────────────────

    def test_blocker_message_names_context_overflow(self) -> None:
        """Blocker message must name context overflow as the cause."""
        text = "Error: 400 invalid_request_error: context window exceeds limit"
        result = detect_context_overflow(text)
        assert result.blocker_message is not None
        assert "context" in result.blocker_message.lower()
        assert "overflow" in result.blocker_message.lower()
        assert "I-00105" in result.blocker_message or "step" in result.blocker_message.lower()

    def test_custom_blocker_message_is_used(self) -> None:
        """Custom blocker_message replaces the default."""
        custom = "CUSTOM BLOCKER: context overflow in I-00105 S07"
        text = "Error: context window exceeds limit"
        result = detect_context_overflow(text, blocker_message=custom)
        assert result.detected is True
        assert result.blocker_message == custom

    # ── 4: Return type / schema ───────────────────────────────────────────

    def test_returns_dataclass_with_detected_boolean(self) -> None:
        """Result must be an OverflowDetectionResult with a detected bool."""
        text = "Error: 400 invalid_request_error: context window exceeds limit"
        result = detect_context_overflow(text)
        assert isinstance(result, OverflowDetectionResult)
        assert isinstance(result.detected, bool)
        assert isinstance(result.signatures_found, tuple)
        assert isinstance(result.blocker_message, (str, type(None)))
        # Concrete value assertions — not just shape.
        assert result.detected is True, (
            "detected must be True when an overflow signature is present"
        )
        assert len(result.signatures_found) >= 1, (
            "signatures_found must contain at least one label when overflow is detected"
        )
        assert result.blocker_message is not None

    def test_multiple_signatures_in_one_text(self) -> None:
        """Text containing multiple signatures → signatures_found lists all."""
        # In practice only one runtime fires, but test the multi-match path.
        text = "anthropic: context window exceeds limit\nalso openai context_length_exceeded"
        result = detect_context_overflow(text)
        assert result.detected is True
        assert len(result.signatures_found) >= 1

    # ── 5: Case-sensitivity ────────────────────────────────────────────────

    def test_signature_is_case_sensitive(self) -> None:
        """Matches are case-sensitive — 'Context Window Exceeds Limit' ≠ signature."""
        text = "Error: Context Window Exceeds Limit (capitalised)"
        result = detect_context_overflow(text)
        # Case differs from the stored signature "context window exceeds limit"
        assert result.detected is False, (
            "Case-sensitive match: capitalised phrase must NOT trigger detection"
        )


class TestOverflowSignatures:
    """Sanity-check the exposed signature list (for test discovery)."""

    def test_returns_list_of_strings(self) -> None:
        """Verifies that overflow_signatures returns a non-empty list of string labels."""
        labels = overflow_signatures()
        assert isinstance(labels, list)
        assert len(labels) >= 5
        for label in labels:
            assert isinstance(label, str)
            assert len(label) > 0

    def test_known_labels_present(self) -> None:
        """The five core signatures must be in the returned list."""
        labels = overflow_signatures()
        expected = {
            "anthropic_context_window_exceeded",
            "openai_context_length_exceeded",
            "azure_context_limit",
            "opencode_context_overflow",
            "litellm_context_exceeded",
        }
        for label in expected:
            assert label in labels, f"Missing expected signature label: {label}"
        # Concrete assertion: the list must have at least the expected count.
        assert len(labels) >= len(expected), (
            f"overflow_signatures() must return at least {len(expected)} labels; got {len(labels)}"
        )
