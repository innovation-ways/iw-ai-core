"""Base types for OSS compliance fix recipes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class FixPreview:
    """Preview of what a recipe would write."""

    target_files: list[Path]
    full_contents: dict[Path, str]
    diffs: dict[Path, str]
    notes: str | None = None


class FixRecipe(Protocol):
    """Idempotent fix for one OSS check."""

    check_id: str
    auto_apply_safe: bool

    def preview(self, repo_root: Path) -> FixPreview:
        """Compute what the fix would change without writing to disk.

        Args:
            repo_root: Absolute path to the target repository root.

        Returns:
            FixPreview describing the files that would be created or modified.
        """

    def apply(self, repo_root: Path) -> FixPreview:
        """Apply the fix to the working tree.

        MUST be idempotent — applying twice yields the same on-disk state
        as applying once.

        Args:
            repo_root: Absolute path to the target repository root.

        Returns:
            FixPreview describing the files that were created or modified.
        """
