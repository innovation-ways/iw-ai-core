"""Unit tests for orch.staleness.git_lookup.

Uses a real temporary git repo (created via subprocess in fixtures) so the
git commands exercise actual git behaviour without touching any live repository.
No database, no docker.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orch.staleness.git_lookup import CommitSummary, commits_since, find_commit_at

# ---------------------------------------------------------------------------
# Fixture: minimal temporary git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one initial commit on main.

    Configures a throwaway user identity so commits succeed in CI environments
    without a global git config.

    Args:
        tmp_path: Pytest-supplied temporary directory.

    Returns:
        Path to the initialized git repository root.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )

    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test User")

    # Initial commit
    (repo / "README.md").write_text("hello")
    git("add", ".")
    git("commit", "-m", "Initial commit")

    return repo


def _add_commit(repo: Path, filename: str, content: str, message: str) -> str:
    """Add a file and create a commit in the repo.

    Args:
        repo: Path to the git repository root.
        filename: Relative path of the file to write and stage.
        content: Text content to write to the file.
        message: Commit message.

    Returns:
        The full 40-character SHA of the newly created commit.
    """
    (repo / filename).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", filename], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", message],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# find_commit_at
# ---------------------------------------------------------------------------


class TestFindCommitAt:
    """Tests for find_commit_at — verifies correct SHA lookup by timestamp."""

    def test_returns_sha_for_timestamp_after_commit(self, git_repo: Path) -> None:
        """Returns the most recent commit before the given timestamp."""
        # The initial commit exists; use a timestamp well in the future.
        ts = datetime.now(tz=UTC).replace(year=datetime.now(tz=UTC).year + 1)
        sha = find_commit_at(git_repo, ts)
        assert sha is not None
        assert len(sha) == 40  # full SHA

    def test_returns_none_for_timestamp_before_any_commit(self, git_repo: Path) -> None:
        """Returns None when no commit existed before the given timestamp."""
        ts = datetime(2000, 1, 1, tzinfo=UTC)
        sha = find_commit_at(git_repo, ts)
        assert sha is None

    def test_returns_correct_commit_between_two(self, git_repo: Path) -> None:
        """When two commits exist, find_commit_at returns the earlier one for a mid-point ts."""
        import time

        sha1 = _add_commit(git_repo, "file1.txt", "v1", "Commit one")
        time.sleep(1.1)  # ensure different second-precision timestamps
        _add_commit(git_repo, "file2.txt", "v2", "Commit two")

        # Get the timestamp of sha1 and add 0.5s
        result = subprocess.run(
            ["git", "-C", str(git_repo), "log", "-1", "--format=%ct", sha1],
            capture_output=True,
            text=True,
            check=True,
        )
        sha1_epoch = int(result.stdout.strip())
        mid_ts = datetime.fromtimestamp(sha1_epoch + 0.5, tz=UTC)

        found = find_commit_at(git_repo, mid_ts)
        assert found == sha1

    def test_nonexistent_repo_returns_none(self, tmp_path: Path) -> None:
        """Returns None when the repo path doesn't exist."""
        ts = datetime.now(tz=UTC)
        result = find_commit_at(tmp_path / "nonexistent", ts)
        assert result is None


# ---------------------------------------------------------------------------
# commits_since
# ---------------------------------------------------------------------------


class TestCommitsSince:
    """Tests for commits_since — verifies watch_paths, ignore_paths, and negated-path filtering."""

    def test_no_new_commits_returns_empty(self, git_repo: Path) -> None:
        """Returns empty list when HEAD is the since_sha."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        head_sha = result.stdout.strip()

        commits = commits_since(git_repo, head_sha, ["**"], [])
        assert commits == []

    def test_new_commit_touching_watched_path(self, git_repo: Path) -> None:
        """Returns commits that touch watched paths."""
        # Get starting sha
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()

        # Make a new commit touching orch/something.py
        (git_repo / "orch").mkdir(exist_ok=True)
        _add_commit(git_repo, "orch/module.py", "code", "Add orch module")

        commits = commits_since(git_repo, start_sha, ["orch/**"], [])
        assert len(commits) == 1
        assert commits[0].subject == "Add orch module"
        assert len(commits[0].sha) == 40

    def test_commit_not_touching_watched_path_excluded(self, git_repo: Path) -> None:
        """Returns empty when new commits don't touch the watched paths."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()

        # Commit touches dashboard/, not orch/
        (git_repo / "dashboard").mkdir(exist_ok=True)
        _add_commit(git_repo, "dashboard/view.py", "html", "Add dashboard view")

        commits = commits_since(git_repo, start_sha, ["orch/**"], [])
        assert commits == []

    def test_ignore_paths_excludes_matching_commits(self, git_repo: Path) -> None:
        """Returns empty when new commits only touch ignored paths."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()

        # Commit touches orch/tests/test_foo.py (which is in ignore_paths)
        (git_repo / "orch" / "tests").mkdir(parents=True, exist_ok=True)
        _add_commit(git_repo, "orch/tests/test_foo.py", "test", "Add test")

        commits = commits_since(git_repo, start_sha, ["orch/**"], ["orch/tests/**"])
        assert commits == []

    def test_mixed_commits_returns_only_watched(self, git_repo: Path) -> None:
        """Only commits that touch watched (and not ignored) paths are returned."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()

        (git_repo / "orch").mkdir(exist_ok=True)
        sha_orch = _add_commit(git_repo, "orch/service.py", "svc", "Add service")
        (git_repo / "docs").mkdir(exist_ok=True)
        _add_commit(git_repo, "docs/readme.md", "docs", "Add docs")

        commits = commits_since(git_repo, start_sha, ["orch/**"], ["**/*.md"])
        assert len(commits) == 1
        assert commits[0].sha == sha_orch

    def test_returns_commit_summary_fields(self, git_repo: Path) -> None:
        """Each CommitSummary has sha and subject."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()
        (git_repo / "orch").mkdir(exist_ok=True)
        sha = _add_commit(git_repo, "orch/foo.py", "x", "My commit subject")

        commits = commits_since(git_repo, start_sha, ["orch/**"], [])
        assert len(commits) == 1
        cs = commits[0]
        assert isinstance(cs, CommitSummary)
        assert cs.sha == sha
        assert cs.subject == "My commit subject"

    def test_invalid_since_sha_returns_empty(self, git_repo: Path) -> None:
        """Returns empty list (with log) when since_sha is invalid."""
        commits = commits_since(git_repo, "deadbeef" * 5, ["**"], [])
        assert commits == []

    def test_negated_watch_path_treated_as_exclude(self, git_repo: Path) -> None:
        """A watch_path starting with '!' is treated as an additional exclude."""
        result = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        start_sha = result.stdout.strip()

        (git_repo / "orch").mkdir(exist_ok=True)
        # Only adds a test file — should be excluded via negated watch_path
        _add_commit(git_repo, "orch/test_x.py", "test", "Add orch test")

        commits = commits_since(git_repo, start_sha, ["orch/**", "!orch/test_*.py"], [])
        assert commits == []
