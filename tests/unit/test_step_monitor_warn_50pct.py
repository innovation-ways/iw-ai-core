"""CR-00024 AC4/AC5: 50%-of-timeout soft-warn idempotency + timeout shadowing.

The warn must fire at most once per step run (idempotent across poll cycles)
and must NOT fire in the same poll cycle where the hard-timeout fires.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from orch.config import DaemonConfig
from orch.daemon.step_monitor import monitor_running_steps
from orch.db.models import RunStatus, StepStatus

if TYPE_CHECKING:
    from pathlib import Path

_FROZEN_TIME = "2026-04-27 12:00:00"
_FROZEN_NOW = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


def _config(tmp_path: Path) -> DaemonConfig:
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def _make_run(
    *,
    started_seconds_ago: int,
    timeout_secs: int,
    warned_50pct_at: datetime | None = None,
) -> MagicMock:
    """Build a minimal StepRun mock for the lifecycle assertions."""
    run = MagicMock()
    run.id = 99
    run.step_id = 1
    run.pid = 12345
    run.status = RunStatus.running
    run.pid_alive = None
    run.started_at = _FROZEN_NOW - timedelta(seconds=started_seconds_ago)
    run.timeout_secs = timeout_secs
    run.last_heartbeat = _FROZEN_NOW - timedelta(seconds=10)
    run.warned_50pct_at = warned_50pct_at
    run.error_message = None
    run.completed_at = None
    run.duration_secs = None
    run.log_file = None
    return run


def _make_db(runs: list) -> MagicMock:
    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.all.return_value = runs
    mock_step = MagicMock()
    mock_step.status = StepStatus.in_progress
    mock_step.work_item_id = "I-99000"
    db.get.return_value = mock_step
    return db


# ---------------------------------------------------------------------------
# AC4 — 50%-warn fires exactly once per StepRun
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_warn_fires_when_past_50pct_and_marker_is_null(tmp_path: Path) -> None:
    """First crossing of 50% emits one step_warning_50pct DaemonEvent + stamps marker."""
    run = _make_run(started_seconds_ago=320, timeout_secs=600, warned_50pct_at=None)
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))

    assert run.warned_50pct_at == _FROZEN_NOW, "marker must be stamped"
    assert run.status == RunStatus.running, "warn is non-terminal"

    db.add.assert_called_once()
    event = db.add.call_args[0][0]
    assert event.event_type == "step_warning_50pct"
    assert event.project_id == "proj"
    assert event.entity_id == "I-99000"

    md = event.event_metadata
    assert md["pid"] == 12345
    assert md["elapsed_secs"] == 320.0
    assert md["timeout_secs"] == 600
    assert 53 <= md["percent"] <= 54


@freeze_time(_FROZEN_TIME)
def test_warn_does_not_fire_when_marker_already_set(tmp_path: Path) -> None:
    """AC4 idempotency: marker already set → no new event emitted."""
    run = _make_run(
        started_seconds_ago=350,
        timeout_secs=600,
        warned_50pct_at=_FROZEN_NOW - timedelta(seconds=30),
    )
    original_marker = run.warned_50pct_at
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))

    assert run.warned_50pct_at == original_marker, "marker must not be re-stamped"
    db.add.assert_not_called()


@freeze_time(_FROZEN_TIME)
def test_warn_does_not_fire_below_50pct(tmp_path: Path) -> None:
    """Below 50% → no warn even when marker is NULL."""
    run = _make_run(started_seconds_ago=200, timeout_secs=600, warned_50pct_at=None)
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))

    assert run.warned_50pct_at is None
    db.add.assert_not_called()


@freeze_time(_FROZEN_TIME)
def test_warn_fires_only_once_across_two_poll_cycles(tmp_path: Path) -> None:
    """Two consecutive poll cycles → exactly one warn event total (idempotent)."""
    run = _make_run(started_seconds_ago=320, timeout_secs=600, warned_50pct_at=None)
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))
        # Marker is now set; next poll cycle, even with more elapsed time, should not re-emit.
        monitor_running_steps(db, "proj", _config(tmp_path))

    # add() called exactly once across both cycles
    assert db.add.call_count == 1
    event = db.add.call_args_list[0][0][0]
    assert event.event_type == "step_warning_50pct"


# ---------------------------------------------------------------------------
# AC5 — timeout shadows the warn in the same poll cycle
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_timeout_branch_shadows_warn_in_same_cycle(tmp_path: Path) -> None:
    """Past 100% timeout: only step_timeout fires, not step_warning_50pct."""
    run = _make_run(started_seconds_ago=700, timeout_secs=600, warned_50pct_at=None)
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))

    assert run.status == RunStatus.timeout, "timeout branch must win"
    # Marker remains NULL — the warn branch was never reached.
    assert run.warned_50pct_at is None

    # Exactly one event was emitted, and it's the timeout one.
    db.add.assert_called_once()
    event = db.add.call_args[0][0]
    assert event.event_type == "step_timeout"


# ---------------------------------------------------------------------------
# Defensive — None timeout / None started_at don't crash
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_no_warn_when_timeout_secs_is_none(tmp_path: Path) -> None:
    run = _make_run(started_seconds_ago=320, timeout_secs=600, warned_50pct_at=None)
    run.timeout_secs = None
    db = _make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", _config(tmp_path))

    assert run.warned_50pct_at is None
    db.add.assert_not_called()
