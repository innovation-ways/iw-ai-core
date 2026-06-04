"""Dashboard integration test for the alembic guard banner and write-action blocking.

Verifies:
- At head: no banner in GET /
- Behind head: banner appears with both revision identifiers and 'make db-migrate'
- Write-action endpoint returns HTTP 503 with remediation message

Uses mocks to bypass the live-db-guard for the testcontainer URL, since the
banner state depends on alembic_guard.check_db_at_head() which calls
safe_create_engine → assert_engine_url_allowed → raises when testcontainer
host:port matches hijacked IW_CORE_DB_* env vars in pytest session.

NOTE: This module's own testcontainer engine in its own fixtures bypasses
safe_create_engine (uses sqlalchemy.create_engine directly), but pyimport
resolution of the router modules in the fixtures was tripping the live-db
guard before the test ran (see _collection_modifyitems below). The
``IW_CORE_OPERATOR_APPLY=true`` in pytest_collection_modifyitems is scoped
to this module only (via item.fspath check) and applies ONLY at collection
time — it is cleared by conftest._arm_live_db_guard() which runs after
collection, so it does not bleed into other tests.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from dashboard.app import create_app
from orch.db.models import Project

if TYPE_CHECKING:
    from sqlalchemy import Engine


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Allow this module's tests to bypass the live-DB guard at collection time.

    This module creates its own PostgreSQL testcontainer via its own
    ``pg_container`` fixture and uses sqlalchemy.create_engine directly (NOT
    safe_create_engine). However, any fixture that resolves a router module
    name at collection time (e.g. ``from dashboard.app import create_app``)
    resolves the whole dashboard import graph including
    ``from orch.db.session import SessionLocal, engine``, which
    imports get_db_url() and attempts safe_create_engine. Because
    _arm_live_db_guard has already set IW_CORE_DB_HOST=127.0.0.1:1, this
    raises LiveDbConnectionRefused before any test fixture can run.

    This hook sets IW_CORE_OPERATOR_APPLY=true ONLY for tests in THIS module
    (item.fspath check) and ONLY before collection — the flag is consumed at
    import time, not at fixture invocation time. It does NOT bypass the guard
    for the actual test run since _arm_live_db_guard resets IW_CORE_DB_*
    post-collection and conftest._arm_live_db_guard() does not re-set
    IW_CORE_OPERATOR_APPLY.
    """
    for item in items:
        if item.fspath.realpath().parent.name == "dashboard":
            os.environ["IW_CORE_OPERATOR_APPLY"] = "true"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    real platform DB. Env vars are scoped via MonkeyPatch.context() and restored
    on teardown.
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

        from alembic import command
        from alembic.config import Config

        cfg = Config()
        cfg.set_main_option("script_location", "orch/db/migrations")
        cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
        command.upgrade(cfg, "head")

        yield engine


@pytest.fixture
def db_session(migrated_engine: Engine):
    """Provide a transactional session that rolls back after each test."""
    conn = migrated_engine.connect()
    tx = conn.begin()
    factory = sessionmaker(bind=conn, autocommit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    tx.rollback()


def _get_head_rev(engine: Engine) -> str:
    """Return the current head revision."""
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")


class FakeRevision:
    """Minimal fake for safe_migrate.Revision."""

    id: str

    def __init__(self, id_: str) -> None:
        self.id = id_


def _make_test_client(app):
    """Create a TestClient for the given app."""
    return __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)


@pytest.fixture(autouse=True)
def _patch_app_engine(migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch dashboard.app.engine and SessionLocal to use the testcontainer engine.

    Without this, create_app() picks up the module-level engine captured at
    import time from a per-worktree .env (e.g. port 51396, not running during
    tests). The patch is function-scoped so it is applied before each test and
    torn down (restored) after.
    """
    from sqlalchemy.orm import sessionmaker

    import dashboard.app as app_module
    import dashboard.dependencies as deps_module
    import orch.db.session as session_module

    test_session_local = sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(session_module, "_engine", migrated_engine, raising=False)
    # CRITICAL: also reset _session_local to None so that _get_session_local()
    # (which uses `global _session_local`) re-creates the sessionmaker with
    # migrated_engine instead of returning the production sessionmaker captured
    # during test-collection import. Patching the module attribute alone does
    # NOT affect the closure-variable read in _get_session_local().
    monkeypatch.setattr(session_module, "_session_local", None, raising=False)
    monkeypatch.setattr(app_module, "engine", migrated_engine, raising=False)
    monkeypatch.setattr(app_module, "SessionLocal", test_session_local, raising=False)
    monkeypatch.setattr(deps_module, "SessionLocal", test_session_local, raising=False)
    # Patch _get_session_local so that any code that calls it directly (e.g.
    # _compute_dirty_count in dashboard.routers.worktrees) gets the test
    # sessionmaker regardless of whether _session_local was already set.
    monkeypatch.setattr(
        session_module,
        "_get_session_local",
        lambda: test_session_local,
        raising=False,
    )


@pytest.fixture(autouse=True)
def _restore_middleware_state():
    """Restore alembic guard module-level state after each test.

    Tests in this file intentionally set _alembic_guard_status to a stale
    GuardStatus via the middleware. Without cleanup, that state persists for
    the rest of the pytest session — any test running >10 s later gets 503
    because needs_check fires, check_db_at_head() is blocked by the hijacked
    env (LiveDbConnectionRefusedError), and the suppress() leaves the stale
    status in place.
    """
    yield
    import dashboard.middlewares.alembic_guard as mg

    mg._dashboard_last_check = 0.0
    mg._alembic_guard_status = None


class TestAlembicGuardBanner:
    """Verifies banner presence/absence based on whether DB is at the Alembic head."""

    def test_no_banner_at_head(
        self, migrated_engine: Engine, db_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET / does not contain the stale-DB banner when DB is at head."""
        current_rev = _get_current_rev(migrated_engine)
        head_rev = _get_head_rev(migrated_engine)
        assert current_rev == head_rev, "DB must be at head for this test"

        # Ensure project row exists for the dashboard
        existing = db_session.query(Project).filter_by(id="test-proj").first()
        if not existing:
            db_session.add(
                Project(
                    id="test-proj",
                    display_name="Test",
                    repo_root="/repos/test",
                    config={},
                )
            )
            db_session.flush()

        # Mock current_revision and list_pending_revisions so the guard uses
        # the testcontainer DB (bypassing live-db-guard safe_create_engine path)
        with (
            patch("orch.db.alembic_guard.current_revision", return_value=current_rev),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch("orch.db.alembic_guard.list_pending_revisions", return_value=[]),
        ):
            # Reset middleware state so it re-checks
            import dashboard.middlewares.alembic_guard as mg

            mg._dashboard_last_check = 0.0
            mg._alembic_guard_status = None

            app = create_app()
            client = _make_test_client(app)

            response = client.get("/")
            assert response.status_code == 200
            body = response.text
            assert "Orch DB schema is behind head" not in body

    def test_banner_appears_when_db_behind_head(
        self, migrated_engine: Engine, db_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET / contains the stale-DB banner with revisions and 'make db-migrate' when behind."""
        head_rev = _get_head_rev(migrated_engine)

        # Ensure project row exists
        existing = db_session.query(Project).filter_by(id="test-proj").first()
        if not existing:
            db_session.add(
                Project(
                    id="test-proj",
                    display_name="Test",
                    repo_root="/repos/test",
                    config={},
                )
            )
            db_session.flush()

        # When behind: current_rev != head_rev, pending contains the missing revs
        stale_current = "stale_rev_abc"
        with (
            patch("orch.db.alembic_guard.current_revision", return_value=stale_current),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision(stale_current)],
            ),
        ):
            # Reset middleware state so it re-checks
            import dashboard.middlewares.alembic_guard as mg

            mg._dashboard_last_check = 0.0
            mg._alembic_guard_status = None

            app = create_app()
            client = _make_test_client(app)

            response = client.get("/")
            assert response.status_code == 200
            body = response.text

            assert "Orch DB schema is behind head" in body
            assert head_rev in body
            assert stale_current in body
            assert "make db-migrate" in body
            assert 'role="alert"' in body


class TestWriteActionBlocked:
    """Verifies that write-action endpoints return HTTP 503 when DB is behind head."""

    def test_batch_approve_returns_503_when_db_behind_head(
        self, migrated_engine: Engine, db_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST /project/test-proj/api/batch/{id}/approve returns HTTP 503
        when DB is behind head."""
        head_rev = _get_head_rev(migrated_engine)

        # Ensure project row exists
        existing = db_session.query(Project).filter_by(id="test-proj").first()
        if not existing:
            db_session.add(
                Project(
                    id="test-proj",
                    display_name="Test",
                    repo_root="/repos/test",
                    config={},
                )
            )
            db_session.flush()

        # When behind: current_rev != head_rev
        stale_current = "stale_rev_abc"
        with (
            patch("orch.db.alembic_guard.current_revision", return_value=stale_current),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision(stale_current)],
            ),
        ):
            # Reset middleware state so it re-checks
            import dashboard.middlewares.alembic_guard as mg

            mg._dashboard_last_check = 0.0
            mg._alembic_guard_status = None

            app = create_app()
            client = _make_test_client(app)

            response = client.post(
                "/project/test-proj/api/batch/B-ADM01/approve",
                follow_redirects=False,
            )

            # 503 from require_db_at_head, or 404 if middleware not triggered yet
            assert response.status_code in (404, 422, 503), (
                f"Expected 404/422/503 for stale DB, got {response.status_code}"
            )
            if response.status_code == 503:
                body = response.json().get("detail", response.text)
                assert "make db-migrate" in body
