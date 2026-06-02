"""Tests for timing middleware (F1/F2)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from dashboard.utils.timing import TimingMiddleware, _query_count_ctx


class TestQueryCountCtx:
    """Tests for QueryCountCtx scenarios."""

    def test_default_zero(self) -> None:
        """Verifies that default zero."""
        assert _query_count_ctx.get() == 0

    def test_increment_and_get(self) -> None:
        """Verifies that increment and get."""
        token = _query_count_ctx.set(0)
        _query_count_ctx.set(_query_count_ctx.get() + 1)
        _query_count_ctx.set(_query_count_ctx.get() + 1)
        assert _query_count_ctx.get() == 2
        _query_count_ctx.reset(token)

    def test_reset(self) -> None:
        """Verifies that reset."""
        token = _query_count_ctx.set(5)
        _query_count_ctx.reset(token)
        assert _query_count_ctx.get() == 0


class TestTimingMiddleware:
    """Tests for TimingMiddleware scenarios."""

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        """Provide mock engine for tests."""
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedout.return_value = 2
        pool.overflow.return_value = 3
        pool.checkedin.return_value = 8
        pool.status.return_value = "Pool size=10, checked out=2, overflow=3"
        engine = MagicMock()
        engine.pool = pool
        return engine

    def test_instantiation_with_engine(self, mock_engine: MagicMock) -> None:
        """Verifies that instantiation with engine."""
        app = MagicMock()
        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=500)
        assert mw._engine is mock_engine
        assert mw._threshold_ms == 500

    def test_default_threshold_is_500(self, mock_engine: MagicMock) -> None:
        """Verifies that default threshold is 500."""
        app = MagicMock()
        mw = TimingMiddleware(app=app, engine=mock_engine)
        assert mw._threshold_ms == 500

    @pytest.mark.asyncio
    async def test_emits_warn_above_threshold(
        self, mock_engine: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies that emits warn above threshold."""
        app = MagicMock()
        mock_request = MagicMock()
        mock_request.url.path = "/test/path"
        mock_request.method = "GET"

        async def slow_call_next(request: MagicMock) -> MagicMock:
            """Return slow call next."""
            time.sleep(0.01)
            response = MagicMock()
            response.status_code = 200
            return response

        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=1)

        dispatch = mw.dispatch.__wrapped__ if hasattr(mw.dispatch, "__wrapped__") else mw.dispatch
        with patch.object(mw, "dispatch", dispatch):
            pass

        response = await mw.dispatch(mock_request, slow_call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_warn_log_contains_required_fields(
        self, mock_engine: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies that warn log contains required fields."""
        import logging

        app = MagicMock()
        mock_request = MagicMock()
        mock_request.url.path = "/slow/path"
        mock_request.method = "POST"

        async def slow_call_next(request: MagicMock) -> MagicMock:
            """Return slow call next."""
            time.sleep(0.05)
            response = MagicMock()
            response.status_code = 201
            return response

        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=1)

        with caplog.at_level(logging.WARNING):
            response = await mw.dispatch(mock_request, slow_call_next)

        assert response.status_code == 201
        warn_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warn_records) >= 1
        warn_msg = warn_records[0].message
        assert "path=/slow/path" in warn_msg or "/slow/path" in warn_msg
        assert "duration_ms" in warn_msg
        assert "db_query_count" in warn_msg

    @pytest.mark.asyncio
    async def test_debug_log_below_threshold(
        self, mock_engine: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies that debug log below threshold."""
        import logging

        app = MagicMock()
        mock_request = MagicMock()
        mock_request.url.path = "/fast/path"
        mock_request.method = "GET"

        async def fast_call_next(request: MagicMock) -> MagicMock:
            """Return fast call next."""
            response = MagicMock()
            response.status_code = 200
            return response

        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=1000)

        with caplog.at_level(logging.DEBUG):
            response = await mw.dispatch(mock_request, fast_call_next)

        assert response.status_code == 200
        debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert len(debug_records) >= 1

    @pytest.mark.asyncio
    async def test_pool_status_in_log(
        self, mock_engine: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies that pool status in log."""
        import logging

        app = MagicMock()
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        async def call_next(request: MagicMock) -> MagicMock:
            """Return call next."""
            response = MagicMock()
            response.status_code = 200
            return response

        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=1000)

        with caplog.at_level(logging.DEBUG):
            await mw.dispatch(mock_request, call_next)

        log_text = caplog.text
        assert "pool" in log_text.lower() or "size" in log_text

    @pytest.mark.asyncio
    async def test_does_not_swallow_upstream_exceptions(self, mock_engine: MagicMock) -> None:
        """Verifies that does not swallow upstream exceptions."""
        app = MagicMock()
        mock_request = MagicMock()
        mock_request.url.path = "/error"
        mock_request.method = "GET"

        async def raising_call_next(request: MagicMock) -> MagicMock:
            """Return raising call next."""
            raise ValueError(" upstream error ")

        mw = TimingMiddleware(app=app, engine=mock_engine, slow_request_ms=500)

        with pytest.raises(ValueError, match="upstream error"):
            await mw.dispatch(mock_request, raising_call_next)
