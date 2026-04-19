"""IW AI Core — Orchestration Daemon.

The daemon is a single Python process that orchestrates AI agent execution
across all registered projects. It runs as a simple polling loop:

    startup → [poll_cycle → sleep] → shutdown

Key design guarantees:
- Never crashes from a single poll failure — errors are logged and the loop continues.
- Per-project error isolation — one project's exception doesn't block others.
- Interruptible sleep — SIGTERM/SIGHUP wake the daemon immediately.
- DB is the only state — crash recovery is fully driven by DB state.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from orch.daemon.batch_manager import BatchManager
from orch.daemon.doc_job_poller import DocJobPoller
from orch.daemon.project_registry import ProjectConfig, ProjectRegistry, sync_project_to_db
from orch.db.models import DaemonEvent, StepRun, StepStatus, WorkflowStep

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


def create_session_factory(db_url: str) -> SessionFactory:
    """Create a session factory bound to the given DB URL."""
    engine = create_engine(db_url, pool_pre_ping=True)
    session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _factory() -> Generator[Session, None, None]:
        session: Session = session_cls()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    return _factory


# ---------------------------------------------------------------------------
# Event emitter helper
# ---------------------------------------------------------------------------


def emit_event(
    db: Session,
    project_id: str | None,
    event_type: str,
    entity_id: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent row and commit immediately."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.commit()


# ---------------------------------------------------------------------------
# Daemon class
# ---------------------------------------------------------------------------


class DaemonAlreadyRunning(RuntimeError):  # noqa: N818
    """Raised when a live daemon PID is found at startup."""


class Daemon:
    """The IW AI Core orchestration daemon.

    Designed for long-running use. All critical state lives in PostgreSQL.
    A crash and restart will pick up exactly where the daemon left off.
    """

    def __init__(
        self,
        config: DaemonConfig,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self.config = config
        self._running = True
        self._wake_event = threading.Event()
        self._poll_count = 0
        self._last_poll_at: datetime | None = None

        # Injected session factory (tests pass a mock; production uses DB URL)
        if session_factory is not None:
            self._session_factory: SessionFactory = session_factory
        else:
            self._session_factory = create_session_factory(config.db_url)

        # Per-project state (populated in _startup)
        self.registry = ProjectRegistry(config.projects_toml)
        self.projects: dict[str, ProjectConfig] = {}
        self.managers: dict[str, BatchManager] = {}
        self.doc_job_poller: DocJobPoller | None = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the daemon. Blocks until SIGTERM or SIGINT."""
        self._setup_signal_handlers()
        self._startup()

        while self._running:
            try:
                self._poll_cycle()
            except Exception:
                logger.exception("Unhandled error in poll cycle — continuing")
                try:
                    with self._session_factory() as db:
                        emit_event(
                            db,
                            project_id=None,
                            event_type="poll_error",
                            message=traceback.format_exc(),
                        )
                except Exception:
                    logger.exception("Failed to emit poll_error event")

            self._sleep(self.config.poll_interval)

        self._shutdown()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _startup(self) -> None:
        """Prepare the daemon for operation.

        1. PID file check/cleanup
        2. Write own PID file
        3. Connect to DB (verify connection)
        4. Load + sync projects
        5. Startup health check (orphan detection)
        6. Emit daemon_started
        """
        pid_file = Path(self.config.pid_file)
        self._check_pid_file(pid_file)
        pid_file.write_text(str(os.getpid()))
        logger.info("Daemon started (PID %d)", os.getpid())

        # Verify DB connectivity
        with self._session_factory() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Database connection verified")

        # Load projects and sync to DB
        self._load_projects()

        # Detect orphans from previous crashes
        self._startup_health_check()

        # Emit daemon_started event
        with self._session_factory() as db:
            emit_event(db, project_id=None, event_type="daemon_started")

        logger.info("Daemon startup complete — entering main loop")

    def _check_pid_file(self, pid_file: Path) -> None:
        """Check for an existing PID file. Clean up stale files; raise on live daemon."""
        if not pid_file.exists():
            return

        try:
            existing_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            logger.warning("Stale/corrupt PID file at %s — removing", pid_file)
            pid_file.unlink(missing_ok=True)
            return

        if _is_pid_alive(existing_pid):
            raise DaemonAlreadyRunning(
                f"Daemon is already running (PID {existing_pid}). "
                f"Stop it first or remove {pid_file}."
            )

        logger.warning("Stale PID file (PID %d dead) — removing and continuing", existing_pid)
        pid_file.unlink(missing_ok=True)

    def _load_projects(self) -> None:
        """Load projects.toml and sync each project to the DB."""
        self.projects = self.registry.load()
        logger.info("Loaded %d project(s) from %s", len(self.projects), self.config.projects_toml)

        self.doc_job_poller = DocJobPoller(self._session_factory, self.config)

        with self._session_factory() as db:
            for project_id, cfg in self.projects.items():
                try:
                    sync_project_to_db(db, cfg)
                    self.managers[project_id] = BatchManager(
                        project_id, cfg, self._session_factory, self.config
                    )
                    logger.info("Registered project %r (%s)", project_id, cfg.repo_root)
                except Exception:
                    logger.exception("Failed to register project %r — skipping", project_id)

    # ------------------------------------------------------------------
    # Startup health check
    # ------------------------------------------------------------------

    def _startup_health_check(self) -> None:
        """Detect and fix inconsistencies from previous daemon crashes.

        Finds step_runs with status='running' that have dead PIDs and marks
        them as failed. Also logs orphaned worktrees.

        Does NOT auto-clean worktrees — just reports them.
        """
        logger.info("Running startup health check")
        orphans_found = 0

        with self._session_factory() as db:
            # Find running step_runs across all projects
            running_runs = db.query(StepRun).filter(StepRun.status.in_(["running"])).all()

            now = datetime.now(UTC)
            for run in running_runs:
                if not _is_pid_alive(run.pid):
                    run.status = "failed"  # type: ignore[assignment]
                    run.error_message = "Daemon restarted — process was dead (orphan recovery)"
                    run.completed_at = now
                    if run.started_at is not None:
                        run.duration_secs = (now - run.started_at).total_seconds()
                    orphans_found += 1
                    logger.warning(
                        "Orphan detected: step_run id=%d PID=%s was dead — marked failed",
                        run.id,
                        run.pid,
                    )
                    # Also update parent WorkflowStep so batch_manager doesn't get stuck
                    parent = db.get(WorkflowStep, run.step_id)
                    if parent is not None and parent.status == StepStatus.in_progress:
                        parent.status = StepStatus.failed
                        parent.completed_at = now
                    emit_event(
                        db,
                        project_id=None,
                        event_type="orphan_detected",
                        message=f"Dead PID {run.pid} for step_run {run.id}",
                        metadata={"type": "dead_pid", "pid": run.pid, "step_run_id": run.id},
                    )

            db.commit()

        # Check for orphaned worktrees on disk
        for project_id, cfg in self.projects.items():
            self._check_orphaned_worktrees(project_id, cfg)

        logger.info("Startup health check complete — %d orphan(s) found", orphans_found)

    def _check_orphaned_worktrees(self, project_id: str, cfg: ProjectConfig) -> None:
        """Log any worktree directories that have no matching active batch_item."""
        worktree_base = Path(cfg.working_dir) / cfg.worktree_base
        if not worktree_base.exists():
            return

        from orch.db.models import BatchItem, BatchItemStatus  # noqa: PLC0415

        with self._session_factory() as db:
            for entry in worktree_base.iterdir():
                if not entry.is_dir():
                    continue
                item_id = entry.name
                active = (
                    db.query(BatchItem)
                    .filter(
                        BatchItem.project_id == project_id,
                        BatchItem.work_item_id == item_id,
                        BatchItem.status.in_(
                            [BatchItemStatus.setting_up, BatchItemStatus.executing]
                        ),
                    )
                    .first()
                )
                if not active:
                    logger.warning(
                        "Orphaned worktree: %s (no active batch_item for %r)", entry, item_id
                    )
                    with self._session_factory() as db2:
                        emit_event(
                            db2,
                            project_id=project_id,
                            event_type="orphan_detected",
                            entity_id=item_id,
                            message=f"Orphaned worktree: {entry}",
                            metadata={
                                "type": "orphaned_worktree",
                                "path": str(entry),
                                "item_id": item_id,
                            },
                        )

    # ------------------------------------------------------------------
    # Main poll cycle
    # ------------------------------------------------------------------

    def _poll_cycle(self) -> None:
        """One complete iteration of the daemon's work."""
        self._poll_count += 1
        self._last_poll_at = datetime.now(UTC)
        logger.debug("Poll cycle #%d", self._poll_count)

        # Phase 1: Reload project config if file changed
        self._reload_projects_if_stale()

        # Phase 2: Per-project processing (isolated — one project can't block others)
        for project_id, cfg in self.projects.items():
            if not cfg.enabled:
                continue

            manager = self.managers.get(project_id)
            if manager is None:
                continue

            try:
                manager.monitor_running_steps()
                manager.process_batches()
                manager.process_merge_queue()
                manager.check_auto_publish()
            except Exception:
                logger.exception("Error processing project %r — skipping", project_id)
                try:
                    with self._session_factory() as db:
                        emit_event(
                            db,
                            project_id=project_id,
                            event_type="project_error",
                            message=traceback.format_exc(),
                        )
                except Exception:
                    logger.exception("Failed to emit project_error event for %r", project_id)

        # Phase 3: Doc generation job polling
        if self.doc_job_poller is not None:
            try:
                self.doc_job_poller.poll()
            except Exception:
                logger.exception("Error in doc job poller — continuing")

        # Phase 4: Emit poll heartbeat so daemon status can report activity
        try:
            with self._session_factory() as db:
                emit_event(
                    db,
                    project_id=None,
                    event_type="daemon_poll",
                    metadata={"poll_count": self._poll_count},
                )
        except Exception:
            logger.exception("Failed to emit daemon_poll event")

    # ------------------------------------------------------------------
    # Project reload
    # ------------------------------------------------------------------

    def _reload_projects_if_stale(self) -> None:
        """Re-read projects.toml if the file's mtime has changed."""
        if not self.registry.is_stale():
            return

        logger.info("projects.toml changed — reloading")
        new_projects, changes = self.registry.reload()

        for project_id, change in changes.items():
            if change == "added":
                cfg = new_projects[project_id]
                self.projects[project_id] = cfg
                self.managers[project_id] = BatchManager(
                    project_id, cfg, self._session_factory, self.config
                )
                logger.info("New project discovered: %r", project_id)
                with self._session_factory() as db:
                    sync_project_to_db(db, cfg)
                    emit_event(db, project_id=project_id, event_type="project_discovered")

            elif change == "removed":
                self.projects.pop(project_id, None)
                self.managers.pop(project_id, None)
                logger.info("Project removed: %r", project_id)

            elif change == "disabled":
                if project_id in self.projects:
                    self.projects[project_id] = new_projects[project_id]
                logger.info("Project disabled: %r", project_id)
                with self._session_factory() as db:
                    emit_event(db, project_id=project_id, event_type="project_disabled")

            elif change == "enabled":
                self.projects[project_id] = new_projects[project_id]
                logger.info("Project re-enabled: %r", project_id)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        """Emit daemon_stopped, remove PID file."""
        logger.info("Daemon shutting down")
        try:
            with self._session_factory() as db:
                emit_event(db, project_id=None, event_type="daemon_stopped")
        except Exception:
            logger.exception("Failed to emit daemon_stopped event")

        pid_file = Path(self.config.pid_file)
        pid_file.unlink(missing_ok=True)
        logger.info("Daemon stopped")

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGHUP, self._handle_reload)

    def _handle_shutdown(self, signum: int, frame: object) -> None:  # noqa: ARG002
        logger.info("Signal %d received — stopping daemon", signum)
        self._running = False
        self._wake_event.set()

    def _handle_reload(self, signum: int, frame: object) -> None:  # noqa: ARG002
        logger.info("SIGHUP received — triggering project reload")
        # Force mtime check on next wake by clearing cached mtime
        self.registry._mtime = 0.0  # noqa: SLF001
        self._wake_event.set()

    # ------------------------------------------------------------------
    # Interruptible sleep
    # ------------------------------------------------------------------

    def _sleep(self, seconds: float) -> None:
        """Sleep for up to `seconds`, interruptible by signal handlers."""
        self._wake_event.wait(timeout=seconds)
        self._wake_event.clear()


# ---------------------------------------------------------------------------
# Process utility
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int | None) -> bool:
    """Check if a process is alive via kill -0. Returns False for None."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
