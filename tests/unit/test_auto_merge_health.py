from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from orch.daemon.auto_merge import AutoMergeConfig
from orch.daemon.auto_merge_health import maybe_run_probe


def _cfg(interval: int = 300) -> AutoMergeConfig:
    d = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=d.phase,
        runtime_option_id=d.runtime_option_id,
        allowlist_patterns=d.allowlist_patterns,
        refuselist_patterns=d.refuselist_patterns,
        max_conflict_hunk_lines=d.max_conflict_hunk_lines,
        max_conflicted_files_per_merge=d.max_conflicted_files_per_merge,
        max_file_size_bytes=d.max_file_size_bytes,
        max_event_metadata_bytes=d.max_event_metadata_bytes,
        llm_call_timeout_seconds=d.llm_call_timeout_seconds,
        health_probe_interval_seconds=interval,
        health_failure_rate_threshold_per_day=d.health_failure_rate_threshold_per_day,
    )


def test_probe_skipped_when_recent_event_exists() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = MagicMock(
        created_at=datetime.now(UTC) - timedelta(seconds=10)
    )
    with patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve:
        resolve.return_value = MagicMock(phase=1)
        maybe_run_probe(db, "proj", _cfg(60))
    assert resolve.call_count == 1
    assert db.add.call_count == 0
    assert db.commit.call_count == 0


def test_probe_fires_when_no_recent_event() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch("orch.daemon.auto_merge_health.subprocess.run") as run,
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="opencode", model="openai/gpt-5.3-codex")
        run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        maybe_run_probe(db, "proj", _cfg())
    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is True


def test_probe_records_failure_on_subprocess_error() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch("orch.daemon.auto_merge_health.subprocess.run") as run,
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="opencode", model="openai/gpt-5.3-codex")
        run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        maybe_run_probe(db, "proj", _cfg())
    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is False
    assert payload["error"] == "boom"


def test_probe_records_failure_on_timeout() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch(
            "orch.daemon.auto_merge_health.subprocess.run",
            side_effect=subprocess.TimeoutExpired("x", 1),
        ),
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="opencode", model="openai/gpt-5.3-codex")
        maybe_run_probe(db, "proj", _cfg())
    assert db.add.call_args[0][0].event_metadata["error"] == "timeout"


def test_probe_skipped_when_phase_0() -> None:
    db = MagicMock()
    with patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve:
        resolve.return_value = MagicMock(phase=0)
        maybe_run_probe(db, "proj", _cfg())
    assert resolve.call_count == 1
    assert db.execute.call_count == 0
    assert db.add.call_count == 0
    assert db.commit.call_count == 0


def test_probe_uses_resolved_per_project_runtime() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch("orch.daemon.auto_merge_health.subprocess.run") as run,
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="claude", model="claude-sonnet-4-6")
        run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        maybe_run_probe(db, "proj", _cfg())
    args = run.call_args.kwargs
    assert args["timeout"] == 75


def test_probe_subprocess_timeout_capped() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch("orch.daemon.auto_merge_health.subprocess.run") as run,
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="opencode", model="openai/gpt-5.3-codex")
        run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        maybe_run_probe(db, "proj", _cfg(20))
    assert run.call_args.kwargs["timeout"] == 15


def test_probe_non_blocking_does_not_raise() -> None:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve,
        patch("orch.daemon.auto_merge_health.subprocess.run", side_effect=RuntimeError("kaboom")),
    ):
        resolve.return_value = MagicMock(phase=1, cli_tool="opencode", model="openai/gpt-5.3-codex")
        maybe_run_probe(db, "proj", _cfg())
    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is False
    assert payload["cli_tool"] == "opencode"
    assert payload["model"] == "openai/gpt-5.3-codex"
    assert payload["error"] == "RuntimeError: kaboom"
