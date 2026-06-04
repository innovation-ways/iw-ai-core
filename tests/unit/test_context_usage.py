"""Unit tests for ``orch.chat.context_usage`` — RED evidence recorded below.

Tests follow the TDD cycle: RED (failing test defines expected behaviour),
GREEN (minimal implementation), REFACTOR.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from orch.chat.context_usage import (
    compute_context_pct,
    compute_effective_context_pct,
    lookup_context_window,
    normalize_pi_messages,
    resolve_model_from_tab,
)

assert inspect.isfunction(compute_context_pct), (
    "compute_context_pct must be a function in orch.chat.context_usage"
)
assert inspect.isfunction(normalize_pi_messages), (
    "normalize_pi_messages must be a function in orch.chat.context_usage"
)


# ---------------------------------------------------------------------------
# Helper to build minimal message dicts
# ---------------------------------------------------------------------------


def _msg(
    role: str,
    *,
    content: str = "hello",
    info: dict[str, Any] | None = None,
    tokens: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return a minimal message dict, optionally carrying token usage."""
    msg: dict[str, Any] = {"role": role, "content": content}
    if info is not None:
        msg["info"] = info
    if tokens is not None:
        msg["tokens"] = tokens
    return msg


# ---------------------------------------------------------------------------
# Token-object shapes
# ---------------------------------------------------------------------------

# Valid OpenCode assistant message with all token sub-fields present
_TOKENS_FULL = {
    "input": 1000,
    "output": 2000,
    "reasoning": 500,
    "cache": {"read": 300, "write": 200},
}

# Missing reasoning / cache sub-fields (each defaults to 0)
_TOKENS_PARTIAL_INPUT_ONLY = {"input": 1000}


# ---------------------------------------------------------------------------
# RED / GREEN / REFACTOR test cases
# ---------------------------------------------------------------------------


class TestComputeContextPct:
    """RED phase: these tests define the expected behaviour."""

    # ── 0: No messages ──────────────────────────────────────────────────────

    def test_returns_none_when_messages_empty(self) -> None:
        """Empty list → None (nothing to compute from)."""
        assert compute_context_pct([], context_window=100000) is None

    def test_returns_none_when_messages_is_not_a_list(self) -> None:
        """Not a list → None (defensive)."""
        assert compute_context_pct(None, context_window=100000) is None
        assert compute_context_pct("not a list", context_window=100000) is None
        assert compute_context_pct({}, context_window=100000) is None

    # ── 1: No assistant message ─────────────────────────────────────────────

    def test_returns_none_when_no_assistant_message(self) -> None:
        """Messages with no assistant role → None."""
        msgs = [_msg("user"), _msg("system")]
        assert compute_context_pct(msgs, context_window=100000) is None

    def test_returns_none_when_assistant_has_no_tokens(self) -> None:
        """Assistant message present but tokens absent → None."""
        msgs = [_msg("user"), _msg("assistant", content="I respond")]
        assert compute_context_pct(msgs, context_window=100000) is None

    # ── 2: Most-recent assistant selection ──────────────────────────────────

    def test_uses_most_recent_assistant_message(self) -> None:
        """Messages with two assistants → most recent (last in list) is used."""
        # Earlier assistant with huge token count must NOT be used.
        msgs = [
            _msg("user"),
            _msg("assistant", tokens={"input": 999999, "output": 999999}),
            _msg("user"),  # newer user message between them
            _msg(
                "assistant",
                info={"role": "assistant"},
                tokens={"input": 1000, "output": 2000},
            ),
        ]
        # Context window is large so used_tokens << window → 3%
        pct = compute_context_pct(msgs, context_window=100000)
        assert pct == 3.0, f"Expected 3.0 (3000/100000*100), got {pct}"

    def test_uses_info_nested_role_for_assistant(self) -> None:
        """Role may be nested under message['info']['role'] (OpenCode payload variant)."""
        msgs = [
            _msg("user"),
            _msg(
                "user",  # wrong role at top level
                info={"role": "assistant"},  # but nested role says assistant
                tokens={"input": 5000, "output": 10000},
            ),
        ]
        pct = compute_context_pct(msgs, context_window=100000)
        assert pct == 15.0, f"Expected 15.0 (15000/100000*100), got {pct}"

    # ── 3: Token summing with optional sub-fields ────────────────────────────

    def test_sums_all_token_sub_fields(self) -> None:
        """All five token sub-fields are summed."""
        msgs = [_msg("assistant", tokens=_TOKENS_FULL)]
        # 1000 + 2000 + 500 + 300 + 200 = 4000
        pct = compute_context_pct(msgs, context_window=100000)
        assert pct == 4.0, f"Expected 4.0 (4000/100000*100), got {pct}"

    def test_treats_missing_sub_fields_as_zero(self) -> None:
        """Token object missing input/output/reasoning/cache keys → defaults to 0."""
        msgs = [
            _msg(
                "assistant",
                tokens={"input": 1000},  # only input present
            )
        ]
        pct = compute_context_pct(msgs, context_window=10000)
        assert pct == 10.0, f"Expected 10.0 (1000/10000*100), got {pct}"

    def test_treats_missing_cache_object_as_all_zero(self) -> None:
        """tokens.cache key absent → both read and write default to 0."""
        msgs = [
            _msg(
                "assistant",
                tokens={"input": 3000, "output": 4000},  # no cache at all
            )
        ]
        pct = compute_context_pct(msgs, context_window=100000)
        assert pct == pytest.approx(7.0), f"Expected ~7.0 (7000/100000*100), got {pct}"

    def test_treats_none_token_values_as_zero(self) -> None:
        """None sub-field values are treated as 0."""
        msgs = [
            _msg(
                "assistant",
                tokens={
                    "input": None,  # type: ignore[arg-type]
                    "output": 5000,
                    "reasoning": None,  # type: ignore[arg-type]
                    "cache": {"read": None, "write": None},  # type: ignore[arg-type]
                },
            )
        ]
        pct = compute_context_pct(msgs, context_window=100000)
        assert pct == 5.0, f"Expected 5.0 (5000/100000*100), got {pct}"

    # ── 4: context_window edge cases ─────────────────────────────────────────

    def test_returns_none_when_context_window_is_none(self) -> None:
        """context_window=None → None (can't compute without limit)."""
        msgs = [_msg("assistant", tokens=_TOKENS_FULL)]
        assert compute_context_pct(msgs, context_window=None) is None

    def test_returns_none_when_context_window_is_zero(self) -> None:
        """context_window=0 → None (division by zero guard)."""
        msgs = [_msg("assistant", tokens=_TOKENS_FULL)]
        assert compute_context_pct(msgs, context_window=0) is None

    def test_returns_none_when_context_window_is_negative(self) -> None:
        """Negative context_window → None."""
        msgs = [_msg("assistant", tokens=_TOKENS_FULL)]
        assert compute_context_pct(msgs, context_window=-1) is None

    def test_returns_none_when_used_tokens_is_zero(self) -> None:
        """All token sub-fields are 0 → None (no meaningful data)."""
        msgs = [
            _msg(
                "assistant",
                tokens={"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}},
            )
        ]
        assert compute_context_pct(msgs, context_window=100000) is None

    # ── 5: Percentage clamping ───────────────────────────────────────────────

    def test_clamps_to_100_at_exactly_full(self) -> None:
        """used_tokens == context_window → 100.0 (not 100.0001...)."""
        msgs = [_msg("assistant", tokens={"input": 50000, "output": 50000})]
        assert compute_context_pct(msgs, context_window=100000) == 100.0

    def test_clamps_to_100_when_over(self) -> None:
        """used_tokens > context_window → 100.0 (should not happen but must clamp)."""
        msgs = [_msg("assistant", tokens={"input": 150000, "output": 50000})]
        assert compute_context_pct(msgs, context_window=100000) == 100.0

    def test_clamps_to_0_when_used_tokens_is_zero_but_context_window_positive(
        self,
    ) -> None:
        """Zero used with positive window → None (not 0.0)."""
        msgs = [_msg("assistant", tokens={"input": 0, "output": 0})]
        assert compute_context_pct(msgs, context_window=100000) is None

    # ── 6: Return type ───────────────────────────────────────────────────────

    def test_returns_float_not_int(self) -> None:
        """Percentage is a float even when it computes to a whole number."""
        msgs = [_msg("assistant", tokens={"input": 10000})]
        result = compute_context_pct(msgs, context_window=100000)
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}: {result}"
        assert result == 10.0


# ---------------------------------------------------------------------------
# normalize_pi_messages tests
# ---------------------------------------------------------------------------


class TestNormalizePiMessages:
    """Tests for ``normalize_pi_messages``."""

    def test_returns_empty_list_for_none(self) -> None:
        """Verifies that returns empty list for none."""
        assert normalize_pi_messages(None) == []

    def test_returns_empty_list_for_non_list(self) -> None:
        """Verifies that returns empty list for non list."""
        assert normalize_pi_messages("not a list") == []
        assert normalize_pi_messages(42) == []

    def test_passes_through_non_dict_messages(self) -> None:
        """Verifies that passes through non dict messages."""
        msgs = ["string", 123, None]
        assert normalize_pi_messages(msgs) == msgs

    def test_translates_usage_dict_to_tokens(self) -> None:
        """Verifies that translates usage dict to tokens."""
        msgs = [{"role": "assistant", "usage": {"input": 5000, "output": 200}}]
        result = normalize_pi_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["tokens"]["input"] == 5000
        assert result[0]["tokens"]["output"] == 200
        assert result[0]["tokens"]["reasoning"] == 0
        assert result[0]["tokens"]["cache"]["read"] == 0
        assert result[0]["tokens"]["cache"]["write"] == 0

    def test_translates_cache_read_cache_write_fields(self) -> None:
        """Verifies that translates cache read cache write fields."""
        msgs = [
            {
                "role": "assistant",
                "usage": {"input": 100, "output": 50, "cacheRead": 20, "cacheWrite": 5},
            }
        ]
        result = normalize_pi_messages(msgs)
        assert result[0]["tokens"]["input"] == 100
        assert result[0]["tokens"]["output"] == 50
        assert result[0]["tokens"]["cache"]["read"] == 20
        assert result[0]["tokens"]["cache"]["write"] == 5

    def test_preserves_non_usage_fields(self) -> None:
        """Verifies that preserves non usage fields."""
        msgs = [{"role": "assistant", "content": "hello", "usage": {"input": 100}}]
        result = normalize_pi_messages(msgs)
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "hello"
        assert result[0]["tokens"]["input"] == 100
        assert "usage" in result[0]

    def test_omits_tokens_when_no_usage(self) -> None:
        """Verifies that omits tokens when no usage."""
        msgs = [{"role": "user", "content": "hello"}]
        result = normalize_pi_messages(msgs)
        assert len(result) == 1
        assert "tokens" not in result[0]

    def test_translates_usage_to_tokens(self) -> None:
        """Pi assistant message with ``usage`` dict becomes nested ``tokens`` dict."""
        pi_msg = {
            "role": "assistant",
            "content": [{"type": "text", "text": "Answer."}],
            "usage": {"input": 5000, "output": 3000, "cacheRead": 500, "cacheWrite": 200},
        }
        result = normalize_pi_messages([pi_msg])
        assert len(result) == 1
        assert result[0]["tokens"] == {
            "input": 5000,
            "output": 3000,
            "reasoning": 0,
            "cache": {"read": 500, "write": 200},
        }
        # Original fields are preserved.
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == pi_msg["content"]

    def test_leaves_non_assistant_messages_unchanged(self) -> None:
        """User message with ``usage`` passes through with ``tokens`` added."""
        pi_msg = {
            "role": "user",
            "content": [{"type": "text", "text": "Hello?"}],
            "usage": {"input": 100, "output": 0},
        }
        result = normalize_pi_messages([pi_msg])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["tokens"]["input"] == 100

    def test_omits_usage_when_absent(self) -> None:
        """Message without ``usage`` has no ``tokens`` key added."""
        pi_msg = {"role": "assistant", "content": [{"type": "text", "text": "Hi."}]}
        result = normalize_pi_messages([pi_msg])
        assert len(result) == 1
        assert "tokens" not in result[0]
        assert "usage" not in result[0]

    def test_partial_usage_fields_default_to_zero(self) -> None:
        """``usage`` missing some fields → those token sub-fields default to 0."""
        pi_msg = {
            "role": "assistant",
            "usage": {"input": 42},  # only input present
        }
        result = normalize_pi_messages([pi_msg])
        assert result[0]["tokens"]["input"] == 42
        assert result[0]["tokens"]["output"] == 0
        assert result[0]["tokens"]["cache"]["read"] == 0
        assert result[0]["tokens"]["cache"]["write"] == 0

    def test_non_dict_message_passes_through(self) -> None:
        """Non-dict message entries pass through without modification."""
        result = normalize_pi_messages(["not a dict", None])
        assert result[0] == "not a dict"
        assert result[1] is None

    def test_none_input_returns_empty_list(self) -> None:
        """Non-list input (including None) returns an empty list."""
        assert normalize_pi_messages(None) == []
        assert normalize_pi_messages("string") == []
        assert normalize_pi_messages(42) == []

    def test_combined_with_compute_context_pct(self) -> None:
        """normalize_pi_messages output feeds correctly into ``compute_context_pct``."""
        pi_messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Answer."}],
                "usage": {"input": 5000, "output": 3000, "cacheRead": 500, "cacheWrite": 200},
            },
        ]
        normalized = normalize_pi_messages(pi_messages)
        pct = compute_context_pct(normalized, context_window=100000)
        # 5000+3000+500+200 = 8700; 8700/100000*100 = 8.7
        assert pct == pytest.approx(8.7)


# ---------------------------------------------------------------------------
# lookup_context_window tests
# ---------------------------------------------------------------------------


class TestLookupContextWindow:
    """Tests for ``lookup_context_window``."""

    def test_returns_context_when_present(self) -> None:
        """Verifies that returns context when present."""
        providers = {
            "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": 128000}}}}]
        }
        assert lookup_context_window(providers, "openai", "gpt-4o") == 128000

    def test_returns_none_when_providers_absent(self) -> None:
        """Verifies that returns none when providers absent."""
        assert lookup_context_window({}, "openai", "gpt-4o") is None

    def test_returns_none_when_provider_not_found(self) -> None:
        """Verifies that returns none when provider not found."""
        providers = {"providers": [{"id": "anthropic", "models": {"claude-3-5": {}}}]}
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_returns_none_when_model_not_found(self) -> None:
        """Verifies that returns none when model not found."""
        providers = {"providers": [{"id": "openai", "models": {"gpt-4o-mini": {}}}]}
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_returns_none_when_limit_absent(self) -> None:
        """Verifies that returns none when limit absent."""
        providers = {"providers": [{"id": "openai", "models": {"gpt-4o": {}}}]}
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_returns_none_when_context_is_zero(self) -> None:
        """Verifies that returns none when context is zero."""
        providers = {
            "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": 0}}}}]
        }
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_returns_none_when_context_is_negative(self) -> None:
        """Verifies that returns none when context is negative."""
        providers = {
            "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": -1}}}}]
        }
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_returns_none_when_context_is_string(self) -> None:
        """Verifies that returns none when context is string."""
        providers = {
            "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": "128000"}}}}]
        }
        assert lookup_context_window(providers, "openai", "gpt-4o") is None

    def test_handles_float_context_value(self) -> None:
        """Verifies that handles float context value."""
        providers = {
            "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": 128000.0}}}}]
        }
        assert lookup_context_window(providers, "openai", "gpt-4o") == 128000


# ---------------------------------------------------------------------------
# resolve_model_from_tab tests
# ---------------------------------------------------------------------------


class TestResolveModelFromTab:
    """Tests for ``resolve_model_from_tab``."""

    def test_prefers_info_providerid_modelid_over_tab_model(self) -> None:
        """Most-recent assistant with info.providerID/modelID wins over tab.model."""
        msgs = [
            _msg("user"),
            _msg("assistant", info={"providerID": "anthropic", "modelID": "claude-3-5-sonnet"}),
        ]
        result = resolve_model_from_tab("openai/gpt-4o", msgs)
        assert result == ("anthropic", "claude-3-5-sonnet")

    def test_falls_back_to_tab_model(self) -> None:
        """When no message has provider/model info, use tab.model."""
        msgs = [_msg("user"), _msg("assistant")]
        result = resolve_model_from_tab("openai/gpt-4o", msgs)
        assert result == ("openai", "gpt-4o")

    def test_returns_none_when_no_providerid_in_tab_model(self) -> None:
        """tab_model without a slash cannot be split."""
        msgs = [_msg("user")]
        assert resolve_model_from_tab("gpt-4o", msgs) is None
        assert resolve_model_from_tab(None, msgs) is None
        assert resolve_model_from_tab("", msgs) is None

    def test_uses_most_recent_assistant_message(self) -> None:
        """Only the most-recent assistant message's info is used."""
        msgs = [
            _msg("user"),
            _msg("assistant", info={"providerID": "old", "modelID": "old-model"}),
            _msg("user"),
            _msg("assistant", info={"providerID": "new", "modelID": "new-model"}),
        ]
        result = resolve_model_from_tab("fallback/model", msgs)
        assert result == ("new", "new-model")

    def test_skips_non_assistant_messages_for_info(self) -> None:
        """Info from user/system messages is not used."""
        msgs = [
            _msg("user", info={"providerID": "bad", "modelID": "bad-model"}),
            _msg("assistant"),
        ]
        result = resolve_model_from_tab("openai/gpt-4o", msgs)
        assert result == ("openai", "gpt-4o")


# ---------------------------------------------------------------------------
# I-00105 — Effective-budget meter (S03 backend-impl)
# ---------------------------------------------------------------------------


class TestComputeEffectiveContextPct:
    """AC1: context gauge must measure against the EFFECTIVE budget.

    The effective budget is:  window − max_output_tokens − safety_buffer
    NOT the raw context_window.  This allows a model like MiniMax-M2.7
    (204,800 window / 131,072 max_output) to correctly show that ~131K
    input is AT or PAST the ceiling, not "64%" as the raw-window meter reads.

    R-00078 finding: "A model's effective input budget is window − max_output,
    not the full window."
    """

    # ── 1: Core effective-budget formula ────────────────────────────────────

    def test_minimax_m2_7_131k_input_is_past_effective_ceiling(self) -> None:
        """MiniMax-M2.7: window=204,800, max_output=131,072, used=131,072.

        Raw-window meter: 131,072 / 204,800 * 100 ≈ 64%  ← MISLEADING.
        Effective budget:  204,800 − 131,072 =  73,728
        Effective pct:     131,072 /   73,728 * 100 ≈ 177.8%  ← CORRECT.

        The gauge MUST report >= 100% (past the effective ceiling).
        """
        pct = compute_effective_context_pct(
            used_tokens=131_072,
            context_window=204_800,
            max_output_tokens=131_072,
        )
        assert isinstance(pct, float), f"Expected float, got {pct!r}"
        assert pct >= 100.0, (
            f"131K input on a 205K/131K-output model is past the effective "
            f"ceiling; meter MUST report >=100%, got {pct}"
        )

    def test_no_overhead_model_small_pct(self) -> None:
        """A model with large window and small output reservation: pct stays low.

        gpt-4o: 128,000 window, 16,384 max_output (theoretical); used 10K input.
        Effective budget: 128,000 − 16,384 = 111,616.
        pct: 10,000 / 111,616 * 100 ≈ 8.96%.
        """
        pct = compute_effective_context_pct(
            used_tokens=10_000,
            context_window=128_000,
            max_output_tokens=16_384,
        )
        # effective_budget = (128,000 − 16,384 − 20,000) = 91,616
        # 10,000 / 91,616 * 100 ≈ 10.9%; allow some tolerance for the default buffer
        assert isinstance(pct, float), f"Expected float, got {pct!r}"
        assert 8.0 <= pct <= 12.0, f"Expected ~9-11%, got {pct}"

    def test_used_at_effective_budget_is_100pct(self) -> None:
        """used_tokens == effective_budget → 100.0 when buffer=0."""
        # effective_budget = 204,800 − 131,072 − 0 = 73,728
        # 73,728 / 73,728 * 100 = 100.0 exactly
        pct = compute_effective_context_pct(
            used_tokens=73_728,
            context_window=204_800,
            max_output_tokens=131_072,
            safety_buffer=0,
        )
        assert pct == 100.0

    def test_used_below_effective_budget_under_100(self) -> None:
        """used_tokens < effective_budget → < 100.0 (normal range)."""
        pct = compute_effective_context_pct(
            used_tokens=40_000,
            context_window=204_800,
            max_output_tokens=131_072,
        )
        assert isinstance(pct, float), f"Expected float, got {pct!r}"
        assert pct < 100.0
        assert pct > 0.0

    def test_used_above_effective_budget_can_exceed_100(self) -> None:
        """used_tokens > effective_budget → pct > 100.0 (warning range).

        Unlike the raw-window meter which clamps at 100, the effective-budget
        meter MUST allow > 100 so the gauge can show "PAST CEILING".
        """
        pct = compute_effective_context_pct(
            used_tokens=90_000,
            context_window=204_800,
            max_output_tokens=131_072,
        )
        assert isinstance(pct, float), f"Expected float, got {pct!r}"
        assert pct > 100.0, f"90K input / 73K effective budget should be >100%, got {pct}"

    # ── 2: safety_buffer parameter ──────────────────────────────────────────

    def test_safety_buffer_reduces_effective_budget(self) -> None:
        """A 20,000-token safety buffer reduces the effective budget further.

        effective_budget = window − max_output − buffer
        For MiniMax-M2.7: 204,800 − 131,072 − 20,000 = 53,728.
        90K input against 53,728 budget ≈ 167%.
        """
        pct = compute_effective_context_pct(
            used_tokens=90_000,
            context_window=204_800,
            max_output_tokens=131_072,
            safety_buffer=20_000,
        )
        assert isinstance(pct, float), f"Expected float, got {pct!r}"
        assert pct > 150.0, f"Expected >150% with 20K buffer, got {pct}"

    def test_default_safety_buffer_is_non_zero(self) -> None:
        """Default buffer must be positive so there is always headroom for the response.

        Without a buffer the model has zero room to generate output — guaranteed overflow.
        """
        pct_default = compute_effective_context_pct(
            used_tokens=73_728,
            context_window=204_800,
            max_output_tokens=131_072,
        )
        pct_no_buffer = compute_effective_context_pct(
            used_tokens=73_728,
            context_window=204_800,
            max_output_tokens=131_072,
            safety_buffer=0,
        )
        # With a default buffer, 73,728 input (== effective budget with no buffer)
        # should push above 100% — proving a positive default exists.
        assert isinstance(pct_default, float), f"Expected float, got {pct_default!r}"
        assert isinstance(pct_no_buffer, float), f"Expected float, got {pct_no_buffer!r}"
        assert pct_default > pct_no_buffer, (
            f"Default pct ({pct_default}) should exceed no-buffer pct ({pct_no_buffer}) — "
            f"proves default buffer is positive"
        )

    def test_zero_safety_buffer_is_explicit_opt_out(self) -> None:
        """safety_buffer=0 disables the reserve (opt-in behaviour)."""
        pct = compute_effective_context_pct(
            used_tokens=73_728,
            context_window=204_800,
            max_output_tokens=131_072,
            safety_buffer=0,
        )
        assert pct == 100.0

    # ── 3: NULL max_output → fall back to raw-window behaviour ─────────────

    def test_null_max_output_falls_back_to_raw_window(self) -> None:
        """max_output_tokens=None: degrade gracefully to raw-window division.

        This ensures the meter NEVER crashes even when the DB has no output
        reservation for a runtime. Matches the design note: "NULL max_output
        falls back gracefully, not crashing."
        """
        pct = compute_effective_context_pct(
            used_tokens=50_000,
            context_window=100_000,
            max_output_tokens=None,
        )
        # Raw window: 50,000 / 100,000 * 100 = 50.0
        assert pct == 50.0, f"NULL max_output should fall back to raw-window; got {pct}"

    def test_null_max_output_no_clamp_above_100(self) -> None:
        """max_output_tokens=None: when input exceeds window, pct may exceed 100.

        The raw-window fallback does NOT clamp at 100 (unlike compute_context_pct).
        This is intentional: the effective-budget meter is designed to show
        "past ceiling" readings, so even the NULL-max_output fallback path
        must allow > 100. Use ``min(pct, 100)`` at the display layer if needed.
        """
        pct = compute_effective_context_pct(
            used_tokens=150_000,
            context_window=100_000,
            max_output_tokens=None,
            safety_buffer=0,  # disable buffer so raw-window fallback is clean
        )
        assert pct == 150.0, f"Expected 150% (uncapped), got {pct}"

    # ── 4: Edge cases ──────────────────────────────────────────────────────

    def test_zero_context_window_returns_none(self) -> None:
        """context_window=0 → None (guard division-by-zero)."""
        assert (
            compute_effective_context_pct(
                used_tokens=50_000,
                context_window=0,
                max_output_tokens=10_000,
            )
            is None
        )

    def test_negative_context_window_returns_none(self) -> None:
        """Negative context_window → None."""
        assert (
            compute_effective_context_pct(
                used_tokens=50_000,
                context_window=-1,
                max_output_tokens=10_000,
            )
            is None
        )

    def test_effective_budget_cannot_be_negative(self) -> None:
        """max_output + buffer > window → effective_budget ≤ 0 → return None.

        A model whose output reservation equals or exceeds its window has no
        usable input budget at all; the meter should not return a confusing
        percentage. Return None (can't compute) rather than crash.
        """
        result = compute_effective_context_pct(
            used_tokens=50_000,
            context_window=100_000,
            max_output_tokens=120_000,  # output > window
            safety_buffer=10_000,
        )
        assert result is None, f"Budget ≤ 0 should return None, got {result}"

    def test_effective_budget_can_be_exactly_zero(self) -> None:
        """effective_budget = 0 → None (can't divide by zero)."""
        # window=100, max_output=100, buffer=0 → effective_budget=0
        result = compute_effective_context_pct(
            used_tokens=50_000,
            context_window=100_000,
            max_output_tokens=100_000,
            safety_buffer=0,
        )
        assert result is None, f"effective_budget=0 should return None, got {result}"


# Modules with no DB I/O — safe to import at unit-test collection time.
