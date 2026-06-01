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
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session, sessionmaker

from orch.daemon.auto_merge import AutoMergeConfig
from orch.daemon.auto_merge_health import maybe_run_probe
from orch.daemon.backup_poller import BackupPoller
from orch.daemon.batch_manager import BatchManager
from orch.daemon.chat_summarization_poller import poll_chat_summarization_jobs
from orch.daemon.doc_index_poller import DocIndexPoller, recover_orphaned_doc_index_jobs
from orch.daemon.doc_job_poller import DocJobPoller
from orch.daemon.keep_alive_poller import KeepAlivePoller
from orch.daemon.project_registry import ProjectConfig, ProjectRegistry, sync_project_to_db
from orch.daemon.worktree_compose import is_alive as compose_is_alive
from orch.daemon.worktree_reaper import reap as reap_orphan_containers
from orch.db.alembic_guard import (
    check_db_at_head,
    remediation_message,
)
from orch.db.identity import check_bound_identity, get_live_instance_id, verify_instance_identity
from orch.db.models import (
    TERMINAL_BATCH_ITEM_STATUSES,
    BatchItem,
    DaemonEvent,
    StepRun,
    StepStatus,
    WorkflowStep,
)
from orch.db.session import get_session as get_shared_session
from orch.db.session import safe_create_engine
from orch.rag.config import TIER_DEFAULTS, IndexTier

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)

SKIP_ALEMBIC_GUARD = os.environ.get("IW_CORE_SKIP_ALEMBIC_GUARD", "").lower() == "true"
_last_mismatch_event_time: float = 0.0


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


def create_session_factory(db_url: str) -> SessionFactory:
    """Create a session factory bound to the given DB URL."""
    from orch.config import get_db_max_overflow, get_db_pool_size, get_db_url

    if db_url == get_db_url():
        return get_shared_session

    engine = safe_create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=get_db_pool_size(),
        max_overflow=get_db_max_overflow(),
        pool_recycle=1800,
        pool_timeout=10,
    )
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
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent row and commit immediately."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.commit()


# ---------------------------------------------------------------------------
# Alembic guard (R2)
# ---------------------------------------------------------------------------


def _alembic_guard_startup(session_factory: SessionFactory) -> None:
    """Fail-fast check at daemon startup.

    Runs after verify_instance_identity. On mismatch:
      - logs CRITICAL with remediation message
      - emits a DaemonEvent of type db_schema_mismatch
      - exits with code 2
    Skippable via IW_CORE_SKIP_ALEMBIC_GUARD=true (operator override only).
    """
    global _last_mismatch_event_time

    if SKIP_ALEMBIC_GUARD:
        if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
            logger.error("IW_CORE_SKIP_ALEMBIC_GUARD cannot be applied in agent context — refusing")
            sys.exit(2)
        logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
        return

    try:
        status = check_db_at_head()
    except Exception as exc:
        logger.critical("alembic guard check failed: %s", exc)
        sys.exit(2)

    if status.ok:
        return

    now = time.time()
    emit_guard_event = now - _last_mismatch_event_time >= 60.0

    msg = remediation_message(status)
    logger.critical("CRITICAL: %s", msg)

    if emit_guard_event:
        _last_mismatch_event_time = now
        with session_factory() as db:
            emit_event(
                db,
                project_id=None,
                event_type="db_schema_mismatch",
                message=msg,
                metadata={
                    "current_rev": status.current_rev,
                    "head_rev": status.head_rev,
                    "pending": status.pending,
                },
            )

    sys.exit(2)


# ---------------------------------------------------------------------------
# Daemon class
# ---------------------------------------------------------------------------


class DaemonAlreadyRunning(RuntimeError):  # noqa: N818
    """Raised when a live daemon PID is found at startup."""


class OrchDbIdentityChanged(RuntimeError):  # noqa: N818
    """Raised when orch DB identity no longer matches daemon startup binding."""


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
        self._last_reap_poll_count = 0
        self._identity_bootstrap_logged = False
        self._bound_instance_id: uuid.UUID | None = None
        self._identity_binding_established = False

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
        self.doc_index_poller: DocIndexPoller | None = None
        self.backup_poller: BackupPoller | None = None
        self._keep_alive_poller: KeepAlivePoller | None = None
        self._last_keep_alive_poll_count: int = 0
        # Shared Ollama LLM for chat summarization — instantiated once, reused
        self._chat_llm = _make_chat_llm()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the daemon. Blocks until SIGTERM or SIGINT."""
        self._setup_signal_handlers()
        self._startup()

        while self._running:
            try:
                self._verify_bound_identity_or_halt()
                self._poll_cycle()
            except OrchDbIdentityChanged:
                self._running = False
                raise
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

        # Verify DB instance identity
        with self._session_factory() as db:
            status = verify_instance_identity(db)
            self._bound_instance_id = get_live_instance_id(db)
            self._identity_binding_established = True
        if status.mode == "match":
            short = str(status.actual)[:8] if status.actual else "?"
            logger.info("Database identity verified (%s)", short)
        elif status.mode == "bootstrap":
            if not self._identity_bootstrap_logged:
                logger.info("DB identity bootstrap notice: %s", status.message)
                self._identity_bootstrap_logged = True
        elif status.mode in ("mismatch", "missing"):
            logger.error("DB identity check failed:\n%s", status.message)
            import sys

            sys.exit(2)

        # Alembic head guard — must be after identity check
        _alembic_guard_startup(self._session_factory)

        # Load projects and sync to DB
        self._load_projects()

        # Recover orphaned doc index jobs from any previous daemon crash
        recover_orphaned_doc_index_jobs(self._session_factory)

        # Detect orphans from previous crashes
        self._startup_health_check()

        # Reap stale/orphan containers from previous runs
        self._reap_orphan_containers()

        # Re-attach to live compose stacks for non-terminal items
        self._reattach_worktrees()

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
        self.doc_index_poller = DocIndexPoller(self._session_factory, self.config)
        self.backup_poller = BackupPoller(self._session_factory, self.config)
        self._keep_alive_poller = KeepAlivePoller()

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

    def _reap_orphan_containers(self) -> None:
        """Reap stale, orphan, and malformed worktree compose containers.

        Called at daemon startup and periodically during the poll loop.
        """
        logger.info("Running container reaper")
        try:
            with self._session_factory() as db:
                reaped = reap_orphan_containers(db)
            if reaped:
                by_class: dict[str, int] = {}
                for f in reaped:
                    by_class[f.classification] = by_class.get(f.classification, 0) + 1
                logger.info(
                    "Container reaper complete: %d reaped (%s)",
                    len(reaped),
                    ", ".join(f"{k}={v}" for k, v in by_class.items()),
                )
            else:
                logger.info("Container reaper complete: no stale/orphan containers found")
        except Exception:
            logger.exception("Container reaper failed — continuing")

    def _reattach_worktrees(self) -> None:
        """Re-attach to live compose stacks on daemon restart.

        Queries non-terminal BatchItems with worktree_compose_path set and
        checks if the compose stack is still alive. If alive, logs re-attach
        without calling up() (AC5: no duplicate phase='up' event for re-attached).
        If not alive, logs that the stack is missing and the next poll cycle's
        normal lifecycle path will handle re-creation.
        """
        try:
            with self._session_factory() as db:
                non_terminal = (
                    db.query(BatchItem)
                    .filter(
                        BatchItem.status.notin_(list(TERMINAL_BATCH_ITEM_STATUSES)),
                        BatchItem.worktree_compose_path.isnot(None),
                    )
                    .all()
                )
                if not non_terminal:
                    return

                for item in non_terminal:
                    item_id = item.id
                    item_path = item.worktree_info.get("path") if item.worktree_info else "unknown"
                    alive = compose_is_alive(str(item_id))
                    if alive:
                        logger.info(
                            "Re-attached to existing compose stack for batch_item id=%d "
                            "(worktree: %s)",
                            item_id,
                            item_path,
                        )
                    else:
                        logger.info(
                            "Compose stack missing for non-terminal batch_item id=%d "
                            "(worktree: %s); will re-setup on next poll",
                            item_id,
                            item_path,
                        )
        except Exception:
            logger.exception("Worktree re-attach failed — continuing")

    def _verify_bound_identity_or_halt(self) -> None:
        """Verify the daemon is still connected to the DB identity from startup."""
        if not self._identity_binding_established:
            return

        with self._session_factory() as db:
            bound_status = check_bound_identity(db, self._bound_instance_id)

        if bound_status.mode == "match":
            return

        details = {
            "bound_instance_id": str(bound_status.bound)
            if bound_status.bound is not None
            else None,
            "live_instance_id": str(bound_status.actual)
            if bound_status.actual is not None
            else None,
            "mode": bound_status.mode,
        }
        logger.critical(
            "CRITICAL: orch DB identity changed mid-run; bound=%s live=%s mode=%s",
            details["bound_instance_id"],
            details["live_instance_id"],
            details["mode"],
        )

        try:
            with self._session_factory() as db:
                emit_event(
                    db,
                    project_id=None,
                    event_type="db_identity_changed",
                    message=bound_status.message,
                    metadata=details,
                )
        except Exception:
            logger.exception("Failed to emit db_identity_changed event")

        raise OrchDbIdentityChanged(bound_status.message)

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
                try:
                    orch_root = Path(__file__).resolve().parent.parent.parent
                    toml_cfg, _ = AutoMergeConfig.load(
                        str(orch_root / "executor" / "auto_merge.toml")
                    )
                    with self._session_factory() as db:
                        maybe_run_probe(db, project_id, toml_cfg)
                except Exception:
                    logger.exception("Auto-merge health probe failed for %r", project_id)
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

        # Phase 4: Doc index job polling (serialised per project, MAX_CONCURRENT=1)
        if self.doc_index_poller is not None:
            try:
                self.doc_index_poller.poll()
            except Exception:
                logger.exception("Error in doc index poller — continuing")

        # Phase 5: Chat summarization job polling (rolling summary compaction)
        try:
            with self._session_factory() as db:
                poll_chat_summarization_jobs(db, llm=self._chat_llm)
        except Exception:
            logger.exception("chat_summarization poll failed")

        # Phase 6: Scheduled DB backup polling (daily window + catch-up)
        backup_poller = getattr(self, "backup_poller", None)
        if backup_poller is not None:
            try:
                backup_poller.poll()
            except Exception:
                logger.exception("Error in backup poller — continuing")

        # Phase 7: Emit poll heartbeat so daemon status can report activity
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

        # Phase 8: Periodic container reaper (every 5 poll cycles)
        if self._poll_count - self._last_reap_poll_count >= 5:
            self._last_reap_poll_count = self._poll_count
            self._reap_orphan_containers()

        # Phase 9: Keep-alive scheduler (every 6 poll cycles ≈ 60 s)
        if self._poll_count - self._last_keep_alive_poll_count >= 6:
            self._last_keep_alive_poll_count = self._poll_count
            if self._keep_alive_poller is not None:
                try:
                    self._keep_alive_poller.poll()
                except Exception:
                    logger.exception("KeepAlivePoller.poll() raised unexpectedly")

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
                self.projects[project_id] = new_projects[project_id]
                self.managers.pop(project_id, None)
                logger.info("Project disabled: %r", project_id)
                with self._session_factory() as db:
                    emit_event(db, project_id=project_id, event_type="project_disabled")

            elif change == "enabled":
                cfg = new_projects[project_id]
                self.projects[project_id] = cfg
                self.managers[project_id] = BatchManager(
                    project_id, cfg, self._session_factory, self.config
                )
                logger.info("Project re-enabled: %r", project_id)

            elif change == "changed":
                old_cfg = self.projects.get(project_id)
                new_cfg = new_projects[project_id]
                self.projects[project_id] = new_cfg
                self.managers[project_id] = BatchManager(
                    project_id, new_cfg, self._session_factory, self.config
                )
                changed_fields: list[str] = []
                if old_cfg is not None:
                    changed_fields = sorted(
                        f.name
                        for f in fields(old_cfg)
                        if getattr(old_cfg, f.name) != getattr(new_cfg, f.name)
                    )
                logger.info(
                    "Project config reloaded: %r (%d field(s) changed)",
                    project_id,
                    len(changed_fields),
                )
                with self._session_factory() as db:
                    sync_project_to_db(db, new_cfg)
                    emit_event(
                        db,
                        project_id=project_id,
                        event_type="project_config_reloaded",
                        entity_id=project_id,
                        entity_type="project",
                        message=f"Project config reloaded for {project_id}: "
                        f"{len(changed_fields)} changes",
                        metadata={
                            "project_id": project_id,
                            "changed_fields": changed_fields,
                        },
                    )

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


def _make_chat_llm() -> Any:
    """Construct a shared Ollama LLM for chat summarization.

    Uses the same model tier defaults (IndexTier.BALANCED → gemma4:26b) and
    the default ollama_url from CodeUnderstandingConfig, consistent with the
    QA, classifier, and module_gen paths. Project-level overrides would require
    a per-project LLM; the chat summarization poller uses the global default.
    """
    from llama_index.llms.ollama import Ollama

    model = TIER_DEFAULTS[IndexTier.BALANCED]["llm_model"]
    return Ollama(model=model, base_url="http://localhost:11434")
