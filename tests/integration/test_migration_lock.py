"""Integration tests for migration-lock CLI commands.

Verifies atomic acquire/release semantics using a real PostgreSQL testcontainer.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import MigrationLock, Project

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def project_with_lock(db_session: Session) -> Project:
    """Insert a Project + migration_locks row (unlocked)."""
    project = Project(
        id="lock-proj",
        display_name="Lock Test Project",
        repo_root="/repos/lock-proj",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    lock = MigrationLock(project_id="lock-proj", current_holder=None)
    db_session.add(lock)
    db_session.flush()

    return project


def _runner(db_session: Session) -> tuple[CliRunner, Callable[[], contextmanager]]:  # type: ignore[type-arg]
    @contextmanager  # type: ignore[arg-type]
    def get_session() -> Generator[Session, None, None]:
        yield db_session

    return CliRunner(), get_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_acquire_when_free(project_with_lock: Project, db_session: Session) -> None:
    """Acquiring a free lock succeeds and sets the holder."""
    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "acquire", "I001", "--branch", "agent/I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 0, result.output
    assert "acquired for I001" in result.output

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    assert lock.current_holder == "I001"
    assert lock.branch == "agent/I001"
    assert lock.locked_at is not None


def test_acquire_when_held_returns_error(project_with_lock: Project, db_session: Session) -> None:
    """Acquiring a held lock exits with code 4 and reports the current holder."""
    # Manually set the lock
    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    from datetime import UTC, datetime

    lock.current_holder = "I003"
    lock.locked_at = datetime(2026, 4, 7, 10, 30, 0, tzinfo=UTC)
    db_session.flush()

    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "acquire", "I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 4
    assert "I003" in result.output


def test_acquire_held_json_output(project_with_lock: Project, db_session: Session) -> None:
    """JSON error output includes error message and code 4 for a held lock."""
    import json as json_mod
    from datetime import UTC, datetime

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    lock.current_holder = "I003"
    lock.locked_at = datetime(2026, 4, 7, 10, 30, 0, tzinfo=UTC)
    db_session.flush()

    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--json", "--project", "lock-proj", "migration-lock", "acquire", "I001"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 4
    data = json_mod.loads(result.output)
    assert data["code"] == 4
    assert "I003" in data["error"]


def test_release_when_holder_matches(project_with_lock: Project, db_session: Session) -> None:
    """Releasing a lock as the current holder sets current_holder to NULL."""
    from datetime import UTC, datetime

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    lock.current_holder = "I001"
    lock.locked_at = datetime.now(UTC)
    db_session.flush()

    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "release", "I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 0, result.output
    assert "released" in result.output

    db_session.refresh(lock)
    assert lock.current_holder is None
    assert lock.locked_at is None


def test_release_when_holder_does_not_match(
    project_with_lock: Project, db_session: Session
) -> None:
    """Releasing a lock held by another item exits with code 4."""
    from datetime import UTC, datetime

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    lock.current_holder = "I003"
    lock.locked_at = datetime.now(UTC)
    db_session.flush()

    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "release", "I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 4
    assert "I003" in result.output


def test_status_free(project_with_lock: Project, db_session: Session) -> None:
    """Status shows 'free' when no holder is set."""
    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "status"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 0, result.output
    assert "free" in result.output


def test_status_held(project_with_lock: Project, db_session: Session) -> None:
    """Status shows holder info when lock is held."""
    from datetime import UTC, datetime

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    lock.current_holder = "I005"
    lock.branch = "agent/I005-branch"
    lock.locked_at = datetime(2026, 4, 7, 10, 30, 0, tzinfo=UTC)
    db_session.flush()

    runner, get_session = _runner(db_session)
    result = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "status"],
        obj={"get_session": get_session, "json": False},
    )
    assert result.exit_code == 0, result.output
    assert "I005" in result.output
    assert "agent/I005-branch" in result.output


def test_sequential_acquire_after_release(project_with_lock: Project, db_session: Session) -> None:
    """After releasing, a new holder can acquire the lock."""
    runner, get_session = _runner(db_session)

    # First acquire
    r1 = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "acquire", "I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert r1.exit_code == 0

    # Release
    r2 = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "release", "I001"],
        obj={"get_session": get_session, "json": False},
    )
    assert r2.exit_code == 0

    # Second holder acquires
    r3 = runner.invoke(
        cli,
        ["--project", "lock-proj", "migration-lock", "acquire", "I002"],
        obj={"get_session": get_session, "json": False},
    )
    assert r3.exit_code == 0

    lock = db_session.get(MigrationLock, "lock-proj")
    assert lock is not None
    assert lock.current_holder == "I002"
