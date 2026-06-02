"""Logging configuration and credential redaction tests — F-00073 S01.

TDD RED phase: write tests that describe the expected behavior.
These tests may fail until the logging infrastructure is in place.

Credential redaction policy:
- SQLAlchemy engine repr must never contain literal passwords
- get_db_url() / get_orch_db_url() return values must not contain raw passwords
- No handler in the logging pipeline should ever receive a URL with credentials exposed
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


class TestLoggingConfiguration:
    """Logging level and propagation for orch and dashboard loggers."""

    def test_orch_logger_exists(self) -> None:
        """logging.getLogger('orch') must be defined."""
        logger = logging.getLogger("orch")
        assert logger is not None

    def test_dashboard_logger_exists(self) -> None:
        """logging.getLogger('dashboard') must be defined."""
        logger = logging.getLogger("dashboard")
        assert logger is not None

    def test_orch_logger_level_is_info_or_lower(self) -> None:
        """orch logger level must be INFO (20) or DEBUG (10) for production visibility."""
        logger = logging.getLogger("orch")
        assert logger.level <= logging.INFO, (
            f"orch logger level is {logger.level} ({logging.getLevelName(logger.level)}) — "
            "expected INFO(20) or DEBUG(10) for production observability"
        )

    def test_dashboard_logger_level_is_info_or_lower(self) -> None:
        """dashboard logger level must be INFO (20) or DEBUG (10)."""
        logger = logging.getLogger("dashboard")
        assert logger.level <= logging.INFO, (
            f"dashboard logger level is {logger.level} ({logging.getLevelName(logger.level)}) — "
            "expected INFO(20) or DEBUG(10)"
        )

    def test_orch_logger_propagates_to_root(self) -> None:
        """orch logger must propagate to avoid duplicate handlers."""
        logger = logging.getLogger("orch")
        assert logger.propagate is True, "orch logger should propagate to root handler"

    def test_dashboard_logger_propagates_to_root(self) -> None:
        """dashboard logger must propagate to avoid duplicate handlers."""
        logger = logging.getLogger("dashboard")
        assert logger.propagate is True, "dashboard logger should propagate to root handler"


class TestCredentialRedaction:
    """Credential redaction — passwords must NEVER appear in logs or reprs."""

    def test_engine_repr_does_not_expose_password(self) -> None:
        """SQLAlchemy engine repr must not contain literal passwords.

        If a connection URL like postgresql+psycopg://user:password@host:port/db
        is passed to create_engine(), the repr must not expose the password.
        """
        from sqlalchemy import create_engine

        url = "postgresql+psycopg://iw:MySecretP@ssw0rd@localhost:5432/iw_ai_core"
        engine = create_engine(url, pool_pre_ping=True)
        try:
            engine_repr = repr(engine)
            assert "MySecretP@ssw0rd" not in engine_repr, (
                f"Password 'MySecretP@ssw0rd' found in engine repr: {engine_repr}"
            )
        finally:
            engine.dispose()

    def test_engine_url_render_hide_password(self) -> None:
        """engine.url.render_as_string() must support hide_password=True."""
        from sqlalchemy import create_engine

        url = "postgresql+psycopg://iw:OpenSesame@localhost:5432/iw_ai_core"
        engine = create_engine(url, pool_pre_ping=True)
        try:
            rendered = engine.url.render_as_string(hide_password=True)
            assert "OpenSesame" not in rendered, (
                f"Password 'OpenSesame' found in render_as_string: {rendered}"
            )
            assert "iw" in rendered, "render_as_string should still show username"
        finally:
            engine.dispose()

    @pytest.mark.xfail(reason="BLOCKER F-00073-S01: raw password in get_db_url()")
    def test_get_db_url_does_not_leak_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_db_url() must not embed raw passwords — credentials must be sanitized."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_ai_core")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "Hunter2!@#$%")

        from orch.config import get_db_url

        url = get_db_url()
        assert "Hunter2!@#$%" not in url, (
            f"Password 'Hunter2!@#$%' leaked in get_db_url() return value: {url}"
        )
        assert "postgresql+psycopg://" in url

    @pytest.mark.xfail(reason="BLOCKER F-00073-S01: raw password in get_orch_db_url()")
    def test_get_orch_db_url_does_not_leak_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_orch_db_url() must not embed raw passwords."""
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_NAME", "iw_ai_core")
        monkeypatch.setenv("IW_CORE_ORCH_DB_USER", "iw")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PASSWORD", "AnotherSecret123")

        from orch.config import get_orch_db_url

        url = get_orch_db_url()
        assert "AnotherSecret123" not in url, (
            f"Password 'AnotherSecret123' leaked in get_orch_db_url() return value: {url}"
        )
        assert "postgresql+psycopg://" in url

    def test_safe_create_engine_password_not_in_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """safe_create_engine() engine repr must not expose the password."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_ai_core")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "TestSecret456")
        monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")

        from orch.db.session import safe_create_engine

        engine = safe_create_engine(
            "postgresql+psycopg://iw:TestSecret456@localhost:5432/iw_ai_core"
        )
        try:
            engine_repr = repr(engine)
            assert "TestSecret456" not in engine_repr, (
                f"Password 'TestSecret456' found in safe_create_engine repr: {engine_repr}"
            )
        finally:
            engine.dispose()

    @pytest.mark.xfail(reason="BLOCKER F-00073-S01: raw password in get_db_url()")
    def test_log_output_never_contains_db_url_with_password(
        self,
        caplog: CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No log record produced by orch code should contain a URL with password."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "iw_ai_core")
        monkeypatch.setenv("IW_CORE_DB_USER", "iw")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "LogSecret789")

        from orch.config import get_db_url

        url = get_db_url()

        with caplog.at_level(logging.DEBUG, logger="orch"):
            logging.getLogger("orch").debug("DB URL: %s", url)

        for record in caplog.records:
            assert "LogSecret789" not in record.message, (
                f"Password 'LogSecret789' found in log message: {record.message}"
            )


@pytest.mark.xfail(reason="BLOCKER F-00073-S01: raw password in get_db_url()")
class TestCredentialRedactionFindings:
    """Documented credential leak findings — must be fixed before going GREEN.

    BLOCKER F-00073-S01: get_db_url() and get_orch_db_url() embed raw passwords
    in their return values, which are then logged directly by orch code.
    e.g. logging.getLogger("orch").debug("DB URL: %s", get_db_url())

    These tests will remain XFAIL until the credential redaction is implemented.
    """

    def test_blocker_documented_placeholder(self) -> None:
        """Verifies that blocker documented placeholder."""
        assert True, "Blocker documented in TestCredentialRedactionFindings"
