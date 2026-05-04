"""Unit tests for I-00062 — _agent_subprocess_env snapshot + strip.

Tests the three-layer defense:
- Layer 1: snapshot of daemon's IW_CORE_DB_* into IW_CORE_ORCH_DB_* BEFORE strip
- Layer 1: strip of IW_CORE_DB_* so agents never inherit orch creds
- Layer 1: setdefault preserves browser-env injection
- Layer 1: extra= dict wins over strip (browser-verification path)
- Layer 2 (indirect): IW_CORE_AGENT_CONTEXT always armed

TDD expectation:
  - test_strips_inherited_orch_db_vars          → FAILS pre-fix, PASSES post-fix
  - test_snapshots_orch_creds_before_strip      → FAILS pre-fix, PASSES post-fix
  - test_snapshot_does_not_overwrite_existing   → PASSES pre-fix (setdefault), PASSES post-fix
  - test_orch_db_url_vars_not_stripped          → PASSES pre+post
  - test_agent_context_flag_armed               → PASSES pre+post
  - test_extra_overrides_strip                  → PASSES pre+post (merge order unchanged)
  - test_bv_env_overrides_strip                 → PASSES pre+post (AC6)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.daemon.batch_manager import _agent_subprocess_env

if TYPE_CHECKING:
    import pytest


class TestAgentSubprocessEnvDoesNotLeakOrchDB:
    """I-00062 reproduction: ensure orch DB connection vars do not leak
    from the daemon's env into the agent subprocess env."""

    def test_strips_inherited_orch_db_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pre-fix: FAILS — os.environ.copy() leaks 5433.
        Post-fix: PASSES — _agent_subprocess_env strips IW_CORE_DB_*."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")  # noqa: S105
        monkeypatch.delenv("IW_CORE_ORCH_DB_PORT", raising=False)

        env = _agent_subprocess_env()

        assert "IW_CORE_DB_HOST" not in env
        assert "IW_CORE_DB_PORT" not in env
        assert "IW_CORE_DB_NAME" not in env
        assert "IW_CORE_DB_USER" not in env
        assert "IW_CORE_DB_PASSWORD" not in env

    def test_snapshots_orch_creds_before_strip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """I-00062 Layer 1: BEFORE stripping IW_CORE_DB_*, snapshot the
        daemon's values into IW_CORE_ORCH_DB_* so the Layer 3 guard has
        a known orch reference. This is what makes the guard fire for
        legacy worktrees whose .env still mirrors main."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")  # noqa: S105
        monkeypatch.delenv("IW_CORE_ORCH_DB_HOST", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_PORT", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_NAME", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_USER", raising=False)
        monkeypatch.delenv("IW_CORE_ORCH_DB_PASSWORD", raising=False)

        env = _agent_subprocess_env()

        assert env["IW_CORE_ORCH_DB_HOST"] == "localhost"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
        assert env["IW_CORE_ORCH_DB_NAME"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_USER"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_PASSWORD"] == "iw_orch_dev"  # noqa: S105

    def test_snapshot_does_not_overwrite_existing_orch_creds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If IW_CORE_ORCH_DB_* is already set (e.g. by browser_env),
        the snapshot must use setdefault and NOT clobber."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")  # noqa: S105
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", "preset-host")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")

        env = _agent_subprocess_env()

        assert env["IW_CORE_ORCH_DB_HOST"] == "preset-host"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"

    def test_orch_db_url_vars_not_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_ORCH_DB_* is the legitimate operator path for
        iw step-done / step-fail / step-start. Must NOT be stripped."""
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_ORCH_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PASSWORD", "iw_orch_dev")  # noqa: S105

        env = _agent_subprocess_env()

        # These must survive — they are the operator's channel
        assert env["IW_CORE_ORCH_DB_HOST"] == "localhost"
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
        assert env["IW_CORE_ORCH_DB_NAME"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_USER"] == "iw_orch"
        assert env["IW_CORE_ORCH_DB_PASSWORD"] == "iw_orch_dev"  # noqa: S105

    def test_agent_context_flag_armed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_AGENT_CONTEXT=true must be set after the strip."""
        env = _agent_subprocess_env()
        assert env["IW_CORE_AGENT_CONTEXT"] == "true"

    def test_extra_overrides_strip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Browser-verification path injects IW_CORE_DB_* via extra={}.
        Verify the merge order: extra wins over the strip."""
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        env = _agent_subprocess_env(
            extra={"IW_CORE_DB_PORT": "39999", "IW_CORE_DB_HOST": "e2e-host"}
        )
        assert env["IW_CORE_DB_PORT"] == "39999"
        assert env["IW_CORE_DB_HOST"] == "e2e-host"


class TestBrowserVerificationEnvStillWins:
    """AC6: existing browser-verification env injection (extra={...})
    still wins after I-00062 snapshot + strip."""

    def test_bv_env_overrides_strip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bv-style call to _agent_subprocess_env(extra={'IW_CORE_DB_PORT':
        '39999', ...}) returns the e2e port, not stripped, not 5433."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")  # noqa: S105

        bv = {
            "IW_CORE_DB_HOST": "e2e-host",
            "IW_CORE_DB_PORT": "39999",
            "IW_CORE_DB_NAME": "iw_orch_e2e",
            "IW_CORE_DB_USER": "e2e_user",
            "IW_CORE_DB_PASSWORD": "e2e_pw",  # noqa: S105
        }
        env = _agent_subprocess_env(extra=bv)

        # Browser-verification env wins (AC6)
        assert env["IW_CORE_DB_HOST"] == "e2e-host"
        assert env["IW_CORE_DB_PORT"] == "39999"
        assert env["IW_CORE_DB_NAME"] == "iw_orch_e2e"
        assert env["IW_CORE_DB_USER"] == "e2e_user"
        assert env["IW_CORE_DB_PASSWORD"] == "e2e_pw"  # noqa: S105
        # Snapshot still happens — guard reference is preserved.
        assert env["IW_CORE_ORCH_DB_PORT"] == "5433"
