"""File-glob → code-review-agent mapping for fix-cycle replay.

Loaded from ``ai-dev/iw-config/review-mapping.toml`` in the worktree.
Missing file → empty mapping → Change 2 is a no-op for that project.
"""

from __future__ import annotations

import logging
import tomllib
from fnmatch import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def load_review_mapping(worktree_path: Path) -> list[tuple[str, list[str]]]:
    """Return [(review_agent_name, [glob, ...]), ...].

    Missing file → empty list (graceful no-op).
    """
    toml_path = worktree_path / "ai-dev" / "iw-config" / "review-mapping.toml"
    if not toml_path.exists():
        return []
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("review-mapping.toml unreadable at %s: %s", toml_path, exc)
        return []
    out: list[tuple[str, list[str]]] = []
    for entry in data.get("mapping", []):
        agent = entry.get("review_agent")
        globs = entry.get("glob", [])
        if isinstance(agent, str) and isinstance(globs, list):
            out.append((agent, [g for g in globs if isinstance(g, str)]))
    return out


def review_agents_for(
    changed_files: list[str],
    mapping: list[tuple[str, list[str]]],
) -> set[str]:
    """Return the set of review-agent names whose globs match ANY of the changed files.

    Uses ``fnmatch`` for glob matching.  Patterns containing ``**`` are
    normalised to ``*`` for fnmatch compatibility (fnmatch does not support
    ``**`` path separators).
    """
    out: set[str] = set()
    for agent, globs in mapping:
        # Normalise double-star globs: fnmatch treats '**' like any other
        # sequence; replacing with '*' is sufficient for the typical
        # "orch/daemon/**" → "orch/daemon/*" single-level match.
        normalised_globs = [g.replace("**/", "*/").replace("/**", "/*") for g in globs]
        for path in changed_files:
            if any(fnmatch(path, g) for g in normalised_globs):
                out.add(agent)
                break
    return out
