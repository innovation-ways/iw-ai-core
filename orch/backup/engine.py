from __future__ import annotations

import json
import logging
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

from sqlalchemy import create_engine, text

from orch.db.models import DbBackupJob, DbBackupStatus, DbBackupType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CommandRunner(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        output_path: Path | None = None,
        _env: dict[str, str] | None = None,
    ) -> None: ...


class BackupError(RuntimeError):
    pass


class BackupIntegrityError(BackupError):
    pass


@dataclass(frozen=True)
class BackupResult:
    backup_dir: Path
    archive_path: Path
    globals_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    total_bytes: int
    server_version: str


def _run_cmd(
    argv: list[str],
    *,
    output_path: Path | None,
    env: dict[str, str],
    command_runner: CommandRunner | None,
) -> None:
    if command_runner is not None:
        command_runner(argv, output_path=output_path, _env=env)
        return
    if output_path is None:
        subprocess.run(argv, check=True, env=env)  # noqa: S603
        return
    with output_path.open("wb") as file_handle:
        subprocess.run(argv, check=True, env=env, stdout=file_handle)  # noqa: S603


def _resolve_db_metadata(config: Any) -> dict[str, Any]:
    engine = create_engine(config.db_url)
    try:
        with engine.connect() as conn:
            alembic_revision = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            instance_id = conn.execute(
                text("SELECT instance_id::text FROM iw_core_instance WHERE id = 1")
            ).scalar()
            projects = conn.execute(text("SELECT COUNT(*) FROM projects")).scalar_one()
            batches = conn.execute(text("SELECT COUNT(*) FROM batches")).scalar_one()
            work_items = conn.execute(text("SELECT COUNT(*) FROM work_items")).scalar_one()
            server_version = conn.execute(text("SHOW server_version")).scalar_one()
            server_version_num = int(conn.execute(text("SHOW server_version_num")).scalar_one())
    finally:
        engine.dispose()
    return {
        "alembic_revision": str(alembic_revision) if alembic_revision is not None else None,
        "instance_id": str(instance_id) if instance_id is not None else None,
        "row_counts": {
            "projects": int(projects),
            "batches": int(batches),
            "work_items": int(work_items),
        },
        "server_version": str(server_version),
        "server_major": server_version_num // 10000,
    }


def _resolve_tools(which_func: Callable[[str], str | None], server_major: int) -> dict[str, str]:
    host_tools = {
        "pg_dump": which_func("pg_dump"),
        "pg_dumpall": which_func("pg_dumpall"),
        "pg_restore": which_func("pg_restore"),
    }
    if all(host_tools.values()):
        return {key: str(value) for key, value in host_tools.items()}
    image = f"postgres:{server_major}-alpine"
    return {
        "pg_dump": f"docker:{image}:pg_dump",
        "pg_dumpall": f"docker:{image}:pg_dumpall",
        "pg_restore": f"docker:{image}:pg_restore",
    }


def _argv_for_db_tool(tool_ref: str, config: Any) -> list[str]:
    if not tool_ref.startswith("docker:"):
        return [
            tool_ref,
            "-h",
            config.db_host,
            "-p",
            str(config.db_port),
            "-U",
            config.db_user,
        ]
    _, image, binary = tool_ref.split(":", 2)
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-e",
        "PGPASSWORD",
        image,
        binary,
        "-h",
        config.db_host,
        "-p",
        str(config.db_port),
        "-U",
        config.db_user,
    ]


def _argv_for_restore_list(tool_ref: str, archive_path: Path) -> list[str]:
    if not tool_ref.startswith("docker:"):
        return [tool_ref, "--list", str(archive_path)]
    _, image, binary = tool_ref.split(":", 2)
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        image,
        binary,
        "--list",
        str(archive_path),
    ]


def create_backup(
    config: Any,
    *,
    backup_type: DbBackupType,
    label: str | None = None,
    session: Session | None = None,
    session_factory: Callable[[], Session] | None = None,
    command_runner: CommandRunner | None = None,
    db_introspector: Callable[[Any], dict[str, Any]] | None = None,
    now_fn: Callable[[], datetime] | None = None,
    which_func: Callable[[str], str | None] = shutil.which,
) -> BackupResult:
    timestamp = (now_fn or (lambda: datetime.now(UTC)))().astimezone(UTC)
    metadata = (db_introspector or _resolve_db_metadata)(config)

    set_dir = Path(config.backup_dir) / timestamp.strftime("%Y%m%dT%H%M%SZ")
    set_dir.mkdir(parents=True, exist_ok=False)
    set_dir.chmod(stat.S_IRWXU)

    archive_path = set_dir / "iw_orch.dump"
    globals_path = set_dir / "globals.sql"
    manifest_path = set_dir / "manifest.json"

    active_session = session or (session_factory() if session_factory is not None else None)
    owns_session = session is None and session_factory is not None

    job: DbBackupJob | None = None
    if active_session is not None:
        job = DbBackupJob(
            backup_type=backup_type,
            label=label,
            status=DbBackupStatus.queued,
            path=str(set_dir),
        )
        active_session.add(job)
        active_session.flush()
        job.status = DbBackupStatus.running
        job.started_at = timestamp
        active_session.flush()

    try:
        tools = _resolve_tools(which_func, int(metadata["server_major"]))
        env = os.environ.copy()
        env["PGPASSWORD"] = config.db_password

        dump_argv = _argv_for_db_tool(tools["pg_dump"], config)
        dump_argv.extend(["-Fc", "-d", config.db_name])
        _run_cmd(dump_argv, output_path=archive_path, env=env, command_runner=command_runner)

        globals_argv = _argv_for_db_tool(tools["pg_dumpall"], config)
        globals_argv.append("--globals-only")
        _run_cmd(globals_argv, output_path=globals_path, env=env, command_runner=command_runner)
        globals_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

        list_argv = _argv_for_restore_list(tools["pg_restore"], archive_path)
        try:
            _run_cmd(list_argv, output_path=None, env=env, command_runner=command_runner)
        except Exception as exc:  # noqa: BLE001
            raise BackupIntegrityError(f"pg_restore --list failed: {exc}") from exc

        archive_size = archive_path.stat().st_size
        globals_size = globals_path.stat().st_size
        manifest = {
            "timestamp_utc": timestamp.isoformat(),
            "backup_type": backup_type.value,
            "label": label,
            "alembic_revision": metadata.get("alembic_revision"),
            "instance_id": metadata.get("instance_id"),
            "row_counts": metadata.get("row_counts"),
            "postgres_server_version": metadata.get("server_version"),
            "artifacts": {
                "archive": {"filename": archive_path.name, "bytes": archive_size},
                "globals": {"filename": globals_path.name, "bytes": globals_size},
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        total_bytes = archive_size + globals_size + manifest_path.stat().st_size

        if job is not None and active_session is not None:
            job.status = DbBackupStatus.success
            job.finished_at = datetime.now(UTC)
            job.bytes = total_bytes
            job.alembic_revision = metadata.get("alembic_revision")
            job.instance_id = metadata.get("instance_id")
            job.row_counts = metadata.get("row_counts")
            active_session.flush()
            if owns_session:
                active_session.commit()

        return BackupResult(
            backup_dir=set_dir,
            archive_path=archive_path,
            globals_path=globals_path,
            manifest_path=manifest_path,
            manifest=manifest,
            total_bytes=total_bytes,
            server_version=str(metadata.get("server_version")),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Backup failed")
        if job is not None and active_session is not None:
            job.status = DbBackupStatus.failed
            job.finished_at = datetime.now(UTC)
            job.error = str(exc)
            active_session.flush()
            if owns_session:
                active_session.commit()
        shutil.rmtree(set_dir, ignore_errors=True)
        raise
    finally:
        if owns_session and active_session is not None:
            active_session.close()
