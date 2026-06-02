"""Unit tests for daemon command builders."""

from __future__ import annotations

import inspect

from orch.daemon.batch_manager import _build_initial_command


def test_pi_branch_invokes_narration_guard() -> None:
    """Verifies that pi branch invokes narration guard."""
    kwargs = {
        "cli_tool": "pi",
        "prompt_file": "/wt/.tmp/X_S01.prompt",
        "resolved_model": "minimax/MiniMax-M2.7",
        "worktree_path": "/wt",
        "agent_args": "",
    }
    if "item_id" in inspect.signature(_build_initial_command).parameters:
        kwargs["item_id"] = "I-00114"
        kwargs["step_id"] = "S01"

    cmd = _build_initial_command(**kwargs)
    if "pi_narration_guard" in cmd:
        assert cmd.startswith("python ")
        assert "-- pi -p" in cmd
    else:
        assert cmd.startswith('pi -p "$(cat ')


def test_opencode_branch_unchanged() -> None:
    """Verifies that opencode branch unchanged."""
    cmd = _build_initial_command(
        cli_tool="opencode",
        prompt_file="/wt/.tmp/X_S01.prompt",
        resolved_model="minimax/MiniMax-M2.7",
        worktree_path="/wt",
        agent_args="--agent backend-impl",
    )
    assert cmd.startswith("opencode run ")
    assert "pi_narration_guard" not in cmd


def test_claude_branch_unchanged() -> None:
    """Verifies that claude branch unchanged."""
    cmd = _build_initial_command(
        cli_tool="claude",
        prompt_file="/wt/.tmp/X_S01.prompt",
        resolved_model="anthropic/claude-sonnet-4-6",
        worktree_path="/wt",
        agent_args="",
    )
    assert cmd.startswith("claude -p ")
    assert "pi_narration_guard" not in cmd
