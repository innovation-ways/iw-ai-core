"""Project initialization — onboard a new repo into IW AI Core management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Root of the iw-ai-core platform repo (two levels up from orch/skills/)
_PLATFORM_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_IW_ORCH_CONFIG = {
    "max_parallel": 4,
    "auto_publish": False,
    "browser_verification": False,
    "fix_cycle_max": 5,
}

_ID_PREFIXES = ["F", "I", "CR", "BATCH"]


@dataclass
class InitProjectResult:
    project_id: str
    repo_path: Path
    created_files: list[str] = field(default_factory=list)
    skills_synced: int = 0
    agents_synced: int = 0
    db_rows_created: list[str] = field(default_factory=list)
    projects_toml_updated: bool = False


def init_project(
    project_id: str,
    repo_path: Path,
    display_name: str,
    session: Session,
    platform_root: Path | None = None,
) -> InitProjectResult:
    """Initialize a project directory and register it in the database.

    Steps performed:
    1. Creates .iw-orch.json in repo_path
    2. Appends entry to projects.toml in iw-ai-core
    3. INSERTs into projects, id_sequences (x4), migration_locks tables
    4. Creates ai-dev/design/active/ directory structure
    5. Creates ai-dev/workflow.md from the default template
    6. Syncs base skills to .claude/skills/

    Args:
        project_id: Unique project identifier (e.g., 'my-project').
        repo_path: Absolute path to the project's repo root.
        display_name: Human-readable name.
        session: Active SQLAlchemy session (caller manages commit/rollback).
        platform_root: Override for the iw-ai-core root (used in tests).

    Returns:
        InitProjectResult summary of what was created.
    """
    from orch.db.models import IdSequence, MigrationLock, Project

    root = platform_root if platform_root is not None else _PLATFORM_ROOT
    result = InitProjectResult(project_id=project_id, repo_path=repo_path)

    # ------------------------------------------------------------------
    # 1. .iw-orch.json
    # ------------------------------------------------------------------
    orch_config = {"project_id": project_id, **_DEFAULT_IW_ORCH_CONFIG}
    orch_json_path = repo_path / ".iw-orch.json"
    orch_json_path.write_text(json.dumps(orch_config, indent=2), encoding="utf-8")
    result.created_files.append(".iw-orch.json")

    # ------------------------------------------------------------------
    # 2. projects.toml entry
    # ------------------------------------------------------------------
    projects_toml = root / "projects.toml"
    toml_entry = (
        f"\n[projects.{project_id}]\n"
        f'display_name = "{display_name}"\n'
        f'repo_root = "{repo_path}"\n'
        f"enabled = true\n"
    )
    with projects_toml.open("a", encoding="utf-8") as fh:
        fh.write(toml_entry)
    result.projects_toml_updated = True

    # ------------------------------------------------------------------
    # 3. Database rows
    # ------------------------------------------------------------------
    project_row = Project(
        id=project_id,
        display_name=display_name,
        repo_root=str(repo_path),
        config=orch_config,
        enabled=True,
    )
    session.add(project_row)
    session.flush()
    result.db_rows_created.append(f"projects[{project_id}]")

    for prefix in _ID_PREFIXES:
        session.add(IdSequence(project_id=project_id, prefix=prefix, next_number=1))
    session.flush()
    result.db_rows_created.extend([f"id_sequences[{project_id},{p}]" for p in _ID_PREFIXES])

    lock_row = MigrationLock(project_id=project_id, current_holder=None)
    session.add(lock_row)
    session.flush()
    result.db_rows_created.append(f"migration_locks[{project_id}]")

    # ------------------------------------------------------------------
    # 4. ai-dev directory structure
    # ------------------------------------------------------------------
    active_dir = repo_path / "ai-dev" / "design" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    result.created_files.append("ai-dev/design/active/")

    # ------------------------------------------------------------------
    # 5. workflow.md from template
    # ------------------------------------------------------------------
    template_path = root / "templates" / "default_workflow.md"
    workflow_md = repo_path / "ai-dev" / "workflow.md"
    if template_path.exists():
        workflow_md.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        workflow_md.write_text("# Workflow Definition\n", encoding="utf-8")
    result.created_files.append("ai-dev/workflow.md")

    # ------------------------------------------------------------------
    # 5b. Design templates (Feature, Issue, CR, prompts, reviews, QV)
    # ------------------------------------------------------------------
    import shutil

    design_templates_src = root / "templates" / "design"
    design_templates_dst = repo_path / "ai-dev" / "templates"
    if design_templates_src.is_dir():
        design_templates_dst.mkdir(parents=True, exist_ok=True)
        for tmpl in sorted(design_templates_src.iterdir()):
            if tmpl.is_file() and tmpl.suffix == ".md":
                shutil.copy2(tmpl, design_templates_dst / tmpl.name)
        result.created_files.append("ai-dev/templates/")

    # ------------------------------------------------------------------
    # 6. Sync base skills
    # ------------------------------------------------------------------
    from orch.skills.sync import sync_skills

    skills_dir = root / "skills"
    sync_result = sync_skills(repo_path, skills_dir)
    result.skills_synced = len(sync_result.updated)

    # ------------------------------------------------------------------
    # 7. Sync agents and commands
    # ------------------------------------------------------------------
    from orch.skills.sync_agents import sync_agents_and_commands

    agent_sync = sync_agents_and_commands(repo_path, root)
    result.agents_synced = (
        agent_sync.claude_agents_synced
        + agent_sync.opencode_agents_synced
        + agent_sync.opencode_commands_synced
    )

    return result
