"""Scan test files for vacuous tests that can't fail.

Four categories are detected (see CR-00046 / Phase-1 P1-CR-A and
`docs/IW_AI_Core_Testing_Strategy.md` §7 / `skills/iw-ai-core-testing/SKILL.md` §1):

  no-assert    A `test_*` (or `async def test_*`) function whose body has no
               assertion of any kind — no `assert`, no `pytest.raises` /
               `pytest.warns`, no `mock.assert_called*` / `mock.assert_await*`.
  tautology    Every `assert` in the body matches a tautological form
               (`assert True`, `assert <bare Name>`, `assert x == x`,
               `assert isinstance(x, T)`, `assert x is not None`,
               `assert len(x) > 0`/`>= 1`/`!= 0`, `assert <expr> in <expr>`).
               Mixed (one tautological + one specific) is OK.
  mock-only    Every assertion-bearing statement is `mock.assert_called*` /
               `mock.assert_await*` on a receiver name containing
               `mock`/`Mock` (case-insensitive substring).
  broad-raises `with pytest.raises(<expr>):` (or bare call form) where
               `<expr>` is `Exception` or `BaseException` and there is no
               `match=` keyword argument.

Usage:
    python scripts/check_test_assertions.py [PATH...]
    python scripts/check_test_assertions.py --baseline <path> tests/
    python scripts/check_test_assertions.py --write-baseline <path> tests/
    python scripts/check_test_assertions.py --strict tests/
    python scripts/check_test_assertions.py --json tests/

A test may be flagged under multiple categories — one entry is emitted per
(path, line, test_name, category). `# noqa: assertion-scanner` on the `def`
line suppresses the report for that specific test.

`tests/conftest.py` and any `**/conftest.py` are skipped (fixtures, not tests).

Exit 0 if no new violations (after baseline), 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ASSERT_CALL_NAMES = frozenset({"raises", "warns"})  # pytest.raises, pytest.warns

CATEGORY_NO_ASSERT = "no-assert"
CATEGORY_TAUTOLOGY = "tautology"
CATEGORY_MOCK_ONLY = "mock-only"
CATEGORY_BROAD_RAISES = "broad-raises"


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    category: str
    test_name: str
    message: str

    def as_baseline_line(self) -> str:
        """Format the violation as a single baseline-file entry.

        Returns:
            A string of the form ``path::test_name # category``.
        """
        return f"{self.path}::{self.test_name} # {self.category}"

    def as_human_line(self) -> str:
        """Format the violation as a human-readable output line.

        Returns:
            A colon-delimited string including path, line, category, test name,
            and message.
        """
        return f"{self.path}:{self.line}: {self.category}: {self.test_name}: {self.message}"

    def as_dict(self) -> dict[str, object]:
        """Serialise the violation to a JSON-safe dict.

        Returns:
            Dict with keys ``path``, ``line``, ``category``, ``test_name``,
            and ``message``.
        """
        return {
            "path": self.path,
            "line": self.line,
            "category": self.category,
            "test_name": self.test_name,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# AST helpers — assertion classification
# ---------------------------------------------------------------------------


def _is_pytest_raises_call(call: ast.Call) -> bool:
    """True if `call` is `pytest.raises(...)`, `pytest.warns(...)`, or bare `raises(...)`."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in ASSERT_CALL_NAMES:
        return True
    return isinstance(func, ast.Name) and func.id in ASSERT_CALL_NAMES


def _is_mock_assert_call(call: ast.Call) -> bool:
    """True if `call` is `<expr>.assert_called*(...)` or `.assert_await*(...)`."""
    func = call.func
    return isinstance(func, ast.Attribute) and (
        func.attr.startswith("assert_call") or func.attr.startswith("assert_await")
    )


def _mock_receiver_name(call: ast.Call) -> str | None:
    """For a mock.assert_called*-style call, return the receiver Name id (or None)."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    value = func.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        # e.g. self.mock_dep.assert_called_once() — walk to the leftmost Name
        cur: ast.expr = value
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        if isinstance(cur, ast.Name):
            return cur.id
        # Use the attribute itself as the "name" fallback
        return value.attr
    return None


def _name_looks_like_mock(name: str | None) -> bool:
    if name is None:
        return False
    return "mock" in name.lower()


def _is_tautological_assert(node: ast.Assert) -> bool:
    """Return True when the assert matches a known tautological form.

    Tautological forms include: ``assert True``, ``assert <bare Name>``,
    ``assert isinstance(x, T)``, ``assert x is not None``,
    ``assert len(x) > 0`` / ``>= 1`` / ``!= 0``, ``assert x == x``,
    and ``assert <expr> in <expr>``.

    Args:
        node: AST Assert node to classify.

    Returns:
        True when every branch of the assert would pass trivially regardless
        of production correctness.
    """
    test = node.test

    # assert True
    if isinstance(test, ast.Constant) and test.value is True:
        return True

    # assert <bare Name> (truthiness only)
    if isinstance(test, ast.Name):
        return True

    # assert isinstance(x, T) — whole assertion is isinstance(...)
    if (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
    ):
        return True

    # assert x is not None — whole assertion
    if isinstance(test, ast.Compare):
        # x == x (same Name both sides)
        if (
            len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.left, ast.Name)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Name)
            and test.left.id == test.comparators[0].id
        ):
            return True

        # x is not None
        if (
            len(test.ops) == 1
            and isinstance(test.ops[0], ast.IsNot)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
        ):
            return True

        # len(x) > 0 / >= 1 / != 0
        if (
            len(test.ops) == 1
            and isinstance(test.left, ast.Call)
            and isinstance(test.left.func, ast.Name)
            and test.left.func.id == "len"
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
        ):
            op = test.ops[0]
            rhs = test.comparators[0].value
            if isinstance(op, ast.Gt) and rhs == 0:
                return True
            if isinstance(op, ast.GtE) and rhs == 1:
                return True
            if isinstance(op, ast.NotEq) and rhs == 0:
                return True

        # `<expr> in <expr>` (whole assertion is a single membership test)
        if len(test.ops) == 1 and isinstance(test.ops[0], ast.In):
            return True

    return False


# ---------------------------------------------------------------------------
# Function-level analysis
# ---------------------------------------------------------------------------


def _function_assertions(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[list[ast.Assert], list[ast.Call], list[ast.Call]]:
    """Return (assert_nodes, raises_calls, mock_calls) found in the body.

    `raises_calls` are `pytest.raises(...)` / `pytest.warns(...)` Call nodes
    (whether used as a context manager or bare expression). `mock_calls` are
    `<expr>.assert_called*` / `<expr>.assert_await*` Call nodes.
    """
    asserts: list[ast.Assert] = []
    raises_calls: list[ast.Call] = []
    mock_calls: list[ast.Call] = []

    for child in ast.walk(func):
        if isinstance(child, ast.Assert):
            asserts.append(child)
            continue
        if isinstance(child, ast.Call):
            if _is_pytest_raises_call(child):
                raises_calls.append(child)
            elif _is_mock_assert_call(child):
                mock_calls.append(child)

    return asserts, raises_calls, mock_calls


def _broad_raises_violations(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.Call]:
    """Return any `pytest.raises(Exception)` / `(BaseException)` calls without `match=`."""
    flagged: list[ast.Call] = []
    for child in ast.walk(func):
        if not isinstance(child, ast.Call) or not _is_pytest_raises_call(child):
            continue
        if not child.args:
            continue
        first = child.args[0]
        if not (isinstance(first, ast.Name) and first.id in {"Exception", "BaseException"}):
            continue
        if any(kw.arg == "match" for kw in child.keywords):
            continue
        flagged.append(child)
    return flagged


def _has_noqa_suppression(source_lines: list[str], lineno: int) -> bool:
    """Return True when the function's ``def`` line carries an assertion-scanner noqa comment.

    Args:
        source_lines: All lines of the source file (1-indexed via list offset).
        lineno: 1-based line number of the ``def`` statement.

    Returns:
        True when ``# noqa`` and ``assertion-scanner`` both appear on the line.
    """
    if lineno < 1 or lineno > len(source_lines):
        return False
    line = source_lines[lineno - 1]
    # Look for the marker comment (case-insensitive on `noqa`, exact on the code).
    lowered = line.lower()
    return "noqa" in lowered and "assertion-scanner" in line


# ---------------------------------------------------------------------------
# Per-file scan
# ---------------------------------------------------------------------------


def scan_file(path: Path, repo_root: Path | None = None) -> list[Violation]:
    """Return the list of violations for `path`."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    source_lines = source.splitlines()
    display_path = _display_path(path, repo_root)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        if _has_noqa_suppression(source_lines, node.lineno):
            continue

        asserts, raises_calls, mock_calls = _function_assertions(node)

        # no-assert: nothing of any kind
        if not asserts and not raises_calls and not mock_calls:
            violations.append(
                Violation(
                    path=display_path,
                    line=node.lineno,
                    category=CATEGORY_NO_ASSERT,
                    test_name=node.name,
                    message="function body contains no assertions",
                )
            )

        # tautology: every `assert` matches a tautological pattern
        if asserts and all(_is_tautological_assert(a) for a in asserts):
            violations.append(
                Violation(
                    path=display_path,
                    line=node.lineno,
                    category=CATEGORY_TAUTOLOGY,
                    test_name=node.name,
                    message=(
                        "every assert matches a tautological form "
                        "(is not None / isinstance / len > 0)"
                    ),
                )
            )

        # mock-only: only assertion-bearing statements are mock.assert_called*
        # on a mock-named receiver (no asserts, no pytest.raises).
        if (
            not asserts
            and mock_calls
            and not raises_calls
            and all(_name_looks_like_mock(_mock_receiver_name(c)) for c in mock_calls)
        ):
            violations.append(
                Violation(
                    path=display_path,
                    line=node.lineno,
                    category=CATEGORY_MOCK_ONLY,
                    test_name=node.name,
                    message=(
                        "only assertions are mock.assert_called*/assert_await* "
                        "on mock-named receivers"
                    ),
                )
            )

        # broad-raises: pytest.raises(Exception) without match=
        if _broad_raises_violations(node):
            violations.append(
                Violation(
                    path=display_path,
                    line=node.lineno,
                    category=CATEGORY_BROAD_RAISES,
                    test_name=node.name,
                    message="pytest.raises(Exception) without match= — too broad",
                )
            )

    return violations


def _display_path(path: Path, repo_root: Path | None) -> str:
    """Render a path as POSIX, relative to `repo_root` when possible."""
    try:
        if repo_root is not None:
            rel = path.resolve().relative_to(repo_root.resolve())
            return rel.as_posix()
    except ValueError:
        pass
    return path.as_posix()


# ---------------------------------------------------------------------------
# Baseline file I/O
# ---------------------------------------------------------------------------


BASELINE_HEADER = """\
# AST assertion-scanner baseline (CR-00046, Phase-1 P1-CR-A).
#
# This file lists test functions that are currently flagged by
# scripts/check_test_assertions.py. Each entry is one of:
#
#     <relative/path/to/test_file.py>::<test_name> # <category>
#
# where <category> is one of: no-assert, tautology, mock-only, broad-raises.
#
# Purpose: this is a *cleanup backlog*, not an accept-list. The gate
# (`make test-assertions` and the `assertions` QV gate) admits these
# legacy offenders so we can land the scanner without first cleaning
# every test, but flags any NEW violations introduced after this baseline.
#
# The right way to silence the gate is to FIX the test (give it a real,
# specific assertion that would fail if the production code regressed) —
# NOT to add it to this file. Run
#
#     uv run python scripts/check_test_assertions.py \\
#         --write-baseline tests/assertion_free_baseline.txt tests/
#
# only when you have *intentionally* accepted that the listed tests stay
# weak (rare; reviewers should push back).
"""


def _load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out


def _write_baseline(path: Path, violations: list[Violation]) -> None:
    lines = sorted({v.as_baseline_line() for v in violations})
    body = BASELINE_HEADER + "\n".join(lines) + ("\n" if lines else "")
    path.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------


def _iter_test_files(root: Path) -> list[Path]:
    """Discover test files under ``root``, skipping conftest.py and non-test files.

    Args:
        root: A file or directory to search. A single file is returned as-is
              when it matches the ``test_*.py`` naming convention.

    Returns:
        Sorted list of test file paths found under ``root``.
    """
    if root.is_file():
        if root.name.startswith("test_") and root.suffix == ".py" and root.name != "conftest.py":
            return [root]
        return []
    if not root.exists():
        return []
    paths: list[Path] = []
    for p in sorted(root.rglob("test_*.py")):
        # Defensive: skip conftest-named files (they don't match test_*.py anyway).
        if p.name == "conftest.py":
            continue
        paths.append(p)
    return paths


def _resolve_repo_root() -> Path:
    """Return the repository root derived from this script's location.

    Returns:
        Absolute path two levels above this script (i.e. the project root).
    """
    # Scanner lives at <repo>/scripts/check_test_assertions.py.
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser for check_test_assertions.

    Returns:
        Configured ArgumentParser with all supported flags.
    """
    parser = argparse.ArgumentParser(
        prog="check_test_assertions",
        description=(
            "Scan Python test files for vacuous tests (no-assert, tautology, "
            "mock-only, broad-raises). Exit 1 on new violations (after baseline)."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["tests"],
        help="One or more files or directories to scan (default: tests).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to a baseline file; violations listed there don't count toward exit code.",
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
    """Run the assertion scanner over the requested paths and report violations.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]`` when None.

    Returns:
        0 when no new violations exist (after baseline), 1 otherwise.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = _resolve_repo_root()

    # Collect violations across all requested paths.
    all_violations: list[Violation] = []
    for raw in args.paths:
        root = Path(raw)
        for test_file in _iter_test_files(root):
            all_violations.extend(scan_file(test_file, repo_root=repo_root))

    # --write-baseline: regenerate the file from scratch and exit 0.
    if args.write_baseline is not None:
        _write_baseline(args.write_baseline, all_violations)
        return 0

    # Apply baseline allowance unless --strict.
    if args.baseline is not None and not args.strict:
        baseline = _load_baseline(args.baseline)
        new_violations = [v for v in all_violations if v.as_baseline_line() not in baseline]
    else:
        new_violations = list(all_violations)

    # JSON output mode.
    if args.json_output:
        payload = {"violations": [v.as_dict() for v in new_violations]}
        print(json.dumps(payload))
    else:
        for v in new_violations:
            print(v.as_human_line())
        if not new_violations:
            # Quiet on success (one short summary, like InnoForge's scanner).
            scanned = sum(1 for raw in args.paths for _ in _iter_test_files(Path(raw)))
            if scanned:
                print(f"No new assertion-scanner violations ({scanned} files scanned).")

    return 1 if new_violations else 0


if __name__ == "__main__":
    sys.exit(main())
