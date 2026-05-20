"""Unit tests for CR-00065 session-file resolution in step_monitor."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest


class _FakeStepRun:
    def __init__(
        self,
        *,
        cli_tool: str = "pi",
        worktree_path: str | None = None,
        session_file: str | None = None,
        started_at: datetime | None = None,
        step_id: int = 1,
    ) -> None:
        self.cli_tool = cli_tool
        self.worktree_path = worktree_path
        self.session_file = session_file
        self.started_at = started_at
        self.id = 1
        self.step_id = step_id


class _FakeDB:
    """Minimal no-op DB session stand-in (we only write attrs on the run)."""


# ---------------------------------------------------------------------------
# Helpers that import the real module functions (patched by monkeypatch below)
# ---------------------------------------------------------------------------


def _call_resolve(run: _FakeStepRun) -> str | None:
    """Call the module-level _resolve_pi_session_file after patch."""
    from orch.daemon import step_monitor as sm

    return sm._resolve_pi_session_file(run)


def _call_maybe_resolve(
    run: _FakeStepRun,
    now: datetime,
) -> None:
    """Call the module-level _maybe_resolve_pi_session_file after patch."""
    from orch.daemon import step_monitor as sm

    return sm._maybe_resolve_pi_session_file(_FakeDB(), run, now)


# ---------------------------------------------------------------------------
# _resolve_pi_session_file
# ---------------------------------------------------------------------------


def test_resolve_pi_returns_none_for_non_pi_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli_tool != 'pi' → always returns None."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    run = _FakeStepRun(
        cli_tool="claude",
        worktree_path="/home/user/proj/CR-00065",
        started_at=datetime.now(UTC),
    )
    assert _call_resolve(run) is None


def test_resolve_pi_returns_none_when_worktree_path_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """worktree_path IS NULL → returns None."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    run = _FakeStepRun(cli_tool="pi", worktree_path=None, started_at=datetime.now(UTC))
    assert _call_resolve(run) is None


def test_resolve_pi_returns_none_when_session_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """~/.pi/agent/sessions/{slug} does not exist → returns None."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/proj/CR-00065",
        started_at=datetime.now(UTC),
    )
    assert _call_resolve(run) is None


def test_resolve_pi_returns_most_recent_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multiple .jsonl files → the most recently modified one is returned.

    We use started_at=None so the mtime filter is skipped (all files qualify).
    """
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    sessions_root.mkdir(parents=True)
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    # Slug for /home/user/CR-00065 → --home-user-CR-00065--
    slug_dir = sessions_root / "--home-user-CR-00065--"
    slug_dir.mkdir()

    old_file = slug_dir / "old.jsonl"
    old_file.write_text(json.dumps({"type": "compaction"}) + "\n")

    time.sleep(0.05)

    new_file = slug_dir / "new.jsonl"
    new_file.write_text(
        json.dumps({"type": "message", "message": {"role": "assistant", "content": []}}) + "\n"
    )

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/CR-00065",
        started_at=None,  # skip mtime filter
    )
    result = _call_resolve(run)
    assert result == str(new_file)


def test_resolve_pi_filters_jsonl_older_than_started_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files with mtime < started_at are excluded from the candidate set.

    The test creates a session file well before ``started_at`` is captured,
    so the file's mtime is strictly less than ``started_at``. The function
    should return ``None`` because no qualifying file exists.
    """
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    sessions_root.mkdir(parents=True)
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    slug_dir = sessions_root / "--home-user-CR-00065--"
    slug_dir.mkdir()

    # Write the file first (old), then capture started_at after it.
    # This guarantees mtime(old_file) < started_at.
    old_file = slug_dir / "old.jsonl"
    old_file.write_text(json.dumps({"type": "compaction"}) + "\n")
    time.sleep(0.05)

    started_at = datetime.now(UTC)

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/CR-00065",
        started_at=started_at,
    )

    result = _call_resolve(run)
    # File is older than started_at → no qualifying files → None
    assert result is None


# ---------------------------------------------------------------------------
# _maybe_resolve_pi_session_file — integration with DB write
# ---------------------------------------------------------------------------


def test_maybe_resolve_writes_session_file_to_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On success the session path is written to run.session_file."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    sessions_root.mkdir(parents=True)
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    slug_dir = sessions_root / "--home-user-CR-00065--"
    slug_dir.mkdir()

    # Capture started_at BEFORE writing the file (step started before any session)
    started_at = datetime.now(UTC)
    time.sleep(0.05)
    session_file = slug_dir / "session.jsonl"
    session_file.write_text(json.dumps({"type": "compaction"}) + "\n")

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/CR-00065",
        session_file=None,
        started_at=started_at,
    )
    _call_maybe_resolve(run, datetime.now(UTC))

    assert run.session_file == str(session_file)


def test_maybe_resolve_does_not_overwrite_existing_session_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If session_file is already set, the function does not change it."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    sessions_root.mkdir(parents=True)
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/CR-00065",
        session_file="/already/set/session.jsonl",  # pre-existing
        started_at=datetime.now(UTC),
    )
    _call_maybe_resolve(run, datetime.now(UTC))

    # Must remain unchanged
    assert run.session_file == "/already/set/session.jsonl"


def test_maybe_resolve_swallows_exceptions_from_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any exception from _resolve_pi_session_file is caught and logged (non-fatal)."""
    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    sessions_root.mkdir(parents=True)
    monkeypatch.setattr("orch.daemon.step_monitor._PI_SESSIONS_DIR", sessions_root)

    run = _FakeStepRun(
        cli_tool="pi",
        worktree_path="/home/user/CR-00065",
        session_file=None,
        started_at=datetime.now(UTC),
    )

    # Simulate _resolve_pi_session_file raising
    def raise_on_resolve(*args, **kwargs):
        raise RuntimeError("simulated filesystem error")

    monkeypatch.setattr(
        "orch.daemon.step_monitor._resolve_pi_session_file",
        raise_on_resolve,
    )

    # Must NOT raise
    _call_maybe_resolve(run, datetime.now(UTC))
    # session_file remains None (no path found due to exception)
    assert run.session_file is None
