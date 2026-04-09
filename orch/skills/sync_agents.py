"""Agent and command distribution engine — sync platform agents/commands to project directories."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class AgentSyncResult:
    """Result of syncing agents and/or commands to a project."""

    claude_agents_synced: int = 0
    opencode_agents_synced: int = 0
    opencode_commands_synced: int = 0
    errors: list[str] = field(default_factory=list)


def _sync_directory(
    source_dir: Path,
    target_dir: Path,
) -> tuple[int, list[str]]:
    """Copy all .md files from source_dir to target_dir, creating it if needed.

    Returns (count_synced, errors).
    """
    errors: list[str] = []
    count = 0

    if not source_dir.is_dir():
        errors.append(f"Source directory does not exist: {source_dir}")
        return 0, errors

    target_dir.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(source_dir.iterdir()):
        if not src_file.is_file() or src_file.suffix != ".md":
            continue
        dst_file = target_dir / src_file.name
        try:
            shutil.copy2(src_file, dst_file)
            count += 1
        except OSError as exc:
            errors.append(f"Failed to copy {src_file.name}: {exc}")

    return count, errors


def sync_agents_and_commands(
    project_path: Path,
    platform_root: Path,
) -> AgentSyncResult:
    """Sync platform agents and commands to a project's .claude/ and .opencode/ directories.

    Copies:
      - agents/claude/*.md  → project/.claude/agents/
      - agents/opencode/*.md → project/.opencode/agents/
      - commands/*.md → project/.opencode/commands/

    Args:
        project_path: Absolute path to the project repo root.
        platform_root: Path to the iw-ai-core root directory.

    Returns:
        AgentSyncResult with sync counts and any errors.
    """
    result = AgentSyncResult()

    # Claude agents
    count, errors = _sync_directory(
        platform_root / "agents" / "claude",
        project_path / ".claude" / "agents",
    )
    result.claude_agents_synced = count
    result.errors.extend(errors)

    # OpenCode agents
    count, errors = _sync_directory(
        platform_root / "agents" / "opencode",
        project_path / ".opencode" / "agents",
    )
    result.opencode_agents_synced = count
    result.errors.extend(errors)

    # OpenCode commands
    count, errors = _sync_directory(
        platform_root / "commands",
        project_path / ".opencode" / "commands",
    )
    result.opencode_commands_synced = count
    result.errors.extend(errors)

    return result
