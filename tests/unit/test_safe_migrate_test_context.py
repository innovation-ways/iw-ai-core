"""CR-00022 S17 R0: safe_migrate helpers must short-circuit under test context.

Without this guard, tests that mock safe_apply/safe_rollback at the
migration_pipeline boundary still leak into the live DB via
_write_migration_log / _acquire_migration_lock / _release_migration_lock,
which call get_db_url() directly and bypass the mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.safe_migrate import _is_test_context_active

if TYPE_CHECKING:
    import pytest


def test_test_context_active_when_only_test_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    assert _is_test_context_active() is True


def test_agent_context_active_when_agent_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
    assert _is_test_context_active() is True


def test_operator_opt_in_overrides_test_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    assert _is_test_context_active() is False


def test_daemon_opt_in_overrides_test_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    assert _is_test_context_active() is False


def test_operator_and_daemon_both_override_agent_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
    assert _is_test_context_active() is False


def test_write_migration_log_is_noop_under_test_context(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: assertion-scanner
    """The smoking gun: _write_migration_log must not touch live DB under test."""
    from orch.db import safe_migrate

    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)

    safe_migrate._write_migration_log(
        revision="test-revision-noop",
        direction="upgrade",
        phase="apply",
        batch_id=-99999,
        success=True,
        stdout_tail="",
        stderr_tail="",
        error_message=None,
    )


def test_acquire_migration_lock_is_noop_under_test_context(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: assertion-scanner
    """_acquire_migration_lock must not touch live DB under test."""
    from orch.db import safe_migrate

    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)

    safe_migrate._acquire_migration_lock(item="daemon")


def test_release_migration_lock_is_noop_under_test_context(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: assertion-scanner
    """_release_migration_lock must not touch live DB under test."""
    from orch.db import safe_migrate

    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)

    safe_migrate._release_migration_lock(item="daemon")
