"""TDD tests for CR-00078: per-batch overlap ignore filtering.

RED case for filter_blocked_by_ignores (anchors tdd_red_evidence).
Full test coverage is owned by S10.

RED evidence: the initial `test_empty_ignores_returns_input` case in this
file was written pre-implementation. The ImportError failure was captured
in CR-00078_S04_Backend_report.md ("ImportError expected"). The helper
is now shipped in orch/daemon/scope_overlap.py — the existing case and
the new cases below are GREEN against the shipped implementation.
"""

from __future__ import annotations

from orch.daemon.scope_overlap import filter_blocked_by_ignores


class TestFilterBlockedByIgnoresEmpty:
    """RED: helper not yet implemented — ImportError expected (captured S04)."""

    def test_empty_ignores_returns_input(self) -> None:
        """When ignored_pairs is empty, filter_blocked_by_ignores returns input unchanged."""
        blocked_by = [
            ("CR-00072", ["docs/IW_AI_Core_Testing_Strategy.md"]),
            ("CR-00057", ["orch/daemon/batch_manager.py"]),
        ]
        result = filter_blocked_by_ignores(blocked_by, set())
        assert result == [
            ("CR-00072", ["docs/IW_AI_Core_Testing_Strategy.md"]),
            ("CR-00057", ["orch/daemon/batch_manager.py"]),
        ]


class TestFilterBlockedByIgnoresFull:
    """All globs of all blocking items are ignored — result is empty."""

    def test_full_ignore_returns_empty(self) -> None:
        """Every (blocking_id, glob) pair is ignored → empty list."""
        blocked_by = [
            ("CR-00072", ["docs/file_a.md", "docs/file_b.md"]),
            ("CR-00057", ["orch/batch_manager.py"]),
        ]
        ignored_pairs = {
            ("CR-00072", "docs/file_a.md"),
            ("CR-00072", "docs/file_b.md"),
            ("CR-00057", "orch/batch_manager.py"),
        }
        result = filter_blocked_by_ignores(blocked_by, ignored_pairs)
        assert result == []


class TestFilterBlockedByIgnoresPartial:
    """Some globs are ignored — only matching ones are dropped."""

    def test_partial_ignore_drops_only_matching_globs(self) -> None:
        """Ignore 1 of 3 globs on one blocking item; the other 2 survive."""
        blocked_by = [
            ("CR-00072", ["docs/intro.md", "docs/deep.md", "docs/guide.md"]),
        ]
        # Ignore only the middle glob
        ignored_pairs = {("CR-00072", "docs/deep.md")}
        result = filter_blocked_by_ignores(blocked_by, ignored_pairs)
        assert result == [("CR-00072", ["docs/intro.md", "docs/guide.md"])]


class TestFilterBlockedByIgnoresTupleDropped:
    """When all globs for a blocking item are ignored, the tuple is removed entirely."""

    def test_tuple_dropped_when_globs_empty(self) -> None:
        """The only glob on blocking_item A is ignored → A-tuple absent from result."""
        blocked_by = [
            ("BLOCK-A", ["only.txt"]),
            ("BLOCK-B", ["other.py", "more.py"]),
        ]
        ignored_pairs = {("BLOCK-A", "only.txt")}
        result = filter_blocked_by_ignores(blocked_by, ignored_pairs)
        # BLOCK-A tuple must not appear at all (not retained empty)
        assert result == [("BLOCK-B", ["other.py", "more.py"])]
        # Assert the exact structure: length == 1, and the surviving tuple is correct
        assert len(result) == 1
        assert result[0] == ("BLOCK-B", ["other.py", "more.py"])


class TestFilterBlockedByIgnoresStringEquality:
    """Ignore glob matching is exact string equality — no fnmatch."""

    def test_string_equality_not_fnmatch(self) -> None:
        """Exact match: ignore "dir/x.py" does NOT match "dir/*.py" in blocked_by."""
        blocked_by = [
            ("CR-00100", ["dir/*.py"]),
        ]
        # Exact string "dir/x.py" is not in blocked_by; the glob pattern "dir/*.py"
        # is only matched via fnmatch in scope_overlap.globs_intersect, not by the
        # ignore filter (which uses exact string equality per the design note).
        ignored_pairs = {("CR-00100", "dir/x.py")}
        result = filter_blocked_by_ignores(blocked_by, ignored_pairs)
        # The pattern "dir/*.py" is NOT dropped because "dir/x.py" != "dir/*.py"
        assert result == [("CR-00100", ["dir/*.py"])]

    def test_exact_string_match_drops_glob(self) -> None:
        """Exact match: ignore "dir/*.py" DOES drop "dir/*.py" from blocked_by."""
        blocked_by = [
            ("CR-00100", ["dir/*.py"]),
        ]
        ignored_pairs = {("CR-00100", "dir/*.py")}
        result = filter_blocked_by_ignores(blocked_by, ignored_pairs)
        assert result == []
