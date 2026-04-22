"""IW CLI — main entry point and Click group definition."""

from __future__ import annotations

import click

from orch.cli.batch_commands import (
    batch_approve,
    batch_create,
    batch_pause,
    batch_resume,
    batch_status,
)
from orch.cli.daemon_commands import daemon
from orch.cli.db_commands import db_identity
from orch.cli.doc_commands import doc_job_done, doc_job_start, doc_update, docs_export
from orch.cli.id_commands import current_project, next_id
from orch.cli.item_commands import approve, archive, item_report, item_status, register, unapprove
from orch.cli.lock_commands import migration_lock
from orch.cli.oss_commands import oss
from orch.cli.project_commands import projects
from orch.cli.search_commands import search
from orch.cli.skills_commands import init_project_cmd, sync_agents_cmd, sync_skills_cmd
from orch.cli.step_commands import (
    step_done,
    step_fail,
    step_kill,
    step_restart,
    step_restart_from,
    step_skip,
    step_start,
)
from orch.cli.worktree_commands import worktree_status


@click.group()
@click.option("--project", "-p", default=None, help="Project ID (overrides auto-detection)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.option("--verbose", "-v", is_flag=True, help="Show debug-level details")
@click.pass_context
def cli(ctx: click.Context, project: str | None, json_output: bool, verbose: bool) -> None:
    """IW AI Core orchestration CLI."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["verbose"] = verbose

    if project:
        ctx.obj["project_id"] = project

    # Lazy session factory — only set if not already injected (tests inject their own)
    if "get_session" not in ctx.obj:

        def _get_session():  # type: ignore[no-untyped-def]
            from orch.db.session import get_session  # noqa: PLC0415

            return get_session()

        ctx.obj["get_session"] = _get_session


cli.add_command(current_project)
cli.add_command(next_id)
cli.add_command(register)
cli.add_command(approve)
cli.add_command(unapprove)
cli.add_command(archive)
cli.add_command(item_status)
cli.add_command(item_report)
cli.add_command(step_start)
cli.add_command(step_done)
cli.add_command(step_fail)
cli.add_command(step_restart)
cli.add_command(step_restart_from, name="step-restart-from")
cli.add_command(step_skip)
cli.add_command(step_kill)
cli.add_command(batch_create)
cli.add_command(batch_approve)
cli.add_command(batch_status)
cli.add_command(batch_pause)
cli.add_command(batch_resume)
cli.add_command(migration_lock)
cli.add_command(search)
cli.add_command(sync_skills_cmd, name="sync-skills")
cli.add_command(sync_agents_cmd, name="sync-agents")
cli.add_command(init_project_cmd, name="init-project")
cli.add_command(daemon)
cli.add_command(projects)
cli.add_command(worktree_status, name="worktree-status")
cli.add_command(doc_update)
cli.add_command(doc_job_start, name="doc-job-start")
cli.add_command(doc_job_done, name="doc-job-done")
cli.add_command(docs_export, name="docs-export")
cli.add_command(db_identity)
cli.add_command(oss)
