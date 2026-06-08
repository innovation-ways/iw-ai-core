"""Unit tests for I-00105 — effective-budget context meter.

AC1: the bug is a calibration error in the meter — it divides by the raw
context window instead of the effective budget (window − max_output − buffer).

These tests verify the meter computes against the EFFECTIVE budget, not the
raw window. The reproduction test (`test_i_00105_context_pct_accounts_for_output_reservation`)
MUST fail against the pre-fix meter and pass against the effective-budget meter.

Coverage:
- AC1   — effective-budget computation (large max_output, small max_output, NULL)
- AC1   — safety_buffer shifts the percentage by the expected amount
- AC1   — edge cases: zero/negative window, zero/negative effective budget
- TDD   — `test_i_00105_context_pct_accounts_for_output_reservation` matches the
          design doc's §Test to Reproduce verbatim
"""

from __future__ import annotations

import pytest

from orch.chat.context_usage import (
    DEFAULT_SAFETY_BUFFER_TOKENS,
    compute_effective_context_pct,
)

# ---------------------------------------------------------------------------
# AC1 — Effective-budget meter
# ---------------------------------------------------------------------------


class TestI00105EffectiveContextPct:
    """I-00105 AC1: context usage is measured against the effective budget."""

    # ── TDD Reproduction Test ─────────────────────────────────────────────────

    def test_i_00105_context_pct_accounts_for_output_reservation(self) -> None:
        """AC1 reproduction: MiniMax-M2.7 at 131 K input reads ≥100 %.

        The design doc §Test to Reproduce:
          "A model whose max_output is a large fraction of its window must report
          usage against the EFFECTIVE budget (window - max_output - buffer), not the
          raw window. FAILS pre-fix (meter divides by the full window)."

        Effective budget = 204,800 − 131,072 − 20,000 = 53,728.
        131,072 / 53,728 * 100 ≈ 244 %.
        Raw-window percentage would be 131,072/204,800*100 ≈ 64 % ← the bug.

        Pre-fix meter (divides by raw window): 131,072/204,800*100 = 64 % → fails this assertion.
        Post-fix meter (divides by effective budget): ~244 % → passes this assertion.
        """
        pct = compute_effective_context_pct(
            used_tokens=131_072,
            context_window=204_800,
            max_output_tokens=131_072,
        )
        assert pct is not None
        assert pct >= 100.0, (
            f"131K input on a 205K/131K-output model is past the effective "
            f"ceiling; meter must report >=100%, got {pct}"
        )
        # Sanity: the raw-window percentage would be ~64 %, which must NOT be returned.
        assert pct > 200.0, (
            f"Meter reported {pct}% — suspiciously close to the raw-window 64%; "
            f"the fix should compute ~244% against the effective budget"
        )

    # ── Large max_output: effective budget >> raw window gap ─────────────────

    def test_large_max_output_near_effective_ceiling_reads_over_100_pct(self) -> None:
        """MiniMax-M2.7 at 131 K input (131,072 tokens) reads ≥100 % effective."""
        result = compute_effective_context_pct(131_072, 204_800, 131_072)
        assert result is not None
        assert result >= 100.0  # at or past the effective ceiling
        assert result > 200.0  # well above 100 %

    def test_large_max_output_raw_window_reads_64_pct(self) -> None:
        """Same inputs with max_output_tokens=None fall back to raw-window 64 %.

        This verifies the NULL fallback — no regression to raw-window division
        when max_output is not known (the meter degrades to today's behaviour
        rather than crashing).
        """
        result = compute_effective_context_pct(131_072, 204_800, None)
        assert result is not None
        assert result == pytest.approx(64.0), (
            f"max_output_tokens=None should fall back to raw-window pct; "
            f"expected ~64.0, got {result}"
        )

    def test_raw_window_pct_and_effective_pct_diverge_materially(self) -> None:
        """At MiniMax-M2.7's problematic input level the two meters differ by ~180 pp.

        This guards against a future regression where both formulas are correct
        but the code path accidentally picks the wrong one. The divergence must
        always be large (the bug is invisible at small max_output fractions).
        """
        raw = compute_effective_context_pct(131_072, 204_800, None)
        effective = compute_effective_context_pct(131_072, 204_800, 131_072)
        assert raw is not None
        assert effective is not None
        gap = effective - raw
        assert gap > 150.0, (
            f"Effective pct ({effective}%) and raw pct ({raw}%) should diverge "
            f"by >150pp for MiniMax-M2.7 at 131K input; gap={gap}pp — "
            f"check the meter is using the correct formula"
        )

    # ── Small max_output: effective budget close to raw window ───────────────

    def test_small_max_output_effective_close_to_raw(self) -> None:
        """A small max_output (e.g. 8K on a 128K window) barely shifts the budget."""
        raw = compute_effective_context_pct(50_000, 128_000, None)
        effective = compute_effective_context_pct(50_000, 128_000, 8_000)
        assert raw is not None
        assert effective is not None
        # 50K/128K = 39 %; 50K/(128K−8K−20K) = 50K/100K = 50 %
        # Gap is ~11pp — small but measurable
        assert raw < effective, "Effective pct should exceed raw pct when max_output > 0"
        assert effective == pytest.approx(50.0), f"Expected 50%, got {effective}"
        assert raw == pytest.approx(39.0625), f"Expected ~39%, got {raw}"

    def test_half_effective_budget_consumed_is_50_pct(self) -> None:
        """Half the effective budget consumed → exactly 50 %."""
        # effective = 128,000 − 64,000 − 20,000 = 44,000; half = 22,000
        result = compute_effective_context_pct(22_000, 128_000, 64_000)
        assert result == 50.0

    # ── NULL max_output: graceful fallback ───────────────────────────────────

    def test_null_max_output_returns_raw_window_pct(self) -> None:
        """max_output_tokens=None → raw-window percentage (no crash, no None)."""
        result = compute_effective_context_pct(50_000, 100_000, None)
        assert result == 50.0

    def test_null_max_output_does_not_raise(self) -> None:
        """max_output_tokens=None must not raise TypeError / AttributeError."""
        result = compute_effective_context_pct(75_000, 200_000, None)
        assert isinstance(result, float)
        assert result == pytest.approx(37.5)

    def test_null_context_window_returns_none(self) -> None:
        """context_window=None → None (degrades gracefully, no division error)."""
        assert compute_effective_context_pct(50_000, None, 50_000) is None

    def test_zero_context_window_returns_none(self) -> None:
        """Verifies that zero context window returns none."""
        assert compute_effective_context_pct(50_000, 0, 50_000) is None

    def test_negative_context_window_returns_none(self) -> None:
        """Verifies that negative context window returns none."""
        assert compute_effective_context_pct(50_000, -1, 50_000) is None

    # ── Safety buffer shifts the effective budget ─────────────────────────────

    def test_safety_buffer_is_subtracted_from_effective_budget(self) -> None:
        """Changing the safety_buffer changes the effective budget.

        Default buffer (20,000): effective = 100,000 − 50,000 − 20,000 = 30,000
        → 15,000 used → 15,000/30,000*100 = 50 %
        Custom buffer (10,000): effective = 100,000 − 50,000 − 10,000 = 40,000
        → 15,000 used → 15,000/40,000*100 = 37.5 %
        """
        result_default = compute_effective_context_pct(15_000, 100_000, 50_000)
        result_custom = compute_effective_context_pct(15_000, 100_000, 50_000, safety_buffer=10_000)
        assert result_default == 50.0, f"Expected 50% with default buffer, got {result_default}"
        assert result_custom == 37.5, f"Expected 37.5% with 10K buffer, got {result_custom}"

    def test_safety_buffer_constant_is_20_000(self) -> None:
        """DEFAULT_SAFETY_BUFFER_TOKENS is the 20,000-token opencode convention."""
        assert DEFAULT_SAFETY_BUFFER_TOKENS == 20_000

    def test_larger_buffer_reduces_effective_budget_increases_pct(self) -> None:
        """A larger safety buffer leaves less room, raising the percentage."""
        result_20k = compute_effective_context_pct(30_000, 100_000, 50_000, safety_buffer=20_000)
        result_5k = compute_effective_context_pct(30_000, 100_000, 50_000, safety_buffer=5_000)
        assert result_20k is not None
        assert result_5k is not None
        assert result_20k > result_5k, (
            "Larger buffer → smaller effective budget → same used_tokens → higher pct"
        )

    # ── Effective ceiling behaviour ──────────────────────────────────────────

    def test_at_effective_ceiling_returns_100_pct(self) -> None:
        """used_tokens == effective_budget → 100.0 % (exact equality, no overshoot)."""
        # effective = 100,000 − 50,000 − 20,000 = 30,000
        result = compute_effective_context_pct(30_000, 100_000, 50_000)
        assert result == 100.0

    def test_over_effective_ceiling_returns_over_100_pct(self) -> None:
        """used_tokens > effective_budget → >100 % (no clamping, unlike raw window)."""
        result = compute_effective_context_pct(35_000, 100_000, 50_000)
        assert result is not None
        assert result > 100.0
        assert result == pytest.approx(116.6667)

    def test_raw_window_caps_at_100_contrast_with_effective_can_exceed(self) -> None:
        """Raw window meter clamps to 100 %; effective-budget meter can exceed it.

        At 205K input on a 204,800-window model (131K output reservation):
        - Raw window pct = 131,072/204,800*100 = 64 % (clamped to 100 pre-fix)
        - Effective pct  = 131,072/(204,800-131,072-20,000)*100 ≈ 244 % (no clamp)

        This contrast proves the fix is active: the effective meter never clamps.
        """
        raw = compute_effective_context_pct(131_072, 204_800, None)
        effective = compute_effective_context_pct(131_072, 204_800, 131_072)
        assert raw is not None
        assert effective is not None
        # Raw meter would clamp to 100 but we test without clamp for NULL case
        assert effective > raw, "Effective pct must exceed raw pct for large max_output"

    # ── Effective budget edge cases ──────────────────────────────────────────

    def test_effective_budget_zero_returns_none(self) -> None:
        """effective_budget == 0 → None (defensive guard, no division by zero)."""
        # 100,000 − 80,000 − 20,000 = 0
        result = compute_effective_context_pct(50_000, 100_000, 80_000)
        assert result is None

    def test_effective_budget_negative_returns_none(self) -> None:
        """effective_budget < 0 → None (defensive guard)."""
        # 100,000 − 90,000 − 20,000 = −10,000
        result = compute_effective_context_pct(50_000, 100_000, 90_000)
        assert result is None

    def test_negative_used_tokens_returns_zero_pct(self) -> None:
        """Negative used_tokens → 0.0 % (never a negative percentage)."""
        result = compute_effective_context_pct(-1000, 100_000, 50_000)
        assert result == 0.0

    def test_zero_used_tokens_returns_zero_pct(self) -> None:
        """Zero used_tokens → 0.0 %."""
        result = compute_effective_context_pct(0, 100_000, 50_000)
        assert result == 0.0

    # ── Type coercion ────────────────────────────────────────────────────────

    def test_float_inputs_coerced(self) -> None:
        """Float context_window / max_output_tokens are coerced to float."""
        result = compute_effective_context_pct(15_000, 100_000.0, 50_000.0)
        assert result == 50.0

    def test_float_safety_buffer(self) -> None:
        """Float safety_buffer is coerced to float (sub-unit precision preserved)."""
        # effective = 100,000 − 50,000 − 10,000.5 = 39,999.5
        # pct = 15,000/39,999.5*100 ≈ 37.50047...
        result = compute_effective_context_pct(15_000, 100_000, 50_000, safety_buffer=10_000.5)
        assert result is not None
        assert 37.4 < result < 37.6  # ~37.5 % with sub-unit precision

    # ── Return type ──────────────────────────────────────────────────────────

    def test_returns_float_not_int(self) -> None:
        """Percentage is always a float (even when it computes to a whole number)."""
        # effective = 200,000 − 100,000 − 20,000 = 80,000; pct = 50,000/80,000*100 = 62.5
        result = compute_effective_context_pct(50_000, 200_000, 100_000)
        assert isinstance(result, float)
        assert result == 62.5
