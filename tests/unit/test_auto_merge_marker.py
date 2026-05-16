"""Unit tests for orch.daemon.auto_merge — marker parsing functions.

RED phase: these tests must fail until auto_merge.py is implemented.
"""

from __future__ import annotations

import json


def test_parse_resolve_marker_valid() -> None:
    """Valid AUTO_RESOLVE_REQUESTED marker is parsed into a dict."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    payload = {"eligible_files": ["tests/unit/test_a.py"], "branch": "agent/F-1", "main_sha": "abc"}
    output = f"AUTO_RESOLVE_REQUESTED={json.dumps(payload)}\nsome other line\n"

    result = parse_auto_resolve_marker(output)

    assert result is not None
    assert result["eligible_files"] == ["tests/unit/test_a.py"]
    assert result["branch"] == "agent/F-1"
    assert result["main_sha"] == "abc"


def test_parse_skip_marker_valid() -> None:
    """Valid AUTO_RESOLVE_SKIPPED marker is parsed into a dict."""
    from orch.daemon.auto_merge import parse_auto_skip_marker

    payload = {"reason": "refuse_list", "refuse_files": [".env"], "eligible_files": []}
    output = f"AUTO_RESOLVE_SKIPPED={json.dumps(payload)}\n"

    result = parse_auto_skip_marker(output)

    assert result is not None
    assert result["reason"] == "refuse_list"
    assert result["refuse_files"] == [".env"]


def test_marker_absent_returns_none_for_resolve() -> None:
    """Output without AUTO_RESOLVE_REQUESTED marker returns None."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    output = "[worktree_commit] INFO: rebase succeeded\n[worktree_commit] OK: merged\n"
    result = parse_auto_resolve_marker(output)
    assert result is None


def test_marker_absent_returns_none_for_skip() -> None:
    """Output without AUTO_RESOLVE_SKIPPED marker returns None."""
    from orch.daemon.auto_merge import parse_auto_skip_marker

    output = "[worktree_commit] INFO: all good\n"
    result = parse_auto_skip_marker(output)
    assert result is None


def test_malformed_json_resolve_returns_none() -> None:
    """Malformed JSON in AUTO_RESOLVE_REQUESTED returns None without raising."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    output = "AUTO_RESOLVE_REQUESTED={not valid json\n"
    result = parse_auto_resolve_marker(output)
    assert result is None


def test_malformed_json_skip_returns_none() -> None:
    """Malformed JSON in AUTO_RESOLVE_SKIPPED returns None without raising."""
    from orch.daemon.auto_merge import parse_auto_skip_marker

    output = "AUTO_RESOLVE_SKIPPED={broken: json}\n"
    result = parse_auto_skip_marker(output)
    assert result is None


def test_parse_resolve_marker_multiline_output() -> None:
    """Marker is found even when surrounded by other worktree_commit lines."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    payload = {"eligible_files": ["docs/guide.md"], "branch": "agent/F-2", "main_sha": "deadbeef"}
    output = "\n".join(
        [
            "[worktree_commit] INFO: Rebase conflicts detected:",
            "[worktree_commit]   - docs/guide.md",
            f"AUTO_RESOLVE_REQUESTED={json.dumps(payload)}",
            "[worktree_commit] ERROR: Rebase conflict in implementation files",
        ]
    )

    result = parse_auto_resolve_marker(output)
    assert result is not None
    assert result["eligible_files"] == ["docs/guide.md"]


def test_parse_skip_marker_mixed_refuse_skip() -> None:
    """AUTO_RESOLVE_SKIPPED with mixed_refuse_list reason is parsed correctly."""
    from orch.daemon.auto_merge import parse_auto_skip_marker

    payload = {
        "reason": "mixed_refuse_list",
        "refuse_files": ["executor/step_executor.sh"],
        "eligible_files": ["tests/test_a.py"],
    }
    output = f"AUTO_RESOLVE_SKIPPED={json.dumps(payload)}\n"

    result = parse_auto_skip_marker(output)
    assert result is not None
    assert result["reason"] == "mixed_refuse_list"
    assert "executor/step_executor.sh" in result["refuse_files"]
