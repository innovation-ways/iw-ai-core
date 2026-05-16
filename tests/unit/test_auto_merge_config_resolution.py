from __future__ import annotations

from unittest.mock import MagicMock

from orch.auto_merge_aggregator import resolve_project_config
from orch.daemon.auto_merge import AutoMergeConfig


def _cfg(**kwargs) -> AutoMergeConfig:
    d = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=kwargs.get("phase", d.phase),
        runtime_option_id=kwargs.get("runtime_option_id", d.runtime_option_id),
        allowlist_patterns=d.allowlist_patterns,
        refuselist_patterns=d.refuselist_patterns,
        max_conflict_hunk_lines=d.max_conflict_hunk_lines,
        max_conflicted_files_per_merge=d.max_conflicted_files_per_merge,
        max_file_size_bytes=d.max_file_size_bytes,
        max_event_metadata_bytes=d.max_event_metadata_bytes,
        llm_call_timeout_seconds=d.llm_call_timeout_seconds,
        health_probe_interval_seconds=d.health_probe_interval_seconds,
        health_failure_rate_threshold_per_day=d.health_failure_rate_threshold_per_day,
    )


def test_resolve_per_project_db_phase_and_runtime_both_set() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=3),
        MagicMock(id=3, cli_tool="opencode", model="openai/gpt-5.3-codex", enabled=True),
    ]
    resolved = resolve_project_config(db, "p", _cfg(phase=0, runtime_option_id=1))
    assert (resolved.phase, resolved.runtime_option_id, resolved.source) == (1, 3, "per_project_db")


def test_resolve_per_project_db_phase_only_runtime_from_toml() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=None),
        MagicMock(id=7, cli_tool="claude", model="claude-sonnet-4-6", enabled=True),
    ]
    resolved = resolve_project_config(db, "p", _cfg(phase=0, runtime_option_id=7))
    assert (resolved.phase, resolved.runtime_option_id, resolved.source) == (1, 7, "toml")


def test_resolve_per_project_db_runtime_only_phase_from_toml() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=None, runtime_option_id=2),
        MagicMock(id=2, cli_tool="opencode", model="openai/gpt-5.3-codex", enabled=True),
    ]
    resolved = resolve_project_config(db, "p", _cfg(phase=1, runtime_option_id=9))
    assert (resolved.phase, resolved.runtime_option_id, resolved.source) == (1, 2, "per_project_db")


def test_resolve_no_db_row_falls_back_to_toml() -> None:
    db = MagicMock()
    db.get.side_effect = [
        None,
        MagicMock(id=9, cli_tool="claude", model="claude-opus-4-7", enabled=True),
    ]
    resolved = resolve_project_config(db, "p", _cfg(phase=1, runtime_option_id=9))
    assert (resolved.phase, resolved.runtime_option_id, resolved.source) == (1, 9, "toml")


def test_resolve_no_db_no_toml_uses_hardcoded_defaults() -> None:
    db = MagicMock()
    db.get.side_effect = [None]
    db.execute.return_value.scalar_one_or_none.return_value = None
    resolved = resolve_project_config(db, "p", _cfg(phase=0, runtime_option_id=None))
    assert resolved.source in {"toml", "hardcoded"}
    assert resolved.model == "openai/gpt-5.3-codex"


def test_resolve_phase_2_in_db_rejected_with_clear_error() -> None:
    db = MagicMock()
    db.get.side_effect = [MagicMock(phase=2, runtime_option_id=None)]
    resolved = resolve_project_config(db, "p", _cfg(phase=1, runtime_option_id=None))
    assert resolved.phase == 0


def test_resolve_phase_3_in_db_rejected_with_clear_error() -> None:
    db = MagicMock()
    db.get.side_effect = [MagicMock(phase=3, runtime_option_id=None)]
    resolved = resolve_project_config(db, "p", _cfg(phase=1, runtime_option_id=None))
    assert resolved.phase == 0


def test_resolve_disabled_runtime_in_db_falls_back_to_toml_runtime() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=99),
        MagicMock(id=99, cli_tool="opencode", model="x", enabled=False),
        MagicMock(id=2, cli_tool="claude", model="claude-sonnet-4-6", enabled=True),
    ]
    resolved = resolve_project_config(db, "p", _cfg(phase=0, runtime_option_id=2))
    assert (resolved.runtime_option_id, resolved.source) == (2, "toml")


def test_resolve_disabled_runtime_emits_auto_merge_config_invalid_once() -> None:
    db = MagicMock()
    latest = MagicMock(event_metadata={"reason": "runtime_option_disabled", "configured_id": 99})
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=99),
        MagicMock(id=99, cli_tool="opencode", model="x", enabled=False),
        None,
    ]
    latest_result = MagicMock()
    latest_result.scalar_one_or_none.return_value = latest
    default_result = MagicMock()
    default_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [latest_result, default_result]
    resolved = resolve_project_config(db, "p", _cfg(runtime_option_id=None))
    assert resolved.runtime_option_id is None
    assert resolved.source == "toml"
    assert resolved.model == "openai/gpt-5.3-codex"
    assert db.add.call_count == 0


def test_resolve_deterministic_invariant_2() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=7),
        MagicMock(id=7, cli_tool="claude", model="claude-sonnet-4-6", enabled=True),
    ] * 10
    baseline = resolve_project_config(db, "p", _cfg())
    for _ in range(9):
        assert resolve_project_config(db, "p", _cfg()) == baseline


def test_resolve_returns_source_field_per_project_db_when_db_row_exists() -> None:
    db = MagicMock()
    db.get.side_effect = [
        MagicMock(phase=1, runtime_option_id=1),
        MagicMock(id=1, cli_tool="opencode", model="openai/gpt-5.3-codex", enabled=True),
    ]
    assert resolve_project_config(db, "p", _cfg()).source == "per_project_db"


def test_resolve_returns_source_field_toml_when_no_db_row() -> None:
    db = MagicMock()
    db.get.side_effect = [
        None,
        MagicMock(id=4, cli_tool="claude", model="claude-opus-4-7", enabled=True),
    ]
    assert resolve_project_config(db, "p", _cfg(runtime_option_id=4)).source == "toml"
