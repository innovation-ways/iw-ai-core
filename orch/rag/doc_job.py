"""DocIndexJobRunner + JOB_REGISTRY_DOC — asyncio background job for doc indexing.

Mirrors CodeIndexJobRunner + JOB_REGISTRY from job.py for the doc indexing side.
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orch.rag.config import CodeUnderstandingConfig

from orch.db.models import DocIndexJob

JOB_REGISTRY_DOC: dict[str, DocIndexJobRunner] = {}


class JobAlreadyRunningError(Exception):
    """Raised when a doc index job is started for a project that already has one running."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"A doc index job is already running for project {project_id}")
        self.project_id = project_id


class DocIndexJobRunner:
    """Asyncio background runner that drives a DocIndexJob through queued → running →
    completed/failed.

    Mirrors CodeIndexJobRunner from job.py for the doc indexing side.

    Attributes:
        job_id: Primary key of the DocIndexJob row being executed.
        project_id: Project whose work-item docs are being indexed.
        config: Embedding model and Ollama connection settings.
        index_path: Root directory for LanceDB table storage.
    """

    def __init__(
        self,
        job_id: str,
        project_id: str,
        config: CodeUnderstandingConfig,
        index_path: str,
        *,
        db_session_factory: Any = None,
    ) -> None:
        self.job_id = job_id
        self.project_id = project_id
        self.config = config
        self.index_path = index_path
        self._db_session_factory = db_session_factory
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._cancel_requested = False

    @property
    def progress_queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._queue

    def request_cancel(self) -> None:
        """Signal the runner to cancel after the current indexing step completes."""
        self._cancel_requested = True

    async def run(self) -> None:
        """Execute the doc index job: choose full or incremental strategy and persist results."""
        from orch.rag.doc_indexer import DocIndexer

        try:
            await self._db_set_status_async(self.job_id, "running")

            indexer = DocIndexer(
                project_id=self.project_id,
                config=self.config,
                index_path=self.index_path,
                db_session_factory=self._db_session_factory,
            )

            # If a previous completed job exists for this project, do an
            # incremental re-index that uses its completed_at as the watermark
            # to skip work items unchanged since then. Otherwise the project
            # has never been indexed (or the previous run failed), so index
            # everything from scratch.
            previous_watermark = await asyncio.to_thread(indexer.get_previous_job_watermark)
            if previous_watermark is not None:
                result = await asyncio.to_thread(
                    indexer.reindex_changed,
                    None,
                    self.progress_queue,
                )
            else:
                result = await asyncio.to_thread(indexer.index_all, self.progress_queue)

            if self._cancel_requested:
                await self._handle_cancel()
                return

            await asyncio.to_thread(
                self._persist_counters,
                self.job_id,
                result.items_discovered,
                result.items_indexed,
                result.chunks_created,
                result.errors,
            )

            if result.errors:
                error_msg = result.errors[0]["error"]
                await self._db_set_status_async(
                    self.job_id, "failed", error=error_msg, completed=True
                )
                self._queue.put_nowait(
                    {"event": "progress", "phase": "error", "message": error_msg}
                )
                return

            await self._db_set_status_async(self.job_id, "completed", completed=True)
            self._queue.put_nowait({"event": "progress", "phase": "done"})

        except asyncio.CancelledError:
            await self._handle_cancel()
        except Exception as e:
            self._queue.put_nowait(
                {
                    "event": "progress",
                    "phase": "error",
                    "message": str(e),
                }
            )
            await self._db_set_status_async(self.job_id, "failed", error=str(e), completed=True)
        finally:
            JOB_REGISTRY_DOC.pop(self.project_id, None)

    async def _handle_cancel(self) -> None:
        await self._db_set_status_async(self.job_id, "cancelled", cancelled=True, completed=True)
        self._queue.put_nowait(
            {
                "event": "progress",
                "phase": "cancelled",
            }
        )

    async def _db_set_status_async(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        cancelled: bool = False,
        completed: bool = False,
    ) -> None:
        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal

        def do_update() -> None:
            from datetime import datetime as dt

            with factory() as session:
                job = session.get(DocIndexJob, job_id)
                if job is None:
                    return
                job.status = status
                if error:
                    errors = list(job.errors) if job.errors else []
                    errors.append(error)
                    job.errors = errors
                    job.error_message = error
                if cancelled:
                    errors = list(job.errors) if job.errors else []
                    errors.append("cancelled by user")
                    job.errors = errors
                now = dt.now(UTC)
                if status == "running" and job.started_at is None:
                    job.started_at = now
                if completed:
                    job.completed_at = now
                session.commit()

        await asyncio.to_thread(do_update)

    def _persist_counters(
        self,
        job_id: str,
        items_discovered: int,
        items_indexed: int,
        chunks_created: int,
        errors: list[dict[str, Any]],
    ) -> None:
        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal
        with factory() as session:
            job = session.get(DocIndexJob, job_id)
            if job is None:
                return
            job.items_discovered = items_discovered
            job.items_indexed = items_indexed
            job.chunks_created = chunks_created
            if errors:
                merged = list(job.errors) if job.errors else []
                merged.extend(errors)
                job.errors = merged
            session.commit()


def start_doc_index_job(
    job: DocIndexJob,
    *,
    config: CodeUnderstandingConfig,
    db_session_factory: Any | None = None,
    runner: DocIndexJobRunner | None = None,
) -> DocIndexJobRunner:
    """Register a DocIndexJobRunner in JOB_REGISTRY_DOC and return it.

    Args:
        job: The DocIndexJob DB row to execute.
        config: Embedding model and Ollama connection settings.
        db_session_factory: Optional session factory; defaults to SessionLocal.
        runner: Pre-constructed runner instance, used in tests to inject a mock.

    Returns:
        The registered DocIndexJobRunner ready to be awaited with runner.run().

    Raises:
        JobAlreadyRunningError: If a runner is already registered for the project.
    """
    project_id = job.project_id
    if project_id in JOB_REGISTRY_DOC:
        raise JobAlreadyRunningError(project_id)

    if runner is None:
        runner = DocIndexJobRunner(
            job_id=job.id,
            project_id=project_id,
            config=config,
            index_path=config.index_path,
            db_session_factory=db_session_factory,
        )

    JOB_REGISTRY_DOC[project_id] = runner
    return runner
