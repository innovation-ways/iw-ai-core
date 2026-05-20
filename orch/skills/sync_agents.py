"""Agent and command distribution engine — sync platform agents/commands to project directories."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentSyncResult:
    """Result of syncing agents and/or commands to a project."""

    claude_agents_synced: int = 0
    pi_agents_synced: int = 0
    pi_extensions_synced: int = 0
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
    """Sync platform agents and commands to a project's .claude/, .pi/, and .opencode/ directories.

    Copies:
      - agents/claude/*.md  → project/.claude/agents/
      - agents/pi/*.md      → project/.pi/agents/
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

    # Pi agents
    count, errors = _sync_directory(
        platform_root / "agents" / "pi",
        project_path / ".pi" / "agents",
    )
    result.pi_agents_synced = count
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

    # Pi extensions — each immediate subdirectory under agents/pi/extensions/
    # is copied recursively to project/.pi/extensions/<name>/.
    # Missing source dir is silently skipped (optional feature).
    pi_extensions_src = platform_root / "agents" / "pi" / "extensions"
    if pi_extensions_src.is_dir():
        try:
            extension_dirs = [d for d in pi_extensions_src.iterdir() if d.is_dir()]
        except OSError as exc:
            logger.warning("Failed to list Pi extensions directory %s: %s", pi_extensions_src, exc)
            extension_dirs = []

        for ext_dir in sorted(extension_dirs):
            dst = project_path / ".pi" / "extensions" / ext_dir.name
            try:
                shutil.copytree(ext_dir, dst, dirs_exist_ok=True, copy_function=shutil.copy2)
                result.pi_extensions_synced += 1
            except (OSError, shutil.Error) as exc:
                logger.warning("Failed to sync Pi extension %s: %s", ext_dir.name, exc)

    return result
