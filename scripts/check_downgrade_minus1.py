#!/usr/bin/env python3
"""Static lint for test files — catch downgrade("-1") / downgrade('-1').

tests/CLAUDE.md rule 4a states:
  "NEVER invoke `alembic` directly from test code outside of dedicated
   migration-round-trip tests. In those tests, downgrade to a *specific
   revision ID*, never `-1`, so the test stays stable as new migrations
   land on top."

Using `-1` in a test is fragile because `-1` means "one step back from
the current head", which changes as new migrations are added. A test
written with `-1` in a worktree may pass locally but fail in CI or a
future worktree where more migrations have landed. The check enforces
the rule at lint time rather than letting the failure surface after
minutes of testcontainer run time.

Exit code 0 = clean, 1 = violations found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches downgrade(...) called with a quoted "-1" or '-1' as the second
# positional argument (or any argument after the first comma).
# Scans for patterns like:  downgrade(cfg, "-1")  /  downgrade(cfg, '-1')
# Skips:   downgrade(cfg, "abc123")  ← specific revision is fine
#          downgrade(cfg, None)       ← None is fine
_BAD_DOWNGRADE_RE = re.compile(r'\bdowngrade\s*\([^)]*,\s*["\'](-1)["\']')

# Files that are allowed to contain downgrade("-1") — specifically,
# tests of this very script and self-referential examples.
_EXCLUDED_BASENAMES = frozenset(["__init__.py", "test_lint_scripts.py"])


def check_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _BAD_DOWNGRADE_RE.search(line):
            findings.append((lineno, line.strip()))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan test files for downgrade('-1') violations.",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=REPO_ROOT / "tests",
        help="Directory to scan (default: <repo>/tests)",
    )
    args = parser.parse_args(argv)

    violations: list[str] = []
    for py_file in args.tests_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if py_file.name in _EXCLUDED_BASENAMES:
            continue
        for lineno, snippet in check_file(py_file):
            rel = py_file.relative_to(args.tests_dir)
            violations.append(f"{rel}:{lineno}: {snippet}")

    if violations:
        sys.stderr.write(
            "ERROR: downgrade('-1') found in test file(s).\n"
            "  tests/CLAUDE.md rule 4a: always downgrade to a *specific revision ID*,\n"
            "  never -1, so tests stay stable as new migrations land.\n\n"
        )
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
