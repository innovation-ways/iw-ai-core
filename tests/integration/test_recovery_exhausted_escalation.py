"""Integration regression tests for failed-step recovery exhaustion escalation."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


@pytest.fixture
def daemon_config(tmp_path: Path) -> DaemonConfig:
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


@pytest.fixture
def manager(
    db_session: Any,
    project_config: ProjectConfig,
    daemon_config: DaemonConfig,
) -> BatchManager:
    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id="test-proj",
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


def _seed_failed_execution_item(
    db: Any,
    *,
    failure_reason: str,
) -> tuple[WorkItem, BatchItem, WorkflowStep]:
    work_item = WorkItem(
        project_id="test-proj",
        id="I-00117",
        type=WorkItemType.Issue,
        title="Recovery exhausted regression",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(work_item)

    batch = Batch(
        project_id="test-proj",
        id="B-00117",
        status=BatchStatus.executing,
        max_parallel=1,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)

    batch_item = BatchItem(
        project_id="test-proj",
        batch_id=batch.id,
        work_item_id=work_item.id,
        execution_group=0,
        status=BatchItemStatus.executing,
    )
    db.add(batch_item)

    failed_step = WorkflowStep(
        project_id="test-proj",
        work_item_id=work_item.id,
        step_number=1,
        step_id="S01",
        agent_label="backend-impl",
        step_type=StepType.implementation,
        status=StepStatus.failed,
    )
    db.add(failed_step)
    db.flush()

    db.add_all(
        [
            StepRun(
                step_id=failed_step.id,
                run_number=1,
                status=RunStatus.failed,
                error_message="first failure",
            ),
            StepRun(
                step_id=failed_step.id,
                run_number=2,
                status=RunStatus.failed,
                error_message=failure_reason,
            ),
        ]
    )
    db.flush()
    return work_item, batch_item, failed_step


def test_exhausted_implementation_step_escalates_visibly(
    db_session: Any,
    test_project: Any,
    manager: BatchManager,
) -> None:
    work_item, batch_item, failed_step = _seed_failed_execution_item(
        db_session,
        failure_reason="Blocked: out-of-scope gate failure",
    )

    manager._check_executing_item(db_session, batch_item)  # noqa: SLF001

    db_session.refresh(work_item)
    db_session.refresh(batch_item)

    assert work_item.status == WorkItemStatus.failed
    assert batch_item.status == BatchItemStatus.failed
    assert work_item.status not in {WorkItemStatus.in_progress}

    events = (
        db_session.query(DaemonEvent)
        .filter_by(
            project_id="test-proj",
            entity_id=work_item.id,
            event_type="step_recovery_exhausted",
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].event_metadata["step_id"] == failed_step.step_id


def test_spec_mismatch_still_routes_to_its_own_handler(
    db_session: Any,
    test_project: Any,
    manager: BatchManager,
) -> None:
    work_item, batch_item, _failed_step = _seed_failed_execution_item(
        db_session,
        failure_reason="SPEC_MISMATCH: requirement explicitly out of scope",
    )

    manager._check_executing_item(db_session, batch_item)  # noqa: SLF001

    spec_events = (
        db_session.query(DaemonEvent)
        .filter_by(
            project_id="test-proj",
            entity_id=work_item.id,
            event_type="spec_mismatch_escalation",
        )
        .all()
    )
    exhausted_events = (
        db_session.query(DaemonEvent)
        .filter_by(
            project_id="test-proj",
            entity_id=work_item.id,
            event_type="step_recovery_exhausted",
        )
        .all()
    )

    assert len(spec_events) == 1
    assert len(exhausted_events) == 0
