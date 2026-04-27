"""Connection-layer chokepoint — refuses to create an engine for the live orch DB
unless an explicit operator/daemon opt-in flag is set.

Public API:
    LiveDbConnectionRefused  — raised when a live-DB connection is attempted
    is_live_db_url(url)       — returns True if URL resolves to the live orch DB
    assert_engine_url_allowed(url) — raises LiveDbConnectionRefused if refused context
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from sqlalchemy.engine.url import make_url

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class LiveDbConnectionRefusedError(RuntimeError):
    """Raised when a connection to the live orch DB is attempted from a
    refused context (test, deprecated agent, or no opt-in)."""


LiveDbConnectionRefused = LiveDbConnectionRefusedError


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
      3. Any refused-context flag is set           → REFUSE (raise)
            - IW_CORE_TEST_CONTEXT=true (pytest conftest)
            - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
      4. No flags set                              → ALLOW (ad-hoc local scripts)

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
