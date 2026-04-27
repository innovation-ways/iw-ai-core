"""Dashboard alembic guard middleware and utilities.

Provides:
    AlembicGuardMiddleware — re-checks DB head at most once every 10 s
    is_db_stale(request) — convenience wrapper for templates
    require_db_at_head — FastAPI dependency that returns HTTP 503 on stale DB
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request  # noqa: TC002
    from starlette.responses import Response  # noqa: TC002

    from orch.db.alembic_guard import GuardStatus

_dashboard_check_lock = threading.Lock()
_dashboard_last_check: float = 0.0
_DASHBOARD_CHECK_INTERVAL = 10.0

_alembic_guard_status: GuardStatus | None = None


class AlembicGuardMiddleware(BaseHTTPMiddleware):
    """Middleware that re-checks alembic head at most once every 10 seconds.

    Stores the current GuardStatus on request.state.alembic_guard_status
    so templates can read it via the Jinja request proxy.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        global _dashboard_last_check, _alembic_guard_status

        now = time.time()
        needs_check = False

        with _dashboard_check_lock:
            if now - _dashboard_last_check >= _DASHBOARD_CHECK_INTERVAL:
                needs_check = True
                _dashboard_last_check = now

        if needs_check:
            from orch.db.alembic_guard import check_db_at_head

            with contextlib.suppress(Exception):
                _alembic_guard_status = check_db_at_head()

        request.state.alembic_guard_status = _alembic_guard_status

        return await call_next(request)


def is_db_stale(request: Request) -> bool:
    """Return True when the DB is behind head (guard status not ok)."""
    status = getattr(request.state, "alembic_guard_status", None)
    if status is None:
        return False
    return not status.ok


def require_db_at_head(request: Request) -> None:
    """FastAPI dependency — returns HTTP 503 when DB is stale.

    Apply to state-mutating endpoints that should be blocked on mismatch.
    """
    if is_db_stale(request):
        from orch.db.alembic_guard import remediation_message

        status = getattr(request.state, "alembic_guard_status", None)
        msg = remediation_message(status) if status else "orch DB schema mismatch"
        raise HTTPException(
            status_code=503,
            detail=msg,
            headers={"Retry-After": "30"},
        )
