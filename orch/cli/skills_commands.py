"""Skills management CLI commands: sync-skills, init-project."""

from __future__ import annotations

import json
from pathlib import Path

import click

from orch.cli.utils import output_error


@click.command("sync-skills")
@click.option("--check", is_flag=True, help="Report what would change without modifying files")
@click.option("--force", "force_skill", default=None, help="Overwrite a project override")
@click.pass_context
def sync_skills_cmd(ctx: click.Context, check: bool, force_skill: str | None) -> None:
    """Sync platform skills to a project's .claude/skills/ directory."""
    from orch.cli.utils import resolve_project
    from orch.skills.sync import sync_skills

    project_id = resolve_project(ctx)
    repo_root = ctx.obj.get("repo_root")

    # When --project is used (no CWD traversal), look up repo_root from DB
    if repo_root is None:
        from sqlalchemy import select

        from orch.db.models import Project

        get_session = ctx.obj["get_session"]
        try:
            with get_session() as session:
                project_row = session.execute(
                    select(Project).where(Project.id == project_id)
                ).scalar_one_or_none()
                if project_row is not None:
                    repo_root = project_row.repo_root
        except Exception:  # noqa: BLE001, S110
            pass

    if repo_root is None:
        output_error(ctx, "Could not determine project repo root", 3)

    project_path = Path(repo_root)

    # Locate platform skills dir relative to this module's package root
    platform_root = Path(__file__).resolve().parent.parent.parent
    skills_dir = platform_root / "skills"

    result = sync_skills(project_path, skills_dir, check_only=check, force_skill=force_skill)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "updated": result.updated,
                    "up_to_date": result.up_to_date,
                    "overridden": result.overridden,
                    "errors": result.errors,
                    "check_only": check,
                }
            )
        )
        return

    action = "Checking" if check else "Syncing"
    click.echo(f"{action} skills for {project_id}...")

    all_skills = sorted(result.updated + result.up_to_date + result.overridden)
    max_len = max((len(s) for s in all_skills), default=0)

    for name in all_skills:
        if name in result.updated:
            label = "updated" if not check else "would update"
            click.echo(f"  {name:<{max_len}}  ({label})")
        elif name in result.up_to_date:
            click.echo(f"  {name:<{max_len}}  (up to date)")
        else:
            click.echo(f"  {name:<{max_len}}  project override (skipped)")

    for err in result.errors:
        click.echo(f"  WARNING: {err}", err=True)

    synced = len(result.updated)
    skipped = len(result.overridden)
    summary = f"Synced {synced} skill{'s' if synced != 1 else ''}."
    if skipped:
        summary += f" {skipped} skipped (project override)."
    click.echo(summary)


@click.command("init-project")
@click.option("--id", "project_id", required=True, help="Unique project identifier")
@click.option(
    "--path",
    "repo_path",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Absolute path to the project's repo root",
)
@click.option("--name", "display_name", required=True, help="Human-readable display name")
@click.pass_context
def init_project_cmd(
    ctx: click.Context, project_id: str, repo_path: Path, display_name: str
) -> None:
    """Initialize a new project for IW AI Core management."""
    from orch.skills.init_project import init_project

    get_session = ctx.obj["get_session"]
    try:
        with get_session() as session:
            result = init_project(
                project_id=project_id,
                repo_path=repo_path,
                display_name=display_name,
                session=session,
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        output_error(ctx, f"Initialization failed: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": result.project_id,
                    "repo_path": str(result.repo_path),
                    "created_files": result.created_files,
                    "skills_synced": result.skills_synced,
                    "db_rows_created": result.db_rows_created,
                    "projects_toml_updated": result.projects_toml_updated,
                }
            )
        )
        return

    click.echo(f"Project initialized: {result.project_id}")
    click.echo(f"  Config: {result.repo_path / '.iw-orch.json'}")
    click.echo("  Registry: projects.toml updated")
    click.echo("  Database: project + ID sequences + migration lock created")
    click.echo(f"  Skills: {result.skills_synced} base skills synced")
    click.echo("  Workflow: ai-dev/workflow.md created from template")
    click.echo("Ready. Project will appear in dashboard on next daemon poll.")
