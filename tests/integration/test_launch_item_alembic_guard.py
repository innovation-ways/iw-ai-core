"""Integration test for _launch_item alembic guard — testcontainer roundtrip.

Verifies that when the DB is behind head, _launch_item sets the BatchItem
to setup_failed with clear notes, emits a DaemonEvent, and does NOT
create a worktree directory.

Uses mock to inject a stale GuardStatus so we don't need to actually
downgrade the testcontainer (which can fail due to alembic graph walk
incompatibility with the downgraded revision).
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


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


def _get_current_rev(engine: Engine) -> str:
    """Read the current alembic_version from the DB."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else ""


def _run_alembic_upgrade_head(engine: Engine) -> None:
    """Run alembic upgrade head."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")


def _make_project(db: Session) -> None:
    """Ensure a minimal project exists so foreign-key constraints pass."""
    existing = db.query(Project).filter_by(id="test-proj").first()
    if not existing:
        db.add(
            Project(
                id="test-proj",
                display_name="Test Project",
                repo_root="/repos/test",
                config={},
            )
        )
        db.flush()


def _make_work_item(db: Session, item_id: str) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Test Item {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def _make_batch(db: Session, batch_id: str, status: BatchStatus = BatchStatus.approved) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


def _make_batch_item(
    db: Session,
    batch_id: str,
    work_item_id: str,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> BatchItem:
    item = BatchItem(
        project_id="test-proj",
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=0,
        status=status,
    )
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestLaunchItemAlembicGuard:
    def test_launch_item_setup_failed_when_db_behind_head(
        self,
        migrated_engine: Engine,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_launch_item sets setup_failed, notes, DaemonEvent, and no worktree
        dir when DB behind head.

        Uses mock to inject a stale GuardStatus (current_rev != head_rev) so the
        alembic guard triggers at the start of _launch_item.
        """
        url = migrated_engine.url.render_as_string(hide_password=False)

        # Ensure project exists
        _make_project(db_session)

        # Create WorkItem and Batch with one pending BatchItem
        _make_work_item(db_session, "WI-00001")
        _make_batch(db_session, "B-00001", BatchStatus.approved)
        batch_item = _make_batch_item(db_session, "B-00001", "WI-00001")
        db_session.commit()

        worktrees_dir = tmp_path / "worktrees"
        worktrees_dir.mkdir()

        project_config = ProjectConfig(
            id="test-proj",
            display_name="Test Project",
            repo_root="/repos/test",
            enabled=True,
            cli_tool="opencode",
            worktree_base=str(worktrees_dir),
            config={},
        )

        @contextmanager
        def session_factory():
            yield db_session

        from orch.config import DaemonConfig

        daemon_config = DaemonConfig(
            db_host="localhost",
            db_port=int(migrated_engine.url.port or 5432),
            db_name=migrated_engine.url.database or "test",
            db_user=str(migrated_engine.url.username or "test"),
            db_password=str(migrated_engine.url.password or "test"),
            db_url=url,
            dashboard_host="127.0.0.1",
            dashboard_port=9900,
            poll_interval=60,
            stall_threshold=600,
            pid_file=str(tmp_path / "daemon.pid"),
            archive_dir=str(tmp_path / "archive"),
            archive_ttl=90,
            log_level="DEBUG",
            log_file=str(tmp_path / "daemon.log"),
            projects_toml=str(tmp_path / "projects.toml"),
        )

        # Set env vars so is_live_db_url returns True (testcontainer matches env)
        # and IW_CORE_DAEMON_CONTEXT=true bypasses live-db-guard refusal
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", str(migrated_engine.url.port or 5432))
        monkeypatch.setenv("IW_CORE_DB_NAME", migrated_engine.url.database or "test")
        monkeypatch.setenv("IW_CORE_DB_USER", str(migrated_engine.url.username or "test"))
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", str(migrated_engine.url.password or "test"))
        monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")

        current_rev = _get_current_rev(migrated_engine)
        stale_head_rev = "ab" + current_rev[2:] if len(current_rev) > 2 else "bbbb"

        from orch.db.alembic_guard import GuardStatus

        stale_status = GuardStatus(
            current_rev=current_rev,
            head_rev=stale_head_rev,
            pending=[stale_head_rev],
            multiple_heads=[],
            ok=False,
        )

        check_mock = MagicMock(return_value=stale_status)

        manager = BatchManager(
            project_id="test-proj",
            project_config=project_config,
            session_factory=session_factory,
            config=daemon_config,
        )

        # Clear any stale events from manager creation
        db_session.query(DaemonEvent).delete()
        db_session.commit()

        # Mock worktree_compose.has_iw_config to return False (no iw-config dir)
        # and check_db_at_head to return the stale status
        with (
            patch(
                "orch.daemon.batch_manager.worktree_compose.has_iw_config",
                return_value=False,
            ),
            patch("orch.daemon.batch_manager.check_db_at_head", check_mock),
        ):
            manager._launch_item(db_session, batch_item)
            # _emit_event does not commit — DaemonEvent rows are added to the
            # session but not committed until the next poll cycle.
            # We commit explicitly here so the test can query them.
            db_session.commit()

        db_session.refresh(batch_item)

        assert batch_item.status == BatchItemStatus.setup_failed, (
            f"Expected status=setup_failed, got {batch_item.status}"
        )

        # R2: batch_item.notes contains current_rev, head_rev, and 'make db-migrate'
        notes = batch_item.notes or ""
        assert current_rev in notes, f"current_rev '{current_rev}' not in notes: {notes}"
        assert stale_head_rev in notes, f"head_rev '{stale_head_rev}' not in notes: {notes}"
        assert "make db-migrate" in notes, f"'make db-migrate' not in notes: {notes}"

        # R3: No worktree directory created
        worktree_path = worktrees_dir / str(batch_item.id)
        assert not worktree_path.exists(), f"Worktree directory should NOT exist at {worktree_path}"

        # R4: DaemonEvent emitted with phase=alembic_guard and reason=db_behind_head
        events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.event_type == "item_failed",
                DaemonEvent.entity_id == "WI-00001",
            )
            .all()
        )

        alembic_events = [
            e
            for e in events
            if e.event_metadata and e.event_metadata.get("phase") == "alembic_guard"
        ]
        assert len(alembic_events) >= 1, (
            f"Expected at least one DaemonEvent with phase=alembic_guard, "
            f"got events: {[(e.event_type, e.event_metadata) for e in events]}"
        )
        evt = alembic_events[0]
        assert evt.event_metadata["reason"] == "db_behind_head", (
            f"Expected reason=db_behind_head, got {evt.event_metadata}"
        )
        assert evt.event_metadata["current_rev"] == current_rev
        assert evt.event_metadata["head_rev"] == stale_head_rev
