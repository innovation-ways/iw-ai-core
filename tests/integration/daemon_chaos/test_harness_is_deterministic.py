"""Self-tests verifying that ChaosDaemonHarness itself is deterministic and idempotent."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.integration.daemon_chaos.conftest import validate_chaos_daemon_request


def test_harness_is_deterministic(chaos_daemon) -> None:
    """Verifies that repeated setup/teardown cycles produce identical cycle counts of 1."""
    observed_cycles: list[int] = []

    for _ in range(10):
        chaos_daemon.teardown()
        chaos_daemon.setup()
        chaos_daemon.inject_fix_cycle_always_fails()
        chaos_daemon.advance_one_cycle()

        assert chaos_daemon.hooks_triggered.get("fix_cycle_always_fails") is True
        observed_cycles.append(chaos_daemon.cycles_advanced)

    assert observed_cycles == [1] * 10


def test_fix_cycle_injection_is_idempotent(chaos_daemon) -> None:
    """Verifies that injecting the same hook twice does not double-trigger or corrupt state."""
    chaos_daemon.inject_fix_cycle_always_fails()
    chaos_daemon.inject_fix_cycle_always_fails()
    chaos_daemon.advance_one_cycle()

    assert chaos_daemon.cycles_advanced == 1
    assert chaos_daemon.hooks_triggered.get("fix_cycle_always_fails") is True


def test_hook_armed_without_poll_cycle_is_teardown_safe(chaos_daemon) -> None:
    """Verifies that arming a hook without running a cycle leaves clean state after teardown."""
    chaos_daemon.inject_fix_cycle_always_fails()
    chaos_daemon.teardown()
    chaos_daemon.setup()

    assert chaos_daemon.hooks_armed == {}
    assert chaos_daemon.hooks_triggered == {}
    assert chaos_daemon.get_fix_cycle_count() == 0


def test_two_scenarios_back_to_back_restore_clean_state(chaos_daemon) -> None:
    """Verifies that running two different scenarios back-to-back does not bleed state."""
    chaos_daemon.inject_worktree_setup_failure_after_clone()
    chaos_daemon.teardown()
    chaos_daemon.setup()

    chaos_daemon.inject_squash_merge_conflict_on_main()
    chaos_daemon.advance_one_cycle()

    assert chaos_daemon.hooks_armed == {"squash_merge_conflict_on_main": True}
    assert chaos_daemon.hooks_triggered.get("squash_merge_conflict_on_main") is True


def test_harness_without_db_session_fixture_errors_loudly() -> None:
    """Verifies that validate_chaos_daemon_request raises RuntimeError when db_session is absent."""
    request = SimpleNamespace(fixturenames=["test_project"])
    with pytest.raises(
        RuntimeError, match="chaos_daemon requires testcontainer-backed db_session fixture"
    ):
        validate_chaos_daemon_request(request)
