"""Unit tests for the backup engine config fields and core create_backup behavior (F-00092)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import orch.config as cfg
from orch.db.models import DbBackupType

_VALID_ENV: dict[str, str] = {
    "IW_CORE_DB_HOST": "127.0.0.1",
    "IW_CORE_DB_PORT": "5544",
    "IW_CORE_DB_NAME": "iw_orch",
    "IW_CORE_DB_USER": "iw_orch",
    "IW_CORE_DB_PASSWORD": "secret",  # noqa: S105
    "IW_CORE_DASHBOARD_HOST": "127.0.0.1",
    "IW_CORE_DASHBOARD_PORT": "9901",
    "IW_CORE_POLL_INTERVAL": "30",
    "IW_CORE_STALL_THRESHOLD": "300",
    "IW_CORE_PID_FILE": "/tmp/test-daemon.pid",  # noqa: S108
    "IW_CORE_ARCHIVE_DIR": "/tmp/test-archive",  # noqa: S108
    "IW_CORE_ARCHIVE_TTL": "90",
    "IW_CORE_LOG_LEVEL": "DEBUG",
    "IW_CORE_LOG_FILE": "/tmp/test-daemon.log",  # noqa: S108
}


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply the minimal valid environment required to call cfg.load_config().

    Args:
        monkeypatch: pytest monkeypatch fixture used to set environment variables.
    """
    for key, value in _VALID_ENV.items():
        monkeypatch.setenv(key, value)


def test_backup_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that backup config defaults are applied when environment variables are absent."""
    _set_base_env(monkeypatch)
    monkeypatch.delenv("IW_CORE_BACKUP_ENABLED", raising=False)
    monkeypatch.delenv("IW_CORE_BACKUP_DIR", raising=False)
    monkeypatch.delenv("IW_CORE_BACKUP_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("IW_CORE_BACKUP_TIME", raising=False)

    config = cfg.load_config()

    assert config.backup_enabled is True
    assert config.backup_dir == "/opt/postgres/data/backups"
    assert config.backup_retention_days == 30
    assert config.backup_time == "03:00"


def test_backup_config_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies that backup config values are overridden when environment variables are set."""
    _set_base_env(monkeypatch)
    monkeypatch.setenv("IW_CORE_BACKUP_ENABLED", "false")
    monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("IW_CORE_BACKUP_RETENTION_DAYS", "7")
    monkeypatch.setenv("IW_CORE_BACKUP_TIME", "01:15")

    config = cfg.load_config()

    assert config.backup_enabled is False
    assert config.backup_dir == str(tmp_path / "backups")
    assert config.backup_retention_days == 7
    assert config.backup_time == "01:15"


def test_manifest_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies that the backup manifest is populated with correct metadata fields."""
    from orch.backup.engine import create_backup

    _set_base_env(monkeypatch)
    monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path))
    config = cfg.load_config()

    def _runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        if "pg_dumpall" in argv[0]:
            assert output_path is not None
            output_path.write_text("-- globals")
        elif "pg_dump" in argv[0]:
            assert output_path is not None
            output_path.write_bytes(b"archive-bytes")
        elif "pg_restore" in argv[0]:
            return

    result = create_backup(
        config,
        backup_type=DbBackupType.manual,
        label="pre-migration",
        command_runner=_runner,
        db_introspector=lambda _cfg: {
            "alembic_revision": "abc123",
            "instance_id": "iid-1",
            "row_counts": {"projects": 2, "batches": 3, "work_items": 4},
            "server_version": "15.12",
            "server_major": 15,
        },
        now_fn=lambda: datetime(2026, 6, 1, 3, 0, 0, tzinfo=UTC),
        which_func=lambda name: f"/usr/bin/{name}",
    )

    assert result.manifest["backup_type"] == "manual"
    assert result.manifest["label"] == "pre-migration"
    assert result.manifest["alembic_revision"] == "abc123"
    assert result.manifest["instance_id"] == "iid-1"
    assert result.manifest["row_counts"] == {"projects": 2, "batches": 3, "work_items": 4}
    assert result.manifest["postgres_server_version"] == "15.12"


def test_integrity_check_failure_cleans_partial_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies that a failed integrity check removes the partial backup set entirely."""
    from orch.backup.engine import BackupIntegrityError, create_backup

    _set_base_env(monkeypatch)
    monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path))
    config = cfg.load_config()

    def _runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        if "pg_dumpall" in argv[0]:
            assert output_path is not None
            output_path.write_text("-- globals")
        elif "pg_dump" in argv[0]:
            assert output_path is not None
            output_path.write_bytes(b"garbage")
        elif "pg_restore" in argv[0]:
            raise RuntimeError("invalid archive")

    with pytest.raises(BackupIntegrityError):
        create_backup(
            config,
            backup_type=DbBackupType.scheduled,
            command_runner=_runner,
            db_introspector=lambda _cfg: {
                "alembic_revision": "abc123",
                "instance_id": "iid-1",
                "row_counts": {"projects": 2, "batches": 3, "work_items": 4},
                "server_version": "15.12",
                "server_major": 15,
            },
            now_fn=lambda: datetime(2026, 6, 1, 3, 0, 0, tzinfo=UTC),
            which_func=lambda name: f"/usr/bin/{name}",
        )

    assert list(tmp_path.iterdir()) == []
