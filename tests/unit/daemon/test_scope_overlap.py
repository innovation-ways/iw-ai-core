"""Unit tests for orch.daemon.scope_overlap — F-00076 cross-batch conflict gate.

Tests the pure glob-intersection helpers with no DB, no I/O.
"""

from __future__ import annotations

import pytest

from orch.daemon.scope_overlap import (
    _strip_test_globs,
    find_blocking_items,
    globs_intersect,
    is_test_path,
)


class TestIsTestPath:
    """Mirror orch/batch_planner.py:_is_test_path semantics."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            # Test directory markers
            ("src/tests/foo.py", True),
            ("src/test/foo.py", True),
            ("src/__tests__/foo.py", True),
            # I-00071: relative test-path prefixes (no leading slash)
            ("tests/dashboard/test_x.py", True),
            ("test/foo.py", True),
            ("__tests__/bar.py", True),
            ("tests/conftest.py", True),
            # I-00071: wider regression coverage
            ("pytest/conftest.py", True),
            ("nested/path/__tests__/file.py", True),
            ("tests/integration/test_x.py", True),
            ("__tests__/integration/foo.py", True),
            ("helpers/test_utils.py", False),  # not a test file — utility module
            # Test file markers
            ("conftest.py", True),
            ("src/conftest.py", True),
            ("foo.test.ts", True),
            ("bar.spec.js", True),
            ("helpers.test.py", True),
            # Non-test paths
            ("src/app/main.py", False),
            ("src/utils/helpers.py", False),
            ("src/__init__.py", False),
            ("testscript.sh", False),
            ("test_data.json", False),
            ("src/test_utils.py", False),  # test_utils is a utility module, not a test
            # Edge cases
            ("", False),
            ("/", False),
        ],
    )
    def test_is_test_path(self, path: str, expected: bool) -> None:
        assert is_test_path(path) is expected


class TestStripTestGlobs:
    def test_strips_test_paths(self) -> None:
        globs = [
            "src/app/**/*.py",
            "src/tests/**/*.py",
            "conftest.py",
            "src/__tests__/helpers.py",
            "src/lib/utils.py",
        ]
        result = _strip_test_globs(globs)
        assert result == ["src/app/**/*.py", "src/lib/utils.py"]

    def test_all_test_globs_returns_empty(self) -> None:
        # Only paths that contain a test marker are stripped.
        # "tests/**/*.py" has no test marker (no leading slash on "tests");
        # use "src/tests/**/*.py" which contains "/tests/"
        globs = ["src/tests/**/*.py", "conftest.py"]
        result = _strip_test_globs(globs)
        assert result == []

    def test_empty_input(self) -> None:
        assert _strip_test_globs([]) == []


class TestGlobsIntersect:
    """Test the probe-based glob intersection algorithm."""

    def test_exact_file_overlap(self) -> None:
        """Two identical file globs collide."""
        a = ["src/app/main.py", "src/app/config.py"]
        b = ["src/app/main.py", "src/app/other.py"]
        result = globs_intersect(a, b)
        assert "src/app/main.py" in result

    def test_dir_glob_intersection(self) -> None:
        """dir/** patterns that share a directory overlap."""
        a = ["src/app/**/*.py"]
        b = ["src/app/main.py", "src/app/config.py"]
        # Both probe patterns from a should match the b paths
        result = globs_intersect(a, b)
        assert result == ["src/app/**/*.py"]

    def test_wildcard_dir_glob_overlap(self) -> None:
        """src/** overlaps with src/app/main.py via the anchor probe."""
        a = ["src/**"]
        b = ["src/app/main.py", "other.txt"]
        result = globs_intersect(a, b)
        assert result == ["src/**"]

    def test_both_wildcard_dir_globs(self) -> None:
        """Two dir/** globs share a parent directory — they collide."""
        a = ["src/**"]
        b = ["src/app/**"]
        # Both have empty anchor after stripping /**, so they share root "src"
        result = globs_intersect(a, b)
        assert result == ["src/**"]

    def test_different_roots_no_overlap(self) -> None:
        """Completely different root paths do not overlap."""
        a = ["src/app/**/*.py"]
        b = ["lib/utils/**/*.py"]
        result = globs_intersect(a, b)
        assert result == []

    def test_mixed_test_and_prod_globs(self) -> None:
        """Test-path globs are stripped before intersection."""
        a = ["src/tests/**/*.py", "src/app/**/*.py"]
        b = ["src/tests/helpers.py", "src/app/main.py"]
        # After stripping test paths:
        # a -> ["src/app/**/*.py"]
        # b -> ["src/app/main.py"]
        # Intersection should include "src/app/**/*.py" since it overlaps with "src/app/main.py"
        result = globs_intersect(a, b)
        assert result == ["src/app/**/*.py"]

    def test_both_empty_lists(self) -> None:
        """Empty inputs return empty intersection."""
        assert globs_intersect([], []) == []
        assert globs_intersect(["a.py"], []) == []
        assert globs_intersect([], ["a.py"]) == []

    def test_double_wildcard_vs_exact(self) -> None:
        """** pattern matches anything — collides with any non-test exact path."""
        a = ["**"]
        b = ["src/app/main.py"]
        result = globs_intersect(a, b)
        assert result == ["**"]

    def test_double_wildcard_vs_dir_glob(self) -> None:
        """** collides with dir/** since both share root."""
        a = ["**"]
        b = ["src/app/**"]
        result = globs_intersect(a, b)
        assert result == ["**"]

    def test_no_overlap_returns_empty_list(self) -> None:
        """When there is no overlap, return the empty list (not None)."""
        a = ["src/a/**/*.py"]
        b = ["src/b/**/*.py"]
        result = globs_intersect(a, b)
        assert result == []

    def test_order_preserved_no_dups(self) -> None:
        """Results preserve original order from a, deduped."""
        a = ["src/app/main.py", "src/app/main.py", "src/lib/utils.py"]
        b = ["src/app/main.py", "src/lib/utils.py"]
        # First two are exact overlap; third is sibling overlap (same parent)
        result = globs_intersect(a, b)
        assert result == ["src/app/main.py", "src/lib/utils.py"]

    def test_nested_dir_with_intermediate_wildcard(self) -> None:
        """src/libs/**/*.py overlaps with src/libs/auth/utils.py."""
        a = ["src/libs/**/*.py"]
        b = ["src/libs/auth/utils.py", "src/libs/db/conn.py"]
        result = globs_intersect(a, b)
        assert result == ["src/libs/**/*.py"]


class TestFindBlockingItems:
    """Test find_blocking_items against in-flight scope tuples."""

    def test_no_blocking(self) -> None:
        """Candidate paths that don't overlap with any in-flight item."""
        candidate = ["src/app/main.py", "src/lib/utils.py"]
        in_flight = [
            ("F-00001", ["src/other/module.py"]),  # different dir entirely
            ("F-00002", ["docs/readme.md"]),  # different top-level
        ]
        result = find_blocking_items(candidate, in_flight)
        assert result == []

    def test_blocks_one_in_flight(self) -> None:
        """Candidate overlaps with exactly one in-flight item."""
        candidate = ["src/app/main.py", "src/app/config.py"]
        in_flight = [
            ("F-00001", ["src/lib/utils.py"]),
            ("F-00002", ["src/app/main.py"]),  # overlaps
            ("F-00003", ["src/lib/other.py"]),
        ]
        result = find_blocking_items(candidate, in_flight)
        assert len(result) == 1
        assert result[0][0] == "F-00002"
        assert "src/app/main.py" in result[0][1]

    def test_blocks_multiple_in_flight(self) -> None:
        """Candidate overlaps with multiple in-flight items."""
        candidate = ["src/app/main.py"]
        in_flight = [
            ("F-00001", ["src/app/main.py"]),  # exact overlap
            ("F-00002", ["src/app/**/*.py"]),  # glob anchor contains candidate
            ("F-00003", ["src/lib/utils.py"]),
        ]
        result = find_blocking_items(candidate, in_flight)
        result_ids = {r[0] for r in result}
        assert "F-00001" in result_ids
        assert "F-00002" in result_ids
        assert "F-00003" not in result_ids

    def test_empty_in_flight(self) -> None:
        """No in-flight items means nothing is blocking."""
        candidate = ["src/app/main.py"]
        result = find_blocking_items(candidate, [])
        assert result == []

    def test_empty_candidate(self) -> None:
        """Empty candidate paths cannot block anything."""
        in_flight = [("F-00001", ["src/app/main.py"])]
        result = find_blocking_items([], in_flight)
        assert result == []


class TestI00071RegressionBatch00078:
    """I-00071 regression — test-path stripping in find_blocking_items.

    Test-path globs (tests/, conftest, *.test.*, *.spec.*, …) are stripped
    from both sides BEFORE globs_intersect runs, so two items whose ONLY
    declared paths are test files cannot block each other even when they
    name the same file or share a glob anchor.

    Originally added (I-00071) to protect against the sibling-directory
    rule firing on tests/dashboard/* paths. The sibling rule was removed
    in I-00099 (2026-05-18); _strip_test_globs is still meaningful as a
    guard against test-file overlap registering as a launch-time block —
    test agents legitimately edit each other's files (fixture refactors,
    shared conftest tweaks) and shouldn't serialise on that.
    """

    def test_two_items_both_only_test_files_under_same_dir_do_not_block(self) -> None:
        """Both items declare only test files under tests/dashboard/ — no sibling block."""
        # Both candidate and in-flight have ONLY test paths under tests/dashboard/.
        # After _strip_test_globs, both sides become empty → no sibling overlap possible.
        candidate_paths = ["tests/dashboard/test_i00067_recent_activity_truncation.py"]
        in_flight = [
            ("I-00069", ["tests/dashboard/test_live_db_guard_log_level.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring only test files under tests/dashboard/ must not "
            f"block each other via sibling-directory check. Was: {result!r}"
        )

    def test_mixed_test_and_prod_paths_test_only_candidate_still_not_blocked(self) -> None:
        """Candidate has only test paths; in-flight has both test and prod paths.

        The test path in the in-flight item must be stripped before sibling
        comparison, so the remaining prod path (dashboard/app.py) does NOT share
        a parent with the candidate's test path (tests/dashboard/test_x.py).
        """
        candidate_paths = ["tests/dashboard/test_i00067_recent_activity_truncation.py"]
        in_flight = [
            ("I-00069", ["dashboard/app.py", "tests/dashboard/test_live_db_guard_log_level.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        # dashboard/app.py (prod, stripped nothing) vs tests/dashboard/test_x.py
        # -> different parents, no sibling overlap
        assert result == [], (
            "Test-path candidate with mixed in-flight must not be blocked when "
            f"prod paths don't share a parent with the test path. Was: {result!r}"
        )


class TestI00099SiblingDirNoLongerBlocks:
    """I-00099 regression — sibling-directory false-positive holds.

    Two items that each touch a different file in a shared parent directory
    must not block each other. The pre-fix code's _same_parent fallback
    fired for any two files sharing a parent dir; this is now removed.
    Items that genuinely need module-level exclusion must declare an
    explicit glob (dir/**) or the exact same file.
    """

    def test_two_different_docs_in_same_dir_do_not_block(self) -> None:
        """Real CR-00057↔CR-00060 case: docs/A.md and docs/B.md must not block."""
        candidate_paths = ["docs/IW_AI_Core_Testing_Strategy.md"]
        in_flight = [
            ("CR-00057", ["docs/IW_AI_Core_AI_Assistant_Models.md"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring different files under docs/ must not block "
            f"each other via the sibling-directory heuristic. Was: {result!r}"
        )

    def test_two_different_daemon_modules_do_not_block(self) -> None:
        """Real CR-00057↔CR-00060 case: orch/daemon/A.py and orch/daemon/B.py must not block."""
        candidate_paths = ["orch/daemon/batch_manager.py"]
        in_flight = [
            ("CR-00057", ["orch/daemon/project_registry.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring different files under orch/daemon/ must not "
            f"block each other via the sibling-directory heuristic. Was: {result!r}"
        )

    def test_exact_file_match_still_blocks(self) -> None:
        """Sanity: when two items declare the EXACT same file, they still block."""
        candidate_paths = ["dashboard/CLAUDE.md"]
        in_flight = [
            ("I-00069", ["dashboard/CLAUDE.md"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00069"
        assert "dashboard/CLAUDE.md" in result[0][1]

    def test_glob_anchor_still_blocks_file_under_anchor(self) -> None:
        """Sanity: an in-flight item declaring 'orch/daemon/**' blocks a candidate
        touching any file under that anchor. globs_intersect must still catch this."""
        candidate_paths = ["orch/daemon/batch_manager.py"]
        in_flight = [
            ("I-00070", ["orch/daemon/**"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00070"

    def test_glob_anchor_other_direction_still_blocks(self) -> None:
        """Sanity: candidate declares 'orch/daemon/**' and in-flight names a specific
        file in that tree. Must still block."""
        candidate_paths = ["orch/daemon/**"]
        in_flight = [
            ("I-00071", ["orch/daemon/batch_manager.py"]),
        ]
        result = find_blocking_items(candidate_paths, in_flight)
        assert len(result) == 1
        assert result[0][0] == "I-00071"
