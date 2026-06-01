from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from orch.db.identity import check_identity


class RestoreError(RuntimeError):
    pass


class RestoreSafetyError(RestoreError):
    pass


@dataclass(frozen=True)
class RestoreTarget:
    host: str
    port: int
    db_name: str
    user: str
    password: str


@dataclass(frozen=True)
class RestoreResult:
    target: RestoreTarget
    identity_mode: str
    row_counts: dict[str, int]


def _as_target(config: Any, target: dict[str, Any] | RestoreTarget | None) -> RestoreTarget:
    if target is None:
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return RestoreTarget(
            host=config.db_host,
            port=int(config.db_port),
            db_name=f"{config.db_name}_restore_{suffix}",
            user=config.db_user,
            password=config.db_password,
        )
    if isinstance(target, RestoreTarget):
        return target
    return RestoreTarget(
        host=str(target["host"]),
        port=int(target["port"]),
        db_name=str(target["db_name"]),
        user=str(target.get("user", config.db_user)),
        password=str(target.get("password", config.db_password)),
    )


def _is_live_prod_target(config: Any, target: RestoreTarget) -> bool:
    return (
        target.host == config.db_host
        and int(target.port) == int(config.db_port)
        and target.db_name == config.db_name
    )


def _run(argv: list[str]) -> None:
    subprocess.run(argv, check=True)  # noqa: S603


def restore(
    config: Any,
    *,
    backup_set: str | Path,
    target: dict[str, Any] | RestoreTarget | None,
    allow_prod: bool = False,
    command_runner: Any = None,
) -> RestoreResult:
    resolved_target = _as_target(config, target)
    if _is_live_prod_target(config, resolved_target) and not allow_prod:
        raise RestoreSafetyError(
            "Refusing restore into live production DB. "
            "Re-run with allow_prod=True only after explicit verification."
        )

    set_dir = Path(backup_set)
    globals_file = set_dir / "globals.sql"
    archive_file = set_dir / "iw_orch.dump"
    if not globals_file.exists() or not archive_file.exists():
        raise RestoreError(
            f"Backup set is missing required artifacts. Expected files:\n"
            f"  {globals_file}\n"
            f"  {archive_file}"
        )

    runner = command_runner or _run

    psql_cmd = [
        "psql",
        "-h",
        resolved_target.host,
        "-p",
        str(resolved_target.port),
        "-U",
        resolved_target.user,
        "-d",
        "postgres",
        "-f",
        str(globals_file),
    ]
    pg_restore_cmd = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "-h",
        resolved_target.host,
        "-p",
        str(resolved_target.port),
        "-U",
        resolved_target.user,
        "-d",
        resolved_target.db_name,
        str(archive_file),
    ]

    try:
        runner(psql_cmd)
    except Exception as exc:  # noqa: BLE001
        raise RestoreError("Failed applying globals. Re-run:\n  " + " ".join(psql_cmd)) from exc

    try:
        runner(pg_restore_cmd)
    except Exception as exc:  # noqa: BLE001
        raise RestoreError(
            "Failed restoring archive. Re-run:\n  " + " ".join(pg_restore_cmd)
        ) from exc

    target_url = (
        f"postgresql+psycopg://{resolved_target.user}:{resolved_target.password}"
        f"@{resolved_target.host}:{resolved_target.port}/{resolved_target.db_name}"
    )
    engine = create_engine(target_url)
    try:
        with Session(engine) as session:
            identity = check_identity(session)
            row_counts = {
                "projects": int(
                    session.execute(text("SELECT COUNT(*) FROM projects")).scalar_one()
                ),
                "batches": int(session.execute(text("SELECT COUNT(*) FROM batches")).scalar_one()),
                "work_items": int(
                    session.execute(text("SELECT COUNT(*) FROM work_items")).scalar_one()
                ),
            }
    finally:
        engine.dispose()

    return RestoreResult(target=resolved_target, identity_mode=identity.mode, row_counts=row_counts)
