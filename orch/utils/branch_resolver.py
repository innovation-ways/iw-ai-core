"""Shared branch-resolver for IW AI Core.

Provides:
  - resolve_branch(repo_root, default_branch): resolve current branch vs configured default.
  - resolve_branch_for_project(repo_root): same, but reads default_branch from .iw-orch.json
    (or falls back to "main").

Importable by both the daemon merge path and the dashboard. No hardcoded "main" in
comparisons — all comparisons use the resolved default_branch.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Sentinel value used when git is unavailable
_UNKNOWN_BRANCH = "unknown"
# Bare fallback default when neither project config nor caller provides one
_DEFAULT_DEFAULT_BRANCH = "main"


@dataclass(frozen=True, slots=True)
class BranchInfo:
    """Result of a branch-resolution call."""

    #: The current branch (or "unknown" if git failed / no repo).
    current_branch: str
    #: The project's configured default branch (never empty — always populated).
    default_branch: str
    #: True when current_branch == default_branch.
    is_on_default: bool


def resolve_branch(repo_root: str, default_branch: str = _DEFAULT_DEFAULT_BRANCH) -> BranchInfo:
    """Return BranchInfo for *repo_root*.

    Parameters
    ----------
    repo_root:
        Absolute path to the project git repository.
    default_branch:
        The configured default branch (e.g. "main", "trunk"). Passed in from
        project config or callers that already read .iw-orch.json. Must not
        be empty.

    Returns
    -------
    BranchInfo
        current_branch, default_branch (as passed in), and is_on_default bool.
        On git errors, current_branch is "unknown" and is_on_default is False.
    """
    if not default_branch:
        default_branch = _DEFAULT_DEFAULT_BRANCH

    try:
        current = subprocess.check_output(  # noqa: S603
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        logger.debug("branch_resolver: git unavailable for %s", repo_root)
        return BranchInfo(
            current_branch=_UNKNOWN_BRANCH,
            default_branch=default_branch,
            is_on_default=False,
        )

    return BranchInfo(
        current_branch=current,
        default_branch=default_branch,
        is_on_default=(current == default_branch),
    )


def resolve_branch_for_project(repo_root: str) -> BranchInfo:
    """Return BranchInfo for *repo_root*, reading default_branch from .iw-orch.json.

    Falls back to "main" when the config file is absent or the key is absent.
    This is the preferred entry point for the daemon and dashboard — it
    encapsulates the config-reading logic in one place.
    """
    default = _read_default_branch(repo_root)
    return resolve_branch(repo_root, default_branch=default)


def _read_default_branch(repo_root: str) -> str:
    """Read the ``default_branch`` key from ``repo_root/.iw-orch.json``.

    Returns ``"main"`` if the file is missing or the key is absent / malformed.
    """
    path = Path(repo_root) / ".iw-orch.json"
    if not path.exists():
        logger.debug(
            ".iw-orch.json not found in %s — defaulting to %s", repo_root, _DEFAULT_DEFAULT_BRANCH
        )
        return _DEFAULT_DEFAULT_BRANCH

    try:
        content = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning(
            "Invalid .iw-orch.json in %s: %s — defaulting to %s",
            repo_root,
            exc,
            _DEFAULT_DEFAULT_BRANCH,
        )
        return _DEFAULT_DEFAULT_BRANCH

    value = content.get("default_branch")
    if isinstance(value, str) and value:
        return value

    logger.debug(
        "No 'default_branch' in .iw-orch.json in %s — defaulting to %s",
        repo_root,
        _DEFAULT_DEFAULT_BRANCH,
    )
    return _DEFAULT_DEFAULT_BRANCH
