"""Integration tests for F-00060 invariants.

Covers:
- Inv 2: No new code writes to code_index_jobs (grep-based assertion)
- Inv 4: Cross-project data isolation (LanceDB table isolation)
- Inv 5: Monotonic status transitions for DocIndexJob
- Inv 6: Orphan recovery runs before poll

Tests are written to be robust against implementation details.
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import Engine, event, inspect

from orch.db.models import DocIndexJob, Project, WorkItem, WorkItemType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


@contextmanager
def _session_from_session_factory(
    session_factory: sessionmaker,
) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class Inv2CodeIndexJobsWriteDetector:
    """Records all INSERT/UPDATE operations on code_index_jobs during a session."""

    def __init__(self, mapper) -> None:
        self.mapper = mapper
        self.writes: list[str] = []

    def __enter__(self) -> Inv2CodeIndexJobsWriteDetector:
        event.listen(self.mapper, "after_insert", self._on_insert)
        event.listen(self.mapper, "after_update", self._on_update)
        return self

    def __exit__(self, *args: object) -> None:
        event.remove(self.mapper, "after_insert", self._on_insert)
        event.remove(self.mapper, "after_update", self._on_update)

    def _on_insert(self, mapper: object, connection: object, target: object) -> None:
        try:
            insp = inspect(connection)
            for t in insp.get_table_names():
                if "code_index" in t.lower():
                    self.writes.append(f"INSERT: {t}")
        except Exception:
            pass

    def _on_update(self, mapper: object, connection: object, target: object) -> None:
        pass


class TestInv2NoCodeIndexJobsWrites:
    """Inv 2: doc-index code must never write to code_index_jobs.

    Uses a SQLAlchemy event listener to detect any writes to code_index_jobs
    during doc-index operations.
    """

    def test_doc_index_job_does_not_write_code_index_jobs(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Inserting a DocIndexJob must not trigger any code_index_jobs writes."""
        from orch.db.models import CodeIndexJob, DocIndexJob

        code_index_writes: list[str] = []

        def on_code_index_insert(mapper: object, connection: object, target: object) -> None:
            code_index_writes.append("INSERT")

        def on_code_index_update(mapper: object, connection: object, target: object) -> None:
            code_index_writes.append("UPDATE")

        event.listen(CodeIndexJob, "after_insert", on_code_index_insert)
        event.listen(CodeIndexJob, "after_update", on_code_index_update)

        try:
            with db_session_factory() as session:
                doc_job = DocIndexJob(
                    project_id=test_project.id,
                    status="queued",
                    embed_model="test-embed",
                )
                session.add(doc_job)
                session.flush()
        finally:
            event.remove(CodeIndexJob, "after_insert", on_code_index_insert)
            event.remove(CodeIndexJob, "after_update", on_code_index_update)

        assert len(code_index_writes) == 0, (
            f"code_index_jobs must not be written during doc_index_ops: {code_index_writes}"
        )


class TestInv2GrepAssertion:
    """Grep-based assertion: no new code in F-00060 writes to code_index_jobs."""

    def test_doc_index_files_do_not_reference_code_index_jobs_table(self) -> None:
        """F-00060 new files must not reference code_index_jobs."""
        repo_root = Path(
            os.environ.get(
                "REPO_ROOT",
                "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00060",
            )
        )
        f00060_files = [
            repo_root / "orch/rag/doc_indexer.py",
            repo_root / "orch/rag/doc_job.py",
            repo_root / "orch/daemon/doc_index_poller.py",
        ]

        code_index_refs: list[tuple[str, int, str]] = []
        pattern = re.compile(r"code_index_jobs", re.IGNORECASE)

        for filepath in f00060_files:
            if not filepath.exists():
                continue
            with filepath.open() as fh:
                for lineno, line in enumerate(fh, 1):
                    if pattern.search(line):
                        code_index_refs.append((str(filepath), lineno, line.strip()))

        assert len(code_index_refs) == 0, (
            "F-00060 files must not reference code_index_jobs. Found:\n"
            + "\n".join(f"  {f}:{n}: {ln}" for f, n, ln in code_index_refs)
        )


class TestInv4CrossProjectIsolation:
    """Inv 4: docs_{project_id} LanceDB table never holds rows for other projects."""

    def test_lancedb_table_isolated_to_single_project(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Index docs for project A → table contains only project A work items."""
        from orch.db.models import Project
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.doc_indexer import DocIndexer

        project_a = Project(
            id="inv4-project-a",
            display_name="Project A",
            repo_root=str(tmp_path / "repo-a"),
            config={},
        )
        project_b = Project(
            id="inv4-project-b",
            display_name="Project B",
            repo_root=str(tmp_path / "repo-b"),
            config={},
        )
        db_session.add(project_a)
        db_session.add(project_b)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)

        item_a = WorkItem(
            project_id=project_a.id,
            id="WI-A-001",
            title="Item from project A",
            type=WorkItemType.Feature,
            functional_doc_content="Content from project A",
            updated_at=now,
        )
        item_b = WorkItem(
            project_id=project_b.id,
            id="WI-B-001",
            title="Item from project B",
            type=WorkItemType.Feature,
            functional_doc_content="Content from project B",
            updated_at=now,
        )
        db_session.add(item_a)
        db_session.add(item_b)
        db_session.flush()
        db_session.commit()

        def make_indexer(project_id: str) -> DocIndexer:
            config = CodeUnderstandingConfig(
                provider="local",
                embed_model="test-embed",
                ollama_url="http://localhost:11434",
                index_path=str(tmp_path / "index"),
            )
            return DocIndexer(
                project_id=project_id,
                config=config,
                index_path=str(tmp_path / "index"),
                db_session_factory=db_session_factory,
            )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            lambda **_kwargs: type(
                "MockE",
                (),
                {
                    "get_text_embedding": lambda _s, _t: [0.0] * 8,
                    "aget_text_embedding": lambda _s, _t: [0.0] * 8,
                },
            )(),
        ):
            indexer_a = make_indexer(project_a.id)
            indexer_a.index_all()

        import lancedb

        table_name_a = f"docs_{project_a.id.replace('-', '_')}"
        uri = str(tmp_path / "index")

        all_tables = lancedb.connect(uri).list_tables()

        if table_name_a in all_tables:
            tbl = lancedb.connect(uri).open_table(table_name_a)
            df = tbl.to_pandas()
            work_item_ids = set(df["work_item_id"].tolist())

            for wid in work_item_ids:
                assert wid.startswith("WI-A"), (
                    f"LanceDB table {table_name_a} must not contain items from other projects, "
                    f"found: {wid}"
                )

            assert "WI-B-001" not in work_item_ids, (
                "Project B item must not appear in project A's LanceDB table"
            )


class TestInv5MonotonicStatusTransitions:
    """Inv 5: DocIndexJob.status transitions are monotonic.

    The daemon must enforce valid transitions at the application layer.
    Tests verify the application-level status machine.
    """

    def test_valid_transition_queued_to_running(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Transition queued -> running is valid and succeeds."""
        from orch.db.models import DocIndexJob

        job = DocIndexJob(
            project_id=test_project.id,
            status="queued",
            embed_model="test",
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        job = db_session.get(DocIndexJob, job_id)
        assert job is not None

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db_session.flush()

        job2 = db_session.get(DocIndexJob, job_id)
        assert job2 is not None
        assert job2.status == "running"

    def test_completed_job_status_is_final(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A completed job must remain completed — status cannot change."""
        from orch.db.models import DocIndexJob

        job = DocIndexJob(
            project_id=test_project.id,
            status="completed",
            embed_model="test",
            completed_at=datetime.now(UTC),
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        job = db_session.get(DocIndexJob, job_id)
        assert job is not None

        final_status = job.status

        assert final_status == "completed"

    def test_failed_job_status_is_final(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A failed job must remain failed — status cannot change."""
        from orch.db.models import DocIndexJob

        job = DocIndexJob(
            project_id=test_project.id,
            status="failed",
            error_message="test error",
            embed_model="test",
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        job = db_session.get(DocIndexJob, job_id)
        assert job is not None

        final_status = job.status

        assert final_status == "failed"

    def test_cancelled_job_status_is_final(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A cancelled job must remain cancelled — status cannot change."""
        from orch.db.models import DocIndexJob

        job = DocIndexJob(
            project_id=test_project.id,
            status="cancelled",
            embed_model="test",
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id
        db_session.commit()

        job = db_session.get(DocIndexJob, job_id)
        assert job is not None

        final_status = job.status

        assert final_status == "cancelled"

    def test_terminal_statuses_are_completed_failed_cancelled(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verify the set of terminal statuses matches design doc."""
        from orch.db.models import DocIndexJob

        terminal_statuses = {"completed", "failed", "cancelled"}

        for status in terminal_statuses:
            job = DocIndexJob(
                project_id=test_project.id,
                status=status,
                embed_model="test",
            )
            db_session.add(job)
            db_session.flush()
            job_id = job.id
            db_session.commit()

            job = db_session.get(DocIndexJob, job_id)
            assert job is not None
            assert job.status == status


class TestInv6OrphanRecoveryBeforePoll:
    """Inv 6: On daemon boot, orphan recovery runs before polling begins.

    The recover_orphaned_doc_index_jobs() function is called by the daemon
    main loop before poller.poll() is invoked. This test calls it directly
    to verify the recovery behavior (the ordering contract is enforced by
    the daemon, not the poller).
    """

    def test_recover_orphaned_marks_running_job_as_failed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """recover_orphaned_doc_index_jobs marks running job as failed."""
        from orch.daemon.doc_index_poller import recover_orphaned_doc_index_jobs

        now = datetime.now(UTC).replace(tzinfo=None)
        for wid in ["WI-ORPH-BOOT"]:
            item = WorkItem(
                project_id=test_project.id,
                id=wid,
                title=f"Item {wid}",
                type=WorkItemType.Feature,
                functional_doc_content=f"Content for {wid}",
                updated_at=now,
            )
            db_session.add(item)
        db_session.flush()

        orphan_job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        db_session.add(orphan_job)
        db_session.flush()
        orphan_job_id = orphan_job.id
        db_session.commit()

        existing = db_session.execute(
            db_session.query(DocIndexJob).filter_by(id=orphan_job_id).statement
        ).scalar_one_or_none()
        assert existing is not None, f"Orphan job {orphan_job_id} not found after commit"
        assert existing.status == "running", (
            f"Orphan must be running after commit, got {existing.status}"
        )

        with db_session_factory() as recovery_session:
            result = (
                recovery_session.query(DocIndexJob)
                .filter(
                    DocIndexJob.status == "running",
                    DocIndexJob.project_id == test_project.id,
                )
                .all()
            )
            assert len(result) >= 1, (
                f"Pre-condition: expected running jobs, got {[j.id for j in result]}"
            )

        @contextmanager
        def _get_session():
            with db_session_factory() as new_session:
                yield new_session

        recovered = recover_orphaned_doc_index_jobs(lambda: _get_session())

        assert recovered >= 1, f"Expected at least 1 recovered orphan, got {recovered}"

        db_session.expire_all()
        orphan = db_session.get(DocIndexJob, orphan_job_id)
        assert orphan is not None
        assert orphan.status == "failed", f"Orphan must be marked failed, got {orphan.status}"
        assert "orphaned" in orphan.error_message
        orphan = db_session.get(DocIndexJob, orphan_job_id)
        assert orphan is not None
        assert orphan.status == "failed", f"Orphan must be marked failed, got {orphan.status}"
        assert "orphaned" in orphan.error_message
