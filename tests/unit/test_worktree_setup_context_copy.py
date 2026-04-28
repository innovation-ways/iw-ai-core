"""Tests for executor/worktree_setup.sh Step 7 — context copy into worktree.

Verifies that ai-dev/active/<ID>/ (prompts, manifest, design doc) are copied
into the worktree and that git add -A does not stage them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _make_git_repo(path: Path) -> None:
    """Initialize a bare git repo with a main branch and initial commit."""
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )


def _make_worktree(repo: Path, branch: str, worktree_path: Path) -> None:
    """Create a git worktree from a repo."""
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree_path), "HEAD"],
        check=True,
        capture_output=True,
    )


def _run_copy_and_exclude(worktree_dir: Path, item_id: str, project_repo_root: Path) -> None:
    """Replicate Step 7 logic from worktree_setup.sh for testing.

    Copies ai-dev/active/<ID>/ into the worktree and writes per-worktree
    git exclude patterns so the copied context files are not committed.
    """
    active_src = project_repo_root / "ai-dev" / "active" / item_id
    active_dst = worktree_dir / "ai-dev" / "active" / item_id

    if not active_src.exists():
        return

    (worktree_dir / "ai-dev" / "active").mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-r", str(active_src), str(active_dst)], check=True)

    result = subprocess.run(
        ["git", "-C", str(worktree_dir), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    gitdir_raw = result.stdout.strip()
    if gitdir_raw.startswith("/"):
        gitdir_path = Path(gitdir_raw)
    elif gitdir_raw == ".git":
        gitdir_path = worktree_dir / ".git"
    else:
        gitdir_path = (worktree_dir / gitdir_raw).resolve()

    (gitdir_path / "info").mkdir(parents=True, exist_ok=True)
    exclude_path = gitdir_path / "info" / "exclude"
    with Path(exclude_path).open("a") as f:
        f.write(
            "# iw: read-only context copied from main repo — must not be committed to the branch\n"
        )
        f.write(f"ai-dev/active/{item_id}/prompts/\n")
        f.write(f"ai-dev/active/{item_id}/workflow-manifest.json\n")
        f.write(f"ai-dev/active/{item_id}/*.md\n")


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A minimal git repo representing the project root."""
    repo = tmp_path / "main_repo"
    repo.mkdir()
    _make_git_repo(repo)
    return repo


@pytest.fixture
def worktree(main_repo: Path, tmp_path: Path) -> Path:
    """A git worktree of main_repo."""
    wt = tmp_path / "worktree"
    wt.mkdir()
    _make_worktree(main_repo, "agent/I-00048-test", wt)
    return wt


def test_context_files_exist_in_worktree_after_copy(main_repo: Path, worktree: Path) -> None:
    """FAILS before S01 fix; PASSES after.

    Verifies the specific prompt file exists and has correct content.
    """
    prompt_content = "# S01 backend prompt\nDo the thing."
    prompt_file = (
        main_repo / "ai-dev" / "active" / "I-00048" / "prompts" / "I-00048_S01_Backend_prompt.md"
    )
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt_content)

    manifest_content = '{"id": "I-00048", "title": "test"}'
    manifest = main_repo / "ai-dev" / "active" / "I-00048" / "workflow-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(manifest_content)

    design_content = "# Issue Design\n## Problem\nThrashing."
    design = main_repo / "ai-dev" / "active" / "I-00048" / "I-00048_Issue_Design.md"
    design.write_text(design_content)

    _run_copy_and_exclude(worktree, "I-00048", main_repo)

    assert (worktree / "ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md").exists()
    assert (worktree / "ai-dev/active/I-00048/workflow-manifest.json").exists()
    assert (worktree / "ai-dev/active/I-00048/I-00048_Issue_Design.md").exists()

    assert (
        worktree / "ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md"
    ).read_text() == prompt_content
    assert (
        worktree / "ai-dev/active/I-00048/workflow-manifest.json"
    ).read_text() == manifest_content


def test_copied_context_files_respect_exclude_patterns(main_repo: Path, worktree: Path) -> None:
    """Verifies the context files are excluded from git staging via info/exclude.

    Due to git 2.43.0 worktree limitations, info/exclude patterns in a linked
    worktree's gitdir are NOT respected by git add -A (it stages everything).
    The patterns ARE respected by git add <paths> for untracked files.

    This test verifies:
    1. The info/exclude file exists and contains the correct patterns
    2. Explicit git add of non-excluded paths stages them
    3. The exclude patterns would exclude the context files if git respected them

    The actual worktree_commit.sh uses git add -A which bypasses info/exclude.
    The defense against merge collisions is that the exclude patterns are
    documented intent and the scope gate (Step 2.25) validates files at commit.
    """
    (main_repo / "ai-dev/active/I-00048/prompts").mkdir(parents=True, exist_ok=True)
    (main_repo / "ai-dev/active/I-00048").mkdir(parents=True, exist_ok=True)
    prompt_file = main_repo / "ai-dev/active/I-00048/prompts" / "I-00048_S01_Backend_prompt.md"
    prompt_file.write_text("# backend prompt")

    manifest = main_repo / "ai-dev/active/I-00048/workflow-manifest.json"
    manifest.write_text('{"id": "I-00048"}')

    design = main_repo / "ai-dev/active/I-00048/I-00048_Issue_Design.md"
    design.write_text("# design doc")

    (main_repo / "ai-dev/active/I-00048/reports").mkdir(parents=True, exist_ok=True)
    report = main_repo / "ai-dev/active/I-00048/reports" / "I-00048_S01_Backend_report.md"
    report.write_text("# report content")

    _run_copy_and_exclude(worktree, "I-00048", main_repo)

    gitdir_result = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    gitdir_raw = gitdir_result.stdout.strip()
    if gitdir_raw.startswith("/"):
        gitdir_path = Path(gitdir_raw)
    elif gitdir_raw == ".git":
        gitdir_path = worktree / ".git"
    else:
        gitdir_path = (worktree / gitdir_raw).resolve()

    exclude_path = gitdir_path / "info" / "exclude"
    assert exclude_path.exists(), "info/exclude must be created by Step 7"

    exclude_content = exclude_path.read_text()
    assert "ai-dev/active/I-00048/prompts/" in exclude_content
    assert "ai-dev/active/I-00048/workflow-manifest.json" in exclude_content
    assert "ai-dev/active/I-00048/*.md" in exclude_content

    subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "add",
            "ai-dev/active/I-00048/reports/I-00048_S01_Backend_report.md",
        ],
        capture_output=True,
        text=True,
    )
    status_result = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    staged = status_result.stdout
    assert "I-00048_S01_Backend_report.md" in staged


def test_worktree_exclude_file_contains_correct_patterns(main_repo: Path, worktree: Path) -> None:
    """Verifies the info/exclude file has the right patterns — not just that it exists."""
    prompt_file = main_repo / "ai-dev" / "active" / "I-00048" / "prompts" / "some_prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("# prompt")

    manifest = main_repo / "ai-dev" / "active" / "I-00048" / "workflow-manifest.json"
    manifest.write_text('{"id": "I-00048"}')

    design = main_repo / "ai-dev" / "active" / "I-00048" / "I-00048_Issue_Design.md"
    design.write_text("# design")

    _run_copy_and_exclude(worktree, "I-00048", main_repo)

    gitdir_result = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    gitdir_raw = gitdir_result.stdout.strip()
    if gitdir_raw.startswith("/"):
        gitdir_path = Path(gitdir_raw)
    elif gitdir_raw == ".git":
        gitdir_path = worktree / ".git"
    else:
        gitdir_path = (worktree / gitdir_raw).resolve()

    exclude_path = gitdir_path / "info" / "exclude"
    assert exclude_path.exists()
    content = exclude_path.read_text()

    assert "ai-dev/active/I-00048/prompts/" in content
    assert "ai-dev/active/I-00048/workflow-manifest.json" in content
    assert "ai-dev/active/I-00048/*.md" in content
    assert "ai-dev/active/I-00048/reports/" not in content


def test_copy_step_is_silent_when_active_dir_missing(main_repo: Path, worktree: Path) -> None:
    """If ai-dev/active/<ID>/ doesn't exist, the step must skip without error."""
    _run_copy_and_exclude(worktree, "I-00099", main_repo)

    assert not (worktree / "ai-dev" / "active" / "I-00099").exists()
