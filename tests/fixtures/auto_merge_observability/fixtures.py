"""Test fixture helpers for auto-merge observability scenarios (F-00084)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any

from orch.db.models import DaemonEvent


def seeded_events_factory(
    db,
    project_id: str,
    *,
    attempts: int = 3,
    resolved: int = 3,
    failed: int = 0,
    skipped: int = 0,
    health_probes: int = 0,
) -> list[DaemonEvent]:
    """Insert a configurable mix of auto-merge DaemonEvent rows and return them.

    Args:
        db: SQLAlchemy session used to add and flush the rows.
        project_id: The project ID to associate with each event.
        attempts: Number of ``merge_auto_resolution_attempted`` events to create.
        resolved: Number of ``merge_auto_resolved`` events (with LLM call metadata).
        failed: Number of ``merge_auto_resolution_failed`` events.
        skipped: Number of ``merge_auto_resolution_skipped`` events.
        health_probes: Number of ``auto_merge_health_probe`` events.

    Returns:
        List of all created DaemonEvent instances after flush.
    """
    rows: list[DaemonEvent] = []
    for _ in range(attempts):
        rows.append(
            DaemonEvent(
                project_id=project_id,
                event_type="merge_auto_resolution_attempted",
                entity_id="W",
                entity_type="work_item",
                message="attempt",
                event_metadata={"phase": 1, "conflict_files": ["a.py"]},
            )
        )
    for i in range(resolved):
        rows.append(
            DaemonEvent(
                project_id=project_id,
                event_type="merge_auto_resolved",
                entity_id="W",
                entity_type="work_item",
                message="resolved",
                event_metadata={
                    "llm_calls": [
                        {
                            "model": "openai/gpt-5.3-codex",
                            "input_tokens": 10 + i,
                            "output_tokens": 20 + i,
                            "file_path": "a.py",
                            "proposed_content": "x",
                        }
                    ]
                },
            )
        )
    for _ in range(failed):
        rows.append(
            DaemonEvent(
                project_id=project_id,
                event_type="merge_auto_resolution_failed",
                entity_id="W",
                entity_type="work_item",
                message="failed",
                event_metadata={"error": "x"},
            )
        )
    for _ in range(skipped):
        rows.append(
            DaemonEvent(
                project_id=project_id,
                event_type="merge_auto_resolution_skipped",
                entity_id="W",
                entity_type="work_item",
                message="skipped",
                event_metadata={"reason": "refuse_list"},
            )
        )
    for i in range(health_probes):
        rows.append(
            DaemonEvent(
                project_id=project_id,
                event_type="auto_merge_health_probe",
                entity_id=None,
                entity_type=None,
                message=None,
                event_metadata={"runtime_reachable": i == 0},
                created_at=datetime.now(UTC),
            )
        )
    for row in rows:
        db.add(row)
    db.flush()
    return rows


def mock_git_show(monkeypatch, file_contents: dict[str, str | None]) -> None:
    """Monkeypatch ``dashboard.routers.auto_merge_ui.subprocess.run`` to return synthetic file
    content.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        file_contents: Mapping from file path to content string.  A ``None``
            value simulates a missing file (non-zero returncode).
    """

    def _run(args: list[str], **kwargs: Any):
        ref = args[-1]
        file_path = ref.split("main:", 1)[1]
        content = file_contents.get(file_path)
        if content is None:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="missing")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=content, stderr="")

    monkeypatch.setattr("dashboard.routers.auto_merge_ui.subprocess.run", _run)


def fake_executor_subprocess(
    monkeypatch, *, response: str = "OK", returncode: int = 0, timeout: bool = False
) -> None:
    """Monkeypatch ``orch.daemon.auto_merge_health.subprocess.run`` with a controllable stub.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        response: stdout string returned by the stub process.
        returncode: Exit code returned by the stub process.
        timeout: When ``True``, raises ``subprocess.TimeoutExpired`` instead of returning.
    """

    def _run(*args: Any, **kwargs: Any):
        if timeout:
            raise subprocess.TimeoutExpired("probe", kwargs.get("timeout", 1))
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=response, stderr=""
        )

    monkeypatch.setattr("orch.daemon.auto_merge_health.subprocess.run", _run)
