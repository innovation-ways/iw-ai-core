"""I-00112 — Keep-Alive Scheduler success contract regression tests (unit layer).

The pre-fix poller logged status='success' whenever ``claude`` exited 0, even when
no API call was actually made (empty stdout, near-zero elapsed). These tests
mock ``subprocess.run`` at the boundary so the success-contract logic itself is
exercised — not the ``fire_claude`` wrapper.

Why ``subprocess.run`` (not ``fire_claude``): mocking at the wrapper re-introduces
the bug class's blind spot. The whole point of the I-00112 fix is the
(returncode, stdout, elapsed_ms) → is_success contract inside ``FireResult``;
only mocking at the kernel boundary exercises it.

The DB-backed tests (`test_i00112_poller_persists_captured_fields`,
`test_i00112_poller_logs_failed_when_contract_violated`) live in
``tests/integration/test_keep_alive_poller_success_contract.py`` because they
require the testcontainer-backed ``db_session`` fixture and a real
``KeepAlivePoller().poll()`` round-trip.

Ref: I-00112 (design doc § Test to Reproduce).
"""

from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from orch.keep_alive_service import fire_claude

# ---------------------------------------------------------------------------
# Reproduction: silent no-op (rc=0, empty stdout, ~0 ms) must NOT be 'success'
# ---------------------------------------------------------------------------


def test_i00112_silent_no_op_is_not_success_empty_stdout() -> None:
    """Reproduction: rc=0 + empty stdout MUST be classified failed, not success."""
    fake = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with (
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        patch("orch.keep_alive_service.time_mod.perf_counter", side_effect=[0.0, 0.001]),
    ):
        result = fire_claude("hi", "claude-sonnet-4-6")
    # Post-fix: result is a FireResult; success contract requires non-empty stdout
    assert result.is_success is False, (
        "rc=0 with empty stdout must NOT be classified success "
        "(I-00112: silent no-op is the whole bug)"
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.elapsed_ms < 500


def test_i00112_silent_no_op_is_not_success_fast_elapsed() -> None:
    """rc=0 + non-empty stdout but <500ms elapsed MUST also be classified failed."""
    fake = CompletedProcess(args=[], returncode=0, stdout="OK", stderr="")
    with (
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        patch("orch.keep_alive_service.time_mod.perf_counter", side_effect=[0.0, 0.020]),
    ):
        result = fire_claude("hi", "claude-sonnet-4-6")
    assert result.is_success is False, (
        "elapsed=20ms is below the 500ms floor — a real Sonnet round-trip "
        "cannot complete that fast; classify as failed (I-00112)"
    )


def test_i00112_real_round_trip_is_success() -> None:
    """rc=0 + non-empty stdout + elapsed>=500ms MUST be classified success."""
    fake = CompletedProcess(args=[], returncode=0, stdout="OK", stderr="")
    with (
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        patch("orch.keep_alive_service.time_mod.perf_counter", side_effect=[0.0, 3.5]),
    ):
        result = fire_claude("hi", "claude-sonnet-4-6")
    assert result.is_success is True
    assert result.elapsed_ms == 3500
    assert result.stdout == "OK"


def test_i00112_nonzero_returncode_is_failure() -> None:
    """rc!=0 is always failure, regardless of stdout."""
    fake = CompletedProcess(args=[], returncode=1, stdout="anything", stderr="boom")
    with (
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        patch("orch.keep_alive_service.time_mod.perf_counter", side_effect=[0.0, 3.0]),
    ):
        result = fire_claude("hi", "claude-sonnet-4-6")
    assert result.is_success is False
    assert result.returncode == 1
    assert result.stderr == "boom"
