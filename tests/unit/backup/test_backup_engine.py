"""Unit tests for the backup engine config fields and core create_backup behavior (F-00092)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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
    monkeypatch.delenv("IW_CORE_BACKUP_DB_USER", raising=False)
    monkeypatch.delenv("IW_CORE_BACKUP_DB_PASSWORD", raising=False)

    config = cfg.load_config()

    assert config.backup_enabled is True
    assert config.backup_dir == "/opt/postgres/data/backups"
    assert config.backup_retention_days == 30
    assert config.backup_time == "03:00"
    assert config.backup_db_user is None
    assert config.backup_db_password is None


def test_backup_config_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies that backup config values are overridden when environment variables are set."""
    _set_base_env(monkeypatch)
    monkeypatch.setenv("IW_CORE_BACKUP_ENABLED", "false")
    monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("IW_CORE_BACKUP_RETENTION_DAYS", "7")
    monkeypatch.setenv("IW_CORE_BACKUP_TIME", "01:15")
    monkeypatch.setenv("IW_CORE_BACKUP_DB_USER", "postgres")
    monkeypatch.setenv("IW_CORE_BACKUP_DB_PASSWORD", "super-secret")

    config = cfg.load_config()

    assert config.backup_enabled is False
    assert config.backup_dir == str(tmp_path / "backups")
    assert config.backup_retention_days == 7
    assert config.backup_time == "01:15"
    assert config.backup_db_user == "postgres"
    assert config.backup_db_password == "super-secret"  # noqa: S105


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


class TestDockerToolRefParsing:
    """Covers the Docker-fallback argv construction when host pg client tools are absent."""

    _CONFIG = SimpleNamespace(db_host="localhost", db_port=5433, db_user="iw_orch")

    def test_resolve_tools_emits_colon_bearing_image_ref(self) -> None:
        """Verifies the docker fallback ref preserves the full colon-bearing image name."""
        from orch.backup.engine import _resolve_tools

        tools = _resolve_tools(lambda _name: None, server_major=15)

        assert tools["pg_dump"] == "docker:postgres:15-alpine:pg_dump"

    def test_db_tool_argv_runs_binary_not_image_suffix(self) -> None:
        """Verifies the docker argv targets image postgres:15-alpine and binary pg_dump.

        Regression for the scheduled-backup exit-127 failure: ``split(":", 2)`` mis-parsed
        the colon in the image name, so docker ran a bogus ``15-alpine:pg_dump`` command.
        """
        from orch.backup.engine import _argv_for_db_tool

        argv = _argv_for_db_tool("docker:postgres:15-alpine:pg_dump", self._CONFIG)

        run_index = argv.index("run")
        # The two positional args after the flags are <image> then <binary>.
        assert "postgres:15-alpine" in argv
        image_index = argv.index("postgres:15-alpine")
        assert argv[image_index + 1] == "pg_dump"
        assert run_index < image_index
        assert "15-alpine:pg_dump" not in argv

    def test_restore_list_argv_runs_binary_not_image_suffix(self, tmp_path: Path) -> None:
        """Verifies the pg_restore --list docker argv parses image and binary correctly."""
        from orch.backup.engine import _argv_for_restore_list

        archive = tmp_path / "iw_orch.dump"
        argv = _argv_for_restore_list("docker:postgres:15-alpine:pg_restore", archive)

        image_index = argv.index("postgres:15-alpine")
        assert argv[image_index + 1] == "pg_restore"
        assert argv[argv.index("--list") + 1] == str(archive)
        assert "15-alpine:pg_restore" not in argv

    def test_restore_list_docker_argv_mounts_archive_parent_dir(self, tmp_path: Path) -> None:
        """Verifies the docker --list invocation bind-mounts the host archive directory.

        Regression: without the mount, ``pg_restore`` inside the container
        sees the literal host path and fails with ``No such file or
        directory`` even when the file is right there on the host. Mounting
        the parent dir at the same path keeps the in-container and host
        paths identical so the existing argv works as-is.
        """
        from orch.backup.engine import _argv_for_restore_list

        archive = tmp_path / "iw_orch.dump"
        argv = _argv_for_restore_list("docker:postgres:15-alpine:pg_restore", archive)

        assert "-v" in argv
        v_index = argv.index("-v")
        mount = argv[v_index + 1]
        expected = f"{archive.parent.resolve()}:{archive.parent.resolve()}"
        assert mount == expected

    def test_restore_list_host_binary_argv_has_no_volume_mount(self, tmp_path: Path) -> None:
        """Verifies the host-binary fallback does not add a docker -v flag.

        When pg_restore is a real host binary, no docker volume mount is
        needed (the binary reads the host file directly).
        """
        from orch.backup.engine import _argv_for_restore_list

        archive = tmp_path / "iw_orch.dump"
        argv = _argv_for_restore_list("/usr/bin/pg_restore", archive)

        assert "-v" not in argv
        assert argv == ["/usr/bin/pg_restore", "--list", str(archive)]

    def test_host_binary_path_is_passed_through_unchanged(self) -> None:
        """Verifies a plain host-binary path is used directly without docker wrapping."""
        from orch.backup.engine import _argv_for_db_tool

        argv = _argv_for_db_tool("/usr/bin/pg_dump", self._CONFIG)

        assert argv[0] == "/usr/bin/pg_dump"
        assert "docker" not in argv

    def test_user_override_replaces_connection_role(self) -> None:
        """Verifies the optional user override drives the -U flag for the globals dump."""
        from orch.backup.engine import _argv_for_db_tool

        argv = _argv_for_db_tool("/usr/bin/pg_dumpall", self._CONFIG, user="postgres")

        assert argv[argv.index("-U") + 1] == "postgres"


def _user_of(argv: list[str]) -> str:
    """Return the value following the ``-U`` flag in a pg-tool argv.

    Args:
        argv: The argument vector passed to the command runner.

    Returns:
        The connection role name supplied via ``-U``.
    """
    return argv[argv.index("-U") + 1]


class TestGlobalsSuperuser:
    """Covers the separate-superuser path for pg_dumpall --globals-only (pg_authid access)."""

    @staticmethod
    def _capturing_runner(
        calls: list[tuple[list[str], dict[str, str]]],
    ) -> object:
        """Build a command_runner that records (argv, env) and writes dump artifacts.

        Args:
            calls: Mutable list each invocation's (argv, env) pair is appended to.

        Returns:
            A command_runner callable compatible with create_backup.
        """

        def _runner(
            argv: list[str],
            *,
            output_path: Path | None = None,
            _env: dict[str, str] | None = None,
        ) -> None:
            calls.append((argv, dict(_env or {})))
            if "pg_dumpall" in argv[0]:
                assert output_path is not None
                output_path.write_text("-- globals")
            elif "pg_dump" in argv[0]:
                assert output_path is not None
                output_path.write_bytes(b"archive-bytes")

        return _runner

    _META = {
        "alembic_revision": "abc123",
        "instance_id": "iid-1",
        "row_counts": {"projects": 1, "batches": 1, "work_items": 1},
        "server_version": "15.12",
        "server_major": 15,
    }

    def test_globals_dump_uses_superuser_when_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verifies the globals dump runs as the backup superuser with its own password."""
        from orch.backup.engine import create_backup

        _set_base_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path))
        monkeypatch.setenv("IW_CORE_BACKUP_DB_USER", "postgres")
        monkeypatch.setenv("IW_CORE_BACKUP_DB_PASSWORD", "super-secret")
        config = cfg.load_config()

        calls: list[tuple[list[str], dict[str, str]]] = []
        create_backup(
            config,
            backup_type=DbBackupType.scheduled,
            command_runner=self._capturing_runner(calls),
            db_introspector=lambda _cfg: self._META,
            now_fn=lambda: datetime(2026, 6, 1, 3, 0, 0, tzinfo=UTC),
            which_func=lambda name: f"/usr/bin/{name}",
        )

        dump = next(a for a, _ in calls if "pg_dumpall" not in a[0] and "pg_dump" in a[0])
        globals_call = next((a, e) for a, e in calls if "pg_dumpall" in a[0])
        globals_argv, globals_env = globals_call

        assert _user_of(dump) == "iw_orch"
        assert _user_of(globals_argv) == "postgres"
        assert globals_env["PGPASSWORD"] == "super-secret"

    def test_globals_dump_falls_back_to_app_role_when_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verifies the globals dump uses the app role when no backup superuser is configured."""
        from orch.backup.engine import create_backup

        _set_base_env(monkeypatch)
        monkeypatch.setenv("IW_CORE_BACKUP_DIR", str(tmp_path))
        monkeypatch.delenv("IW_CORE_BACKUP_DB_USER", raising=False)
        monkeypatch.delenv("IW_CORE_BACKUP_DB_PASSWORD", raising=False)
        config = cfg.load_config()

        calls: list[tuple[list[str], dict[str, str]]] = []
        create_backup(
            config,
            backup_type=DbBackupType.scheduled,
            command_runner=self._capturing_runner(calls),
            db_introspector=lambda _cfg: self._META,
            now_fn=lambda: datetime(2026, 6, 1, 3, 0, 0, tzinfo=UTC),
            which_func=lambda name: f"/usr/bin/{name}",
        )

        globals_argv, globals_env = next((a, e) for a, e in calls if "pg_dumpall" in a[0])

        assert _user_of(globals_argv) == "iw_orch"
        assert globals_env["PGPASSWORD"] == "secret"
