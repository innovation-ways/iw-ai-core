"""Regression net for the live-DB write guard — the I-00041 class of outage.

The guard lives in ``orch.db.live_db_guard`` and is the single chokepoint for
SQLAlchemy engine creation in ``orch/``. It refuses to build an engine for a
URL that resolves to the live orchestration DB whenever the caller runs in a
*refused context* — pytest (``IW_CORE_TEST_CONTEXT``) or an agent worktree
(``IW_CORE_AGENT_CONTEXT``). Incident I-00041 shipped because nothing pinned
this behaviour; this module is that pin.

Safety — no test here connects to anything:
  * A "live DB" URL is *simulated* via env-var injection: ``IW_CORE_DB_HOST``
    and ``IW_CORE_DB_PORT`` are monkeypatched to a synthetic host:port and the
    test URL is built to match. ``is_live_db_url()`` then classifies it as the
    live DB without any real host being involved.
  * ``create_engine`` never opens a socket, so ``safe_create_engine`` either
    raises (refused context) or returns a lazy ``Engine`` — port 5433 is
    never contacted.

Contexts covered (CR-00075 AC1):
  * test-collection context — ``IW_CORE_TEST_CONTEXT=true`` + live-DB URL
  * agent-worktree context  — ``IW_CORE_AGENT_CONTEXT=true`` + live-DB URL

Every assertion is behavioural: the guard *raises* ``LiveDbConnectionRefusedError``
(not merely logs or returns ``None``). The refused-context tests use a
context-specific ``match=`` so a regression that swaps which flag is honoured
is caught, not masked.

Genuine vulnerability handling (CR-00075 AC5): if the guard does NOT fire when
it must, write the test as the failing reproduction, mark
``@pytest.mark.xfail(strict=False, reason="I-NNNNN: ...")``, file a
high-priority security Incident, and flag a SECURITY BLOCKER in the step
report. Never fix production code in this CR.
"""

from __future__ import annotations

import pytest

# Synthetic "live DB" coordinates — never a real host. Tests monkeypatch
# IW_CORE_DB_HOST / IW_CORE_DB_PORT to these values so is_live_db_url()
# classifies the constructed URL as the live orch DB without any real host
# being contacted. The ``.invalid`` TLD (RFC 2606) can never resolve.
_LIVE_HOST = "synthetic-live-orch-db.invalid"
_LIVE_PORT = 5433
_LIVE_URL = f"postgresql+psycopg://orch:orch@{_LIVE_HOST}:{_LIVE_PORT}/iw_orch"

# A non-live URL: different host AND port, so is_live_db_url() returns False.
_OTHER_HOST = "scratch-host.invalid"
_OTHER_PORT = 5432
_NON_LIVE_URL = f"postgresql+psycopg://u:p@{_OTHER_HOST}:{_OTHER_PORT}/scratch"


def _point_env_at_synthetic_live_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make IW_CORE_DB_HOST / IW_CORE_DB_PORT describe the synthetic live DB.

    Setup-only helper — it injects no assertions, so each test still carries
    its own behavioural assert / pytest.raises.
    """
    monkeypatch.setenv("IW_CORE_DB_HOST", _LIVE_HOST)
    monkeypatch.setenv("IW_CORE_DB_PORT", str(_LIVE_PORT))


def _clear_allow_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the operator/daemon opt-in flags so a refused context is not bypassed."""
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)


# ---------------------------------------------------------------------------
# is_live_db_url — URL classification
# ---------------------------------------------------------------------------


class TestIsLiveDbUrlClassification:
    """is_live_db_url() classifies a URL as the live orch DB by host:port."""

    def test_matches_configured_live_host_and_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A URL at the configured live host:port is classified as the live DB."""
        _point_env_at_synthetic_live_db(monkeypatch)
        from orch.db import live_db_guard as ldbg

        assert ldbg.is_live_db_url(_LIVE_URL) is True

    def test_different_host_is_not_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A URL at the live port but a different host is NOT the live DB."""
        _point_env_at_synthetic_live_db(monkeypatch)
        from orch.db import live_db_guard as ldbg

        url = f"postgresql+psycopg://orch:orch@elsewhere.invalid:{_LIVE_PORT}/iw_orch"
        assert ldbg.is_live_db_url(url) is False

    def test_different_port_is_not_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A URL at the live host but a different port is NOT the live DB."""
        _point_env_at_synthetic_live_db(monkeypatch)
        from orch.db import live_db_guard as ldbg

        url = f"postgresql+psycopg://orch:orch@{_LIVE_HOST}:5432/iw_orch"
        assert ldbg.is_live_db_url(url) is False


# ---------------------------------------------------------------------------
# Context 1 — test-collection context (IW_CORE_TEST_CONTEXT=true)
# ---------------------------------------------------------------------------


class TestGuardFiresInTestCollectionContext:
    """The guard MUST refuse a live-DB URL when IW_CORE_TEST_CONTEXT=true.

    This simulates what happens if a test module accidentally imports
    ``orch.db.session`` (which builds an engine via ``safe_create_engine``)
    while the live-DB env vars are active at collection time.
    """

    def test_safe_create_engine_raises_under_test_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """safe_create_engine raises in test context — behavioural, not a log line."""
        _point_env_at_synthetic_live_db(monkeypatch)
        _clear_allow_flags(monkeypatch)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        # match= pins the *test-context* refusal branch, not just any refusal.
        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="IW_CORE_TEST_CONTEXT"):
            ldbg.safe_create_engine(_LIVE_URL)

    def test_assert_engine_url_allowed_raises_under_test_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """assert_engine_url_allowed raises in test context for a live-DB URL."""
        _point_env_at_synthetic_live_db(monkeypatch)
        _clear_allow_flags(monkeypatch)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="refused"):
            ldbg.assert_engine_url_allowed(_LIVE_URL)

    def test_non_live_url_allowed_under_test_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The guard does not over-block: a non-live URL builds an engine even in
        test context. Behavioural assert: the returned engine targets exactly
        the URL we asked for (no silent substitution)."""
        _point_env_at_synthetic_live_db(monkeypatch)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_NON_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _OTHER_HOST
            assert engine.url.port == _OTHER_PORT
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Context 2 — agent-worktree context (IW_CORE_AGENT_CONTEXT=true)
# ---------------------------------------------------------------------------


class TestGuardFiresInAgentWorktreeContext:
    """The guard MUST stay active in agent worktrees: IW_CORE_AGENT_CONTEXT=true
    + a live-DB URL is refused. This is the path the 2026-04-26 outage took."""

    def test_safe_create_engine_raises_under_agent_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """safe_create_engine raises in agent context for a live-DB URL."""
        _point_env_at_synthetic_live_db(monkeypatch)
        _clear_allow_flags(monkeypatch)
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        # match= pins the *agent-context* refusal branch specifically.
        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT"):
            ldbg.safe_create_engine(_LIVE_URL)

    def test_assert_engine_url_allowed_raises_under_agent_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """assert_engine_url_allowed raises in agent context for a live-DB URL."""
        _point_env_at_synthetic_live_db(monkeypatch)
        _clear_allow_flags(monkeypatch)
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        with pytest.raises(ldbg.LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT"):
            ldbg.assert_engine_url_allowed(_LIVE_URL)

    def test_non_live_url_allowed_under_agent_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guard does not over-block agent worktrees: a non-live URL builds
        an engine even when IW_CORE_AGENT_CONTEXT=true."""
        _point_env_at_synthetic_live_db(monkeypatch)
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_NON_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _OTHER_HOST
            assert engine.url.port == _OTHER_PORT
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Operator / daemon opt-in — the guard must NOT over-block legitimate callers
# ---------------------------------------------------------------------------


class TestOperatorAndDaemonOptInBypass:
    """The explicit operator/daemon opt-in flags let a live-DB URL through.

    These are positive controls: they prove the refused-context tests above
    fail because of the *context flag*, not because the URL is unconditionally
    blocked.
    """

    def test_operator_apply_allows_live_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_OPERATOR_APPLY=true lets a live-DB URL build an engine."""
        _point_env_at_synthetic_live_db(monkeypatch)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()

    def test_daemon_context_allows_live_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_DAEMON_CONTEXT=true lets a live-DB URL build an engine."""
        _point_env_at_synthetic_live_db(monkeypatch)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        from orch.db import live_db_guard as ldbg

        engine = ldbg.safe_create_engine(_LIVE_URL, pool_pre_ping=False)
        try:
            assert engine.url.host == _LIVE_HOST
            assert engine.url.port == _LIVE_PORT
        finally:
            engine.dispose()
