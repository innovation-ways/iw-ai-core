"""Unit tests for orch.daemon.auto_merge — build_resolution_prompt().

Covers: work item header, file path, three-way content sections, commit logs,
ABSTAIN clause, no-invention clause, determinism, description truncation,
no environment variable leakage, and prompt hash sensitivity to content changes.
"""

from __future__ import annotations

import hashlib
from unittest.mock import patch


def _run_git_stub(cmd, **kwargs):
    """Stub for subprocess.run that returns fake git output."""
    import subprocess

    args = cmd if isinstance(cmd, list) else cmd
    joined = " ".join(str(a) for a in args)
    if ":1:" in joined:
        stdout = "merge-base content\n"
    elif ":2:" in joined:
        stdout = "ours (main) content\n"
    elif ":3:" in joined:
        stdout = "theirs (branch) content\n"
    elif "log" in joined:
        stdout = "commit abc1234\nAuthor: Test\n\n    fix something\n"
    else:
        stdout = ""
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")


def _default_kwargs() -> dict:
    return {
        "worktree_path": "/repos/proj/.worktrees/F-00001",
        "file_path": "tests/unit/test_foo.py",
        "main_sha": "abc123def456",
        "branch_name": "agent/F-00001-some-feature",
        "item_id": "F-00001",
        "item_title": "Some Feature",
        "item_description": "Implements some feature with tests and docs.",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prompt_includes_work_item_header() -> None:
    """Output contains item_id and item_title in the header section."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    assert len(prompt) > 200
    assert "F-00001" in prompt
    assert "Some Feature" in prompt


def test_prompt_includes_file_path() -> None:
    """Output contains the relative file path being resolved."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    assert len(prompt) > 200
    assert "tests/unit/test_foo.py" in prompt


def test_prompt_includes_three_way_content() -> None:
    """Output contains MERGE BASE, MAIN'S CURRENT VERSION, and THIS BRANCH'S VERSION sections."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    # Verify all three sides of the merge are represented
    # The prompt uses git show :1:, :2:, :3: refs
    assert len(prompt) > 200
    assert "merge-base content" in prompt
    assert "ours (main) content" in prompt
    assert "theirs (branch) content" in prompt


def test_prompt_includes_recent_commits_both_sides() -> None:
    """Output contains git-log-style sections for both main and HEAD."""
    from orch.daemon.auto_merge import build_resolution_prompt

    def _git_stub_with_distinct_logs(cmd, **kwargs):
        import subprocess

        args = cmd if isinstance(cmd, list) else cmd
        joined = " ".join(str(a) for a in args)
        if ":1:" in joined:
            stdout = "base content\n"
        elif ":2:" in joined:
            stdout = "main content\n"
        elif ":3:" in joined:
            stdout = "branch content\n"
        elif "log" in joined and "HEAD" in joined:
            stdout = "commit deadbeef\nAuthor: Branch Author\n\n    branch commit\n"
        elif "log" in joined:
            # main_sha log
            stdout = "commit cafebabe\nAuthor: Main Author\n\n    main commit\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")

    with patch("subprocess.run", side_effect=_git_stub_with_distinct_logs):
        prompt = build_resolution_prompt(**_default_kwargs())

    # Both sides' commit history should appear
    assert "main commit" in prompt or "cafebabe" in prompt
    assert "branch commit" in prompt or "deadbeef" in prompt


def test_prompt_includes_abstain_clause() -> None:
    """Output contains literal string 'ABSTAIN'."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    assert len(prompt) > 200
    assert "ABSTAIN" in prompt


def test_prompt_includes_no_invention_clause() -> None:
    """Output forbids inventing new behaviour (contains relevant instruction)."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    # The prompt must contain an instruction against inventing code/logic
    lower = prompt.lower()
    assert "invent" in lower or "not in the main" in lower or "do not invent" in lower


def test_prompt_is_deterministic() -> None:
    """Same inputs → byte-identical prompt strings across 10 invocations."""
    from orch.daemon.auto_merge import build_resolution_prompt

    kwargs = _default_kwargs()

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompts = [build_resolution_prompt(**kwargs) for _ in range(10)]

    first = prompts[0]
    assert all(p == first for p in prompts[1:])
    assert isinstance(first, str)
    assert len(first) > 100


def test_prompt_truncates_oversized_description() -> None:
    """10,000-word item description is bounded to ~500 words."""
    from orch.daemon.auto_merge import build_resolution_prompt

    # 10,000 unique words
    long_desc = " ".join([f"uniqueword{i}" for i in range(10000)])

    kwargs = {**_default_kwargs(), "item_description": long_desc}

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**kwargs)

    # First 500 words appear; word 500+ must not appear
    assert "uniqueword0" in prompt
    assert "uniqueword499" in prompt
    assert "uniqueword500" not in prompt
    assert "uniqueword9999" not in prompt


def test_prompt_no_environment_leakage(monkeypatch) -> None:
    """Environment variables must NOT appear in the prompt."""
    from orch.daemon.auto_merge import build_resolution_prompt

    monkeypatch.setenv("FAKE_SECRET", "leak-this-secret-value")

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(**_default_kwargs())

    assert "leak-this-secret-value" not in prompt
    assert "FAKE_SECRET" not in prompt


def test_prompt_hash_changes_with_content() -> None:
    """Different file contents → different sha256(prompt)."""
    from orch.daemon.auto_merge import build_resolution_prompt

    def _make_git_stub(ours_content: str):
        def _stub(cmd, **kwargs):
            import subprocess

            args = cmd if isinstance(cmd, list) else cmd
            joined = " ".join(str(a) for a in args)
            if ":1:" in joined:
                stdout = "base\n"
            elif ":2:" in joined:
                stdout = ours_content
            elif ":3:" in joined:
                stdout = "theirs\n"
            elif "log" in joined:
                stdout = "commit abc\n"
            else:
                stdout = ""
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")

        return _stub

    with patch("subprocess.run", side_effect=_make_git_stub("version_A\n")):
        prompt_a = build_resolution_prompt(**_default_kwargs())

    with patch("subprocess.run", side_effect=_make_git_stub("version_B_completely_different\n")):
        prompt_b = build_resolution_prompt(**_default_kwargs())

    hash_a = hashlib.sha256(prompt_a.encode()).hexdigest()
    hash_b = hashlib.sha256(prompt_b.encode()).hexdigest()

    assert hash_a != hash_b


def test_prompt_is_deterministic_original() -> None:
    """Calling build_resolution_prompt() twice with identical inputs produces the same string."""
    from orch.daemon.auto_merge import build_resolution_prompt

    kwargs = {
        "worktree_path": "/repos/proj/.worktrees/F-00001",
        "file_path": "tests/unit/test_foo.py",
        "main_sha": "abc123def456",
        "branch_name": "agent/F-00001-some-feature",
        "item_id": "F-00001",
        "item_title": "Some Feature",
        "item_description": "Implements some feature with tests and docs.",
    }

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt1 = build_resolution_prompt(**kwargs)
        prompt2 = build_resolution_prompt(**kwargs)

    assert prompt1 == prompt2
    assert isinstance(prompt1, str)
    assert len(prompt1) > 50


def test_prompt_contains_abstain_token() -> None:
    """The prompt must instruct the LLM to output ABSTAIN when it cannot resolve."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(
            worktree_path="/repos/proj/.worktrees/F-00001",
            file_path="tests/unit/test_foo.py",
            main_sha="abc123",
            branch_name="agent/F-00001-feature",
            item_id="F-00001",
            item_title="Feature",
            item_description="Does something.",
        )

    assert len(prompt) > 200
    assert "ABSTAIN" in prompt


def test_prompt_contains_work_item_info() -> None:
    """The prompt must include the work item id and title."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(
            worktree_path="/repos/proj/.worktrees/F-00001",
            file_path="docs/design.md",
            main_sha="deadbeef",
            branch_name="agent/F-00001-thing",
            item_id="F-00001",
            item_title="My Special Feature",
            item_description="A detailed description of the feature.",
        )

    assert len(prompt) > 200
    assert "F-00001" in prompt
    assert "My Special Feature" in prompt


def test_prompt_contains_file_path() -> None:
    """The prompt must include the relative file path being resolved."""
    from orch.daemon.auto_merge import build_resolution_prompt

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(
            worktree_path="/repos/proj/.worktrees/F-00001",
            file_path="docs/api.md",
            main_sha="deadbeef",
            branch_name="agent/F-00001-thing",
            item_id="F-00001",
            item_title="Title",
            item_description="Desc.",
        )

    assert len(prompt) > 200
    assert "docs/api.md" in prompt


def test_prompt_truncates_long_description() -> None:
    """Descriptions longer than 500 words are truncated in the prompt."""
    from orch.daemon.auto_merge import build_resolution_prompt

    long_desc = " ".join([f"word{i}" for i in range(600)])

    with patch("subprocess.run", side_effect=_run_git_stub):
        prompt = build_resolution_prompt(
            worktree_path="/repos/proj/.worktrees/F-00001",
            file_path="tests/test_x.py",
            main_sha="abc",
            branch_name="agent/F-00001",
            item_id="F-00001",
            item_title="Long Desc",
            item_description=long_desc,
        )

    assert "word0" in prompt
    assert "word499" in prompt
    assert "word500" not in prompt
