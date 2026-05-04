"""I-00062 AC3: orch.config refuses to resolve to orch port in agent context.

The fail-fast guard in get_db_url() raises RuntimeError when:
  - IW_CORE_AGENT_CONTEXT=true  AND
  - IW_CORE_ORCH_DB_PORT is set  AND
  - IW_CORE_DB_PORT == IW_CORE_ORCH_DB_PORT

get_orch_db_url() does NOT apply the guard — it is the legitimate operator
channel that must reach 5433 even in agent context.

TDD expectation:
  - test_agent_context_with_orch_port_raises     → FAILS pre-fix, PASSES post-fix
  - test_agent_context_with_worktree_port_passes → PASSES pre+post
  - test_operator_context_with_orch_port_passes  → PASSES pre+post
  - test_get_orch_db_url_does_not_apply_guard    → PASSES pre+post
  - test_runbook_string_in_error_message         → PASSES post-fix (guard has msg)
  - test_legacy_worktree_with_inherited_orch_port_raises → FAILS pre-fix twice
    (no snapshot, no guard), PASSES post-fix (both layers fire)
"""

from __future__ import annotations

import pytest

# Import config fresh per-test so dotenv loading happens with the patched env.
# NEVER use importlib.reload — use monkeypatch.setenv/delenv only.


class TestAgentContextFailFast:
    def test_agent_context_with_orch_port_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Agent context + DB port matches ORCH port → RuntimeError named I-00062.

        Pre-fix: no guard → silently returns 5433 URL.
        Post-fix: guard fires with runbook reference.
        """
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        # Import inside test to pick up the patched env
        from orch import config

        with pytest.raises(RuntimeError, match="I-00062"):
            config.get_db_url()

    def test_agent_context_with_worktree_port_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Agent context + DB port differs from ORCH port → allowed (per-worktree DB).

        The whole point of per-worktree DB is that it runs on a different port.
        Guard must not fire when ports differ.
        """
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "36216")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch")

        from orch import config

        url = config.get_db_url()
        assert "36216" in url
        assert "5433" not in url

    def test_operator_context_with_orch_port_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Operator (no IW_CORE_AGENT_CONTEXT) is unaffected — must reach 5433."""
        monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        from orch import config

        url = config.get_db_url()
        assert "5433" in url

    def test_get_orch_db_url_does_not_apply_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_orch_db_url is the legitimate operator channel — must reach 5433
        even in agent context. The guard must NOT apply here."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        from orch import config

        url = config.get_orch_db_url()
        assert "5433" in url

    def test_runbook_string_in_error_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When guard fires, the error message must reference I-00062 runbook."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        from orch import config

        with pytest.raises(RuntimeError) as exc_info:
            config.get_db_url()
        assert "I-00062" in str(exc_info.value)

    def test_legacy_worktree_with_inherited_orch_port_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end semantic: legacy (no-compose) worktree whose .env mirrors
        main's IW_CORE_DB_PORT=5433.

        Pre-fix: no snapshot in _agent_subprocess_env, no guard in get_db_url
                 → silent leak to 5433. Test FAILS because no exception raised.
        Post-fix: _agent_subprocess_env snapshots ORCH_DB_PORT=5433;
                  load_dotenv from .env sets DB_PORT=5433;
                  guard fires with RuntimeError.
        """
        # Simulate the post-_agent_subprocess_env state: IW_CORE_ORCH_DB_PORT
        # is set (from snapshot) but IW_CORE_DB_PORT is 5433 (from legacy .env).
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        from orch import config

        with pytest.raises(RuntimeError, match="I-00062"):
            config.get_db_url()

    def test_guard_does_not_fire_when_orch_port_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If IW_CORE_ORCH_DB_PORT is not set, guard cannot compare — must pass."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        monkeypatch.delenv("IW_CORE_ORCH_DB_PORT", raising=False)
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

        from orch import config

        # No orch port to compare against — guard short-circuits, URL is returned
        url = config.get_db_url()
        assert "5433" in url
