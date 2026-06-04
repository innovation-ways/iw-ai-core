"""Integration coverage for probe → step_executor_lib.sh → runtime CLI.

Manual RED reasoning (pre-S01): if maybe_run_probe called
`step_executor.sh --step-type ... --agent ... --model ...`, step_executor.sh would
fail early (`ERROR: Worktree not found or invalid: --agent`), the fake runtime
shim on PATH would not run, no capture file would be produced, and these tests
would fail on runtime_reachable/capture assertions.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.daemon.auto_merge import AutoMergeConfig
from orch.daemon.auto_merge_health import maybe_run_probe


def _write_fake_cli(dir_: Path, name: str, capture_file: Path, *, output_ok: bool) -> None:
    script = dir_ / name
    lines = [
        "#!/usr/bin/env bash",
        f'echo "argv: $*" > "{capture_file}"',
        f'cat >> "{capture_file}"',
    ]
    if output_ok:
        lines.extend(['echo "OK"', "exit 0"])
    else:
        lines.extend(['echo "nope" >&2', "exit 1"])
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _probe_cfg() -> AutoMergeConfig:
    cfg = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=cfg.phase,
        runtime_option_id=cfg.runtime_option_id,
        allowlist_patterns=cfg.allowlist_patterns,
        refuselist_patterns=cfg.refuselist_patterns,
        max_conflict_hunk_lines=cfg.max_conflict_hunk_lines,
        max_conflicted_files_per_merge=cfg.max_conflicted_files_per_merge,
        max_file_size_bytes=cfg.max_file_size_bytes,
        max_event_metadata_bytes=cfg.max_event_metadata_bytes,
        llm_call_timeout_seconds=cfg.llm_call_timeout_seconds,
        health_probe_interval_seconds=20,
        health_failure_rate_threshold_per_day=cfg.health_failure_rate_threshold_per_day,
    )


def test_probe_invokes_runtime_via_lib_script_and_records_reachable(
    tmp_path: Path, monkeypatch
) -> None:
    capture = tmp_path / "captured.txt"
    _write_fake_cli(tmp_path, "opencode", capture, output_ok=True)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve:
        resolve.return_value = MagicMock(
            phase=1,
            cli_tool="opencode",
            model="minimax/MiniMax-M2.7",
        )
        maybe_run_probe(db, "proj", _probe_cfg())

    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is True, payload
    assert payload["error"] is None
    captured = capture.read_text(encoding="utf-8")
    assert "minimax/MiniMax-M2.7" in captured
    assert "Reply with the single word OK." in captured


def test_probe_records_unreachable_when_runtime_returns_non_zero(
    tmp_path: Path, monkeypatch
) -> None:
    capture = tmp_path / "captured-failure.txt"
    _write_fake_cli(tmp_path, "opencode", capture, output_ok=False)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve:
        resolve.return_value = MagicMock(
            phase=1,
            cli_tool="opencode",
            model="minimax/MiniMax-M2.7",
        )
        maybe_run_probe(db, "proj", _probe_cfg())

    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is False, payload
    assert payload["error"]
    captured = capture.read_text(encoding="utf-8")
    assert "minimax/MiniMax-M2.7" in captured
    assert "Reply with the single word OK." in captured
