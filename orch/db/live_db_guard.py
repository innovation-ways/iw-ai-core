"""Connection-layer chokepoint — refuses to create an engine for the live orch DB
unless an explicit operator/daemon opt-in flag is set.

Public API:
    LiveDbConnectionRefused  — raised when a live-DB connection is attempted
    is_live_db_url(url)       — returns True if URL resolves to the live orch DB
    assert_engine_url_allowed(url) — raises LiveDbConnectionRefused if refused context
    iw_cli_orch_bridge()      — context manager allowing the iw CLI process to
                                connect to the orch DB (its legitimate channel)
                                without leaking the bypass to subprocesses or
                                pytest contexts.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy.engine.url import make_url

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_iw_cli_orch_bridge_active: bool = False


class LiveDbConnectionRefusedError(RuntimeError):
    """Raised when a connection to the live orch DB is attempted from a
    refused context (test, deprecated agent, or no opt-in)."""


LiveDbConnectionRefused = LiveDbConnectionRefusedError


@contextmanager
def iw_cli_orch_bridge() -> Iterator[None]:
    """Mark the calling process as the iw CLI bridging an agent to the orch DB.

    The iw CLI is the legitimate channel for agents to record orchestration
    state (`step-start`, `step-done`, `item-status`, …). Without this marker,
    every iw invocation under IW_CORE_AGENT_CONTEXT=true is refused — a
    catch-22 because the agent has no way to talk to the orchestrator.

    Strictly scoped:
      - Process-local module flag (NOT an env var). Subprocesses spawned by
        the CLI (pytest, alembic, agents the daemon launches downstream)
        do NOT inherit the bypass.
      - Loses to IW_CORE_TEST_CONTEXT (a CliRunner-driven test cannot bypass
        the guard via this bridge — the test-context refusal fires first).
      - Wins over IW_CORE_AGENT_CONTEXT (resolves the catch-22).
      - Resets on exit (try/finally) so test isolation is preserved.
    """
    global _iw_cli_orch_bridge_active
    previous = _iw_cli_orch_bridge_active
    _iw_cli_orch_bridge_active = True
    try:
        yield
    finally:
        _iw_cli_orch_bridge_active = previous


def _get_live_db_host_port() -> tuple[str, str]:
    """Return the live orch DB host and port from env vars."""
    host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    port = os.environ.get("IW_CORE_DB_PORT", "5433")
    return host, port


def is_live_db_url(url: str) -> bool:
    """Return True if `url` resolves to the live orch DB.

    Match priority:
      1. IW_CORE_EXPECTED_INSTANCE_ID is set → the configured host:port IS
         the live DB fingerprint. Any URL at that host:port with matching
         credentials is the live DB. (We do not probe the DB to verify the
         fingerprint — that would open a connection and defeat the guard.)
      2. IW_CORE_EXPECTED_INSTANCE_ID is unset → fall back to host:port
         comparison against IW_CORE_DB_HOST / IW_CORE_DB_PORT.

    Returns False on parse failures (fail-open for non-PG URLs).
    """
    try:
        parsed = make_url(url)
    except Exception:
        return False

    live_host, live_port = _get_live_db_host_port()

    parsed_host = parsed.host or ""
    parsed_port = str(parsed.port or 5432)

    return parsed_host == live_host and parsed_port == live_port


def assert_engine_url_allowed(url: str) -> None:
    """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
    the caller is in a refused context.

    Decision matrix (evaluated top-to-bottom, first match wins):
      1. URL is NOT the live DB                    → ALLOW (no-op)
      2. Any allowed-context flag is set           → ALLOW (operator/daemon)
            - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
            - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
      3. IW_CORE_TEST_CONTEXT=true                 → REFUSE (raise)
            (pytest conftest — strictly refused; the iw CLI bridge below
            cannot bypass this, so CliRunner-driven tests cannot reach the
            live DB even when invoking the CLI in-process)
      4. iw CLI orchestrator bridge is active      → ALLOW
            (entered by `iw_cli_orch_bridge()` from the CLI entrypoint —
            the legitimate channel for agents to record orchestration state)
      5. IW_CORE_AGENT_CONTEXT=true                → REFUSE (raise)
      6. No flags set                              → ALLOW (ad-hoc local scripts)

    Allowed-context wins over refused-context (rule 2 before rule 3).
    Rationale: an operator running daemon code locally inside a pytest
    sub-shell is intentional; the operator's explicit opt-in is more
    specific than the inherited test-context default.
    """
    if not is_live_db_url(url):
        return

    if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
        return
    if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
        return

    if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
        raise LiveDbConnectionRefusedError(
            "Connection to live orch DB refused: "
            "host:port of the URL matches the live orch DB, "
            "and IW_CORE_TEST_CONTEXT is set. "
            "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
            "`iw migrations apply --i-am-operator` or run from the daemon "
            "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
        )

    if _iw_cli_orch_bridge_active:
        return

    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
        raise LiveDbConnectionRefusedError(
            "Connection to live orch DB refused: "
            "host:port of the URL matches the live orch DB, "
            "and IW_CORE_AGENT_CONTEXT is set. "
            "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
            "`iw migrations apply --i-am-operator` or run from the daemon "
            "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
        )


def safe_create_engine(url: str, **kwargs: object) -> Engine:
    """Create a SQLAlchemy engine after asserting the URL is allowed.

    This is the single chokepoint for all engine creation in `orch/`.
    Every `create_engine` call in the codebase must route through here.
    """
    assert_engine_url_allowed(url)
    from sqlalchemy import create_engine as _create_engine

    return _create_engine(url, **kwargs)
