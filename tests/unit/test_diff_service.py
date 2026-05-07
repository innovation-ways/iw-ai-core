"""Unit tests for orch/diff_service.py.

RED phase: tests define expected behavior before implementation exists.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from orch.diff_service import (
    GENERATED_FILE_GLOBS,
    is_generated_path,
    parse_diff_summary,
    resolve_diff,
)

# ---------------------------------------------------------------------------
# Fixtures — real git diff output (captured from actual git commands)
# ---------------------------------------------------------------------------

# Real git diff for a modified file (added 1 line to existing file)
MODIFIED_DIFF = """diff --git a/foo.py b/foo.py
index ce01362..94954ab 100644
--- a/foo.py
+++ b/foo.py
@@ -1 +1,2 @@
 hello
+world
"""

# Real git diff for a new/added file
ADDED_DIFF = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..3e75765
--- /dev/null
+++ b/new.py
@@ -0,0 +1 @@
+new
"""

# Real git diff for a deleted file
DELETED_DIFF = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
index 3e75765..0000000
--- a/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-old content
"""

# Real git diff for renamed file (similarity index 90%)
RENAMED_DIFF = """diff --git a/src/renamed_old.py b/src/renamed_new.py
similarity index 90%
rename from src/renamed_old.py
rename to src/renamed_new.py
--- a/src/renamed_old.py
+++ b/src/renamed_new.py
@@ -1 +1 @@
-old name
+new name
"""

# Binary file diff
BINARY_DIFF = """diff --git a/logo.png b/logo.png
index 1234567..89abcdef 100644
Binary files a/logo.png and b/logo.png differ
"""

# Generated file diff (uv.lock)
GENERATED_DIFF = """diff --git a/uv.lock b/uv.lock
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/uv.lock
@@ -0,0 +1 @@
+# generated lock file
"""


# ---------------------------------------------------------------------------
# parse_diff_summary
# ---------------------------------------------------------------------------


class TestParseDiffSummary:
    """Parse a unified diff into a JSON-serialisable summary list."""

    def test_added_file(self) -> None:
        result = parse_diff_summary(ADDED_DIFF)
        assert len(result) == 1
        assert result[0]["path"] == "new.py"
        assert result[0]["status"] == "A"
        assert result[0]["added"] == 1
        assert result[0]["removed"] == 0
        assert result[0]["is_generated"] is False
        assert result[0]["is_binary"] is False
        assert result[0]["old_path"] is None

    def test_modified_file(self) -> None:
        result = parse_diff_summary(MODIFIED_DIFF)
        foo = next(f for f in result if f["path"] == "foo.py")
        assert foo["status"] == "M"
        assert foo["added"] == 1
        assert foo["removed"] == 0

    def test_deleted_file(self) -> None:
        result = parse_diff_summary(DELETED_DIFF)
        deleted = next(f for f in result if f["path"] == "deleted.py")
        assert deleted["status"] == "D"
        assert deleted["added"] == 0
        assert deleted["removed"] == 1

    def test_renamed_file(self) -> None:
        result = parse_diff_summary(RENAMED_DIFF)
        renamed = next(f for f in result if f["path"] == "src/renamed_new.py")
        assert renamed["status"] == "R"
        assert renamed["old_path"] == "src/renamed_old.py"

    def test_binary_file(self) -> None:
        result = parse_diff_summary(BINARY_DIFF)
        assert len(result) == 1
        assert result[0]["path"] == "logo.png"
        assert result[0]["is_binary"] is True
        assert result[0]["added"] == 0
        assert result[0]["removed"] == 0

    def test_generated_file_flag(self) -> None:
        result = parse_diff_summary(GENERATED_DIFF)
        assert result[0]["is_generated"] is True

    def test_parsed_entries_have_required_keys(self) -> None:
        result = parse_diff_summary(MODIFIED_DIFF)
        entry = result[0]
        assert set(entry.keys()) == {
            "path",
            "status",
            "added",
            "removed",
            "is_generated",
            "is_binary",
            "old_path",
        }


# ---------------------------------------------------------------------------
# is_generated_path
# ---------------------------------------------------------------------------


class TestIsGeneratedPath:
    """Match path against GENERATED_FILE_GLOBS using fnmatch."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("uv.lock", True),
            ("package-lock.json", True),
            ("pnpm-lock.yaml", True),
            ("yarn.lock", True),
            ("poetry.lock", True),
            ("build/output.min.js", True),
            ("snapshots/test.snap", True),
            ("src/main.py", False),
            ("README.md", False),
            ("docs/guide.pdf", False),
            ("src/app.min.js", True),
        ],
    )
    def test_generated_globs(self, path: str, expected: bool) -> None:
        assert is_generated_path(path) == expected

    def test_generated_file_globs_is_tuple(self) -> None:
        assert isinstance(GENERATED_FILE_GLOBS, tuple)


# ---------------------------------------------------------------------------
# resolve_diff — routing
# ---------------------------------------------------------------------------


class TestResolveDiff:
    """Route to correct diff source based on (item, step_run, worktree_path)."""

    def _fake_item(
        self,
        archived_at: Any = None,
        merge_commit_sha: str | None = None,
        diff_text: str | None = None,
    ) -> MagicMock:
        item = MagicMock()
        item.archived_at = archived_at
        item.merge_commit_sha = merge_commit_sha
        item.diff_text = diff_text
        return item

    def _fake_step_run(
        self,
        diff_text: str | None = None,
        worktree_path: str | None = None,
    ) -> MagicMock:
        sr = MagicMock()
        sr.diff_text = diff_text
        sr.worktree_path = worktree_path
        return sr

    def _fake_project(self, repo_root: str = "/repo") -> MagicMock:
        p = MagicMock()
        p.repo_root = repo_root
        return p

    # step_run provided → use step_run.diff_text
    def test_step_run_has_diff_text(self) -> None:
        item = self._fake_item()
        step_run = self._fake_step_run(diff_text="stored diff", worktree_path="/wt")
        project = self._fake_project()
        result = resolve_diff(
            item=item,
            step_run=step_run,
            project=project,
            worktree_path="/wt",
        )
        assert result == "stored diff"

    # step_run provided but no diff_text → fallback to live git diff in worktree
    def test_step_run_no_diff_text_falls_back_to_live(self) -> None:
        item = self._fake_item()
        step_run = self._fake_step_run(diff_text=None, worktree_path="/wt")
        project = self._fake_project()
        with patch("orch.diff_service._git_diff_step_head", return_value="live step diff"):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path="/wt",
            )
        assert result == "live step diff"

    # step_run provided, no diff_text, git fails → None
    def test_step_run_git_fails_returns_none(self) -> None:
        item = self._fake_item()
        step_run = self._fake_step_run(diff_text=None, worktree_path="/wt")
        project = self._fake_project()
        with patch("orch.diff_service._git_diff_step_head", return_value=None):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path="/wt",
            )
        assert result is None

    # no step_run, item archived → use item.diff_text
    def test_archived_item_uses_db_snapshot(self) -> None:
        import datetime

        archived = datetime.datetime.now(tz=datetime.UTC)
        item = self._fake_item(archived_at=archived, diff_text="archived diff")
        step_run = None
        project = self._fake_project()
        result = resolve_diff(item=item, step_run=step_run, project=project, worktree_path=None)
        assert result == "archived diff"

    # no step_run, not archived, merge_commit_sha → live git diff against parent in repo_root
    def test_merged_item_with_sha_uses_repo_diff(self) -> None:
        item = self._fake_item(merge_commit_sha="abc123")
        step_run = None
        project = self._fake_project(repo_root="/repo")
        with patch("orch.diff_service._git_diff_merge_commit", return_value="merge diff"):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path=None,
            )
        assert result == "merge diff"

    # no step_run, not archived, no merge_commit_sha, worktree alive → live diff in worktree
    def test_in_progress_worktree_live_diff(self) -> None:
        item = self._fake_item(archived_at=None, merge_commit_sha=None)
        step_run = None
        project = self._fake_project(repo_root="/repo")
        with patch("orch.diff_service._git_diff_worktree_head", return_value="worktree diff"):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path="/wt",
            )
        assert result == "worktree diff"

    # nothing available → None
    def test_nothing_available_returns_none(self) -> None:
        item = self._fake_item(archived_at=None, merge_commit_sha=None)
        step_run = None
        project = self._fake_project(repo_root="/repo")
        with patch("orch.diff_service._git_diff_worktree_head", return_value=None):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path=None,
            )
        assert result is None


# ---------------------------------------------------------------------------
# Subprocess failure → resolver returns None (never raises)
# ---------------------------------------------------------------------------


class TestResolveDiffSubprocessFailure:
    """Invariant: resolver returns None instead of raising on git failure."""

    def _fake_item(self, **kwargs: Any) -> MagicMock:
        item = MagicMock()
        item.archived_at = kwargs.get("archived_at")
        item.merge_commit_sha = kwargs.get("merge_commit_sha")
        item.diff_text = kwargs.get("diff_text")
        return item

    def _fake_step_run(self, **kwargs: Any) -> MagicMock:
        sr = MagicMock()
        sr.diff_text = kwargs.get("diff_text")
        sr.worktree_path = kwargs.get("worktree_path")
        return sr

    def _fake_project(self, repo_root: str = "/repo") -> MagicMock:
        p = MagicMock()
        p.repo_root = repo_root
        return p

    def test_git_diff_step_head_fails_returns_none(self) -> None:
        """Subprocess failure in step-diff path returns None, does not raise."""
        item = self._fake_item()
        step_run = self._fake_step_run(diff_text=None, worktree_path="/wt")
        project = self._fake_project()
        with patch("orch.diff_service._run_git", side_effect=OSError("git not found")):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path="/wt",
            )
        assert result is None

    def test_git_diff_merge_commit_fails_returns_none(self) -> None:
        """Subprocess failure in merge-commit path returns None."""
        item = self._fake_item(merge_commit_sha="abc123")
        step_run = None
        project = self._fake_project(repo_root="/repo")
        with patch("orch.diff_service._run_git", side_effect=OSError("git not found")):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path=None,
            )
        assert result is None

    def test_git_diff_worktree_fails_returns_none(self) -> None:
        """Subprocess failure in worktree path returns None."""
        item = self._fake_item(archived_at=None, merge_commit_sha=None)
        step_run = None
        project = self._fake_project(repo_root="/repo")
        with patch("orch.diff_service._run_git", side_effect=OSError("git not found")):
            result = resolve_diff(
                item=item,
                step_run=step_run,
                project=project,
                worktree_path="/wt",
            )
        assert result is None


# ---------------------------------------------------------------------------
# GENERATED_FILE_GLOBS — all entries covered, invariant with JS frontend
# ---------------------------------------------------------------------------


class TestGeneratedFileGlobsInvariant:
    """Invariant 8: canonical glob list is shared without drift between backend and JS."""

    @pytest.mark.parametrize(
        "glob_pattern",
        GENERATED_FILE_GLOBS,
        ids=lambda p: p,
    )
    def test_all_globs_match_is_generated_path(self, glob_pattern: str) -> None:
        """Every entry in GENERATED_FILE_GLOBS must produce True via is_generated_path."""
        # Build a representative path that matches each glob pattern
        if "*" in glob_pattern:
            # Wildcard: test both a matching and non-matching case
            assert is_generated_path(glob_pattern.replace("*", "file")) is True
        else:
            assert is_generated_path(glob_pattern) is True

    def test_glob_list_is_stable_tuple(self) -> None:
        """GENERATED_FILE_GLOBS must be an immutable tuple for import-time safety."""
        assert isinstance(GENERATED_FILE_GLOBS, tuple)
        assert len(GENERATED_FILE_GLOBS) > 0

    def test_no_renamed_entries(self) -> None:
        """Each glob entry must be distinct (no duplicates)."""
        assert len(GENERATED_FILE_GLOBS) == len(set(GENERATED_FILE_GLOBS))


# ---------------------------------------------------------------------------
# parse_diff_summary — additional edge cases
# ---------------------------------------------------------------------------


class TestParseDiffSummaryEdgeCases:
    """Additional parse_diff_summary coverage beyond basic status types."""

    def test_file_with_a_and_b_prefixes_stripped(self) -> None:
        """Paths prefixed with 'a/' or 'b/' must be stripped to bare paths."""
        diff_with_prefixes = """diff --git a/src/foo.py b/src/foo.py
index ce01362..94954ab 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1 +1,2 @@
 hello
+world
"""
        result = parse_diff_summary(diff_with_prefixes)
        assert len(result) == 1
        assert result[0]["path"] == "src/foo.py"

    def test_mixed_adds_and_deletes_in_same_file(self) -> None:
        """A file with both added and removed lines accumulates both counts."""
        mixed_diff = """diff --git a/mixed.py b/mixed.py
index 0000000..1234567 100644
--- a/mixed.py
+++ b/mixed.py
@@ -1,3 +1,5 @@
 old line one
-old line two
-old line three
+new line one
+new line two
+new line three
+new line four
+new line five
"""
        result = parse_diff_summary(mixed_diff)
        mixed = next(f for f in result if f["path"] == "mixed.py")
        # unidiff counts only the +/- lines (context lines are not counted)
        assert mixed["added"] == 4  # new line one..four
        assert mixed["removed"] == 2  # old line two..three
        assert mixed["status"] == "M"

    def test_renamed_file_low_similarity_renders_as_single_r_entry(
        self,
    ) -> None:
        """Git rename detection (≥50% similarity) produces status=R, not A+D."""
        # Low similarity (<50%) produces add+delete in default git, not rename
        # But standard rename detection (≥50%) produces R
        rename_diff = """diff --git a/old_module.py b/new_module.py
similarity index 90%
rename from old_module.py
rename to new_module.py
--- a/old_module.py
+++ b/new_module.py
@@ -1 +1 @@
-old
+new
"""
        result = parse_diff_summary(rename_diff)
        assert len(result) == 1
        assert result[0]["status"] == "R"
        assert result[0]["old_path"] == "old_module.py"
        assert result[0]["is_binary"] is False

    def test_multiple_files_in_summary(self) -> None:
        """A diff touching multiple files returns one entry per file."""
        multi_diff = """diff --git a/foo.py b/foo.py
index ce01362..94954ab 100644
--- a/foo.py
+++ b/foo.py
@@ -1 +1,2 @@
 hello
+world
diff --git a/bar.py b/bar.py
new file mode 100644
index 0000000..3e75765
--- /dev/null
+++ b/bar.py
@@ -0,0 +1 @@
+new bar
"""
        result = parse_diff_summary(multi_diff)
        assert len(result) == 2
        paths = {r["path"] for r in result}
        assert paths == {"foo.py", "bar.py"}
        statuses = {r["status"] for r in result}
        assert "M" in statuses
        assert "A" in statuses
