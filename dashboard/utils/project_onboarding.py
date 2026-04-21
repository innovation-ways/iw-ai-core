"""Project onboarding helpers — pure functions, no DB or FastAPI imports."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_PROJECT_ID_RE = re.compile(r"^[a-z0-9](-?[a-z0-9]+)*$")


def slugify_project_id(name: str) -> str:
    """Lowercase, replace non-[a-z0-9] runs with '-', strip leading/trailing dashes."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def next_available_project_id(base_slug: str, existing_ids: Iterable[str]) -> str:
    """Return base_slug if unique, otherwise append -2, -3, ... until unique."""
    existing = set(existing_ids)
    if base_slug not in existing:
        return base_slug
    candidate = f"{base_slug}-2"
    n = 2
    while candidate in existing:
        n += 1
        candidate = f"{base_slug}-{n}"
    return candidate


def safe_resolve_path(raw: str, safe_root: Path) -> Path:
    """Expand ~, resolve, and enforce the path is inside safe_root.

    Raises ValueError if input is empty, resolved path is not absolute,
    or resolved path escapes safe_root.
    """
    if not raw:
        raise ValueError("Path must not be empty.")

    resolved = Path(raw).expanduser().resolve(strict=False)

    if not resolved.is_absolute():
        raise ValueError(f"Resolved path '{resolved}' is not absolute.")

    try:
        resolved.relative_to(safe_root)
    except ValueError:
        raise ValueError(
            f"Path '{resolved}' is outside the allowed directory '{safe_root}'."
        ) from None

    return resolved


def validate_repo_root(path: Path) -> None:
    """Validate path is an existing directory containing a .git entry.

    Raises ValueError with a user-friendly message on failure.
    """
    if not path.exists():
        raise ValueError(f"Selected folder '{path}' does not exist.")

    if not path.is_dir():
        raise ValueError(f"Selected path '{path}' is not a directory.")

    git_path = path / ".git"
    if not git_path.exists() or not git_path.is_dir():
        raise ValueError(f"Selected folder '{path}' is not a git repository (no .git entry found).")


def is_valid_project_id(project_id: str) -> bool:
    """Check project_id matches ^[a-z0-9][a-z0-9-]*$ (no leading dash, lowercase)."""
    return bool(_PROJECT_ID_RE.match(project_id))
