"""Request-timing + DB pool-status middleware for IW AI Core dashboard."""

from __future__ import annotations

import contextlib
import logging
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy import Engine
    from starlette.requests import Request  # noqa: TC002
    from starlette.responses import Response  # noqa: TC002
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_query_count_ctx: ContextVar[int] = ContextVar("query_count", default=0)


def _before_cursor_execute(
    _conn: Any,
    _cursor: Any,
    _statement: Any,
    _parameters: Any,
    _context: Any,
    _executemany: Any,
) -> None:
    _query_count_ctx.set(_query_count_ctx.get() + 1)


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        engine: Engine,
        slow_request_ms: int = 500,
    ) -> None:
        super().__init__(app)
        self._engine = engine
        self._threshold_ms = slow_request_ms

    @property
    def _pool(self):  # type: ignore[no-untyped-def]
        if self._engine is None:
            return None
        return self._engine.pool

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        from sqlalchemy import event

        start = time.monotonic()
        path = request.url.path
        method = request.method

        token = _query_count_ctx.set(0)

        with contextlib.suppress(Exception):
            event.listen(self._engine, "before_cursor_execute", _before_cursor_execute)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            logger.error("Timing middleware error: %s", exc)
            raise
        finally:
            with contextlib.suppress(Exception):
                event.remove(self._engine, "before_cursor_execute", _before_cursor_execute)

        duration_ms = (time.monotonic() - start) * 1000
        query_count = _query_count_ctx.get()
        _query_count_ctx.reset(token)

        pool_size = pool_checked_out = pool_overflow = pool_checked_in = 0
        with contextlib.suppress(Exception):
            pool = self._pool
            if pool is not None:
                pool_size = pool.size()
                pool_checked_out = pool.checkedout()
                pool_overflow = pool.overflow()
                pool_checked_in = pool.checkedin()

        if duration_ms > self._threshold_ms:
            logger.warning(
                "Slow request: path=%s method=%s status=%s duration_ms=%.2f"
                " db_query_count=%d pool={size=%d checked_out=%d overflow=%d checked_in=%d}",
                path,
                method,
                status_code,
                duration_ms,
                query_count,
                pool_size,
                pool_checked_out,
                pool_overflow,
                pool_checked_in,
            )
        else:
            logger.debug(
                "Request: path=%s method=%s status=%s duration_ms=%.2f"
                " db_query_count=%d pool={size=%d checked_out=%d overflow=%d checked_in=%d}",
                path,
                method,
                status_code,
                duration_ms,
                query_count,
                pool_size,
                pool_checked_out,
                pool_overflow,
                pool_checked_in,
            )

        return response
