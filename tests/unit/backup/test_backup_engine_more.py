"""Additional engine unit coverage for F-00092 (S11).

Fills the gaps left by ``test_backup_engine.py`` (manifest fields + integrity
failure cleanup) with the Boundary Behavior rows that are pure-filesystem
concerns and need no live database:

- "Backup dir missing"      → engine creates it recursively before writing.
- "Globals file contains role password hashes" / Invariant 8
                            → set dir is ``0700`` and globals file ``0600``.
- "Backup dir disk full mid-dump" → a write failure partway through marks the
                            backup failed (re-raises) and removes the partial set
                            so it is never counted as a successful backup.

All tests inject ``command_runner`` / ``db_introspector`` / ``which_func`` /
``now_fn`` so they exercise the real engine logic without pg client tools and
without a database (no session passed → no DbBackupJob row).
"""

from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orch.backup.engine import create_backup
from orch.db.models import DbBackupType

_META: dict[str, Any] = {
    "alembic_revision": "abc123",
    "instance_id": "iid-1",
    "row_counts": {"projects": 2, "batches": 3, "work_items": 4},
    "server_version": "15.12",
    "server_major": 15,
}


def _config(backup_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        backup_dir=str(backup_dir),
        db_host="127.0.0.1",
        db_port=5544,
        db_name="iw_orch",
        db_user="iw_orch",
        db_password="secret",  # noqa: S106
    )


def _ok_runner(
    argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
) -> None:
    """A command runner that fakes successful pg_dump / pg_dumpall / pg_restore."""
    if "pg_dumpall" in argv[0]:
        assert output_path is not None
        output_path.write_text("-- globals: CREATE ROLE iw_orch PASSWORD 'SCRAM-...';\n")
    elif "pg_dump" in argv[0]:
        assert output_path is not None
        output_path.write_bytes(b"PGDMP-archive-bytes")
    elif "pg_restore" in argv[0]:
        return


def _make(backup_dir: Path, *, command_runner: Any) -> Any:
    return create_backup(
        _config(backup_dir),
        backup_type=DbBackupType.scheduled,
        command_runner=command_runner,
        db_introspector=lambda _cfg: dict(_META),
        now_fn=lambda: datetime(2026, 6, 1, 3, 0, 0, tzinfo=UTC),
        which_func=lambda name: f"/usr/bin/{name}",
    )


def test_backup_dir_created_recursively_when_missing(tmp_path: Path) -> None:
    """Boundary: ``IW_CORE_BACKUP_DIR`` does not exist → engine creates it."""
    missing = tmp_path / "deep" / "nested" / "backups"
    assert not missing.exists()

    result = _make(missing, command_runner=_ok_runner)

    assert result.backup_dir.exists()
    # The set dir is created *inside* the (now-created) backup_dir.
    assert result.backup_dir.parent == missing
    assert result.archive_path.exists()
    assert result.globals_path.exists()
    assert result.manifest_path.exists()


def test_globals_secrecy_permissions(tmp_path: Path) -> None:
    """Invariant 8: set dir is 0700 and the --globals-only file is 0600."""
    result = _make(tmp_path, command_runner=_ok_runner)

    dir_mode = stat.S_IMODE(result.backup_dir.stat().st_mode)
    globals_mode = stat.S_IMODE(result.globals_path.stat().st_mode)

    assert dir_mode == 0o700, f"set dir must be 0700, got {dir_mode:o}"
    assert globals_mode == 0o600, f"globals file must be 0600, got {globals_mode:o}"


def test_mid_dump_write_failure_reraises_and_cleans_partial_set(tmp_path: Path) -> None:
    """Boundary "disk full mid-dump": a write failure during pg_dump re-raises and
    the partial backup set is removed (not counted as a successful backup)."""

    def _failing_runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        if "pg_dump" in argv[0] and "pg_restore" not in argv[0]:
            # Simulate ENOSPC partway through writing the -Fc archive.
            raise OSError(28, "No space left on device")

    with pytest.raises(OSError, match="No space left on device"):
        _make(tmp_path, command_runner=_failing_runner)

    # The partial set directory must have been removed; nothing left behind that
    # a later "list / catch-up" could mistake for a successful backup.
    assert list(tmp_path.iterdir()) == []
