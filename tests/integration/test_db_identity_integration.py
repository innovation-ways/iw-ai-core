"""Integration tests for orch.db.identity — CR-00014.

Tests daemon startup gate, dashboard health endpoint, and migration roundtrip
with real PostgreSQL testcontainers.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.identity import (
    InstanceMismatchError,
    InstanceRowMissingError,
    verify_instance_identity,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine


@pytest.fixture(scope="module")
def pg_container():
    """PostgreSQL 15 testcontainer, module-scoped to share across tests."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container):
    """SQLAlchemy engine connected to the testcontainer DB, with alembic migrations run.

    Sets IW_CORE_DB_* env vars so that alembic (via env.py) connects to the
    testcontainer rather than the real platform DB. The env vars are restored
    on fixture teardown so they don't leak to subsequent tests (which would
    then try to connect to the now-stopped testcontainer port).
    Alembic runs all migrations (creating all tables and FTS triggers)
    and seeds the iw_core_instance row.
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


def _seed_project(engine: Engine) -> None:
    """Ensure a minimal project exists so foreign-key constraints pass."""
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 FROM projects WHERE id = 'test-proj'"))
        if r.fetchone() is None:
            conn.execute(
                text(
                    "INSERT INTO projects (id, display_name, repo_root, config) "
                    "VALUES ('test-proj', 'Test', '/repos/test', '{}')"
                )
            )
            conn.commit()


@pytest.fixture
def seeded_engine(migrated_engine: Engine) -> Engine:
    """Ensure project row exists before each test."""
    _seed_project(migrated_engine)
    return migrated_engine


@pytest.fixture
def db_session(seeded_engine: Engine):
    """Provide a transactional session that rolls back after each test."""
    conn = seeded_engine.connect()
    tx = conn.begin()
    factory = sessionmaker(bind=conn, autocommit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    tx.rollback()
    conn.close()


@pytest.fixture
def identity_matched(monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine) -> None:
    """Set IW_CORE_EXPECTED_INSTANCE_ID to the actual seeded instance ID."""
    with migrated_engine.connect() as conn:
        row = conn.execute(text("SELECT instance_id FROM iw_core_instance WHERE id = 1")).fetchone()
        assert row is not None, "iw_core_instance row must exist for identity_matched"
    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(row.instance_id))


@pytest.fixture
def identity_mismatched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set IW_CORE_EXPECTED_INSTANCE_ID to a different random UUID."""
    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(uuid.uuid4()))


@pytest.fixture
def identity_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure IW_CORE_EXPECTED_INSTANCE_ID is not set."""
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)


@pytest.fixture(autouse=True)
def _restore_iw_core_instance_row(migrated_engine: Engine) -> None:
    """Module-level guard: ensure ``iw_core_instance`` has its (id=1, UUID) row.

    R-00077 / CR-00055: ``test_daemon_startup_refuses_on_missing_row`` DELETEs
    the row, and ``TestMigrationRoundtrip`` downgrades the entire table.
    Under randomised order, that leak breaks every other test in the module
    that expects the row to exist (TestDaemonStartupGate's other three methods
    + the pre-roundtrip read in TestMigrationRoundtrip's quarantined test).
    Mirrors ``TestDashboardHealthzIdentity::ensure_instance_row`` but at
    module scope so it covers every test class in the file.
    """
    with migrated_engine.connect() as conn:
        table_present = conn.execute(
            text("SELECT 1 FROM pg_tables WHERE tablename = 'iw_core_instance'")
        ).fetchone()
        if table_present is None:
            cfg = Config()
            cfg.set_main_option("script_location", "orch/db/migrations")
            cfg.set_main_option(
                "sqlalchemy.url",
                migrated_engine.url.render_as_string(hide_password=False),
            )
            command.upgrade(cfg, "head")
        conn.execute(
            text(
                "INSERT INTO iw_core_instance (id, instance_id) "
                "SELECT 1, gen_random_uuid() "
                "WHERE NOT EXISTS (SELECT 1 FROM iw_core_instance WHERE id = 1)"
            )
        )
        conn.commit()


class TestDaemonStartupGate:
    """Tests that verify_instance_identity() behaves correctly for each mode."""

    def test_daemon_startup_proceeds_on_match(
        self, migrated_engine: Engine, identity_matched: None
    ) -> None:
        """When env matches DB row, verify_instance_identity does not raise."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            status = verify_instance_identity(session)
            assert status.mode == "match"
        finally:
            session.close()

    def test_daemon_startup_refuses_on_mismatch(
        self, migrated_engine: Engine, identity_mismatched: None
    ) -> None:
        """When env differs from DB row, verify_instance_identity raises."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            with pytest.raises(InstanceMismatchError):
                verify_instance_identity(session)
        finally:
            session.close()

    def test_daemon_startup_proceeds_on_bootstrap(
        self, migrated_engine: Engine, identity_unset: None
    ) -> None:
        """When env is unset and row exists, proceed in bootstrap mode."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            status = verify_instance_identity(session)
            assert status.mode == "bootstrap"
        finally:
            session.close()

    def test_daemon_startup_refuses_on_missing_row(
        self, migrated_engine: Engine, identity_matched: None
    ) -> None:
        """When env is set but row is missing, raise InstanceRowMissingError."""
        with migrated_engine.connect() as conn:
            conn.execute(text("DELETE FROM iw_core_instance"))
            conn.commit()

        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            with pytest.raises(InstanceRowMissingError):
                verify_instance_identity(session)
        finally:
            session.close()


class TestDashboardHealthzIdentity:
    """Tests for GET /healthz/identity endpoint.

    The dashboard lifespan calls verify_instance_identity via SessionLocal.
    To test this, we directly call check_identity with a session from
    migrated_engine, which is equivalent to what the healthz endpoint does.
    """

    @pytest.fixture(autouse=True)
    def ensure_instance_row(self, migrated_engine: Engine) -> None:
        """Ensure iw_core_instance row exists before each test.

        Previous tests (e.g. TestDaemonStartupGate) may have deleted this row.
        Restore it so this test class's fixtures see a consistent state.
        """
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
            ).fetchone()
            if result is None:
                conn.execute(
                    text(
                        "INSERT INTO iw_core_instance (id, instance_id) "
                        "SELECT 1, gen_random_uuid() "
                        "WHERE NOT EXISTS (SELECT 1 FROM iw_core_instance WHERE id = 1)"
                    )
                )
                conn.commit()

    @pytest.mark.smoke
    def test_healthz_identity_200_on_match(
        self,
        migrated_engine: Engine,
        identity_matched: None,
    ) -> None:
        """check_identity returns mode=match when env matches DB."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            from orch.db.identity import check_identity

            status = check_identity(session)
            assert status.mode == "match"
        finally:
            session.close()

    @pytest.mark.smoke
    def test_healthz_identity_503_on_mismatch(
        self,
        migrated_engine: Engine,
        identity_mismatched: None,
    ) -> None:
        """check_identity returns mode=mismatch when env differs from DB."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            from orch.db.identity import check_identity

            status = check_identity(session)
            assert status.mode == "mismatch"
        finally:
            session.close()

    @pytest.mark.smoke
    def test_healthz_identity_200_on_bootstrap(
        self,
        migrated_engine: Engine,
        identity_unset: None,
    ) -> None:
        """check_identity returns mode=bootstrap when env is unset."""
        session_factory = sessionmaker(bind=migrated_engine)
        session = session_factory()
        try:
            from orch.db.identity import check_identity

            status = check_identity(session)
            assert status.mode == "bootstrap"
        finally:
            session.close()


class TestMigrationRoundtrip:
    @pytest.mark.order_dependent
    @pytest.mark.xfail(
        strict=False,
        reason=(
            "Module-scoped migrated_engine is outside the conftest's per-test "
            "clone (R-00077); sibling tests in this module read/insert "
            "iw_core_instance and random intra-module order can leave "
            "uuid_before equal to uuid_after, failing the != assertion."
        ),
    )
    def test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid(
        self, migrated_engine: Engine
    ) -> None:
        """alembic downgrade -1 drops iw_core_instance; upgrade head re-creates with new UUID."""
        # NOTE(P1-CR-C-followup-randomly): module-scoped migrated_engine leak;
        # fix would scope-down to function or add explicit cleanup.
        cfg = Config()
        cfg.set_main_option("script_location", "orch/db/migrations")
        cfg.set_main_option(
            "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
        )

        with migrated_engine.connect() as conn:
            row_before = conn.execute(
                text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
            ).fetchone()
            assert row_before is not None
            uuid_before = row_before.instance_id

        # Target the revision before iw_core_instance so the test is stable
        # regardless of later migrations added on top.
        command.downgrade(cfg, "824e6e6f34ee")

        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_tables WHERE tablename = 'iw_core_instance'")
            )
            assert result.fetchone() is None, "Table should be dropped after downgrade"

        command.upgrade(cfg, "head")

        with migrated_engine.connect() as conn:
            row_after = conn.execute(
                text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
            ).fetchone()
            assert row_after is not None
            assert row_after.instance_id != uuid_before, (
                "New UUID should be generated on re-upgrade"
            )
