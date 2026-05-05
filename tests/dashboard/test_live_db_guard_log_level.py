"""Tests for I-00069: LiveDbConnectionRefusedError log-level demotion in test context.

Verifies:
- RED before S01: LiveDbConnectionRefusedError is logged at ERROR with traceback
- GREEN after S01: LiveDbConnectionRefusedError is logged at DEBUG (test context)
  or WARNING (non-test context), no traceback
- Regression: other exceptions still log at ERROR with traceback
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from dashboard.app import create_app


class TestI00069LiveDbGuardLogLevel:
    """Log-level behaviour for LiveDbConnectionRefusedError in dashboard/app.py."""

    def test_i00069_live_db_guard_refusal_is_not_error_in_test_context(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """RED before S01, GREEN after.

        Under IW_CORE_TEST_CONTEXT=true, dashboard startup MUST NOT log the
        expected LiveDbConnectionRefusedError at ERROR with a traceback.
        The demoted DEBUG line must still be emitted (semantic assertion).
        """
        # Belt-and-braces: ensure test context flag is set (session fixture
        # already sets it, but explicit is clearer than implicit)
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")

        # Capture DEBUG and above on the dashboard.app logger specifically
        caplog.set_level(logging.DEBUG, logger="dashboard.app")

        # create_app() must succeed — the refusal is swallowed
        app = create_app()

        # Verify alembic_guard_status is None (expected refusal path taken)
        assert app.state.alembic_guard_status is None

        # --- Semantic assertion: the demoted DEBUG line is actually present ---
        # This proves the fix took effect, not just that ERROR is absent.
        debug_records_mentioning_refusal = [
            r
            for r in caplog.records
            if r.levelno == logging.DEBUG and "LiveDbConnectionRefused" in r.getMessage()
        ]
        assert debug_records_mentioning_refusal, (
            "Expected a DEBUG-level record mentioning 'LiveDbConnectionRefused' "
            "in test context; none found. The demoted log line is missing."
        )

        # --- Negative assertion: no ERROR record mentions LiveDbConnectionRefused ---
        # This is the core bug fix: the ERROR + traceback must not appear.
        error_records_mentioning_refusal = [
            r
            for r in caplog.records
            if r.levelno >= logging.ERROR
            and "LiveDbConnectionRefused" in (r.getMessage() + (r.exc_text or ""))
        ]
        assert error_records_mentioning_refusal == [], (
            "LiveDbConnectionRefusedError must NOT log at ERROR in test context; "
            f"found {len(error_records_mentioning_refusal)} ERROR record(s): "
            f"{[(r.getMessage(), r.exc_text) for r in error_records_mentioning_refusal]}"
        )

    def test_i00069_non_refusal_exception_still_logs_error(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Genuine startup failures must STILL log at ERROR with traceback.

        Prevents over-correction where the fix accidentally silences real bugs.
        """
        caplog.set_level(logging.DEBUG, logger="dashboard.app")

        # Monkeypatch check_db_at_head to raise a non-refusal exception
        with patch(
            "dashboard.app.check_db_at_head",
            side_effect=RuntimeError("synthetic boot failure"),
        ):
            app = create_app()

        # Verify alembic_guard_status is None (exception was caught)
        assert app.state.alembic_guard_status is None

        # --- Regression assertion: genuine failure logs at ERROR with traceback ---
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, "Expected at least one ERROR-level record for RuntimeError"

        # exc_text is populated by logger.exception() and contains the traceback
        error_records_with_traceback = [r for r in error_records if r.exc_text]
        assert error_records_with_traceback, (
            "RuntimeError must still log at ERROR with a traceback (exc_text); "
            f"found {len(error_records)} ERROR record(s) but none had exc_text. "
            "The over-correction would silence real boot failures."
        )
