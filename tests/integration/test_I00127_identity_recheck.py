# ruff: noqa: N999

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import select

from orch.config import DaemonConfig
from orch.daemon.main import Daemon, OrchDbIdentityChanged
from orch.db.models import DaemonEvent, IwCoreInstance


@contextmanager
def _session_factory_from_sessionmaker(db_session_factory):
    session = db_session_factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def _make_config(tmp_path: Path, db_url: str) -> DaemonConfig:
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url=db_url,
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=0,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def test_I00127_daemon_halts_when_identity_changes_mid_run(  # noqa: N802
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with db_session_factory() as session:
        row = session.get(IwCoreInstance, 1)
        assert row is not None
        bound_id = row.instance_id
        monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(bound_id))

    daemon = Daemon(
        _make_config(tmp_path, "postgresql+psycopg://unused"),
        session_factory=lambda: _session_factory_from_sessionmaker(db_session_factory),
    )

    monkeypatch.setattr(daemon, "_setup_signal_handlers", lambda: None)
    monkeypatch.setattr(daemon, "_load_projects", lambda: None)
    monkeypatch.setattr(daemon, "_startup_health_check", lambda: None)
    monkeypatch.setattr(daemon, "_reap_orphan_containers", lambda: None)
    monkeypatch.setattr(daemon, "_reattach_worktrees", lambda: None)
    monkeypatch.setattr("orch.daemon.main._alembic_guard_startup", lambda *_: None)

    calls = {"count": 0}

    def _poll_flip_identity() -> None:
        calls["count"] += 1
        with db_session_factory() as session:
            row = session.get(IwCoreInstance, 1)
            assert row is not None
            row.instance_id = uuid.uuid4()
            session.commit()

    monkeypatch.setattr(daemon, "_poll_cycle", _poll_flip_identity)

    with pytest.raises(OrchDbIdentityChanged):
        daemon.run()

    assert calls["count"] == 1, "daemon must halt at loop boundary before next poll"

    with db_session_factory() as session:
        event = session.scalar(
            select(DaemonEvent)
            .where(DaemonEvent.event_type == "db_identity_changed")
            .order_by(DaemonEvent.id.desc())
        )

    assert event is not None
    assert event.event_metadata["bound_instance_id"] == str(bound_id)
    assert event.event_metadata["live_instance_id"] != str(bound_id)
    assert event.event_metadata["mode"] == "changed"


def test_I00127_daemon_keeps_polling_when_identity_matches(  # noqa: N802
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with db_session_factory() as session:
        row = session.get(IwCoreInstance, 1)
        assert row is not None
        monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(row.instance_id))

    daemon = Daemon(
        _make_config(tmp_path, "postgresql+psycopg://unused"),
        session_factory=lambda: _session_factory_from_sessionmaker(db_session_factory),
    )

    monkeypatch.setattr(daemon, "_setup_signal_handlers", lambda: None)
    monkeypatch.setattr(daemon, "_load_projects", lambda: None)
    monkeypatch.setattr(daemon, "_startup_health_check", lambda: None)
    monkeypatch.setattr(daemon, "_reap_orphan_containers", lambda: None)
    monkeypatch.setattr(daemon, "_reattach_worktrees", lambda: None)
    monkeypatch.setattr("orch.daemon.main._alembic_guard_startup", lambda *_: None)

    calls = {"count": 0}

    def _poll_twice_then_stop() -> None:
        calls["count"] += 1
        if calls["count"] >= 2:
            daemon._running = False

    monkeypatch.setattr(daemon, "_poll_cycle", _poll_twice_then_stop)

    daemon.run()
    assert calls["count"] == 2

    with db_session_factory() as session:
        event = session.scalar(
            select(DaemonEvent).where(DaemonEvent.event_type == "db_identity_changed")
        )
    assert event is None


def test_I00127_daemon_halts_when_identity_row_absent_and_pin_set(  # noqa: N802
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with db_session_factory() as session:
        row = session.get(IwCoreInstance, 1)
        assert row is not None
        bound_id = row.instance_id
        monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(bound_id))

    daemon = Daemon(
        _make_config(tmp_path, "postgresql+psycopg://unused"),
        session_factory=lambda: _session_factory_from_sessionmaker(db_session_factory),
    )

    monkeypatch.setattr(daemon, "_setup_signal_handlers", lambda: None)
    monkeypatch.setattr(daemon, "_load_projects", lambda: None)
    monkeypatch.setattr(daemon, "_startup_health_check", lambda: None)
    monkeypatch.setattr(daemon, "_reap_orphan_containers", lambda: None)
    monkeypatch.setattr(daemon, "_reattach_worktrees", lambda: None)
    monkeypatch.setattr("orch.daemon.main._alembic_guard_startup", lambda *_: None)

    calls = {"count": 0}

    def _poll_delete_identity_row() -> None:
        calls["count"] += 1
        with db_session_factory() as session:
            row = session.get(IwCoreInstance, 1)
            assert row is not None
            session.delete(row)
            session.commit()

    monkeypatch.setattr(daemon, "_poll_cycle", _poll_delete_identity_row)

    with pytest.raises(OrchDbIdentityChanged):
        daemon.run()

    assert calls["count"] == 1, "daemon must halt at loop boundary before next poll"

    with db_session_factory() as session:
        event = session.scalar(
            select(DaemonEvent)
            .where(DaemonEvent.event_type == "db_identity_changed")
            .order_by(DaemonEvent.id.desc())
        )

    assert event is not None
    assert event.event_metadata["bound_instance_id"] == str(bound_id)
    assert event.event_metadata["live_instance_id"] is None
    assert event.event_metadata["mode"] == "missing_while_pinned"
