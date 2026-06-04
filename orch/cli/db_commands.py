"""DB instance identity commands — CR-00014.

Commands:
    iw db-identity show   — show live UUID, expected UUID, and mode (always exits 0)
    iw db-identity check — verify identity;
        exit 0=match/bootstrap, 2=mismatch, 3=missing, 1=conn error
"""

from __future__ import annotations

import sys

import click

from orch.db.identity import (
    InstanceMismatchError,
    InstanceRowMissingError,
    check_identity,
    get_expected_instance_id,
    get_live_instance_id,
    verify_instance_identity,
)


@click.group("db-identity")
def db_identity() -> None:
    """Show or verify the orchestration DB instance identity fingerprint."""


@db_identity.command("show")
@click.pass_context
def show(ctx: click.Context) -> None:
    """Show live DB instance UUID, expected UUID (or unset), and mode.

    Always exits 0 — this is a read-only diagnostic.
    """
    get_session = ctx.obj.get("get_session")
    if get_session is None:
        click.echo("ERROR: no session factory available", err=True)
        sys.exit(1)

    try:
        with get_session() as session:
            actual = get_live_instance_id(session)
            expected = get_expected_instance_id()
            status = check_identity(session)

        click.echo(f"Live UUID  : {actual}")
        click.echo(f"Expected   : {expected or '(unset)'}")
        click.echo(f"Mode       : {status.mode}")
        sys.exit(0)
    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)


@db_identity.command("check")
@click.pass_context
def check(ctx: click.Context) -> None:
    """Verify DB instance identity.

    Exit codes: 0=match/bootstrap, 2=mismatch, 3=missing row, 1=conn error."""
    get_session = ctx.obj.get("get_session")
    if get_session is None:
        click.echo("ERROR: no session factory available", err=True)
        sys.exit(1)

    try:
        with get_session() as session:
            status = verify_instance_identity(session)

        short = str(status.actual)[:8] if status.actual else "?"
        if status.mode == "match":
            click.echo(f"OK: DB identity matches ({short})")
            sys.exit(0)
        elif status.mode == "bootstrap":
            click.echo(f"BOOTSTRAP: {status.message}")
            sys.exit(0)
        elif status.mode == "mismatch":
            click.echo(f"MISMATCH:\n{status.message}", err=True)
            sys.exit(2)
        elif status.mode == "missing":
            click.echo(f"MISSING:\n{status.message}", err=True)
            sys.exit(3)
        else:
            click.echo(f"UNKNOWN mode: {status.mode}", err=True)
            sys.exit(1)
    except InstanceMismatchError as exc:
        click.echo(f"MISMATCH:\n{exc}", err=True)
        sys.exit(2)
    except InstanceRowMissingError as exc:
        click.echo(f"MISSING:\n{exc}", err=True)
        sys.exit(3)
    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)
