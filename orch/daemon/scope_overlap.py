"""Glob intersection helpers for the F-00076 cross-batch conflict gate.

Pure functions — no DB, no logging beyond local imports. Imported by
batch_manager._process_batch() to decide whether a candidate item conflicts
with any in-flight item in the same project.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_TEST_PATH_MARKERS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    "conftest",
    ".test.",
    ".spec.",
)


def is_test_path(glob: str) -> bool:
    """Return True when the glob targets test files only.

    Mirror orch/batch_planner.py:_is_test_path semantics.
    Also recognises relative test directories (tests/, test/, __tests__/)
    as the first path segment.
    """
    if glob.startswith(("tests/", "test/", "__tests__/")):
        return True
    return any(marker in glob for marker in _TEST_PATH_MARKERS)


def _strip_test_globs(globs: Iterable[str]) -> list[str]:
    return [g for g in globs if not is_test_path(g)]


def _pattern_to_anchor(pattern: str) -> str:
    """Strip trailing /** and * from a glob to produce its directory anchor.

    Examples:
        "src/app/**/*.py"  -> "src/app"
        "src/app/**"       -> "src/app"
        "src/app/*.py"     -> "src/app"
        "src/app/main.py"  -> "src/app/main.py"
        "**"               -> "**"
    """
    # Handle /** anywhere in the pattern (globstar)
    if "/**" in pattern:
        idx = pattern.index("/**")
        return pattern[:idx]
    # Strip trailing /** or /*
    while True:
        if pattern.endswith("/**"):
            pattern = pattern[:-3]
        elif pattern.endswith("/*"):
            pattern = pattern[:-2]
        elif pattern.endswith("/"):
            pattern = pattern[:-1]
        else:
            break
    return pattern


def _is_under_dir(path: str, directory: str) -> bool:
    """Return True when `path` is at or under `directory` (same tree)."""
    return path == directory or path.startswith(directory + "/")


def globs_intersect(a: list[str], b: list[str]) -> list[str]:
    """Return globs from `a` that share at least one matching path with any
    glob in `b`, after stripping test-path globs from both sides.

    Implementation:
    - Exact path match: pattern == b_path
    - fnmatch: fnmatch(b_path, pattern) handles ** and wildcards
    - Anchor containment: b_path is under the anchor directory

    Limitations: Patterns that diverge significantly from gitignore-style
    (e.g. character classes intersecting only on synthetic strings) may
    produce false-negative non-overlaps; in that case rebase-time scope_gate
    is the safety net.

    Returns the conflicting globs from `a` (deduped, original order
    preserved). Empty list when there is no overlap.
    """
    a = _strip_test_globs(a)
    b_stripped = _strip_test_globs(b)

    if not a or not b_stripped:
        return []

    conflicting: list[str] = []
    seen: set[str] = set()

    for pattern in a:
        anchor = _pattern_to_anchor(pattern)

        for b_path in b_stripped:
            # Exact match
            if pattern == b_path:
                if pattern not in seen:
                    conflicting.append(pattern)
                    seen.add(pattern)
                continue

            # fnmatch (handles **, *, ?)
            if fnmatch.fnmatch(b_path, pattern):
                if pattern not in seen:
                    conflicting.append(pattern)
                    seen.add(pattern)
                continue

            # Anchor containment: b_path is under the anchor directory
            if anchor and anchor != "**" and _is_under_dir(b_path, anchor):
                if pattern not in seen:
                    conflicting.append(pattern)
                    seen.add(pattern)
                continue

    return conflicting


def find_blocking_items(
    candidate_paths: list[str],
    in_flight: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    """For each (item_id, paths) in `in_flight`, return those that conflict
    with `candidate_paths`. The second element of each result tuple is the
    list of conflicting globs (intersection from candidate's side).

    Conflict semantics: only exact path / glob intersection (via
    `globs_intersect`). Two items that merely touch sibling files under the
    same parent directory do NOT block each other — that policy proved too
    coarse and serialised batches whose planner-assigned execution_group had
    already declared them parallel-safe. This keeps the runtime gate aligned
    with `orch/batch_planner.py`'s intra-batch overlap detection (strict set
    intersection on impacted_paths).
    """
    if not candidate_paths or not in_flight:
        return []

    result: list[tuple[str, list[str]]] = []

    candidate_paths = _strip_test_globs(candidate_paths)
    if not candidate_paths:
        return []

    for item_id, in_flight_paths in in_flight:
        in_flight_paths = _strip_test_globs(in_flight_paths)
        intersecting = globs_intersect(candidate_paths, in_flight_paths)
        if intersecting:
            result.append((item_id, intersecting))

    return result
