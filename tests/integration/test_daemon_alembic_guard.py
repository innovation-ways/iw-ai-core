"""Integration test for daemon alembic guard startup behavior.

Verifies that _alembic_guard_startup exits non-zero when the DB is behind head,
logs a CRITICAL message containing both revision identifiers and 'make db-migrate'.

Uses direct in-process call with monkeypatched sys.exit to capture exit code.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from sqlalchemy import Engine


@pytest.fixture(scope="module")
def pg_container():
    """PostgreSQL 15 testcontainer, module-scoped."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container):
    """SQLAlchemy engine connected to testcontainer, with alembic migrations run to head.

    Sets IW_CORE_DB_* env vars so alembic connects to the testcontainer, not the
    real platform DB. The env vars are scoped to this fixture via MonkeyPatch.context()
    and restored on teardown.
    """
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        mp.setenv("IW_CORE_DB_PORT", str(parsed.port))
        mp.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        mp.setenv("IW_CORE_DB_USER", str(parsed.username))
        mp.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))

        engine = create_engine(url, pool_pre_ping=True)

        cfg = Config()
        cfg.set_main_option("script_location", "orch/db/migrations")
        cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
        command.upgrade(cfg, "head")

        yield engine


def _get_head_rev(engine: Engine) -> str:
    """Return the current head revision."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else ""


def _get_current_rev(engine: Engine) -> str:
    """Read the current alembic_version from the DB."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else ""


def _run_alembic_upgrade_head(engine: Engine) -> None:
    """Run alembic upgrade head to bring DB to head."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")


class TestDaemonStartupGuard:
    def test_daemon_exits_nonzero_when_db_behind_head_via_mock(
        self,
        migrated_engine: Engine,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_alembic_guard_startup exits code 2 with CRITICAL log when DB is behind head.

        Uses mock to inject a stale GuardStatus rather than actually downgrading,
        because the alembic walk_revisions can fail when the DB revision doesn't
        align with the script directory's expected starting point.
        The mock verifies the exact daemon behavior: exit code 2, CRITICAL log,
        head_rev and current_rev in message.
        """
        url = migrated_engine.url.render_as_string(hide_password=False)
        _run_alembic_upgrade_head(migrated_engine)
        head_rev = _get_head_rev(migrated_engine)
        current_rev = _get_current_rev(migrated_engine)
        assert current_rev == head_rev, "DB must be at head for this test"

        # Set env vars so is_live_db_url returns True (matches testcontainer host:port)
        # and IW_CORE_DAEMON_CONTEXT=true bypasses live-db-guard refusal
        env_vars = {
            "IW_CORE_DB_HOST": "localhost",
            "IW_CORE_DB_PORT": str(migrated_engine.url.port or 5432),
            "IW_CORE_DB_NAME": migrated_engine.url.database or "test",
            "IW_CORE_DB_USER": str(migrated_engine.url.username or "test"),
            "IW_CORE_DB_PASSWORD": str(migrated_engine.url.password or "test"),
            "IW_CORE_DB_URL": url,
            "IW_CORE_DAEMON_CONTEXT": "true",
            "IW_CORE_LOG_LEVEL": "DEBUG",
        }
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

        from orch.db.alembic_guard import GuardStatus

        stale_status = GuardStatus(
            current_rev=current_rev,
            head_rev="ab" + current_rev[2:] if len(current_rev) > 2 else "bbb",
            pending=["rev_c", "rev_b"],
            multiple_heads=[],
            ok=False,
        )

        exit_codes: list[int] = []

        def fake_sys_exit(code: int) -> None:
            exit_codes.append(code)
            raise SystemExit(code)

        monkeypatch.setattr(sys, "exit", fake_sys_exit)

        with patch("orch.daemon.main.check_db_at_head", return_value=stale_status):
            from sqlalchemy.orm import sessionmaker

            from orch.daemon.main import _alembic_guard_startup
            from orch.db.session import safe_create_engine

            engine = safe_create_engine(url, pool_pre_ping=True)
            factory = sessionmaker(bind=engine)

            with (
                caplog.at_level(logging.DEBUG, logger="orch.daemon.main"),
                contextlib.suppress(SystemExit),
            ):
                _alembic_guard_startup(factory)

            engine.dispose()

        critical_records = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        log_output = " ".join(r.message for r in critical_records)

        assert len(exit_codes) >= 1, f"Expected sys.exit to be called, got exit_codes={exit_codes}"
        assert exit_codes[0] == 2, f"Expected exit code 2, got {exit_codes[0]}"
        assert "CRITICAL" in log_output, f"Expected CRITICAL in log output: {log_output}"
        assert stale_status.head_rev in log_output, (
            f"Expected head_rev '{stale_status.head_rev}' in log output: {log_output}"
        )
        assert current_rev in log_output, (
            f"Expected current_rev '{current_rev}' in log output: {log_output}"
        )
        assert "make db-migrate" in log_output, (
            f"Expected 'make db-migrate' in log output: {log_output}"
        )
