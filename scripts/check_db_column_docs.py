"""Scan SQLAlchemy model columns for missing doc= descriptions.

One violation category is detected (see CR-00085 / TESTS_ENHANCEMENT.md §8
row 4.5):

  missing-doc  A SQLAlchemy `Column` on a mapped class whose declaration
               carries no `doc=` argument (or the doc string is empty),
               and whose fully-qualified name is not in the baseline allowlist.

Acceptable description carriers (in priority order):

  1. `col.doc` is truthy — the `doc` attribute on the SQLAlchemy ``Column``
     object is a non-empty string.
  2. The column's FQN (e.g. ``orch.db.models.WorkItem.id``) appears in the
     baseline file (one FQN per line; ``#``-prefixed lines and blank lines
     are comments).

Anything else is a violation.

Usage:
    python scripts/check_db_column_docs.py
    python scripts/check_db_column_docs.py --baseline <path>
    python scripts/check_db_column_docs.py --write-baseline <path>
    python scripts/check_db_column_docs.py --strict
    python scripts/check_db_column_docs.py --json

Exit 0 if no new violations (after baseline), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Mapper

BASELINE_HEADER = """\
# DB-column doc baseline (CR-00085).
#
# Each line is one fully-qualified column name that currently lacks a
# `doc=` argument on its SQLAlchemy Column declaration. Format:
#
#     <module>.<Class>.<sql_column_name>
#
# Purpose: this is a *cleanup backlog*, not an accept-list. The gate
# (`make check-column-docs`) admits these legacy offenders so we can
# land the scanner without first writing descriptions for every column,
# but flags any NEW undocumented column added after this baseline.
#
# The right way to silence the gate is to ADD a real `doc="..."` on the
# Column declaration, NOT to add the FQN to this file. Run
#
#     uv run python scripts/check_db_column_docs.py \\
#         --write-baseline orch/db/column_docs_baseline.txt
#
# only when you have *intentionally* accepted a legacy column staying
# undocumented (rare; reviewers should push back).
"""


@dataclass(frozen=True)
class Violation:
    """A column declared without a doc= argument and not in the baseline."""

    module: str
    class_name: str
    column_name: str
    fqn: str
    message: str

    def as_baseline_line(self) -> str:
        """One-line FQN for baseline file (no category — only one category)."""
        return self.fqn

    def as_human_line(self) -> str:
        return f"{self.fqn}: {self.message}"

    def as_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "class_name": self.class_name,
            "column_name": self.column_name,
            "fqn": self.fqn,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Core scanning logic
# ---------------------------------------------------------------------------


def scan(
    baseline: Iterable[str] | Path | None = None,
    mappers: Iterable[Mapper] | None = None,
) -> list[Violation]:
    """Scan model columns, returning violations not covered by the baseline.

    Parameters
    ----------
    baseline:
        Iterable of FQN strings that are already accepted, or a ``Path`` to a
        baseline file (one FQN per line).  If a ``Path`` that does not exist is
        passed, a ``FileNotFoundError`` is raised.  ``None`` / empty iterable
        means "no legacy allowlist" (pure audit mode).
    mappers:
        Iterable of SQLAlchemy ``Mapper`` objects to scan.  When ``None``,
        defaults to all mappers reachable from ``orch.db.models.Base``.
        Passing an explicit list is useful in tests and for composable use.

    Returns
    -------
    list[Violation]
        All undocumented columns not in the baseline.
    """
    # Resolve default mappers.
    if mappers is None:
        from orch.db.models import Base

        mappers = list(Base.registry.mappers)

    # Resolve baseline.
    if isinstance(baseline, Path):
        if not baseline.exists():
            raise FileNotFoundError(f"--baseline path not found: {baseline}")
        baseline_set = _load_baseline(baseline)
    else:
        baseline_set = set(baseline) if baseline is not None else set()

    violations: list[Violation] = []
    for mapper in mappers:
        cls = mapper.class_
        for col in mapper.local_table.columns:
            fqn = f"{cls.__module__}.{cls.__name__}.{col.name}"
            if fqn in baseline_set:
                continue
            if bool(col.doc):
                continue
            violations.append(
                Violation(
                    module=cls.__module__,
                    class_name=cls.__name__,
                    column_name=col.name,
                    fqn=fqn,
                    message="missing description",
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Baseline I/O helpers
# ---------------------------------------------------------------------------


def _load_baseline(path: Path) -> set[str]:
    """Parse baseline file (one FQN per non-comment line)."""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out


def _write_baseline(path: Path, violations: list[Violation]) -> None:
    """Write the current violation set as a sorted baseline file.

    Args:
        path: Destination path for the baseline file.
        violations: Current violations to persist as the new accepted backlog.
    """
    lines = sorted({v.as_baseline_line() for v in violations})
    body = BASELINE_HEADER + "\n".join(lines) + ("\n" if lines else "")
    path.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for check_db_column_docs.

    Returns:
        Configured ArgumentParser with baseline, write-baseline, strict, and
        JSON output flags.
    """
    parser = argparse.ArgumentParser(
        prog="check_db_column_docs",
        description=(
            "Scan SQLAlchemy model columns for undocumented columns "
            "(missing doc=). Exit 1 on new violations (after baseline)."
        ),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline file; FQNs listed there don't count toward exit code.",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help="Overwrite the given file with the current violation set (sorted) and exit 0.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Ignore --baseline; every violation contributes to exit code.",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help='Emit {"violations":[...]} to stdout instead of human-readable lines.',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Scan SQLAlchemy model columns for missing ``doc=`` descriptions and report results.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]`` when None.

    Returns:
        0 when no new violations are found (after baseline), 1 otherwise.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --write-baseline: scan all mappers, write, and exit 0.
    if args.write_baseline is not None:
        violations = scan()
        _write_baseline(args.write_baseline, violations)
        return 0

    # Apply baseline unless --strict.
    if args.baseline is not None and not args.strict:
        baseline_set = _load_baseline(args.baseline)
        violations = scan(baseline=baseline_set)
    else:
        violations = scan()

    # JSON output mode.
    if args.json_output:
        payload = {"violations": [v.as_dict() for v in violations]}
        print(json.dumps(payload))
    else:
        for v in violations:
            print(v.as_human_line())
        if not violations:
            print("No new undocumented columns found.")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
