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
    def _run(*args: Any, **kwargs: Any):
        if timeout:
            raise subprocess.TimeoutExpired("probe", kwargs.get("timeout", 1))
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=response, stderr=""
        )

    monkeypatch.setattr("orch.daemon.auto_merge_health.subprocess.run", _run)
