"""Innovation Ways doc-system distribution to managed projects.

The master doc-system config (brand, editorial guidelines, system instructions)
lives in the platform repo under ``ai-dev/doc-system/``. Every managed project
needs a local copy so the ``iw-doc-system`` doc-generation agent can read brand
colours and editorial rules and produce on-brand deliverables consistently
across the fleet. This module mirrors the *shared* part of that tree into a
project's ``ai-dev/doc-system/`` directory.

It is the doc-system analogue of :mod:`orch.skills.sync_assets` (brand assets)
and :mod:`orch.skills.sync` (skills): recursive, idempotent (skips byte-identical
files), and safe to run on every project repeatedly.

The per-project ``catalog/`` subtree is deliberately **excluded** — each project
catalogues its own documents, so syncing it would clobber project-owned state.
Only ``brand/``, ``editorial/``, and top-level files (e.g. ``CLAUDE.md``) are
distributed.
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

# Master doc-system directory, relative to the platform repo root.
DOC_SYSTEM_REL_PATH = "ai-dev/doc-system"

# Subdirectories that are project-specific and must never be overwritten by a
# sync. Each project owns its own document catalogue.
EXCLUDED_DIRS = ("catalog",)


@dataclass
class DocSystemSyncResult:
    """Outcome of syncing doc-system config into one project.

    Attributes:
        copied: Repo-relative paths of files written (or that would be written
            in check mode).
        up_to_date: Repo-relative paths already byte-identical at the target.
        skipped: Repo-relative paths skipped because they live under an excluded
            (project-specific) directory.
        errors: Human-readable messages for files that could not be copied.
    """

    copied: list[str] = field(default_factory=list)
    up_to_date: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _is_excluded(rel: Path) -> bool:
    """Return True when ``rel``'s top-level directory is project-specific."""
    return len(rel.parts) > 0 and rel.parts[0] in EXCLUDED_DIRS


def _iter_files(root: Path) -> list[Path]:
    """Return all regular files under ``root`` (recursive), sorted for stability."""
    return sorted(p for p in root.rglob("*") if p.is_file())


def sync_doc_system(
    project_root: Path,
    doc_system_src: Path,
    *,
    check_only: bool = False,
) -> DocSystemSyncResult:
    """Mirror the shared master doc-system config into a project's ``ai-dev/doc-system/``.

    Copies every file under ``doc_system_src`` to the matching path under
    ``project_root/ai-dev/doc-system``, preserving the directory structure, with
    the exception of the project-specific ``catalog/`` subtree which is left
    untouched. Byte-identical files are skipped. The operation is a no-op when
    the project is the platform repo itself (source and destination resolve to
    the same dir).

    Args:
        project_root: The target project's repo root.
        doc_system_src: The master ``ai-dev/doc-system`` directory in the
            platform repo.
        check_only: When True, report what would change without writing anything.

    Returns:
        A :class:`DocSystemSyncResult` describing copied / up-to-date / skipped /
        errored files.
    """
    result = DocSystemSyncResult()

    if not doc_system_src.is_dir():
        result.errors.append(f"doc-system source directory not found: {doc_system_src}")
        return result

    dst_root = project_root / "ai-dev" / "doc-system"

    # No-op when the project IS the platform repo (don't copy a tree onto itself).
    if dst_root.resolve() == doc_system_src.resolve():
        for src_file in _iter_files(doc_system_src):
            rel = src_file.relative_to(doc_system_src)
            if _is_excluded(rel):
                result.skipped.append(str(rel))
            else:
                result.up_to_date.append(str(rel))
        return result

    for src_file in _iter_files(doc_system_src):
        rel = src_file.relative_to(doc_system_src)
        if _is_excluded(rel):
            result.skipped.append(str(rel))
            continue
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
