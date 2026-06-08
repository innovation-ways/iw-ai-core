"""Unit tests for the ``iw db-backup`` CLI group (F-00092 S09).

These tests exercise the CLI wiring (argument parsing, exit codes, engine
delegation, output shape) without touching a live database. The backup engine,
retention, and restore helpers themselves are covered by their own unit and
integration tests; here we only assert the CLI contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from click.testing import CliRunner

from orch.cli.backup_commands import db_backup
from orch.db.models import DbBackupStatus, DbBackupType


class _FakeScalarResult:
    """Stub for SQLAlchemy ScalarResult returned by session.scalars()."""

    def __init__(self, rows: list[Any]) -> None:
        """Args:
        rows: The rows to return from all().
        """
        self._rows = rows

    def all(self) -> list[Any]:
        """Returns the list of rows provided at construction.

        Returns:
            The list of row stubs.
        """
        return self._rows


class _FakeSession:
    """Stub SQLAlchemy session that returns pre-configured rows from scalars()."""

    def __init__(self, rows: list[Any]) -> None:
        """Args:
        rows: Rows to be returned by scalars().all().
        """
        self._rows = rows
        self.committed = False

    def scalars(self, _stmt: Any) -> _FakeScalarResult:
        """Returns a _FakeScalarResult wrapping the pre-configured rows.

        Args:
            _stmt: Ignored SQLAlchemy statement.

        Returns:
            A _FakeScalarResult containing the configured rows.
        """
        return _FakeScalarResult(self._rows)

    def commit(self) -> None:
        """Records that commit was called."""
        self.committed = True


def _session_factory(session: _FakeSession) -> Any:
    """Wrap a _FakeSession in a context-manager factory matching get_session interface.

    Args:
        session: The fake session to yield.

    Returns:
        A zero-argument context manager factory that yields the session.
    """

    @contextmanager
    def _cm() -> Any:
        yield session

    return _cm


def test_list_renders_recorded_backups() -> None:
    """Verifies that iw db-backup list renders all recorded backup fields in output."""
    rows = [
        SimpleNamespace(
            id="job-1",
            backup_type=DbBackupType.manual,
            label="pre-migration",
            status=DbBackupStatus.success,
            created_at="2026-06-01T03:00:00+00:00",
            bytes=2048,
            path="/opt/postgres/data/backups/20260601T030000Z",
        ),
    ]
    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["list"],
        obj={"get_session": _session_factory(_FakeSession(rows))},
    )

    assert result.exit_code == 0, result.output
    assert "manual" in result.output
    assert "pre-migration" in result.output
    assert "success" in result.output
    assert "/opt/postgres/data/backups/20260601T030000Z" in result.output


def test_list_empty_reports_no_backups() -> None:
    """Verifies that iw db-backup list reports a no-backups message when the table is empty."""
    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["list"],
        obj={"get_session": _session_factory(_FakeSession([]))},
    )

    assert result.exit_code == 0, result.output
    assert "No backups" in result.output


def test_list_reads_all_attrs_inside_session() -> None:
    """Regression: list must not access row attrs after the session has closed.

    The bug was that the rendering loop lived outside the
    ``with get_session()`` block, so reading lazy attributes like
    ``row.bytes`` triggered ``DetachedInstanceError`` on a real SQLAlchemy
    session. This test simulates that with a fake session that flips a
    "closed" flag on ``__exit__`` and rows whose attribute access raises
    once closed.
    """
    closed = {"flag": False}

    class _ClosingRow:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def __getattr__(self, name: str) -> Any:
            if closed["flag"]:
                raise RuntimeError(f"attribute {name!r} accessed after session close")
            return self._data[name]

    session = _FakeSession(
        [
            _ClosingRow(
                {
                    "id": "job-1",
                    "backup_type": DbBackupType.manual,
                    "label": "pre-migration",
                    "status": DbBackupStatus.success,
                    "created_at": "2026-06-01T03:00:00+00:00",
                    "bytes": 2048,
                    "path": "/opt/postgres/data/backups/20260601T030000Z",
                }
            ),
        ]
    )

    @contextmanager
    def _closing_session_factory() -> Any:
        try:
            yield session
        finally:
            closed["flag"] = True  # simulate SQLAlchemy session close on __exit__

    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["list"],
        obj={"get_session": _closing_session_factory},
    )

    assert result.exit_code == 0, result.output
    assert "pre-migration" in result.output
    assert "2048" in result.output
    # The "close" ran from the ``with`` block; reaching this point means
    # no row attribute was touched afterwards.
    assert closed["flag"] is True


def test_create_records_manual_backup(monkeypatch: Any) -> None:
    """Verifies that iw db-backup create delegates to the engine with backup_type=manual."""
    captured: dict[str, Any] = {}

    def fake_create_backup(
        config: Any, *, backup_type: Any, label: Any = None, **kwargs: Any
    ) -> Any:
        captured["backup_type"] = backup_type
        captured["label"] = label
        return SimpleNamespace(backup_dir=Path("/opt/backups/set"), total_bytes=4096)

    monkeypatch.setattr("orch.cli.backup_commands.create_backup", fake_create_backup)
    monkeypatch.setattr(
        "orch.cli.backup_commands.load_config",
        lambda: SimpleNamespace(backup_enabled=True),
    )

    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["create", "--label", "pre-migration"],
        obj={"get_session": _session_factory(_FakeSession([]))},
    )

    assert result.exit_code == 0, result.output
    assert captured["backup_type"] == DbBackupType.manual
    assert captured["label"] == "pre-migration"
    assert "/opt/backups/set" in result.output


def test_restore_refuses_prod_without_allow_prod(monkeypatch: Any, tmp_path: Path) -> None:
    """Verifies that iw db-backup restore exits with code 2 and REFUSED when targeting."""
    monkeypatch.setattr(
        "orch.cli.backup_commands.load_config",
        lambda: SimpleNamespace(
            db_host="127.0.0.1",
            db_port=5433,
            db_name="iw_orch",
            db_user="iw_orch",
            db_password="secret",  # noqa: S106
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["restore", "--from", str(tmp_path), "--target", "iw_orch"],
        obj={},
    )

    assert result.exit_code == 2, result.output
    assert "REFUSED" in result.output
