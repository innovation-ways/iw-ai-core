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


@click.command("sync-agents")
@click.pass_context
def sync_agents_cmd(ctx: click.Context) -> None:
    """Sync platform agents and commands to a project's .claude/ and .opencode/ directories."""
    from orch.cli.utils import resolve_project
    from orch.skills.sync_agents import sync_agents_and_commands

    project_id = resolve_project(ctx)
    repo_root = ctx.obj.get("repo_root")

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

    platform_root = Path(__file__).resolve().parent.parent.parent

    result = sync_agents_and_commands(Path(repo_root), platform_root)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "claude_agents": result.claude_agents_synced,
                    "pi_agents": result.pi_agents_synced,
                    "pi_extensions": result.pi_extensions_synced,
                    "opencode_agents": result.opencode_agents_synced,
                    "opencode_commands": result.opencode_commands_synced,
                    "errors": result.errors,
                }
            )
        )
        return

    click.echo(f"Syncing agents for {project_id}...")
    click.echo(f"  Claude agents: {result.claude_agents_synced}")
    click.echo(f"  Pi agents: {result.pi_agents_synced}")
    click.echo(f"  Pi extensions: {result.pi_extensions_synced}")
    click.echo(f"  OpenCode agents: {result.opencode_agents_synced}")
    click.echo(f"  OpenCode commands: {result.opencode_commands_synced}")
    for err in result.errors:
        click.echo(f"  WARNING: {err}", err=True)
    total = (
        result.claude_agents_synced
        + result.pi_agents_synced
        + result.pi_extensions_synced
        + result.opencode_agents_synced
        + result.opencode_commands_synced
    )
    click.echo(f"Total: {total} files synced.")


@click.command("sync-templates")
@click.option("--check", is_flag=True, help="Report what would change without modifying files")
@click.option(
    "--project", "project_id", default=None, help="Sync a specific project only (default: all)"
)
@click.pass_context
def sync_templates_cmd(ctx: click.Context, check: bool, project_id: str | None) -> None:
    """Sync design templates from templates/design/ to all registered projects."""
    import filecmp
    import shutil

    from sqlalchemy import select

    from orch.db.models import Project

    platform_root = Path(__file__).resolve().parent.parent.parent
    templates_src = platform_root / "templates" / "design"

    if not templates_src.is_dir():
        output_error(ctx, f"Source directory not found: {templates_src}", 1)

    source_files = sorted(f for f in templates_src.iterdir() if f.is_file() and f.suffix == ".md")

    get_session = ctx.obj["get_session"]
    with get_session() as session:
        q = select(Project)
        if project_id:
            q = q.where(Project.id == project_id)
        projects_data = [(p.id, p.repo_root) for p in session.execute(q).scalars().all()]

    if not projects_data:
        target = f"project '{project_id}'" if project_id else "any registered project"
        output_error(ctx, f"No projects found for {target}", 3)

    results: dict[str, dict[str, list[str]]] = {}
    for pid, repo_root in projects_data:
        dst = Path(repo_root) / "ai-dev" / "templates"
        updated: list[str] = []
        up_to_date: list[str] = []
        errors: list[str] = []

        if not check:
            try:
                dst.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                errors.append(f"Cannot create {dst}: {exc}")
                results[pid] = {
                    "updated": updated,
                    "up_to_date": up_to_date,
                    "errors": errors,
                }
                continue

        for src_file in source_files:
            dst_file = dst / src_file.name
            needs_update = not dst_file.exists() or not filecmp.cmp(
                src_file, dst_file, shallow=False
            )
            if needs_update:
                if not check:
                    try:
                        shutil.copy2(src_file, dst_file)
                    except OSError as exc:
                        errors.append(f"{src_file.name}: {exc}")
                        continue
                updated.append(src_file.name)
            else:
                up_to_date.append(src_file.name)

        results[pid] = {"updated": updated, "up_to_date": up_to_date, "errors": errors}

    if ctx.obj.get("json"):
        import json

        click.echo(json.dumps({"check_only": check, "projects": results}))
        return

    action = "Checking" if check else "Syncing"
    click.echo(f"{action} design templates for {len(results)} project(s)...")
    for pid, r in results.items():
        n_updated = len(r["updated"])
        n_ok = len(r["up_to_date"])
        verb = "would update" if check else "updated"
        click.echo(f"  {pid}: {n_updated} {verb}, {n_ok} up to date")
        for err in r["errors"]:
            click.echo(f"    WARNING: {err}", err=True)

    total_updated = sum(len(r["updated"]) for r in results.values())
    qualifier = "would be " if check else ""
    plural = "s" if total_updated != 1 else ""
    click.echo(f"Done. {total_updated} template file{plural} {qualifier}synced.")


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
                    "agents_synced": result.agents_synced,
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
    click.echo(f"  Agents: {result.agents_synced} agents/commands synced")
    click.echo("  Workflow: ai-dev/workflow.md created from template")
    click.echo("Ready. Project will appear in dashboard on next daemon poll.")
