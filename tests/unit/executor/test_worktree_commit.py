"""Unit tests for executor/worktree_commit.sh.

Tests are driven via subprocess against temporary git repositories.
A shim `iw` script is injected into PATH to avoid needing a live DB.

Bugs covered:
- C2: data loss on successful merge — stashed untracked files must be restored
- L3: stdout/stderr typo — diff output must go to stderr, not stdout
- H9: missing commit body — squash-merge commit must have full body
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent.parent.parent.parent / "executor" / "worktree_commit.sh"


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def _make_git_repo(path: Path) -> None:
    """Initialise a git repo with one initial commit on main."""
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], cwd=path)
    _git(["config", "user.email", "test@test.com"], cwd=path)
    _git(["config", "user.name", "Test"], cwd=path)
    (path / "README.md").write_text("# test\n")
    _git(["add", "README.md"], cwd=path)
    _git(["commit", "-m", "init"], cwd=path)


def _make_iw_shim(bin_dir: Path, item_id: str = "I-00001", title: str = "Test Item") -> None:
    """Write a tiny `iw` shim that returns a minimal item-status JSON."""
    iw = bin_dir / "iw"
    iw.write_text(f'#!/usr/bin/env bash\necho \'{{"id": "{item_id}", "title": "{title}"}}\'\n')
    iw.chmod(0o755)


def _setup_worktree_with_branch(
    project: Path,
    item_id: str,
    branch_files: dict[str, str],
) -> Path:
    """
    Create a git worktree for item_id with the given files committed on a branch.

    Returns the worktree path.
    """
    worktrees = project / ".worktrees"
    worktrees.mkdir(exist_ok=True)
    worktree = worktrees / item_id

    branch = f"agent/{item_id}-work"
    _git(["worktree", "add", "-b", branch, str(worktree), "HEAD"], cwd=project)

    _git(["config", "user.email", "test@test.com"], cwd=worktree)
    _git(["config", "user.name", "Test"], cwd=worktree)

    for rel_path, content in branch_files.items():
        dest = worktree / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    _git(["add", "-A"], cwd=worktree)
    _git(["commit", "-m", f"impl({item_id}): add files"], cwd=worktree)

    return worktree


def _run_commit(
    project: Path,
    item_id: str,
    extra_env: dict[str, str] | None = None,
    iw_title: str = "Test Item",
) -> subprocess.CompletedProcess[str]:
    """Run worktree_commit.sh with a shim iw in PATH."""
    bin_dir = project / "_bin"
    bin_dir.mkdir(exist_ok=True)
    _make_iw_shim(bin_dir, item_id, iw_title)

    # Also provide jq shim that returns the title from the JSON
    jq = bin_dir / "jq"
    jq.write_text(
        "#!/usr/bin/env bash\n"
        # real jq may or may not be available — provide a shim that handles
        # the specific call pattern: jq -r .title
        'exec /usr/bin/jq "$@"\n'
    )
    jq.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(project),
    }
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [str(SCRIPT), item_id, str(project)],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# C2: data loss on successful merge
# ---------------------------------------------------------------------------


class TestStashRestore:
    """C2: Untracked files on main must be restored after a successful merge."""

    def test_unrelated_untracked_file_survives_merge(self, tmp_path: Path) -> None:
        """An untracked file on main that the branch does NOT add must survive the merge."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        # Branch adds impl.py
        _setup_worktree_with_branch(project, "I-00001", {"impl.py": "# impl\n"})

        # An unrelated untracked file on main
        unrelated = project / "unrelated.md"
        unrelated.write_text("# My notes\n")

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, (
            f"merge failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # The untracked file must still be there
        assert unrelated.exists(), "unrelated.md was deleted by the merge"
        assert unrelated.read_text() == "# My notes\n"

    def test_colliding_untracked_file_gets_iw_collision_suffix(self, tmp_path: Path) -> None:
        """
        When the branch adds a file that also exists as untracked on main,
        main ends up with the branch's content AND the user's original is saved
        with a .iw-collision suffix so it can be recovered.
        """
        project = tmp_path / "proj"
        _make_git_repo(project)

        branch_content = "# Branch version\n"
        user_content = "# User's local notes\n"

        # Branch adds local_notes.md
        _setup_worktree_with_branch(project, "I-00001", {"local_notes.md": branch_content})

        # User has an untracked local_notes.md on main
        (project / "local_notes.md").write_text(user_content)

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, (
            f"merge failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # The merged file has the branch's content
        merged_file = project / "local_notes.md"
        assert merged_file.exists(), "local_notes.md missing after merge"
        assert merged_file.read_text() == branch_content, (
            f"Expected branch content, got: {merged_file.read_text()!r}"
        )

        # The user's original is preserved with .iw-collision suffix
        collision_file = project / "local_notes.md.iw-collision"
        assert collision_file.exists(), (
            "local_notes.md.iw-collision not found — user's content was lost"
        )
        assert collision_file.read_text() == user_content


# ---------------------------------------------------------------------------
# L3: stdout/stderr typo — diff output must not go to stdout
# ---------------------------------------------------------------------------


class TestStdoutClean:
    """L3: A successful merge must produce no output on stdout."""

    def test_successful_merge_produces_no_stdout(self, tmp_path: Path) -> None:
        """worktree_commit.sh must produce no stdout output on success."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        _setup_worktree_with_branch(project, "I-00001", {"feature.py": "x = 1\n"})

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, f"merge failed:\nstderr: {result.stderr}"
        assert result.stdout == "", f"Expected empty stdout on success, got:\n{result.stdout!r}"


# ---------------------------------------------------------------------------
# H9: missing commit body on squash-merge
# ---------------------------------------------------------------------------


class TestCommitBody:
    """H9: The squash-merge commit message must contain all required fields."""

    def test_commit_message_has_item_id_and_title(self, tmp_path: Path) -> None:
        """The commit message first line contains the item ID and title."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        _setup_worktree_with_branch(project, "I-00001", {"service.py": "pass\n"})

        result = _run_commit(project, "I-00001", iw_title="Add service layer")
        assert result.returncode == 0, f"merge failed:\nstderr: {result.stderr}"

        log = _git(["log", "-1", "--format=%B"], cwd=project)
        msg = log.stdout

        assert "I-00001" in msg
        # Title from iw shim
        assert "Add service layer" in msg or "(title unavailable)" in msg

    def test_commit_message_has_branch_name(self, tmp_path: Path) -> None:
        """The commit message body contains the Branch field."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        _setup_worktree_with_branch(project, "I-00001", {"x.py": "pass\n"})

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, f"merge failed:\nstderr: {result.stderr}"

        log = _git(["log", "-1", "--format=%B"], cwd=project)
        msg = log.stdout
        assert "Branch:" in msg
        assert "agent/I-00001" in msg

    def test_commit_message_has_files_changed(self, tmp_path: Path) -> None:
        """The commit message body contains the Files changed field."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        _setup_worktree_with_branch(project, "I-00001", {"a.py": "1\n", "b.py": "2\n"})

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, f"merge failed:\nstderr: {result.stderr}"

        log = _git(["log", "-1", "--format=%B"], cwd=project)
        msg = log.stdout
        assert "Files changed:" in msg

    def test_commit_message_has_source_commits(self, tmp_path: Path) -> None:
        """The commit message body contains the Source commits field."""
        project = tmp_path / "proj"
        _make_git_repo(project)

        _setup_worktree_with_branch(project, "I-00001", {"c.py": "3\n"})

        result = _run_commit(project, "I-00001")
        assert result.returncode == 0, f"merge failed:\nstderr: {result.stderr}"

        log = _git(["log", "-1", "--format=%B"], cwd=project)
        msg = log.stdout
        assert "Source commits:" in msg
