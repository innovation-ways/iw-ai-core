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
        """Queued job → poll() → job status leaves queued (runner's async task updates it).

        The mock indexer completes very quickly so we cannot reliably catch the
        intermediate "running" state. What we *can* assert is that the job is no
        longer "queued" — i.e. the poller actually launched a runner that
        progressed the job through the state machine.
        """
        create_items_for_project(db_session, test_project, ["WI-POLL-1"])
        db_session.flush()

        job = DocIndexJob(project_id=test_project.id, status="queued")
        db_session.add(job)
        db_session.flush()
        job_id = job.id

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)

        async def run_and_wait_for_completion() -> None:
            with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
                poller.poll()
                # Wait for any pending runner tasks to finish under the patch
                # so the embedding mock is in scope when the runner thread runs.
                pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        try:
            asyncio.run(run_and_wait_for_completion())

            db_session.expire_all()
            refreshed = db_session.get(DocIndexJob, job_id)
            assert refreshed is not None
            assert refreshed.status != "queued", (
                f"Expected status to leave 'queued', got {refreshed.status}"
            )
        finally:
            JOB_REGISTRY_DOC.pop(test_project.id, None)

    def test_concurrency_cap_only_one_runs(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Two queued jobs for same project → only one is launched per poll cycle."""
        create_items_for_project(db_session, test_project, ["WI-CAP-1", "WI-CAP-2"])
        db_session.flush()

        job1 = DocIndexJob(project_id=test_project.id, status="queued")
        job2 = DocIndexJob(project_id=test_project.id, status="queued")
        db_session.add(job1)
        db_session.add(job2)
        db_session.flush()
        job1_id = job1.id
        job2_id = job2.id

        config = type(
            "MockDaemonConfig",
            (),
            {
                "index_path": str(tmp_path / "index"),
            },
        )()

        poller = DocIndexPoller(db_session_factory, config)

        async def run_and_wait_for_completion() -> None:
            with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
                poller.poll()
                pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        try:
            asyncio.run(run_and_wait_for_completion())

            db_session.expire_all()
            r1 = db_session.get(DocIndexJob, job1_id)
            r2 = db_session.get(DocIndexJob, job2_id)
            assert r1 is not None
            assert r2 is not None
            # Exactly one of the queued jobs should have been picked up by this
            # poll cycle (concurrency cap = 1). The other remains queued for
            # the next cycle. The launched job has progressed past "queued".
            launched = [j for j in [r1, r2] if j.status != "queued"]
            still_queued = [j for j in [r1, r2] if j.status == "queued"]
            assert len(launched) == 1, (
                f"Expected 1 launched job, got {len(launched)}: "
                f"[(r1.status={r1.status}), (r2.status={r2.status})]"
            )
            assert len(still_queued) == 1, (
                f"Expected 1 still-queued job, got {len(still_queued)}: "
                f"[(r1.status={r1.status}), (r2.status={r2.status})]"
            )
        finally:
            JOB_REGISTRY_DOC.pop(test_project.id, None)


class TestDocIndexPollerSessionBoundary:
    """Regression coverage for the DetachedInstanceError that caused poll() to
    abort on every cycle until commit a82faa1 (2026-04-26). The fix materialises
    plain project_id strings inside the `with self._session_factory()` block so
    no ORM attribute is read after the session closes.

    The test uses a session_factory wrapper that mimics production's
    `orch.db.session.get_session()` semantics — commit-then-close — because that
    is what causes `expire_on_commit=True` to mark attributes as expired before
    the session closes. A bare `with sessionmaker() as db:` only calls close()
    without commit, leaves cached column values in __dict__, and would let
    `project.id` succeed on a detached instance — silently passing against the
    buggy code (false green).
    """

    def test_poll_invokes_process_project_for_each_enabled_id_without_detached_error(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Two enabled projects + one disabled → poll() calls _process_project
        once per enabled id (the disabled one is filtered) and never raises
        DetachedInstanceError on the post-session ORM access.
        """
        enabled_a = Project(
            id="proj-enabled-a",
            display_name="Enabled A",
            repo_root="/repos/a",
            config={},
            enabled=True,
        )
        enabled_b = Project(
            id="proj-enabled-b",
            display_name="Enabled B",
            repo_root="/repos/b",
            config={},
            enabled=True,
        )
        disabled = Project(
            id="proj-disabled",
            display_name="Disabled",
            repo_root="/repos/c",
            config={},
            enabled=False,
        )
        db_session.add_all([enabled_a, enabled_b, disabled])
        db_session.flush()

        @contextmanager
        def production_like_session_factory() -> Generator[Session, None, None]:
            """Mirror orch.db.session.get_session() lifecycle so attribute
            expiration on close matches production. expire_all() before close
            stands in for the production commit (which would break test
            isolation against the outer transaction this fixture owns).
            """
            session = db_session_factory()
            try:
                yield session
                session.expire_all()
            except BaseException:
                session.rollback()
                raise
            finally:
                session.close()

        config = type(
            "MockDaemonConfig",
            (),
            {"index_path": str(tmp_path / "index")},
        )()

        poller = DocIndexPoller(production_like_session_factory, config)

        seen: list[str] = []
        poller._process_project = lambda pid: seen.append(pid)  # type: ignore[method-assign]

        # The bug — if reintroduced — would raise DetachedInstanceError here on
        # the line `self._process_project(project.id)` after the session closed
        # and attributes were expired.
        poller.poll()

        assert sorted(seen) == ["proj-enabled-a", "proj-enabled-b"], (
            f"Expected _process_project to be called for both enabled projects "
            f"and only those projects, got {seen}"
        )
        assert "proj-disabled" not in seen, (
            f"Disabled project must be filtered out, but {seen} includes it"
        )
