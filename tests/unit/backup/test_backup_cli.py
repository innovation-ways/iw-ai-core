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
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.committed = False

    def scalars(self, _stmt: Any) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)

    def commit(self) -> None:
        self.committed = True


def _session_factory(session: _FakeSession) -> Any:
    @contextmanager
    def _cm() -> Any:
        yield session

    return _cm


def test_list_renders_recorded_backups() -> None:
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
    runner = CliRunner()
    result = runner.invoke(
        db_backup,
        ["list"],
        obj={"get_session": _session_factory(_FakeSession([]))},
    )

    assert result.exit_code == 0, result.output
    assert "No backups" in result.output


def test_create_records_manual_backup(monkeypatch: Any) -> None:
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
