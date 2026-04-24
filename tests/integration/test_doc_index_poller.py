"""Integration tests for DocIndexPoller (orch/daemon/doc_index_poller.py).

Mirrors test_doc_job_routes.py for the doc index job side.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

from orch.daemon.doc_index_poller import DocIndexPoller, recover_orphaned_doc_index_jobs
from orch.db.models import DocIndexJob, Project, WorkItem, WorkItemType
from orch.rag.doc_job import JOB_REGISTRY_DOC

MOCK_EMBED_MODEL = "test-embed-model"


def mock_embed(text: str) -> list[float]:
    vec = [0.0] * 8
    h = sum(text.encode()[:4])
    vec[h % 8] = 0.5 + (h % 10) * 0.05
    return vec


class MockOllamaEmbedding:
    model_name = MOCK_EMBED_MODEL

    def __init__(self, **kwargs: object) -> None:
        pass

    def get_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)


def create_items_for_project(
    session: Session,
    project: Project,
    item_ids: list[str],
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    for wid in item_ids:
        item = WorkItem(
            project_id=project.id,
            id=wid,
            title=f"Item {wid}",
            type=WorkItemType.Feature,
            functional_doc_content=f"Functional doc content for {wid}.",
            updated_at=now,
        )
        session.add(item)
    session.flush()


@contextmanager
def _session_from_session_factory(
    session_factory: sessionmaker,
) -> Generator[Session, None, None]:
    """Wrap a sessionmaker as a context manager yielding the session directly."""
    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


class TestDocIndexOrphanRecovery:
    def test_recover_orphaned_marks_running_as_failed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
    ) -> None:
        """Pre-seed a running job → recovery marks it failed with 'orphaned by daemon restart'."""
        create_items_for_project(db_session, test_project, ["WI-ORPH-1"])
        db_session.flush()

        job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            started_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        recovered = recover_orphaned_doc_index_jobs(
            lambda: _session_from_session_factory(db_session_factory)
        )
        assert recovered == 1

        refreshed_job = db_session.get(DocIndexJob, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status == "failed"
        assert "orphaned by daemon restart" in refreshed_job.error_message
        assert refreshed_job.completed_at is not None

    def test_recovery_idempotent(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
    ) -> None:
        """Call recovery twice → second call changes nothing."""
        create_items_for_project(db_session, test_project, ["WI-IDEM-1"])
        db_session.flush()

        job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            started_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        recovered1 = recover_orphaned_doc_index_jobs(
            lambda: _session_from_session_factory(db_session_factory)
        )
        assert recovered1 == 1

        refreshed_job = db_session.get(DocIndexJob, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status == "failed"

        recovered2 = recover_orphaned_doc_index_jobs(
            lambda: _session_from_session_factory(db_session_factory)
        )
        assert recovered2 == 0

        refreshed_job2 = db_session.get(DocIndexJob, job_id)
        assert refreshed_job2 is not None
        assert refreshed_job2.status == "failed"
        assert refreshed_job2.error_message == "orphaned by daemon restart"

    def test_recovery_only_affects_running(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
    ) -> None:
        """Recovery only touches 'running' jobs — queued/completed/failed are untouched."""
        create_items_for_project(db_session, test_project, ["WI-ONLY-1"])
        db_session.flush()

        job_queued = DocIndexJob(project_id=test_project.id, status="queued")
        job_completed = DocIndexJob(project_id=test_project.id, status="completed")
        db_session.add(job_queued)
        db_session.add(job_completed)
        db_session.flush()
        job_q_id = job_queued.id
        job_c_id = job_completed.id
        db_session.commit()

        recovered = recover_orphaned_doc_index_jobs(
            lambda: _session_from_session_factory(db_session_factory)
        )
        assert recovered == 0

        rq = db_session.get(DocIndexJob, job_q_id)
        rc = db_session.get(DocIndexJob, job_c_id)
        assert rq is not None
        assert rq.status == "queued"
        assert rc is not None
        assert rc.status == "completed"


class TestDocIndexPollerStallDetection:
    def test_stalled_job_marked_failed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Running job exceeding stall timeout → marked failed with 'stalled' message."""
        create_items_for_project(db_session, test_project, ["WI-STALL-1"])
        db_session.flush()

        old_time = datetime.now(UTC) - timedelta(seconds=600 + 10)
        job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            started_at=old_time,
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)
        poller.poll()

        refreshed_job = db_session.get(DocIndexJob, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status == "failed", (
            f"Expected status=failed, got {refreshed_job.status}"
        )
        assert "stalled" in refreshed_job.error_message
        assert refreshed_job.completed_at is not None

    def test_non_stalled_running_job_not_marked_failed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """A running job with recent started_at is NOT marked failed."""
        create_items_for_project(db_session, test_project, ["WI-FRESH-1"])
        db_session.flush()

        job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            started_at=datetime.now(UTC),
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)
        poller.poll()

        refreshed_job = db_session.get(DocIndexJob, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status == "running"


class TestDocIndexPollerLaunch:
    def test_poll_launches_job_sets_status_to_running(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Queued job → poll() → job status becomes running (runner's async task updates it)."""
        create_items_for_project(db_session, test_project, ["WI-POLL-1"])
        db_session.flush()

        job = DocIndexJob(project_id=test_project.id, status="queued")
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)

        async def run_and_check() -> None:
            with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
                poller.poll()
            await asyncio.sleep(1.0)

        asyncio.run(run_and_check())

        refreshed = db_session.get(DocIndexJob, job_id)
        assert refreshed is not None
        assert refreshed.status == "running", f"Expected running, got {refreshed.status}"
        if test_project.id in JOB_REGISTRY_DOC:
            JOB_REGISTRY_DOC.pop(test_project.id)

    def test_concurrency_cap_only_one_runs(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Two queued jobs for same project → only one transitions to running."""
        create_items_for_project(db_session, test_project, ["WI-CAP-1", "WI-CAP-2"])
        db_session.flush()

        job1 = DocIndexJob(project_id=test_project.id, status="queued")
        job2 = DocIndexJob(project_id=test_project.id, status="queued")
        db_session.add(job1)
        db_session.add(job2)
        db_session.flush()
        job1_id = job1.id
        job2_id = job2.id
        db_session.commit()

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)

        async def run_and_check() -> None:
            with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
                poller.poll()
            await asyncio.sleep(1.0)

        asyncio.run(run_and_check())

        r1 = db_session.get(DocIndexJob, job1_id)
        r2 = db_session.get(DocIndexJob, job2_id)
        assert r1 is not None
        assert r2 is not None
        running = [j for j in [r1, r2] if j.status == "running"]
        assert len(running) == 1, (
            f"Expected 1 running job, got {len(running)}: "
            f"[(r1.status={r1.status}), (r2.status={r2.status})]"
        )
        if test_project.id in JOB_REGISTRY_DOC:
            JOB_REGISTRY_DOC.pop(test_project.id)
