"""Agent-context env-var handling tests (CR-00075 AC4).

``IW_CORE_AGENT_CONTEXT=true`` is the flag the daemon injects into every agent
worktree subprocess. It marks the process as untrusted: operator-only actions
(applying a migration, connecting to the live orch DB) must be refused.

This module organises and extends the agent-context guard coverage that lives
piecemeal in ``tests/integration/test_agent_migrate_guard.py`` — it does NOT
replace that file.

It asserts three things:
  1. Operator-only commands are blocked when the flag is set — both the
     ``iw migrations apply`` CLI (exit code 2) and the engine-creation guard
     (raises ``LiveDbConnectionRefusedError``). The refusal is *explicit*: a
     non-zero exit / a raised exception with a remediation message, never a
     silent no-op.
  2. The refusal signal is an **exact** string match on ``"true"``. A capital
     ``"True"``, the integer-string ``"1"``, and the empty string are NOT
     treated as the refusal signal. The daemon always injects exactly
     ``"true"`` (see ``orch/daemon/batch_manager._build_agent_env``), so the
     exact-match is safe in practice — and an agent cannot *weaken* the
     restriction by tampering, because the guard re-reads ``os.environ`` live
     on every call (point 3) and an agent that could set env vars at all
     could simply unset the flag; the guard is a daemon-side discipline, not
     an adversarial sandbox.
  3. The guard re-reads the live env var on every call — it never caches a
     stale value. Flipping the flag within a single test invocation flips the
     guard's behaviour.

Safety: no test connects to anything. A live-DB URL is simulated via env-var
injection; ``create_engine`` never opens a socket. The CLI test is refused by
the guard before any DB connection is attempted.

Genuine vulnerability handling (CR-00075 AC5): if the guard accepts an
unexpected value as a bypass signal, or an operator-only command is NOT
blocked, write the test as the failing reproduction, mark
``@pytest.mark.xfail(strict=False, reason="I-NNNNN: ...")``, file a
high-priority security Incident, and flag a SECURITY BLOCKER in the step
report. Never fix production code in this CR.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Synthetic "live DB" coordinates — never a real host (RFC 2606 .invalid TLD).
_LIVE_HOST = "synthetic-live-orch-db.invalid"
_LIVE_PORT = 5433
_LIVE_URL = f"postgresql+psycopg://orch:orch@{_LIVE_HOST}:{_LIVE_PORT}/iw_orch"

# Repo root: this file is tests/integration/security/<file> → parents[3].
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _simulate_live_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point IW_CORE_DB_HOST/PORT at the synthetic live DB and clear the
    test/operator/daemon flags so the AGENT_CONTEXT branch is reached.

    Setup-only helper — injects no assertions; each test carries its own.
    """
    monkeypatch.setenv("IW_CORE_DB_HOST", _LIVE_HOST)
    monkeypatch.setenv("IW_CORE_DB_PORT", str(_LIVE_PORT))
    monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)


# ---------------------------------------------------------------------------
# 1. Operator-only commands are blocked under IW_CORE_AGENT_CONTEXT=true
# ---------------------------------------------------------------------------


class TestAgentContextBlocksOperatorCommands:
    """An agent-context process cannot run operator-only actions."""

    @pytest.mark.integration
    def test_agent_context_blocks_iw_migrations_apply(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`iw migrations apply --i-am-operator` exits 2 (refused) under
        IW_CORE_AGENT_CONTEXT=true, and the refusal names the agent context.

        The non-zero exit code is the behavioural signal; the substring check
        confirms the refusal is the agent guard and not an unrelated failure.
        """
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

        result = subprocess.run(
            ["uv", "run", "iw", "migrations", "apply", "--i-am-operator"],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=120,
        )

        assert result.returncode == 2, (
            f"Expected exit 2 (agent blocked); got {result.returncode}.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "agent" in combined, f"Refusal output must name the agent context; got {combined!r}"

    def test_agent_context_refusal_is_explicit_with_remediation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """safe_create_engine in agent context raises an explicit refusal — a
        message that names IW_CORE_AGENT_CONTEXT and a remediation path — not a
        silent no-op or a bare exception."""
        _simulate_live_db_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        with pytest.raises(
            ldbg.LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT"
        ) as exc_info:
            ldbg.safe_create_engine(_LIVE_URL)

        message = str(exc_info.value)
        assert message.startswith("Connection to live orch DB refused")
        assert "Remediation" in message


# ---------------------------------------------------------------------------
# 2. The refusal signal is an exact "true" — non-"true" values do not block
# ---------------------------------------------------------------------------


class TestAgentContextRefusalSignalIsExactMatch:
    """IW_CORE_AGENT_CONTEXT is honoured only as the exact string "true".

    These tests document the guard's contract: the daemon always injects
    exactly "true", so non-"true" values are simply "not in agent context".
    Each test reaches a behavioural assert (an engine is built) — if a
    non-"true" value were wrongly treated as the refusal signal,
    ``safe_create_engine`` would raise and the test would fail.
    """

    def test_lowercase_true_is_the_refusal_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The exact string "true" triggers the refusal — guard raises."""
        _simulate_live_db_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT"):
            ldbg.safe_create_engine(_LIVE_URL)

    def test_capital_true_is_not_the_refusal_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ "True" (capital T) is not the exact signal — guard does not raise."""
        _simulate_live_db_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "True")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()

    def test_integer_one_is_not_the_refusal_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ "1" is not the exact string "true" — guard does not raise."""
        _simulate_live_db_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "1")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()

    def test_empty_string_is_not_the_refusal_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ "" (empty string) is not the exact signal — guard does not raise."""
        _simulate_live_db_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# 3. The guard re-reads the live env var — it never caches a stale value
# ---------------------------------------------------------------------------


class TestAgentContextGuardReReadsLiveEnv:
    """The guard reads os.environ on every call — no stale caching."""

    def test_guard_rereads_env_within_a_single_invocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Set the flag → guard raises; unset it within the same test → guard
        allows. Proves the guard re-evaluates the live env var each call rather
        than caching the value seen at import or first use."""
        _simulate_live_db_env(monkeypatch)
        from orch.db import live_db_guard as ldbg

        # Phase 1 — flag set: the guard refuses.
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT"):
            ldbg.safe_create_engine(_LIVE_URL)

        # Phase 2 — flag removed in the SAME invocation: the guard now allows.
        monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()
