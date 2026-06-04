"""Unit tests for Pi agent sync (CR-00062 S04).

Covers:
  - ``AgentSyncResult.pi_agents_synced`` field exists with a default of 0
  - ``sync_agents_and_commands`` copies ``agents/pi/*.md`` into ``.pi/agents/``
  - The sync is idempotent — re-running produces byte-identical output and the
    same count
  - The total file count reported by the CLI (sum of all counters) includes
    ``pi_agents_synced``

All tests use ``tmp_path`` — no DB or network I/O.
"""

from __future__ import annotations

import filecmp
from pathlib import Path

from orch.skills.sync_agents import AgentSyncResult, sync_agents_and_commands


def _write(path: Path, content: str = "stub\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_platform_tree(
    platform_root: Path,
    *,
    pi_files: dict[str, str] | None = None,
    claude_files: dict[str, str] | None = None,
    opencode_files: dict[str, str] | None = None,
    commands: dict[str, str] | None = None,
) -> None:
    """Build a fake ``platform_root`` containing the four source directories."""
    pi_files = pi_files or {}
    claude_files = claude_files or {}
    opencode_files = opencode_files or {}
    commands = commands or {}

    for name, body in pi_files.items():
        _write(platform_root / "agents" / "pi" / name, body)
    for name, body in claude_files.items():
        _write(platform_root / "agents" / "claude" / name, body)
    for name, body in opencode_files.items():
        _write(platform_root / "agents" / "opencode" / name, body)
    for name, body in commands.items():
        _write(platform_root / "commands" / name, body)


# ---------------------------------------------------------------------------
# AgentSyncResult dataclass invariant
# ---------------------------------------------------------------------------


def test_agent_sync_result_has_pi_agents_synced_field() -> None:
    """AgentSyncResult must expose pi_agents_synced with a default of 0.

    RED-phase assertion for CR-00062 S04 (captured by S04's
    ``test_sync_creates_pi_agents_directory`` first, then specialised here as
    the field-level invariant): before the field was added, this test failed
    with ``AttributeError: 'AgentSyncResult' object has no attribute
    'pi_agents_synced'``.
    """
    result = AgentSyncResult()
    assert result.pi_agents_synced == 0


# ---------------------------------------------------------------------------
# sync_agents_and_commands behaviour
# ---------------------------------------------------------------------------


def test_sync_creates_pi_agents_directory(tmp_path: Path) -> None:
    """Pi master files must be copied to ``<project>/.pi/agents/`` and counted."""
    platform_root = tmp_path / "platform"
    project_path = tmp_path / "project"

    _build_platform_tree(
        platform_root,
        pi_files={"backend-impl.md": "pi-body-1\n", "tests-impl.md": "pi-body-2\n"},
        claude_files={"backend-impl.md": "claude-body\n"},
        opencode_files={"backend-impl.md": "opencode-body\n"},
        commands={"review.md": "cmd-body\n"},
    )

    result = sync_agents_and_commands(project_path, platform_root)

    target = project_path / ".pi" / "agents"
    assert result.pi_agents_synced == 2
    assert (target / "backend-impl.md").is_file()
    assert (target / "tests-impl.md").is_file()
    # Byte-level: copied content matches the source exactly.
    assert (target / "backend-impl.md").read_text() == "pi-body-1\n"
    assert (target / "tests-impl.md").read_text() == "pi-body-2\n"
    assert result.errors == []


def test_sync_creates_target_when_missing(tmp_path: Path) -> None:
    """The ``.pi/agents/`` directory is created if it doesn't yet exist."""
    platform_root = tmp_path / "platform"
    project_path = tmp_path / "project"

    _build_platform_tree(platform_root, pi_files={"qv-gate.md": "qv-body\n"})

    target = project_path / ".pi" / "agents"
    assert not target.exists()

    result = sync_agents_and_commands(project_path, platform_root)

    assert target.is_dir()
    assert (target / "qv-gate.md").is_file()
    assert result.pi_agents_synced == 1


def test_sync_pi_idempotent(tmp_path: Path) -> None:
    """Re-running sync produces byte-identical files and the same count.

    This is AC3's idempotency clause — the daemon resyncs on every worktree
    creation, so the second-and-subsequent calls must not corrupt or duplicate
    files.
    """
    platform_root = tmp_path / "platform"
    project_path = tmp_path / "project"

    _build_platform_tree(
        platform_root,
        pi_files={
            "backend-impl.md": "pi-body-1\n",
            "tests-impl.md": "pi-body-2\n",
            "orchestrator.md": "pi-body-3\n",
        },
    )

    first = sync_agents_and_commands(project_path, platform_root)
    target = project_path / ".pi" / "agents"
    snapshot = {p.name: p.read_bytes() for p in sorted(target.iterdir())}

    second = sync_agents_and_commands(project_path, platform_root)
    after = {p.name: p.read_bytes() for p in sorted(target.iterdir())}

    assert first.pi_agents_synced == 3
    assert second.pi_agents_synced == 3
    assert snapshot == after
    # Use filecmp to defend against silent encoding/permissions drift between
    # the two calls — every source file should still be byte-equal to its
    # copy after the second run.
    for src in (platform_root / "agents" / "pi").iterdir():
        if src.suffix == ".md":
            assert filecmp.cmp(src, target / src.name, shallow=False)


def test_sync_total_count_includes_pi(tmp_path: Path) -> None:
    """Total file count printed by the CLI must be the sum of all four
    counters — Pi included.

    The CLI sums ``claude_agents + pi_agents + opencode_agents +
    opencode_commands`` for the human-readable ``Total: N files synced.`` line
    (see ``orch/cli/skills_commands.py:sync_agents_cmd``). This test pins that
    arithmetic — a future contributor who adds a counter without updating the
    total will fail here, and a future drop-by-rename of ``pi_agents_synced``
    will be caught too.
    """
    platform_root = tmp_path / "platform"
    project_path = tmp_path / "project"

    _build_platform_tree(
        platform_root,
        pi_files={f"pi_{i}.md": f"pi-{i}\n" for i in range(3)},  # 3 pi
        claude_files={f"claude_{i}.md": f"c-{i}\n" for i in range(4)},  # 4 claude
        opencode_files={f"oc_{i}.md": f"oc-{i}\n" for i in range(2)},  # 2 opencode agents
        commands={f"cmd_{i}.md": f"k-{i}\n" for i in range(5)},  # 5 opencode commands
    )

    result = sync_agents_and_commands(project_path, platform_root)

    assert result.pi_agents_synced == 3
    assert result.claude_agents_synced == 4
    assert result.opencode_agents_synced == 2
    assert result.opencode_commands_synced == 5

    total = (
        result.claude_agents_synced
        + result.pi_agents_synced
        + result.opencode_agents_synced
        + result.opencode_commands_synced
    )
    assert total == 3 + 4 + 2 + 5
    assert total == 14
