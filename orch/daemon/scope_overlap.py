"""Glob intersection helpers for the F-00076 cross-batch conflict gate.

Pure functions — no DB, no logging beyond local imports. Imported by
batch_manager._process_batch() to decide whether a candidate item conflicts
with any in-flight item in the same project.

Conflict detection is solely via ``globs_intersect`` — exact-file matches,
fnmatch wildcards, and glob-anchor containment. The sibling-directory rule
was removed in I-00099 (2026-05-18) after it generated false-positive holds
on large dirs like ``docs/``, ``orch/daemon/``, and ``dashboard/routers/``.
The remaining safety nets are:

  (a) ``globs_intersect`` still catches exact-file matches and glob-anchor
      containment;
  (b) items that genuinely need module-level exclusion declare ``dir/**``
      explicitly;
  (c) git merge resolves real text conflicts.

Two concrete cases motivated the removal: ``docs/IW_AI_Core_Testing_Strategy.md``
vs ``docs/IW_AI_Core_AI_Assistant_Models.md`` (CR-00060 ↔ CR-00057) and
``orch/daemon/batch_manager.py`` vs ``orch/daemon/project_registry.py``
(same two items) — both produced sibling-directory false positives in
production before the fix.
"""

from __future__ import annotations

import fnmatch
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

# Default allow patterns for test paths — mirrors the historical implicit
# is_test_path strip. These are factored into DEFAULT_BLOCK_PATTERNS
# so that projects with no .iw-orch.json overlap_gate block get the same
# behaviour as before (tests/**, conftest, *.test.*, *.spec.* etc. are
# allowed through the gate by default).
DEFAULT_ALLOW_PATTERNS: tuple[str, ...] = (
    "tests/**",
    "test/**",
    "__tests__/**",
    "**/*conftest*",
    "**/*.test.*",
    "**/*.spec.*",
)
DEFAULT_BLOCK_PATTERNS: tuple[str, ...] = ("**/*",)

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


def _matches(glob: str, pattern: str) -> bool:
    """Return True when `glob` matches `pattern` via fnmatch + anchor-containment.

    Anchor-containment means a pattern like ``dashboard/**`` matches
    ``dashboard/static/chat_assistant/chat.js`` even though plain fnmatch
    would not (because the literal ``/`` between ``dashboard`` and ``static``
    does not satisfy ``**`` in fnmatch semantics).
    """
    # Fast path: direct fnmatch
    try:
        if fnmatch.fnmatch(glob, pattern):
            return True
    except Exception:  # noqa: BLE001
        logger.warning("fnmatch error on glob=%r pattern=%r — treated as no match", glob, pattern)
        return False

    # Anchor-containment: check whether the glob is under the pattern's anchor.
    anchor = _pattern_to_anchor(pattern)
    return bool(anchor and anchor != "**" and _is_under_dir(glob, anchor))


def globs_intersect(a: list[str], b: list[str]) -> list[str]:
    """Return globs from `a` that share at least one matching path with any
    glob in `b`.

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
    if not a or not b:
        return []

    conflicting: list[str] = []
    seen: set[str] = set()

    for pattern in a:
        anchor = _pattern_to_anchor(pattern)

        for b_path in b:
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

            # Reverse anchor containment: a's anchor (directory) contains b_path.
            # This handles the case where b is a dir-glob (e.g. "dir/**") and a
            # is a concrete file under that same directory.
            b_anchor = _pattern_to_anchor(b_path)
            if b_anchor and b_anchor != "**" and _is_under_dir(pattern, b_anchor):
                if pattern not in seen:
                    conflicting.append(pattern)
                    seen.add(pattern)
                continue

    return conflicting


def find_blocking_items(
    candidate_paths: list[str],
    in_flight: list[tuple[str, list[str]]],
    *,
    block_patterns: list[str],
    allow_patterns: list[str],
) -> list[tuple[str, list[str]]]:
    """For each (item_id, paths) in `in_flight`, return those that conflict
    with `candidate_paths`. The second element of each result tuple is the
    list of conflicting globs (from the candidate's side) after applying
    the per-project block/allow policy.

    Policy evaluation (per conflicting glob):
      1. If no block_patterns are given, the gate is off — never blocks.
      2. The glob is checked against each block_pattern via
         ``_matches(glob, pattern)`` + anchor-containment. If it matches
         any block_pattern it is in-scope for gating.
      3. If the glob also matches any allow_pattern it is dropped from the
         intersecting list.
      4. If the filtered list for an in-flight item is empty, that item
         does not appear in the result.

    Args:
        candidate_paths: impacted_paths from the candidate work item.
        in_flight: list of (work_item_id, impacted_paths) for in-flight items.
        block_patterns: glob patterns that define in-scope overlap. An empty
            list means the gate is disabled — nothing will be considered
            blocking.
        allow_patterns: glob patterns that exempt a conflicting glob from
            blocking. Applied per-glob (not all-or-nothing).

    Returns:
        list[tuple[item_id, conflicting_globs]] in original order.
    """
    if not candidate_paths or not in_flight:
        return []

    # Gate off: empty block_patterns means never block.
    if not block_patterns:
        return []

    result: list[tuple[str, list[str]]] = []

    for item_id, in_flight_paths in in_flight:
        intersecting = globs_intersect(candidate_paths, in_flight_paths)
        if not intersecting:
            continue

        # Filter: keep only globs that are in-scope (match a block_pattern).
        in_scope: list[str] = []
        for g in intersecting:
            matched_block = False
            for bp in block_patterns:
                try:
                    if _matches(g, bp):
                        matched_block = True
                        break
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "find_blocking_items: unparseable block pattern %r — skipping", bp
                    )
                    break
            if matched_block:
                in_scope.append(g)

        if not in_scope:
            continue

        # Allow filter: per-glob exemption.
        allowed: list[str] = []
        for g in in_scope:
            matched_allow = False
            for ap in allow_patterns:
                try:
                    if _matches(g, ap):
                        matched_allow = True
                        break
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "find_blocking_items: unparseable allow pattern %r — skipping", ap
                    )
                    break
            if not matched_allow:
                allowed.append(g)

        if allowed:
            result.append((item_id, allowed))

    return result
