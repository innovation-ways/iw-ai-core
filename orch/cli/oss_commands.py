"""OSS compliance commands: install, scan, enable, disable, status."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

import click

from orch.config import CORE_ROOT
from orch.db.models import OssScan
from orch.oss import probe_tier1, run_scan, write_project_config
from orch.oss.config_writer import ConfigFileExistsError

INSTALL_SCRIPT = (
    CORE_ROOT / ".claude" / "skills" / "iw-oss-publish" / "scripts" / "install_tools.sh"
)

SCAN_SCRIPT = CORE_ROOT / ".claude" / "skills" / "iw-oss-publish" / "scripts" / "scan.py"


@click.group("oss")
def oss() -> None:
    """OSS compliance workflow management."""


@oss.command("install")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Probe tool availability without installing",
)
@click.option(
    "--tier2",
    is_flag=True,
    default=False,
    help="Also install Tier-2 recommended tools",
)
@click.pass_context
def install(ctx: click.Context, dry_run: bool, tier2: bool) -> None:  # noqa: ARG001
    """Probe or install Tier-1 OSS compliance tools.

    With --dry-run: list missing tools and their install commands (exit 0).

    Without --dry-run: run the installer script and return its exit code.
    """
    if dry_run:
        statuses = probe_tier1()
        missing = {name: s for name, s in statuses.items() if not s.installed}
        if not missing:
            click.echo("All Tier-1 tools are installed.")
            sys.exit(0)

        click.echo(f"{'Tool':<20} {'Status':<12} Install command")
        click.echo("-" * 80)
        for name, status in sorted(missing.items()):
            click.echo(f"{name:<20} {'MISSING':<12} {status.install_cmd}")
        sys.exit(0)
    else:
        if not INSTALL_SCRIPT.exists():
            click.echo(f"Error: install script not found at {INSTALL_SCRIPT}", err=True)
            sys.exit(2)

        cmd = ["bash", str(INSTALL_SCRIPT)]
        if tier2:
            cmd.append("--tier2")

        try:
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if proc.stdout:
                for line in proc.stdout:
                    click.echo(line, nl=False)
            exit_code = proc.wait()
        except Exception as exc:
            click.echo(f"Error running installer: {exc}", err=True)
            sys.exit(2)

        sys.exit(exit_code)


@oss.command("scan")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def scan(ctx: click.Context, project_id: str, json_output: bool) -> None:
    """Run OSS compliance scan against a project."""
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        from orch.db.models import Project

        project = session.get(Project, project_id)
        if project is None:
            if json_output:
                click.echo(json.dumps({"error": f"Project '{project_id}' not found", "code": 2}))
            else:
                click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(2)

        if not project.oss_enabled:
            msg = (
                f"OSS not enabled for {project_id}; "
                f"run `iw oss enable --project {project_id}` first"
            )
            if json_output:
                click.echo(json.dumps({"error": msg, "code": 2}))
            else:
                click.echo(f"Error: {msg}", err=True)
            sys.exit(2)

        if not SCAN_SCRIPT.exists():
            msg = f"Scan script not found at {SCAN_SCRIPT}"
            if json_output:
                click.echo(json.dumps({"error": msg, "code": 2}))
            else:
                click.echo(f"Error: {msg}", err=True)
            sys.exit(2)

        def session_factory() -> Session:
            return session  # type: ignore[no-any-return]

        try:
            scan_result = asyncio.get_event_loop().run_until_complete(
                run_scan(
                    project,
                    "scan",
                    session_factory=session_factory,
                    skill_scan_path=SCAN_SCRIPT,
                )
            )
        except Exception as exc:
            msg = f"Scan failed: {exc}"
            if json_output:
                click.echo(json.dumps({"error": msg, "code": 2}))
            else:
                click.echo(f"Error: {msg}", err=True)
            sys.exit(2)

        pill_color = scan_result.pill_color.value if scan_result.pill_color else "gray"

        if json_output:
            counts: dict[str, Any] = {}
            if scan_result.summary_json:
                s = scan_result.summary_json
                counts = {
                    "must_pass": s.get("must_pass", 0),
                    "must_fail": s.get("must_fail", 0),
                    "must_human_required": s.get("must_human_required", 0),
                    "should_pass": s.get("should_pass", 0),
                    "should_fail": s.get("should_fail", 0),
                    "should_human_required": s.get("should_human_required", 0),
                    "may_pass": s.get("may_pass", 0),
                    "may_fail": s.get("may_fail", 0),
                    "may_human_required": s.get("may_human_required", 0),
                }

            output = {
                "project_id": project_id,
                "pill_color": pill_color,
                "exit_code": scan_result.exit_code,
                "head_sha": scan_result.head_sha,
                "stale": False,
                "counts": counts,
                "scan_id": scan_result.id,
                "completed_at": (
                    scan_result.completed_at.isoformat() if scan_result.completed_at else None
                ),
            }
            click.echo(json.dumps(output))
        else:
            click.echo(f"Scan complete: pill={pill_color} scan_id={scan_result.id}")

        if pill_color == "red":
            sys.exit(1)
        sys.exit(0)


@oss.command("enable")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config file")
@click.pass_context
def enable(ctx: click.Context, project_id: str, force: bool) -> None:
    """Enable OSS compliance for a project and write its config file."""
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        from orch.db.models import Project

        project = session.get(Project, project_id)
        if project is None:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(2)

        repo_root = Path(project.repo_root)
        if not (repo_root / ".git").exists():
            click.echo(f"Error: path {repo_root} is not a git repo", err=True)
            sys.exit(2)

        try:
            write_project_config(project, force=force)
        except ConfigFileExistsError:
            click.echo(
                f"Config file already exists and differs: {repo_root}/.iw/oss-publish.toml "
                "(pass --force to overwrite)",
                err=True,
            )
            sys.exit(2)
        except Exception as exc:
            click.echo(f"Error writing config: {exc}", err=True)
            sys.exit(2)

        project.oss_enabled = True
        session.commit()

        click.echo(f"OSS compliance enabled for {project_id}")


@oss.command("disable")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.pass_context
def disable(ctx: click.Context, project_id: str) -> None:
    """Disable OSS compliance for a project."""
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        from orch.db.models import Project

        project = session.get(Project, project_id)
        if project is None:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(2)

        project.oss_enabled = False
        session.commit()

        click.echo(f"OSS compliance disabled for {project_id}")


@oss.command("fix")
@click.argument("check_id")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--apply", is_flag=True, help="Apply the fix (default: preview only)")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def fix(ctx: click.Context, check_id: str, project_id: str, apply: bool, json_output: bool) -> None:
    """Preview or apply the auto-fix for a single OSS check."""
    from orch.oss.fix_recipes import get_recipe

    get_session = ctx.obj["get_session"]
    with get_session() as session:
        from orch.db.models import Project

        project = session.get(Project, project_id)
        if project is None:
            click.echo(f"Project {project_id} not found", err=True)
            sys.exit(2)
        repo_root = Path(project.repo_root)

    recipe = get_recipe(check_id)
    if recipe is None:
        click.echo(f"No auto-fix recipe registered for {check_id}", err=True)
        sys.exit(2)

    if apply:
        preview = recipe.apply(repo_root)
        action = "apply"
    else:
        preview = recipe.preview(repo_root)
        action = "preview"

    if json_output:
        click.echo(
            json.dumps(
                {
                    "action": action,
                    "check_id": check_id,
                    "target_files": [str(p) for p in preview.target_files],
                    "full_contents": {str(p): c for p, c in preview.full_contents.items()},
                    "diffs": {str(p): d for p, d in preview.diffs.items()},
                    "notes": preview.notes,
                }
            )
        )
    else:
        click.echo(f"{action}: {check_id} — {len(preview.target_files)} file(s)")
        if preview.notes:
            click.echo(f"  notes: {preview.notes}")
        for p in preview.target_files:
            click.echo(f"  - {p}")
    sys.exit(0)


@oss.command("status")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def status(ctx: click.Context, project_id: str, json_output: bool) -> None:
    """Show the latest OSS scan status for a project."""
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        from orch.db.models import Project

        project = session.get(Project, project_id)
        if project is None:
            if json_output:
                click.echo(json.dumps({"error": f"Project '{project_id}' not found", "code": 2}))
            else:
                click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(2)

        latest_scan = (
            session.query(OssScan)
            .filter(OssScan.project_id == project_id)
            .order_by(OssScan.started_at.desc())
            .first()
        )

        if latest_scan is None:
            if json_output:
                output = {
                    "project_id": project_id,
                    "pill_color": "gray",
                    "exit_code": None,
                    "head_sha": None,
                    "stale": False,
                    "counts": {
                        "must_pass": 0,
                        "must_fail": 0,
                        "must_human_required": 0,
                        "should_pass": 0,
                        "should_fail": 0,
                        "should_human_required": 0,
                        "may_pass": 0,
                        "may_fail": 0,
                        "may_human_required": 0,
                    },
                    "scan_id": None,
                    "completed_at": None,
                }
                click.echo(json.dumps(output))
            else:
                click.echo(f"No scans found for {project_id} (pill: gray)")
            sys.exit(0)

        pill_color = latest_scan.pill_color.value if latest_scan.pill_color else "gray"

        stale = False
        if latest_scan.head_sha:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],  # noqa: S607
                    cwd=project.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    current_sha = result.stdout.strip()
                    stale = current_sha != latest_scan.head_sha
            except Exception:  # noqa: S110
                pass

        counts: dict[str, Any] = {}
        if latest_scan.summary_json:
            s = latest_scan.summary_json
            counts = {
                "must_pass": s.get("must_pass", 0),
                "must_fail": s.get("must_fail", 0),
                "must_human_required": s.get("must_human_required", 0),
                "should_pass": s.get("should_pass", 0),
                "should_fail": s.get("should_fail", 0),
                "should_human_required": s.get("should_human_required", 0),
                "may_pass": s.get("may_pass", 0),
                "may_fail": s.get("may_fail", 0),
                "may_human_required": s.get("may_human_required", 0),
            }

        if json_output:
            output = {
                "project_id": project_id,
                "pill_color": pill_color,
                "exit_code": latest_scan.exit_code,
                "head_sha": latest_scan.head_sha,
                "stale": stale,
                "counts": counts,
                "scan_id": latest_scan.id,
                "completed_at": (
                    latest_scan.completed_at.isoformat() if latest_scan.completed_at else None
                ),
            }
            click.echo(json.dumps(output))
        else:
            stale_str = " [STALE]" if stale else ""
            head = latest_scan.head_sha or "?"
            click.echo(
                f"{project_id}: pill={pill_color} scan={latest_scan.id} head={head}{stale_str}"
            )

        sys.exit(0)
