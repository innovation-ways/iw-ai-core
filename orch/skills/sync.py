"""Skill distribution engine — sync platform skills to project directories."""

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOCK_FILE = ".iw-skills-lock.json"
SKILL_MANIFEST = "SKILL.md"
PLATFORM_VERSION = "1.0.0"


@dataclass
class SkillSyncResult:
    updated: list[str] = field(default_factory=list)
    up_to_date: list[str] = field(default_factory=list)
    overridden: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_skill_version(skill_md_path: Path) -> str | None:
    """Read the YAML version: field from a SKILL.md frontmatter block.

    Frontmatter is delimited by --- lines at the start of the file.
    Returns the version string, or None if not found or unreadable.
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not content.startswith("---"):
        return None

    end = content.find("\n---", 3)
    if end == -1:
        return None

    frontmatter = content[3:end]
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped[len("version:") :].strip().strip("'\"")
    return None


def _read_lock(project_path: Path) -> dict[str, Any]:
    lock_file = project_path / LOCK_FILE
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"synced_at": None, "platform_version": PLATFORM_VERSION, "skills": {}}


def _write_lock(project_path: Path, lock_data: dict[str, Any]) -> None:
    (project_path / LOCK_FILE).write_text(json.dumps(lock_data, indent=2), encoding="utf-8")


def sync_skills(
    project_path: Path,
    skills_dir: Path,
    check_only: bool = False,
    force_skill: str | None = None,
) -> SkillSyncResult:
    """Sync platform skills from skills_dir to project_path/.claude/skills/.

    Args:
        project_path: Absolute path to the project repo root.
        skills_dir: Path to the iw-ai-core/skills/ master copies directory.
        check_only: If True, report what would change without modifying files.
        force_skill: Skill name to overwrite even if project has an override.

    Returns:
        SkillSyncResult with categorised outcomes for each skill.
    """
    project_skills_dir = project_path / ".claude" / "skills"
    lock_data = _read_lock(project_path)
    skills_state: dict[str, Any] = lock_data.setdefault("skills", {})

    result = SkillSyncResult()

    if not skills_dir.is_dir():
        return result

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name

        master_version = parse_skill_version(skill_dir / SKILL_MANIFEST)
        if master_version is None:
            result.errors.append(f"{skill_name}: could not read version from SKILL.md")
            continue

        project_skill_dir = project_skills_dir / skill_name
        lock_entry = skills_state.get(skill_name)

        # Determine if this skill is a project override:
        #   - Explicitly marked overridden in the lock file, OR
        #   - Exists in the project but has NO lock entry (manually created before any sync)
        is_override = (lock_entry is not None and lock_entry.get("overridden", False)) or (
            lock_entry is None and project_skill_dir.exists()
        )

        is_forced = force_skill == skill_name

        if is_override and not is_forced:
            result.overridden.append(skill_name)
            # Record the override in the lock without changing files
            project_version = (
                lock_entry.get("version", master_version) if lock_entry else master_version
            )
            skills_state[skill_name] = {
                "version": project_version,
                "source": "project",
                "overridden": True,
            }
            continue

        # Platform-managed path: compare versions
        installed_version = lock_entry.get("version") if lock_entry else None
        is_current = (
            installed_version == master_version and project_skill_dir.exists() and not is_forced
        )

        if is_current:
            result.up_to_date.append(skill_name)
        else:
            if not check_only:
                if project_skill_dir.exists():
                    shutil.rmtree(project_skill_dir)
                shutil.copytree(skill_dir, project_skill_dir)
            result.updated.append(skill_name)

        skills_state[skill_name] = {
            "version": master_version,
            "source": "platform",
            "overridden": False,
        }

    lock_data["skills"] = skills_state
    lock_data["synced_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lock_data["platform_version"] = PLATFORM_VERSION

    if not check_only:
        _write_lock(project_path, lock_data)

    return result
