"""Session provisioning for MCP tool handlers.

MCP tool handlers must obtain a short-lived database session per call, exactly
as the ``iw`` CLI opens one per invocation. This module centralises that so:

* In production the handlers use :func:`orch.db.session.get_session` under the
  process-wide ``iw_cli_orch_bridge`` opened by :func:`orch.mcp.server.main`.
* In tests an injected factory (the testcontainer session) is used instead, so
  tool handlers never touch the live orch DB — mirroring how the CLI tests
  inject ``ctx.obj["get_session"]``.

The override is a plain module-global (not a ``ContextVar``) on purpose:
FastMCP runs sync tools in a worker thread, and module globals are shared
across threads whereas ``ContextVar`` values are not copied into them.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    SessionFactory = Callable[[], AbstractContextManager[Session]]

#: Test-injected session factory. ``None`` in production (use the real DB).
_session_factory: SessionFactory | None = None


def set_session_factory(factory: SessionFactory) -> None:
    """Override the session factory used by MCP tool handlers.

    Intended for tests only — inject a factory that yields a testcontainer
    session so tool handlers never reach the live orch DB.

    Args:
        factory: Zero-arg callable returning a context manager that yields a
            SQLAlchemy ``Session``.
    """
    global _session_factory
    _session_factory = factory


def reset_session_factory() -> None:
    """Clear any test-injected session factory, restoring production behaviour."""
    global _session_factory
    _session_factory = None


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Yield a database session for a single MCP tool call.

    Uses the test-injected factory when one is set (see
    :func:`set_session_factory`); otherwise opens a real session via
    :func:`orch.db.session.get_session` (commit on success, rollback on error).

    Yields:
        An active SQLAlchemy ``Session`` scoped to the tool call.
    """
    if _session_factory is not None:
        with _session_factory() as session:
            yield session
        return

    from orch.db.session import get_session  # noqa: PLC0415

    with get_session() as session:
        yield session
