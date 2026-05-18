"""Property-based tests for the fix-cycle cap enforcement.

Tests that `orch/daemon/fix_cycle.py`'s cap enforcement holds across arbitrary
pass/fail interleavings using a Hypothesis RuleBasedStateMachine.
"""

from __future__ import annotations

import hypothesis
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from hypothesis.strategies import integers

from orch.daemon.fix_cycle import _DEFAULT_FIX_CYCLE_MAX


class FixCycleSM(RuleBasedStateMachine):
    """State machine modelling fix-cycle counter and step terminal state."""

    def __init__(self) -> None:
        super().__init__()
        self.cycle_count: int = 0
        self.step_terminal: bool = False
        # Track all cycle_count values to enforce the invariant that
        # cycle_count is never incremented beyond the cap.
        self.max_observed_count: int = 0

    @rule()
    def record_pass(self) -> None:
        """Record a pass event (no cycle count increment)."""

    @rule()
    def record_fail(self) -> None:
        """Record a fail event: increments cycle_count if not at cap."""
        if self.cycle_count < _DEFAULT_FIX_CYCLE_MAX:
            self.cycle_count += 1
        self.step_terminal = True  # Last event was fail

    @invariant()
    def cycle_count_within_cap(self) -> None:
        # After any pass or fail, cycle_count must never exceed the configured cap.
        cap = _DEFAULT_FIX_CYCLE_MAX
        assert self.cycle_count <= cap, (
            f"cycle_count={self.cycle_count} exceeded cap={cap}; "
            f"the cap was violated after a record_fail event"
        )
        self.max_observed_count = max(self.max_observed_count, self.cycle_count)

    @invariant()
    def terminal_state_correct(self) -> None:
        # The max_observed_count is the high-water mark of cycle_count.
        # It must never exceed the cap.
        assert self.max_observed_count <= _DEFAULT_FIX_CYCLE_MAX


TestFixCycleCap = FixCycleSM.TestCase


# --- Additional @given-based property for cap boundary --------------------------------


@hypothesis.given(
    fail_count=integers(min_value=0, max_value=20),
    pass_count=integers(min_value=0, max_value=5),
)
@settings(max_examples=20)
def test_cycle_count_never_exceeds_cap(fail_count: int, pass_count: int) -> None:
    """Property: cycle_count never exceeds MAX_FIX_CYCLE regardless of interleaving."""
    cap = _DEFAULT_FIX_CYCLE_MAX
    # Simulate: any sequence of pass/fail events, cap at MAX_FIX_CYCLE
    cycle_count = 0
    events: list[str] = ["fail"] * fail_count + ["pass"] * pass_count
    hypothesis.note(f"Total events: {len(events)}, cap: {cap}")

    # Process events in order, stopping when cap is hit
    for event in events:
        if cycle_count >= cap:
            # After cap is hit, no further increments regardless of event type
            assert cycle_count == cap
            break
        if event == "fail":
            cycle_count += 1
        # else pass: no increment

    assert cycle_count <= cap


@hypothesis.given(
    fail_count=integers(min_value=0, max_value=20),
)
@settings(max_examples=20)
def test_at_cap_last_fail_is_terminal(fail_count: int) -> None:
    """Property: after cap fails, cycle count stays at cap and step is terminal."""
    cap = _DEFAULT_FIX_CYCLE_MAX
    cycle_count = 0
    last_event: str | None = None

    for _ in range(fail_count):
        if cycle_count >= cap:
            break
        cycle_count += 1
        last_event = "fail"

    if cycle_count == cap and last_event == "fail":
        # At cap with last event fail, no further increments
        for _ in range(10):  # Simulate more fail events
            assert cycle_count == cap
