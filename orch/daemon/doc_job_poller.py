"""DocJobPoller — daemon component for DocGenerationJob lifecycle.

Polls for queued DocGenerationJob records and launches AI agents.
Runs as part of the main daemon poll loop.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.daemon.batch_manager import _agent_subprocess_env
from orch.db.models import (
    DaemonEvent,
    DocGenerationJob,
    EditorialCategory,
    Project,
    ProjectDoc,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)

_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"
_STALL_TIMEOUT_MINUTES = 15
_PID_RACE_PROTECTION_SECONDS = 10


def _is_pid_alive(pid: int) -> bool:
    """Return True if the kernel knows about this PID.

    ``PermissionError`` means the process exists but we can't signal it — alive.
    ``ProcessLookupError`` means the process is gone — dead.
    Anything else bubbles up.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:  # noqa: F821 — subclass of OSError in Python 3
        return False
    except PermissionError:
        return True


class DocJobPoller:
    """Polls for queued DocGenerationJob records and launches AI agents."""

    MAX_CONCURRENT_JOBS_PER_PROJECT = 2

    def __init__(self, session_factory: SessionFactory, config: DaemonConfig) -> None:
        self._session_factory = session_factory
        self.config = config

    def poll(self) -> None:
        """Single poll cycle:
        1. Detect and mark stalled jobs (timeout)
        2. Detect dead subprocesses and mark them failed (~60s detection)
        3. For each project: if running_count < MAX_CONCURRENT, dequeue and launch next job
        """
        from orch.doc_service import DocService

        # Phase 1: stall / dead-subprocess detection
        with self._session_factory() as db:
            svc = DocService(db)

            # PID liveness probe — runs BEFORE the wall-clock stall sweep
            dead_jobs = self._detect_dead_subprocess_jobs(db)
            for job in dead_jobs:
                try:
                    worktree_path = None
                    project = db.get(Project, job.project_id)
                    if project is not None:
                        worktree_path = project.repo_root
                    svc.complete_doc_job(
                        job.id,
                        error="agent process exited without calling iw doc-job-done",
                        worktree_path=worktree_path,
                    )
                    logger.info(
                        "Marked dead-subprocess job %s as failed (PID %s, started at %s)",
                        job.id,
                        job.agent_pid,
                        job.started_at,
                    )
                except Exception:
                    logger.exception("Failed to mark dead-subprocess job %s as failed", job.id)

            # Wall-clock stall sweep
            stalled = svc.get_stalled_jobs(timeout_minutes=_STALL_TIMEOUT_MINUTES)
            for job in stalled:
                try:
                    svc.complete_doc_job(
                        job.id,
                        error=f"generation timeout after {_STALL_TIMEOUT_MINUTES} minutes",
                    )
                    logger.info(
                        "Marked stalled job %s as failed (started at %s)",
                        job.id,
                        job.started_at,
                    )
                except Exception:
                    logger.exception("Failed to mark stalled job %s as failed", job.id)

            db.commit()

        with self._session_factory() as db:
            projects = db.query(Project).filter(Project.enabled == True).all()  # noqa: E712

            for project in projects:
                self._process_project(project.id)

    def _detect_dead_subprocess_jobs(self, db: Session) -> list[DocGenerationJob]:
        """Return running jobs whose agent_pid no longer points at a live process.

        Skips jobs started within the last 10 seconds to avoid racing the kernel's
        fork-to-PID assignment on freshly-launched subprocesses.
        """
        from orch.db.models import JobStatus

        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=_PID_RACE_PROTECTION_SECONDS)

        jobs = (
            db.query(DocGenerationJob)
            .filter(
                DocGenerationJob.status == JobStatus.running,
                DocGenerationJob.agent_pid.isnot(None),
            )
            .all()
        )

        dead = []
        for job in jobs:
            pid: int | None = job.agent_pid
            if pid is None:
                continue
            started_at = job.started_at
            # Skip jobs that are too young — kernel may not have registered the fork yet
            if started_at is not None and started_at > cutoff:
                continue
            if not _is_pid_alive(pid):
                dead.append(job)

        return dead

    def _process_project(self, project_id: str) -> None:
        """Process queued jobs for a single project."""
        from orch.doc_service import DocService

        with self._session_factory() as db:
            svc = DocService(db)
            running_count = svc.get_running_jobs_count(project_id)

            if running_count >= self.MAX_CONCURRENT_JOBS_PER_PROJECT:
                return

            slots_available = self.MAX_CONCURRENT_JOBS_PER_PROJECT - running_count
            queued_ids = [
                (j.id, j.doc_id) for j in svc.get_queued_jobs(project_id, limit=slots_available)
            ]

        for job_id, doc_id in queued_ids:
            job = None
            doc = None
            project_cfg = None
            with self._session_factory() as db:
                job = db.get(DocGenerationJob, job_id)
                doc = db.get(ProjectDoc, doc_id) if doc_id else None
                project_cfg = db.get(Project, project_id)

                if job is None or doc is None or project_cfg is None:
                    logger.warning(
                        "Job %s references missing job/doc=%s or project=%s",
                        job_id,
                        doc_id,
                        project_id,
                    )
                    continue

                # Force-load all attributes needed outside this session, then expunge
                # so the objects remain accessible after the session closes.
                _ = (
                    job.id,
                    job.doc_id,
                    job.status,
                    job.trigger_reason,
                    job.guide_snapshot,
                    job.section_guides_snapshot,
                )
                _ = (
                    doc.doc_id,
                    doc.editorial_category,
                    doc.doc_type,
                    doc.project_id,
                )
                _ = (
                    project_cfg.id,
                    project_cfg.repo_root,
                    project_cfg.config,
                    project_cfg.display_name,
                )
                db.expunge(job)
                db.expunge(doc)
                db.expunge(project_cfg)

            try:
                self._launch_job(job, doc, project_cfg)
            except Exception:
                logger.exception(
                    "Failed to launch job %s for doc %s",
                    job_id,
                    doc_id,
                )

    def _launch_job(
        self,
        job: DocGenerationJob,
        doc: ProjectDoc,
        project: Project,
    ) -> None:
        """Select skill, build command, launch subprocess, update job with PID."""
        from orch.doc_service import DocService

        skill = self._select_skill(doc.editorial_category)

        cmd = self._build_agent_command(job, project, skill)
        worktree_path = project.repo_root

        log_dir = Path(worktree_path) / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"

        proc = subprocess.Popen(  # noqa: S602
            cmd,
            shell=True,
            cwd=worktree_path,
            stdout=log_file.open("w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_agent_subprocess_env(),
        )

        with self._session_factory() as db:
            svc = DocService(db)
            svc.start_doc_job(job.id, pid=proc.pid, skill_used=skill)
            _emit_event(
                db,
                project.id,
                "doc_job_launched",
                job.id,
                "doc_job",
                f"Doc job {job.id} launched (PID {proc.pid}, skill={skill})",
                {"doc_id": doc.doc_id, "pid": proc.pid, "skill": skill},
            )
            db.commit()

        logger.info(
            "Launched doc job %s for doc %s (PID %d, skill=%s)",
            job.id,
            doc.doc_id,
            proc.pid,
            skill,
        )

    def _select_skill(self, editorial_category: EditorialCategory) -> str:
        """Map editorial category to skill name."""
        category_str = (
            editorial_category.value
            if hasattr(editorial_category, "value")
            else str(editorial_category)
        )
        if category_str in ("guide", "compliance", "marketing", "release"):
            return "iw-doc-system"
        return "iw-doc-generator"

    def _build_agent_command(
        self,
        job: DocGenerationJob,
        project: Project,
        skill: str,
    ) -> list[str]:
        """Build the agent launch command following the project's executor pattern."""
        cli_tool = project.config.get("cli_tool", "opencode") if project.config else "opencode"

        if cli_tool == "opencode":
            cmd = f'opencode run "/{skill} doc-job {job.id}" --dangerously-skip-permissions'
        else:
            cmd = f'claude -p "/{skill} doc-job {job.id}" --permission-mode bypassPermissions'

        return [cmd]


def _emit_event(
    db: Session,
    project_id: str | None,
    event_type: str,
    entity_id: str | None,
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
