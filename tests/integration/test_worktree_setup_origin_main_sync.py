"""Integration test for I-00084: stale origin/main ref sync in worktree setup.

After worktree_setup.sh creates a worktree, the new worktree's origin/main ref
must match the local main branch, even if origin/main was stale beforehand.

This test verifies the fix:
    git -C "$WORKTREE_DIR" fetch . main:refs/remotes/origin/main 2>/dev/null || true

inserted in executor/worktree_setup.sh immediately after `git worktree add`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in cwd and return CompletedProcess."""
    cmd = ["git", *args]
    return subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, cwd=cwd, timeout=30
    )


def _git_check(*args: str, cwd: Path) -> str:
    """Run a git command, assert success, and return stdout stripped."""
    result = _git(*args, cwd=cwd)
    assert result.returncode == 0, f"git {' '.join(args)} failed in {cwd}:\n{result.stderr}"
    return result.stdout.strip()


def _make_repo_with_stale_origin_main(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a repo where origin/main is intentionally stale.

    Returns (repo_path, stale_sha, current_main_sha).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_check("init", "-b", "main", cwd=repo)
    _git_check("config", "user.email", "test@test.com", cwd=repo)
    _git_check("config", "user.name", "Test User", cwd=repo)

    # Initial commit — this becomes the stale origin/main SHA
    (repo / "README.md").write_text("initial")
    _git_check("add", "README.md", cwd=repo)
    _git_check("commit", "-m", "initial commit", cwd=repo)
    stale_sha = _git_check("rev-parse", "HEAD", cwd=repo)

    # Set origin/main to the initial commit (simulating a never-pushed remote)
    _git_check("update-ref", "refs/remotes/origin/main", stale_sha, cwd=repo)

    # Add 5 more commits to local main — origin/main stays behind
    for i in range(5):
        (repo / f"file_{i}.py").write_text(f"# file {i}")
        _git_check("add", f"file_{i}.py", cwd=repo)
        _git_check("commit", "-m", f"local-main-{i}", cwd=repo)

    current_main_sha = _git_check("rev-parse", "HEAD", cwd=repo)

    # Precondition check
    origin_main_sha = _git_check("rev-parse", "refs/remotes/origin/main", cwd=repo)
    assert origin_main_sha == stale_sha, (
        f"precondition failed: origin/main should be stale "
        f"(expected {stale_sha}, got {origin_main_sha})"
    )
    assert current_main_sha != stale_sha, "precondition: main must be ahead of origin/main"

    return repo, stale_sha, current_main_sha


def _create_worktree(repo: Path, branch: str, worktree_path: Path) -> None:
    """Create a git worktree at worktree_path on a new branch."""
    _git_check("worktree", "add", "-b", branch, str(worktree_path), "HEAD", cwd=repo)


def _get_origin_main_sha(cwd: Path) -> str | None:
    """Return the SHA that origin/main points to in the given worktree/repo, or None."""
    result = _git("rev-parse", "refs/remotes/origin/main", cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _apply_origin_main_sync(worktree_path: Path) -> None:
    """Apply the fix: sync origin/main to local main inside the worktree.

    This mirrors the exact command added to executor/worktree_setup.sh:
        git -C "$WORKTREE_DIR" fetch . main:refs/remotes/origin/main 2>/dev/null || true
    """
    result = subprocess.run(  # noqa: S603
        ["git", "fetch", ".", "main:refs/remotes/origin/main"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
        timeout=30,
    )
    # The || true means we don't fail on error, just best-effort
    # But in tests we assert it succeeds
    assert result.returncode == 0, (
        f"git fetch . main:refs/remotes/origin/main failed:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorktreeSetupOriginMainSync:
    """AC1 + AC2: origin/main must match local main after worktree creation."""

    def test_i00084_origin_main_is_stale_before_fix(self, tmp_path: Path) -> None:
        """Precondition: without the fix, origin/main stays stale in new worktrees.

        This test confirms the bug exists: after a plain `git worktree add`,
        origin/main inside the worktree still points to the old stale SHA,
        not the current local main.
        """
        repo, stale_sha, current_main_sha = _make_repo_with_stale_origin_main(tmp_path)
        worktree_path = tmp_path / "worktrees" / "I-99001"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Plain worktree add — no sync applied (this is the pre-fix state)
        _create_worktree(repo, "agent/I-99001-test", worktree_path)

        origin_main_in_worktree = _get_origin_main_sha(worktree_path)

        # Without the fix, origin/main still reflects the stale SHA (not current main)
        assert origin_main_in_worktree == stale_sha, (
            f"Expected stale origin/main={stale_sha} before fix, but got {origin_main_in_worktree}"
        )
        assert origin_main_in_worktree != current_main_sha, (
            "Bug not reproduced: origin/main unexpectedly points to current main "
            "without the fix being applied"
        )

    def test_i00084_origin_main_matches_local_main_after_sync(self, tmp_path: Path) -> None:
        """AC1: after applying the fix command, origin/main matches local main.

        This test exercises the git command in isolation (not via worktree_setup.sh).
        It verifies that `git fetch . main:refs/remotes/origin/main` correctly
        advances origin/main to local main. Structural presence of this command
        in worktree_setup.sh is verified by test_i00084_worktree_setup_sh_sync_command_is_present.

        The test simulates what worktree_setup.sh does:
        1. git worktree add (creates worktree — origin/main still stale)
        2. git fetch . main:refs/remotes/origin/main (the fix)

        After step 2, origin/main inside the worktree must equal local main.
        """
        repo, stale_sha, current_main_sha = _make_repo_with_stale_origin_main(tmp_path)
        worktree_path = tmp_path / "worktrees" / "I-99001"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: create worktree (mirrors `git worktree add -b $BRANCH $WORKTREE_DIR HEAD`)
        _create_worktree(repo, "agent/I-99001-test", worktree_path)

        # Confirm origin/main is still stale at this point (precondition)
        assert _get_origin_main_sha(worktree_path) == stale_sha, (
            "Precondition: origin/main should be stale before the fix command runs"
        )

        # Step 2: apply the fix (mirrors the new line in worktree_setup.sh)
        _apply_origin_main_sync(worktree_path)

        # Assert: origin/main inside the worktree now matches local main
        origin_main_after = _get_origin_main_sha(worktree_path)
        assert origin_main_after == current_main_sha, (
            f"worktree_setup must sync origin/main to local main; "
            f"got {origin_main_after!r} expected {current_main_sha!r}"
        )

    def test_i00084_sync_is_idempotent(self, tmp_path: Path) -> None:
        """Running the sync command twice does not error or change state."""
        repo, _stale_sha, current_main_sha = _make_repo_with_stale_origin_main(tmp_path)
        worktree_path = tmp_path / "worktrees" / "I-99002"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        _create_worktree(repo, "agent/I-99002-test", worktree_path)

        _apply_origin_main_sync(worktree_path)
        _apply_origin_main_sync(worktree_path)  # second call — must not fail

        origin_main_after = _get_origin_main_sha(worktree_path)
        assert origin_main_after == current_main_sha, (
            f"After double sync, origin/main should still be {current_main_sha}, "
            f"got {origin_main_after}"
        )

    def test_i00084_makefile_diff_coverage_sync_command_is_present(self) -> None:
        """AC3 structural guard: Makefile diff-coverage target contains the origin/main sync line.

        This is a code-path presence check (structural guard), not a behavioral test.
        It verifies the defensive Makefile fix (Fix 2) is present so that even
        worktrees created without worktree_setup.sh get a correct origin/main before
        diff-cover runs. Behavioral correctness of the git command is verified in
        test_i00084_origin_main_matches_local_main_after_sync.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        makefile = repo_root / "Makefile"
        assert makefile.exists(), "Makefile not found at repo root"

        content = makefile.read_text()

        # Verify the sync command appears in the diff-coverage target
        assert "fetch . main:refs/remotes/origin/main" in content, (
            "Makefile diff-coverage target must contain "
            "'git fetch . main:refs/remotes/origin/main' as a defensive sync. "
            "Add it as the first recipe line of the diff-coverage: target."
        )

    def test_i00084_worktree_setup_sh_sync_command_is_present(self) -> None:
        """AC2 structural guard: executor/worktree_setup.sh contains the origin/main sync line.

        This is a code-path presence check (structural guard), not a behavioral test.
        It verifies Fix 1 is present in the script. Behavioral correctness of the git
        command is verified in test_i00084_origin_main_matches_local_main_after_sync.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        script = repo_root / "executor" / "worktree_setup.sh"
        assert script.exists(), "executor/worktree_setup.sh not found"

        content = script.read_text()

        assert "fetch . main:refs/remotes/origin/main" in content, (
            "executor/worktree_setup.sh must contain "
            "'git fetch . main:refs/remotes/origin/main' after 'git worktree add'. "
            "This syncs origin/main to local main so diff-cover sees the right base."
        )
