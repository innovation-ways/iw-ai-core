#!/usr/bin/env python3
"""Static lint for Alembic migration files — catch hardcoded down_revision.

WHAT IT CHECKS
  Every newly-added migration file (git diff vs main) must set
  ``down_revision = "PENDING"`` (literal string) rather than a hardcoded
  revision hash.  ``migration_rebase.py`` resolves "PENDING" into the real
  chain head at merge time (see CR-00091).

WHY IT IS DIFF-SCOPED
  Once a migration is merged, ``migration_rebase.py`` resolves "PENDING" to
  the real hash and commits that.  Every committed migration on ``main``
  therefore carries a real hash — there are 84 migrations on main today and
  0 of them use ``"PENDING"`` (83 real hashes + 1 baseline ``None``).
  A whole-directory scan that requires ``"PENDING"`` would flag all 83
  committed migrations and break ``make lint`` on a clean checkout.

  This script inspects ONLY migration files that are **added in the current
  branch** (git diff vs ``main`` / ``origin/main``).  Those are the only
  files that should still hold ``"PENDING"`` — they are resolved later,
  at merge time, by the daemon.

WHAT IS ALLOWED
  - ``down_revision = "PENDING"`` — sentinel for new migrations in a branch
  - ``down_revision = None`` — baseline migration only
  - ``down_revision = ("PENDING", "abc123")`` — merge migration (tuple form)

WHAT IS FLAGGED
  - ``down_revision = "abc123"`` — hardcoded hash (not PENDING)
  - ``down_revision: str | None = 'abc123'`` — type annotation + hardcoded hash

Exit code 0 = clean / no added migrations, 1 = violations found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_SUBDIR = "orch/db/migrations/versions"

# Match a down_revision assignment to a quoted string that is NOT "PENDING".
# Allows type annotations (e.g. `down_revision: str | None = 'abc123'`).
# Does NOT match:
#   - "PENDING"       (allowed sentinel)
#   - None            (no quotes)
#   - ("PENDING", ...) (tuple — equals sign not immediately followed by a quote)
_DOWN_REVISION_RE = re.compile(
    r'^\s*down_revision\s*(?::[^=]*)?\s*=\s*(?P<val>["\'](?!PENDING)[^"\']+["\'])',
    re.MULTILINE,
)


def check_file(path: Path) -> list[tuple[int, str]]:
    """Check a single migration file for hardcoded down_revision violations.

    Pure predicate — no git assumptions, no directory assumptions.
    Returns a list of (lineno, snippet) for each violation found.
    """
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _DOWN_REVISION_RE.search(line):
            findings.append((lineno, line.strip()))
    return findings


def _current_branch() -> str | None:
    """Return the current git branch name, or None if it cannot be determined."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _added_migration_files() -> list[Path]:
    """Discover migration files added in the current branch vs main.

    Returns [] immediately when running on the main branch itself — migrations
    committed directly to main have already been "merged" (their down_revision
    values are real hashes, not PENDING, which is correct post-merge state).
    The PENDING check is only meaningful on feature/fix branches pending merge
    through the daemon's migration_rebase.py queue.

    Fails open: if no base ref resolves or any git call fails, returns []
    so the run exits 0 rather than crashing lint.
    """
    if _current_branch() == "main":
        return []

    # Determine base ref — try origin/main first, then main
    for ref in ("origin/main", "main"):
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", ref],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
            base_ref = ref
            break
        except subprocess.CalledProcessError:
            continue
    else:
        # No base ref resolved (e.g. detached worktree with no main branch)
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--diff-filter=AM", "--name-only", base_ref, "--", MIGRATIONS_SUBDIR],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        # git diff error — fail open
        return []

    files: list[Path] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        path = REPO_ROOT / line.strip()
        if path.is_file() and not any(p == "__pycache__" for p in path.parts):
            files.append(path)

    return files


def main() -> int:
    """Scan newly-added migration files for hardcoded ``down_revision`` values.

    Returns:
        0 when no violations are found (or no added migrations exist), 1 otherwise.
    """
    violations: list[str] = []
    for path in _added_migration_files():
        for lineno, snippet in check_file(path):
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{lineno}: {snippet}")

    if violations:
        sys.stderr.write(
            "ERROR: down_revision must be 'PENDING' in new migrations.\n"
            "  New migration files (git diff vs main) that set down_revision to a\n"
            "  hardcoded hash will break migration_rebase.py at merge time.\n"
            "  Use 'PENDING' (resolved by migration_rebase.py at merge).\n"
            "  Allowed: 'PENDING', None, ('PENDING', 'abc123').\n"
            "  FlAGGED: down_revision = 'abc123' (hardcoded hash).\n\n"
        )
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
