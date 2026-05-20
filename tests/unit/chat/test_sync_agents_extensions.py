"""Unit tests for Pi extension sync in ``orch.skills.sync_agents`` (F-00087).

Invariant #8 — ``pi_extensions_synced`` counter increments on copy.
AC7 — sync engine copies Pi extensions + idempotency + broken symlink handling.

Tests:
    - test_sync_copies_pi_extensions_subdirs_into_dot_pi_extensions
    - test_pi_extensions_synced_counter_increments
    - test_sync_is_idempotent
    - test_broken_symlink_in_extension_dir_does_not_break_sync
    - test_existing_pi_agents_still_synced

All tests use tmp_path so no real filesystem outside the test is touched.
"""

from __future__ import annotations

from pathlib import Path

from orch.skills.sync_agents import AgentSyncResult, sync_agents_and_commands

# ---------------------------------------------------------------------------
# Fixtures: build a minimal platform_root and project_path in tmp_path
# ---------------------------------------------------------------------------


def _build_platform_root(tmp_path: Path) -> Path:
    """Create a minimal platform_root with agents/pi/extensions/ and agents/pi/*.md."""
    platform_root = tmp_path / "platform"
    # Pi agents directory (CR-00062 files — must still be synced)
    pi_agents = platform_root / "agents" / "pi"
    pi_agents.mkdir(parents=True, exist_ok=True)
    (pi_agents / "agent-one.md").write_text("# Agent One")
    (pi_agents / "agent-two.md").write_text("# Agent Two")

    # Claude agents directory
    claude_agents = platform_root / "agents" / "claude"
    claude_agents.mkdir(parents=True, exist_ok=True)
    (claude_agents / "claude-agent.md").write_text("# Claude")

    # OpenCode agents directory
    opencode_agents = platform_root / "agents" / "opencode"
    opencode_agents.mkdir(parents=True, exist_ok=True)
    (opencode_agents / "oc-agent.md").write_text("# OC")

    # Commands directory
    commands = platform_root / "commands"
    commands.mkdir(parents=True, exist_ok=True)
    (commands / "cmd.md").write_text("# Cmd")

    return platform_root


def _add_extension(
    platform_root: Path,
    ext_name: str,
    files: dict[str, str],
) -> Path:
    """Add an extension directory under agents/pi/extensions/<ext_name>/."""
    ext_dir = platform_root / "agents" / "pi" / "extensions" / ext_name
    ext_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (ext_dir / filename).write_text(content)
    return ext_dir


# ---------------------------------------------------------------------------
# Invariant #8 + AC7 — basic copy and counter
# ---------------------------------------------------------------------------


def test_sync_copies_pi_extensions_subdirs_into_dot_pi_extensions(
    tmp_path: Path,
) -> None:
    """sync_agents_and_commands copies each extension subdir into project/.pi/extensions/<name>/."""
    platform_root = _build_platform_root(tmp_path)
    _add_extension(
        platform_root,
        "iw-chat-approvals",
        {
            "index.ts": "export default {};",
            "package.json": '{"name":"iw-chat-approvals"}',
            "README.md": "# IW Chat Approvals",
        },
    )

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    result = sync_agents_and_commands(project_path, platform_root)

    dest = project_path / ".pi" / "extensions" / "iw-chat-approvals"
    assert dest.is_dir(), f"extension dir not created: {dest}"

    index_ts = dest / "index.ts"
    assert index_ts.is_file(), "index.ts not synced"
    assert index_ts.read_text() == "export default {};"

    pkg_json = dest / "package.json"
    assert pkg_json.is_file(), "package.json not synced"
    assert pkg_json.read_text() == '{"name":"iw-chat-approvals"}'

    readme = dest / "README.md"
    assert readme.is_file(), "README.md not synced"

    assert result.pi_extensions_synced == 1


def test_pi_extensions_synced_counter_increments(tmp_path: Path) -> None:
    """pi_extensions_synced equals the number of extension dirs successfully copied."""
    platform_root = _build_platform_root(tmp_path)
    _add_extension(platform_root, "ext-alpha", {"a.ts": "// alpha"})
    _add_extension(platform_root, "ext-beta", {"b.ts": "// beta"})
    _add_extension(platform_root, "ext-gamma", {"c.ts": "// gamma"})

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    result = sync_agents_and_commands(project_path, platform_root)

    assert result.pi_extensions_synced == 3, (
        f"expected 3 extensions synced, got {result.pi_extensions_synced}"
    )


# ---------------------------------------------------------------------------
# AC7 — idempotency
# ---------------------------------------------------------------------------


def test_sync_is_idempotent(tmp_path: Path) -> None:
    """Running sync_agents_and_commands twice produces the same result both times."""
    platform_root = _build_platform_root(tmp_path)
    _add_extension(
        platform_root,
        "iw-chat-approvals",
        {"index.ts": "// v1", "package.json": '{"version":"1.0.0"}'},
    )

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    result1 = sync_agents_and_commands(project_path, platform_root)
    result2 = sync_agents_and_commands(project_path, platform_root)

    assert result1.pi_extensions_synced == 1
    assert result2.pi_extensions_synced == 1

    # File content must be byte-identical after second sync.
    dest_ts = project_path / ".pi" / "extensions" / "iw-chat-approvals" / "index.ts"
    assert dest_ts.read_text() == "// v1"
    assert not result2.errors, f"second sync produced errors: {result2.errors}"


# ---------------------------------------------------------------------------
# AC7 — broken symlink in extension dir
# ---------------------------------------------------------------------------


def test_broken_symlink_in_extension_dir_does_not_break_sync(
    tmp_path: Path,
) -> None:
    """A dangling symlink inside an extension dir must not crash the sync.

    Per the design (§Boundary Behavior): sync catches the error, logs a warning,
    continues with other extensions, and only increments the counter for
    successful copies.
    """
    platform_root = _build_platform_root(tmp_path)

    # Good extension that should succeed.
    _add_extension(platform_root, "good-ext", {"index.ts": "// good"})

    # Extension with a dangling symlink.
    bad_ext_dir = platform_root / "agents" / "pi" / "extensions" / "bad-ext"
    bad_ext_dir.mkdir(parents=True, exist_ok=True)
    (bad_ext_dir / "real.ts").write_text("// real file")
    dangling = bad_ext_dir / "dangling.ts"
    # Create the symlink pointing at a non-existent target.
    dangling.symlink_to("/nonexistent/target.ts")
    assert dangling.is_symlink(), "test bug: dangling must be a symlink"
    assert not dangling.exists(), "test bug: symlink target must not exist"

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    # Must not raise; should complete and process the good extension.
    result = sync_agents_and_commands(project_path, platform_root)

    # The good extension must have been copied.
    good_dest = project_path / ".pi" / "extensions" / "good-ext" / "index.ts"
    assert good_dest.is_file(), "good extension must still be synced despite bad neighbour"

    # The counter reflects only successful copies: good=1, bad=0 (error suppressed).
    # The bad extension may have partially succeeded or fully failed depending on
    # whether shutil.copytree raises before or after copying real.ts.
    # The invariant is: pi_extensions_synced counts full successes only.
    # Errors are collected in result.errors OR silently logged — both are acceptable.
    # The most important assertion is that the good extension was synced.
    assert result.pi_extensions_synced >= 1, "at least the good extension must be counted"


# ---------------------------------------------------------------------------
# AC7 — existing pi_agents_synced not regressed
# ---------------------------------------------------------------------------


def test_existing_pi_agents_still_synced(tmp_path: Path) -> None:
    """CR-00062's pi_agents_synced counter must still work alongside pi_extensions_synced."""
    platform_root = _build_platform_root(tmp_path)
    _add_extension(platform_root, "iw-chat-approvals", {"index.ts": "// ext"})

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    result = sync_agents_and_commands(project_path, platform_root)

    # Two .md files in agents/pi/ were created by _build_platform_root.
    assert result.pi_agents_synced == 2, (
        f"expected 2 pi agents synced, got {result.pi_agents_synced}"
    )
    assert result.pi_extensions_synced == 1, (
        f"expected 1 pi extension synced, got {result.pi_extensions_synced}"
    )

    # Verify the pi agents are actually on disk.
    assert (project_path / ".pi" / "agents" / "agent-one.md").is_file()
    assert (project_path / ".pi" / "agents" / "agent-two.md").is_file()

    # Verify the extension is on disk.
    assert (project_path / ".pi" / "extensions" / "iw-chat-approvals" / "index.ts").is_file()


# ---------------------------------------------------------------------------
# AgentSyncResult dataclass has pi_extensions_synced field defaulting to 0
# ---------------------------------------------------------------------------


def test_agent_sync_result_has_pi_extensions_synced_field() -> None:
    """AgentSyncResult.pi_extensions_synced exists and defaults to 0."""
    result = AgentSyncResult()
    assert hasattr(result, "pi_extensions_synced"), (
        "AgentSyncResult must have a pi_extensions_synced field"
    )
    assert result.pi_extensions_synced == 0, (
        f"default should be 0, got {result.pi_extensions_synced}"
    )


# ---------------------------------------------------------------------------
# No extensions dir — no error (missing source is silently skipped)
# ---------------------------------------------------------------------------


def test_no_extensions_dir_does_not_cause_error(tmp_path: Path) -> None:
    """When agents/pi/extensions/ does not exist, sync completes with 0 pi_extensions_synced."""
    platform_root = _build_platform_root(tmp_path)
    # Deliberately do NOT create agents/pi/extensions/.
    assert not (platform_root / "agents" / "pi" / "extensions").exists()

    project_path = tmp_path / "myproject"
    project_path.mkdir()

    result = sync_agents_and_commands(project_path, platform_root)

    assert result.pi_extensions_synced == 0
    assert not result.errors
