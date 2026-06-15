"""Innovation Ways brand-asset distribution to managed projects.

The master brand assets (logos, icons, social images) live in the platform repo
under ``ai-dev/iw-assets/``. Every managed project needs a local copy so that
documents authored in that project can reference the brand assets and so the
identity stays consistent across the fleet. This module mirrors the master tree
into a project's ``ai-dev/iw-assets/`` directory.

It is the brand-asset analogue of :mod:`orch.skills.sync` (skills) and the
``sync-templates`` command (design templates): recursive, idempotent (skips
byte-identical files), and safe to run on every project repeatedly.
"""

from __future__ import annotations

import filecmp
import logging
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Master assets directory, relative to the platform repo root.
ASSETS_REL_PATH = "ai-dev/iw-assets"


@dataclass
class AssetSyncResult:
    """Outcome of syncing brand assets into one project.

    Attributes:
        copied: Repo-relative paths of files written (or that would be written
            in check mode).
        up_to_date: Repo-relative paths already byte-identical at the target.
        errors: Human-readable messages for files that could not be copied.
    """

    copied: list[str] = field(default_factory=list)
    up_to_date: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _iter_files(root: Path) -> list[Path]:
    """Return all regular files under ``root`` (recursive), sorted for stability."""
    return sorted(p for p in root.rglob("*") if p.is_file())


def sync_assets(
    project_root: Path,
    assets_src: Path,
    *,
    check_only: bool = False,
) -> AssetSyncResult:
    """Mirror the master brand assets into a project's ``ai-dev/iw-assets/``.

    Copies every file under ``assets_src`` to the matching path under
    ``project_root/ai-dev/iw-assets``, preserving the directory structure.
    Byte-identical files are skipped. The operation is a no-op when the project
    is the platform repo itself (source and destination resolve to the same dir).

    Args:
        project_root: The target project's repo root.
        assets_src: The master ``ai-dev/iw-assets`` directory in the platform repo.
        check_only: When True, report what would change without writing anything.

    Returns:
        An :class:`AssetSyncResult` describing copied / up-to-date / errored files.
    """
    result = AssetSyncResult()

    if not assets_src.is_dir():
        result.errors.append(f"Asset source directory not found: {assets_src}")
        return result

    dst_root = project_root / "ai-dev" / "iw-assets"

    # No-op when the project IS the platform repo (don't copy a tree onto itself).
    if dst_root.resolve() == assets_src.resolve():
        for src_file in _iter_files(assets_src):
            result.up_to_date.append(str(src_file.relative_to(assets_src)))
        return result

    for src_file in _iter_files(assets_src):
        rel = src_file.relative_to(assets_src)
        dst_file = dst_root / rel
        needs_update = not dst_file.exists() or not filecmp.cmp(src_file, dst_file, shallow=False)
        if not needs_update:
            result.up_to_date.append(str(rel))
            continue
        if not check_only:
            try:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
            except OSError as exc:
                result.errors.append(f"{rel}: {exc}")
                continue
        result.copied.append(str(rel))

    return result
