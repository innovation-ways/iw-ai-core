"""DocIndexPoller — daemon component for DocIndexJob lifecycle.

Polls for queued DocIndexJob records and launches DocIndexJobRunner instances.
Runs as part of the main daemon poll loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orch.db.models import (
    DaemonEvent,
    DocIndexJob,
    Project,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)


class DocIndexPoller:
    """Polls for queued DocIndexJob records and launches asyncio runners."""

    MAX_CONCURRENT_JOBS_PER_PROJECT = 1

    STALL_TIMEOUT_SECONDS = 600

    def __init__(self, session_factory: SessionFactory, config: DaemonConfig) -> None:
        self._session_factory = session_factory
        self.config = config

    def poll(self) -> None:
        """Single poll cycle:
        1. Detect and mark stalled jobs (timeout)
        2. For each project: if running_count < MAX_CONCURRENT, dequeue and launch next job
        """
        self._mark_stalled_jobs()

        with self._session_factory() as db:
            projects = db.query(Project).filter(Project.enabled == True).all()  # noqa: E712

        for project in projects:
            self._process_project(project.id)

    def _mark_stalled_jobs(self) -> None:
        with self._session_factory() as db:
            cutoff = datetime.now(UTC).timestamp() - self.STALL_TIMEOUT_SECONDS
            cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)

            stalled = (
                db.query(DocIndexJob)
                .filter(
                    DocIndexJob.status == "running",
                    DocIndexJob.started_at < cutoff_dt,
                )
                .all()
            )

            for job in stalled:
                job.status = "failed"
                job.error_message = "stalled (exceeded 10 min)"
                job.completed_at = datetime.now(UTC)
                logger.info(
                    "Marked stalled doc index job %s as failed (started at %s)",
                    job.id,
                    job.started_at,
                )

            if stalled:
                db.commit()

    def _process_project(self, project_id: str) -> None:
        """Process queued jobs for a single project."""
        job_row = None
        project_cfg = None

        with self._session_factory() as db:
            running_count = (
                db.query(DocIndexJob)
                .filter(
                    DocIndexJob.project_id == project_id,
                    DocIndexJob.status == "running",
                )
                .count()
            )

            if running_count >= self.MAX_CONCURRENT_JOBS_PER_PROJECT:
                return

            job_row = (
                db.query(DocIndexJob)
                .filter(
                    DocIndexJob.project_id == project_id,
                    DocIndexJob.status == "queued",
                )
                .order_by(DocIndexJob.triggered_at.asc())
                .first()
            )

            if job_row is None:
                return

            project_cfg = db.get(Project, project_id)

            if project_cfg is None:
                logger.warning(
                    "DocIndexJob %s references missing project %s",
                    job_row.id,
                    project_id,
                )
                return

            _ = (
                job_row.id,
                job_row.project_id,
                job_row.status,
                job_row.triggered_at,
            )
            _ = (
                project_cfg.id,
                project_cfg.repo_root,
                project_cfg.config,
                project_cfg.display_name,
            )
            db.expunge(job_row)
            db.expunge(project_cfg)

        if job_row is not None and project_cfg is not None:
            try:
                self._launch_job(job_row, project_cfg)
            except Exception:
                logger.exception(
                    "Failed to launch doc index job %s for project %s",
                    job_row.id,
                    project_id,
                )

    def _launch_job(self, job: DocIndexJob, project: Project) -> None:
        """Instantiate DocIndexJobRunner, register in JOB_REGISTRY_DOC, spawn async task."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.doc_job import (
            DocIndexJobRunner,
            JobAlreadyRunningError,
            start_doc_index_job,
        )

        project_config: dict[str, Any] = project.config or {}
        code_config = project_config.get("code_understanding", {})

        config = CodeUnderstandingConfig(
            provider=code_config.get("provider", "local"),
            llm_model=code_config.get("llm_model"),
            embed_model=code_config.get("embed_model"),
            index_tier=code_config.get("index_tier", "balanced"),
            ollama_url=code_config.get("ollama_url", "http://localhost:11434"),
            index_path=self.config.index_path,
        )

        try:
            runner = DocIndexJobRunner(
                job_id=job.id,
                project_id=project.id,
                config=config,
                index_path=config.index_path,
                db_session_factory=self._session_factory,
            )
            start_doc_index_job(job, config=config, runner=runner)
        except JobAlreadyRunningError:
            logger.warning(
                "Doc index job for project %s is already running — skipping job %s",
                project.id,
                job.id,
            )
            return

        asyncio.create_task(runner.run())

        with self._session_factory() as db:
            _emit_event(
                db,
                project.id,
                "doc_index_job_launched",
                job.id,
                "doc_index_job",
                f"Doc index job {job.id} launched for project {project.id}",
                {"project_id": project.id},
            )
            db.commit()

        logger.info(
            "Launched doc index job %s for project %s",
            job.id,
            project.id,
        )


def _emit_event(
    db: Session,
    project_id: str | None,
    event_type: str,
    entity_id: str | None = None,
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent row (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)


def recover_orphaned_doc_index_jobs(session_factory: SessionFactory) -> int:
    """Mark all running DocIndexJob records as failed (orphaned by daemon restart).

    Must be called before the main poll loop begins to prevent colliding with
    stale 'running' rows from a previous daemon crash.

    Returns the number of jobs recovered.
    """
    recovered = 0
    with session_factory() as db:
        now = datetime.now(UTC)
        result = db.query(DocIndexJob).filter(DocIndexJob.status == "running").all()
        for job in result:
            job.status = "failed"
            job.error_message = "orphaned by daemon restart"
            job.completed_at = now
            recovered += 1

        if recovered > 0:
            db.commit()

    if recovered:
        logger.warning(
            "Orphan recovery: marked %d doc index job(s) as failed",
            recovered,
        )

    return recovered
