"""Unit tests for always_in_scope parsing in project_registry (CR-00089 S01)."""

from __future__ import annotations

from pathlib import Path

from orch.daemon import fix_cycle
from orch.daemon.project_registry import ProjectConfig, _build_project_config
from orch.db.models import FixStatus


def test_build_project_config_parses_always_in_scope_paths(tmp_path: Path) -> None:
    """projects.toml always_in_scope.paths is exposed on ProjectConfig."""
    entry = {
        "repo_root": str(tmp_path),
        "enabled": True,
        "always_in_scope": {"paths": ["tests/assertion_free_baseline.txt", "docs/**/*.md"]},
    }

    cfg = _build_project_config("test-proj", entry)

    assert cfg is not None
    assert cfg.always_in_scope_paths == ["tests/assertion_free_baseline.txt", "docs/**/*.md"]


def test_build_project_config_defaults_always_in_scope_paths_to_empty(tmp_path: Path) -> None:
    """Missing always_in_scope block defaults to empty list."""
    entry = {
        "repo_root": str(tmp_path),
        "enabled": True,
    }

    cfg = _build_project_config("test-proj", entry)

    assert cfg is not None
    assert cfg.always_in_scope_paths == []


def test_always_in_scope_empty_by_default(tmp_path: Path) -> None:
    entry = {
        "repo_root": str(tmp_path),
        "enabled": True,
    }

    cfg = _build_project_config("test-proj", entry)

    assert cfg is not None
    assert cfg.always_in_scope_paths == []


def test_always_in_scope_invalid_paths_type_defaults_to_empty(tmp_path: Path) -> None:
    entry = {
        "repo_root": str(tmp_path),
        "enabled": True,
        "always_in_scope": {"paths": "not-a-list"},
    }

    cfg = _build_project_config("test-proj", entry)

    assert cfg is not None
    assert cfg.always_in_scope_paths == []


def test_always_in_scope_appended_to_allowed(monkeypatch, tmp_path: Path) -> None:
    project_config = ProjectConfig(
        id="p",
        display_name="P",
        repo_root=str(tmp_path),
        enabled=True,
        cli_tool="opencode",
        model="m",
        worktree_base=".worktrees",
        config={},
        always_in_scope_paths=["tests/assertion_free_baseline.txt"],
    )

    monkeypatch.setattr(fix_cycle, "_load_allowed_paths", lambda *_args, **_kwargs: ["orch/foo.py"])
    monkeypatch.setattr(fix_cycle, "_build_scope_block", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(fix_cycle, "run_llm_agent", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(fix_cycle, "_captured_paths", lambda *_args, **_kwargs: set())

    allowed_seen: list[str] = []

    def _spy_scope_match(path: str, pattern: str) -> bool:
        allowed_seen.append(pattern)
        return True

    monkeypatch.setattr(fix_cycle, "scope_match", _spy_scope_match)

    result = fix_cycle.run_fix_cycle(
        worktree_path=tmp_path,
        item_id="CR-00089",
        step_id="S05",
        cycle_number=1,
        gate_failure="fail",
        project_config=project_config,
    )

    assert result.status == FixStatus.completed
    assert allowed_seen == []

    allowed = ["orch/foo.py"] + project_config.always_in_scope_paths
    assert allowed == ["orch/foo.py", "tests/assertion_free_baseline.txt"]


def test_always_in_scope_no_violation_for_global_file(monkeypatch, tmp_path: Path) -> None:
    project_config = ProjectConfig(
        id="p",
        display_name="P",
        repo_root=str(tmp_path),
        enabled=True,
        cli_tool="opencode",
        model="m",
        worktree_base=".worktrees",
        config={},
        always_in_scope_paths=["tests/assertion_free_baseline.txt"],
    )

    monkeypatch.setattr(fix_cycle, "_load_allowed_paths", lambda *_args, **_kwargs: ["orch/foo.py"])
    monkeypatch.setattr(fix_cycle, "_build_scope_block", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(fix_cycle, "run_llm_agent", lambda *_args, **_kwargs: {"ok": True})

    snapshots = [set(), {"tests/assertion_free_baseline.txt"}]
    monkeypatch.setattr(fix_cycle, "_captured_paths", lambda *_args, **_kwargs: snapshots.pop(0))

    result = fix_cycle.run_fix_cycle(
        worktree_path=tmp_path,
        item_id="CR-00089",
        step_id="S05",
        cycle_number=1,
        gate_failure="fail",
        project_config=project_config,
    )

    assert result.status == FixStatus.completed
    assert result.fix_metadata == {}
