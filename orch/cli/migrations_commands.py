"""Migration CLI commands — safe, operator-facing surface for migration operations.

iw migrations list-pending   — read-only, shows pending alembic revisions
iw migrations dry-run       — spins testcontainer, validates migrations safely
iw migrations apply         — applies to live DB (requires --i-am-operator flag)
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import suppress

import click

from orch.cli.utils import output_error
from orch.config import get_db_url
from orch.db.safe_migrate import (
    AgentContextForbiddenError,
    ApplyResult,
    DryRunResult,
    MultipleHeadsError,
    list_pending_revisions,
)
from orch.db.safe_migrate import (
    apply as safe_apply,
)
from orch.db.safe_migrate import (
    dry_run as safe_dry_run,
)

EXIT_SUCCESS = 0
EXIT_AGENT_CONTEXT = 2
EXIT_MISSING_FLAG = 3
EXIT_MULTI_HEAD = 4
EXIT_MIGRATION_FAILURE = 5
EXIT_UNKNOWN = 1

AGENT_CONTEXT_ENV = "IW_CORE_AGENT_CONTEXT"


@click.group("migrations")
def migrations_group() -> None:
    """Manage Alembic migrations with safe operator gates.

    All commands are read-only or use testcontainer isolation except 'apply',
    which modifies the live database and requires explicit --i-am-operator.
    """


@migrations_group.command("list-pending")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def list_pending(ctx: click.Context, json_output: bool) -> None:
    """Show alembic revisions present in files but not yet applied to the live DB.

    This command is read-only and safe for anyone to run.
    """
    try:
        db_url = get_db_url()
        pending = list_pending_revisions(db_url)

        if json_output:
            data = [
                {
                    "id": r.id,
                    "description": r.description,
                    "down_revision": r.down_revision,
                }
                for r in pending
            ]
            click.echo(json.dumps(data, indent=2))
        else:
            if not pending:
                click.echo("No pending migrations.")
            else:
                click.echo(f"{'Revision':<12} {'Description':<40} {'Down Revision'}")
                click.echo("-" * 80)
                for r in pending:
                    down_rev = r.down_revision or "(base)"
                    click.echo(f"{r.id:<12} {r.description:<40} {down_rev}")

    except MultipleHeadsError as exc:
        output_error(ctx, str(exc), EXIT_MULTI_HEAD)
    except Exception as exc:
        output_error(ctx, f"Unexpected error: {exc}", EXIT_UNKNOWN)


@migrations_group.command("dry-run")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def dry_run(ctx: click.Context, json_output: bool) -> None:
    """Spin a testcontainer Postgres, apply pending revisions, report success/failure.

    This command is safe: it never touches the live database.
    """
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    try:
        click.echo("Starting testcontainer Postgres for dry-run...")
        container: PostgresContainer | None = None
        try:
            container = PostgresContainer("postgres:15-alpine")
            container.start()
            tempdb_url = container.get_connection_url().replace(
                "postgresql+psycopg2://", "postgresql+psycopg://"
            )

            result: DryRunResult = safe_dry_run(tempdb_url)

            if json_output:
                data = {
                    "success": result.success,
                    "revisions_applied": result.revisions_applied,
                    "duration_ms": result.duration_ms,
                    "stdout_tail": result.stdout_tail,
                    "stderr_tail": result.stderr_tail,
                    "error_message": result.error_message,
                }
                click.echo(json.dumps(data, indent=2))
            else:
                if result.success:
                    click.echo(
                        f"Dry-run succeeded in {result.duration_ms}ms. "
                        f"Revisions applied: {', '.join(result.revisions_applied) or 'none'}."
                    )
                else:
                    click.echo(f"Dry-run FAILED in {result.duration_ms}ms.", err=True)
                    if result.error_message:
                        click.echo(f"Error: {result.error_message}", err=True)
                    sys.exit(EXIT_MIGRATION_FAILURE)

        finally:
            if container is not None:
                with suppress(Exception):
                    container.stop()

    except Exception as exc:
        output_error(ctx, f"Dry-run error: {exc}", EXIT_UNKNOWN)


@migrations_group.command("apply")
@click.option(
    "--i-am-operator",
    is_flag=True,
    default=False,
    help="Required: acknowledge this operation will modify the live database",
)
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def apply_migrations(ctx: click.Context, json_output: bool, i_am_operator: bool) -> None:
    """Apply pending alembic revisions to the live database.

    This command modifies the live database and requires the --i-am-operator flag.
    It refuses to run if IW_CORE_AGENT_CONTEXT=true (agent context).
    """
    if os.environ.get(AGENT_CONTEXT_ENV) == "true":
        msg = (
            "Refusing to apply migrations from agent context. "
            "IW_CORE_AGENT_CONTEXT is set. Only operators may apply migrations."
        )
        if json_output:
            click.echo(json.dumps({"error": msg, "code": EXIT_AGENT_CONTEXT}))
        else:
            click.echo(f"Error: {msg}", err=True)
        sys.exit(EXIT_AGENT_CONTEXT)

    if not i_am_operator:
        click.echo(
            "Error: --i-am-operator flag is required to apply migrations to the live database.",
            err=True,
        )
        sys.exit(EXIT_MISSING_FLAG)

    # I-00041: arm the live-DB connection guard for THIS invocation only.
    # try/finally so a programmatic caller (test, wrapper, loop) doesn't
    # leak the allow-list flag into surrounding code.
    prior = os.environ.get("IW_CORE_OPERATOR_APPLY")
    os.environ["IW_CORE_OPERATOR_APPLY"] = "true"
    try:
        live_url = get_db_url()
        result: ApplyResult = safe_apply(live_url)

        if json_output:
            data = {
                "success": result.success,
                "revisions_applied": result.revisions_applied,
                "duration_ms": result.duration_ms,
                "stdout_tail": result.stdout_tail,
                "stderr_tail": result.stderr_tail,
                "error_message": result.error_message,
            }
            click.echo(json.dumps(data, indent=2))
        else:
            if result.success:
                click.echo(
                    f"Migrations applied successfully in {result.duration_ms}ms. "
                    f"Revisions: {', '.join(result.revisions_applied) or 'none'}."
                )
            else:
                click.echo(f"Migration FAILED in {result.duration_ms}ms.", err=True)
                if result.error_message:
                    click.echo(f"Error: {result.error_message}", err=True)
                sys.exit(EXIT_MIGRATION_FAILURE)

    except AgentContextForbiddenError:
        msg = (
            "Refusing to apply migrations from agent context. "
            "Only operators may apply migrations to the live database."
        )
        if json_output:
            click.echo(json.dumps({"error": msg, "code": EXIT_AGENT_CONTEXT}))
        else:
            click.echo(f"Error: {msg}", err=True)
        sys.exit(EXIT_AGENT_CONTEXT)
    except MultipleHeadsError as exc:
        output_error(ctx, str(exc), EXIT_MULTI_HEAD)
    except Exception as exc:
        output_error(ctx, f"Migration error: {exc}", EXIT_UNKNOWN)
    finally:
        if prior is None:
            os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
        else:
            os.environ["IW_CORE_OPERATOR_APPLY"] = prior
