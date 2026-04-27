"""Unit tests for orch.db.live_db_guard — the connection-layer chokepoint.

These tests verify the guard's logic WITHOUT any database connection.
Uses monkeypatch to control env vars and make_url to construct test URLs.

Covers:
- R1 (tests/unit/test_live_db_guard.py): all 13 test cases for is_live_db_url
  and assert_engine_url_allowed across test/agent/daemon/operator contexts.
- I-00041 follow-up: iw_cli_orch_bridge — narrowly-scoped allow context for
  the CLI's own engine creation (resolves the agent-CLI catch-22).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from orch.db import live_db_guard as guard_module
from orch.db.live_db_guard import (
    LiveDbConnectionRefused,
    assert_engine_url_allowed,
    is_live_db_url,
    iw_cli_orch_bridge,
)

# ---------------------------------------------------------------------------
# R1 unit tests — is_live_db_url
# ---------------------------------------------------------------------------


def test_is_live_db_url_matches_by_host_port_when_no_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host:port match → is_live_db_url returns True."""
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = is_live_db_url("postgresql://x:y@localhost:5433/iw_orch")
    assert result is True


def test_is_live_db_url_rejects_different_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same host, different port → False."""
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = is_live_db_url("postgresql://x:y@localhost:55432/iw_orch")
    assert result is False


def test_is_live_db_url_rejects_different_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different host, same port → False."""
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = is_live_db_url("postgresql://x:y@otherhost:5433/iw_orch")
    assert result is False


def test_is_live_db_url_fails_open_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed URL → fail-open (returns False, does NOT raise)."""
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = is_live_db_url("not-a-url")
    assert result is False


def test_is_live_db_url_fails_open_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No IW_CORE_DB_* vars → implementation uses defaults (localhost:5433).

    The implementation falls back to defaults when env vars are unset,
    so only URLs that DON'T match the defaults fail-open.
    """
    monkeypatch.delenv("IW_CORE_DB_HOST", raising=False)
    monkeypatch.delenv("IW_CORE_DB_PORT", raising=False)
    result = is_live_db_url("postgresql://x:y@otherhost:5433/iw_orch")
    assert result is False


# ---------------------------------------------------------------------------
# R1 unit tests — assert_engine_url_allowed (refused contexts)
# ---------------------------------------------------------------------------


def test_assert_allowed_refuses_under_test_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_TEST_CONTEXT=true + live URL → raises LiveDbConnectionRefused."""
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    with pytest.raises(LiveDbConnectionRefused) as exc_info:
        assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
    msg = str(exc_info.value)
    assert "host:port" in msg, f"missing host:port in refusal: {msg!r}"
    assert "IW_CORE_TEST_CONTEXT" in msg, f"missing flag name in refusal: {msg!r}"
    assert "iw migrations apply --i-am-operator" in msg, f"missing remediation hint: {msg!r}"


def test_assert_allowed_refuses_under_agent_context_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_AGENT_CONTEXT=true (deprecated) → still raises, with flag name in message."""
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    with pytest.raises(LiveDbConnectionRefused) as exc_info:
        assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
    msg = str(exc_info.value)
    assert "host:port" in msg, f"missing host:port in refusal: {msg!r}"
    assert "IW_CORE_AGENT_CONTEXT" in msg, f"missing flag name in refusal: {msg!r}"


# ---------------------------------------------------------------------------
# R1 unit tests — assert_engine_url_allowed (allowed contexts)
# ---------------------------------------------------------------------------


def test_assert_allowed_passes_under_operator_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_OPERATOR_APPLY=true → live URL is allowed."""
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    assert assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch") is None


def test_assert_allowed_passes_under_daemon_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_DAEMON_CONTEXT=true → live URL is allowed."""
    monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    assert assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch") is None


def test_assert_allowed_passes_for_non_live_url_under_test_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-live URL → guard short-circuits before context check → allowed."""
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = assert_engine_url_allowed("postgresql://x:y@localhost:55432/test")
    assert result is None


def test_assert_allowed_default_allow_when_no_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No context flags → default-allow (backwards compatibility for ad-hoc scripts)."""
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
    assert result is None


def test_operator_flag_wins_over_test_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both IW_CORE_OPERATOR_APPLY and IW_CORE_TEST_CONTEXT set → operator wins."""
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    result = assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
    assert result is None


# ---------------------------------------------------------------------------
# R1 unit tests — safe_create_engine integration
# ---------------------------------------------------------------------------


def test_safe_create_engine_calls_guard_before_creating_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """safe_create_engine raises without calling create_engine when context is refused.

    Verifies the guard short-circuits before engine creation by patching
    sqlalchemy.create_engine and confirming it's never called when the
    guard would refuse the URL.
    """
    from orch.db.live_db_guard import safe_create_engine as sce

    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")

    with patch("sqlalchemy.create_engine") as mock_create_engine:
        with pytest.raises(LiveDbConnectionRefused):
            sce("postgresql://x:y@localhost:5433/iw_orch")
        mock_create_engine.assert_not_called()


# ---------------------------------------------------------------------------
# I-00041 follow-up — iw_cli_orch_bridge
# ---------------------------------------------------------------------------


def test_iw_cli_orch_bridge_allows_live_url_under_agent_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_AGENT_CONTEXT=true + bridge active → live URL is allowed.

    Resolves the catch-22 where the iw CLI (the legitimate channel for
    agents to record orchestration state) was refused by its own guard.
    """
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")

    with iw_cli_orch_bridge():
        result = assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
        assert result is None


def test_iw_cli_orch_bridge_does_not_bypass_test_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IW_CORE_TEST_CONTEXT=true + bridge active → STILL refused.

    Defense-in-depth: a CliRunner-driven test invoking the CLI in-process
    must NOT be able to reach the live DB through the bridge. The test
    context refusal fires before the bridge is consulted.
    """
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")

    with iw_cli_orch_bridge():
        with pytest.raises(LiveDbConnectionRefused) as exc_info:
            assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
        assert "IW_CORE_TEST_CONTEXT" in str(exc_info.value)


def test_iw_cli_orch_bridge_resets_on_normal_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bridge flag resets to False after exiting the context manager."""
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")

    assert guard_module._iw_cli_orch_bridge_active is False
    with iw_cli_orch_bridge():
        assert guard_module._iw_cli_orch_bridge_active is True
    assert guard_module._iw_cli_orch_bridge_active is False

    # Post-exit, the agent-context refusal must fire again.
    with pytest.raises(LiveDbConnectionRefused) as exc_info:
        assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")
    assert "IW_CORE_AGENT_CONTEXT" in str(exc_info.value)


def test_iw_cli_orch_bridge_resets_on_exception() -> None:
    """Bridge flag resets to False even when the body raises.

    The mid-flight state (flag is True inside the body) is covered by
    test_iw_cli_orch_bridge_resets_on_normal_exit; this test specifically
    verifies the try/finally cleanup path.
    """
    assert guard_module._iw_cli_orch_bridge_active is False

    def _enter_and_raise() -> None:
        with iw_cli_orch_bridge():
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _enter_and_raise()
    assert guard_module._iw_cli_orch_bridge_active is False


def test_iw_cli_orch_bridge_nested_restores_previous_state() -> None:
    """Nested bridge entry/exit restores the prior flag value, not False.

    This protects against accidental resets if the CLI ever re-enters its
    own group (e.g., a future composite command).
    """
    assert guard_module._iw_cli_orch_bridge_active is False
    with iw_cli_orch_bridge():
        assert guard_module._iw_cli_orch_bridge_active is True
        with iw_cli_orch_bridge():
            assert guard_module._iw_cli_orch_bridge_active is True
        # Outer context's flag must still be True after inner exits.
        assert guard_module._iw_cli_orch_bridge_active is True
    assert guard_module._iw_cli_orch_bridge_active is False
