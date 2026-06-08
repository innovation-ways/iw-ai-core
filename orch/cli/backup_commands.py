"""Orchestration DB backup commands — F-00092.

Commands:
    iw db-backup create [--label TEXT]   — run a backup synchronously (records a
        ``manual`` job; works even when the daemon is down — Invariant 5 / AC2)
    iw db-backup list                    — list recorded backups
    iw db-backup prune                   — apply retention now (manual-exempt)
    iw db-backup restore --from <set>    — guided restore into a safe non-prod
        target (refuses the live prod DB unless ``--allow-prod``)
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click
from sqlalchemy import select

from orch.backup.engine import create_backup
from orch.backup.restore import RestoreError, RestoreSafetyError, restore
from orch.backup.retention import prune_scheduled_backups
from orch.config import load_config
from orch.db.models import DbBackupJob, DbBackupType

if TYPE_CHECKING:
    from orch.backup.restore import RestoreResult


def _require_session_factory(ctx: click.Context) -> Any:
    get_session = ctx.obj.get("get_session") if ctx.obj else None
    if get_session is None:
        click.echo("ERROR: no session factory available", err=True)
        sys.exit(1)
    return get_session


@click.group("db-backup")
def db_backup() -> None:
    """Create, list, prune, and restore orchestration DB logical backups."""


@db_backup.command("create")
@click.option(
    "--label", default=None, help="Optional label; on-demand backups are recorded as manual."
)
@click.pass_context
def create(ctx: click.Context, label: str | None) -> None:
    """Run a backup synchronously and record a manual DbBackupJob.

    Works even when the daemon is not running (Invariant 5 / AC2).
    """
    config = load_config()
    if not config.backup_enabled:
        click.echo(
            "Note: scheduled backups are disabled (IW_CORE_BACKUP_ENABLED=false); "
            "running this on-demand backup anyway."
        )

    get_session = _require_session_factory(ctx)

    result: Any = None
    error: Exception | None = None
    with get_session() as session:
        try:
            result = create_backup(
                config,
                backup_type=DbBackupType.manual,
                label=label,
                session=session,
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            # Persist the failed-job row before unwinding so the failure is
            # visible in `iw db-backup list` and the Jobs view.
            session.commit()
            error = exc

    if error is not None:
        click.echo(f"ERROR: backup failed: {error}", err=True)
        sys.exit(1)

    click.echo(f"Backup created: {result.backup_dir}")
    click.echo(f"  size : {result.total_bytes} bytes")
    if label:
        click.echo(f"  label: {label}")
    sys.exit(0)


@db_backup.command("list")
@click.pass_context
def list_backups(ctx: click.Context) -> None:
    """List recorded backups (type, label, status, timestamp, size, path)."""
    get_session = _require_session_factory(ctx)

    with get_session() as session:
        rows = list(
            session.scalars(select(DbBackupJob).order_by(DbBackupJob.created_at.desc())).all()
        )
        # Read every column we render while the session is still open.
        # Accessing row.bytes (or any other lazy attribute) after the
        # ``with`` block exits triggers DetachedInstanceError on a
        # SQLAlchemy row that wasn't fully eager-loaded.
        rendered: list[tuple[str, str, str, str, str, str]] = []
        for row in rows:
            size = "-" if row.bytes is None else str(row.bytes)
            label = row.label or "-"
            rendered.append(
                (
                    row.backup_type.value,
                    row.status.value,
                    str(row.created_at),
                    size,
                    label,
                    row.path,
                )
            )

    if not rendered:
        click.echo("No backups recorded.")
        return

    header = f"{'TYPE':<10} {'STATUS':<8} {'CREATED':<32} {'SIZE':>12}  LABEL / PATH"
    click.echo(header)
    for backup_type, status, created_at, size, label, path in rendered:
        click.echo(f"{backup_type:<10} {status:<8} {created_at:<32} {size:>12}  {label}  {path}")


@db_backup.command("prune")
@click.pass_context
def prune(ctx: click.Context) -> None:
    """Apply retention now: delete scheduled backups older than the configured
    retention. Manual/labeled backups are always exempt."""
    config = load_config()
    get_session = _require_session_factory(ctx)

    with get_session() as session:
        result = prune_scheduled_backups(
            session,
            retention_days=config.backup_retention_days,
        )
        session.commit()

    click.echo(f"Pruned {len(result.deleted_job_ids)} scheduled backup(s).")
    for path in result.deleted_paths:
        click.echo(f"  removed {path}")


@db_backup.command("restore")
@click.option(
    "--from", "from_set", required=True, help="Path to the backup-set directory to restore."
)
@click.option(
    "--target",
    default=None,
    help="Target DB name on the configured host (default: a fresh non-prod restore DB).",
)
@click.option(
    "--allow-prod",
    is_flag=True,
    default=False,
    help="Allow restoring over the live production DB (dangerous; off by default).",
)
def restore_cmd(from_set: str, target: str | None, allow_prod: bool) -> None:
    """Restore a backup set into a safe non-prod target (globals first, then dump).

    Refuses the live production DB unless ``--allow-prod`` is supplied
    (Invariant 4 / AC5).
    """
    config = load_config()

    target_arg: dict[str, Any] | None = None
    if target:
        target_arg = {
            "host": config.db_host,
            "port": config.db_port,
            "db_name": target,
            "user": config.db_user,
            "password": config.db_password,
        }

    try:
        result: RestoreResult = restore(
            config,
            backup_set=from_set,
            target=target_arg,
            allow_prod=allow_prod,
        )
    except RestoreSafetyError as exc:
        click.echo(f"REFUSED: {exc}", err=True)
        sys.exit(2)
    except RestoreError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Restored into {result.target.db_name} (identity: {result.identity_mode})")
    for name, count in result.row_counts.items():
        click.echo(f"  {name}: {count}")
    sys.exit(0)
