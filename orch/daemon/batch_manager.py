"""BatchManager — per-project batch orchestration.

Handles the full lifecycle of batch execution:
  approved → executing → (item setup → step launch → step completion) → merge queue
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shlex
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from orch.daemon import scope_overlap, worktree_compose
from orch.daemon.scope_overlap import filter_blocked_by_ignores
from orch.db.alembic_guard import check_db_at_head, remediation_message
from orch.db.models import (
    TERMINAL_BATCH_ITEM_STATUSES,
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchOverlapIgnore,
    BatchStatus,
    DaemonEvent,
    QvBaseline,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)

# Executor scripts: iw-ai-core/executor/
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"

# C3: default timeout (seconds) for items stuck in setting_up
_DEFAULT_SETTING_UP_THRESHOLD_SECS = 600

# H1: terminal statuses that block downstream execution groups (merged is success, not a failure)
# CR-00028: merge_failed, migration_invalid, and migration_rebase_failed are excluded because
# they are operator-recoverable — the operator can retry via restart-merge or abandon via
# abandon-merge.
# CR-00096: setup_failed is excluded because it is an infrastructure failure (worktree setup,
# DB migration mismatch, port conflict) — not an implementation failure. The worktree never
# started so no implementation output was produced; downstream items cannot have a code
# dependency on it. The item can be retried after the environment is corrected (iw item-retry).
_BLOCKING_TERMINAL_STATUSES = TERMINAL_BATCH_ITEM_STATUSES - {
    BatchItemStatus.merged,
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
    BatchItemStatus.setup_failed,
}


class WorktreeSetupError(RuntimeError):
    """Raised when the worktree setup script exits non-zero."""


class BatchManager:
    """Manages batch execution for a single project.

    Instantiated once per project by the Daemon. Holds no critical state —
    all operational state lives in PostgreSQL.
    """

    def __init__(
        self,
        project_id: str,
        project_config: ProjectConfig,
        session_factory: Any,
        config: DaemonConfig,
    ) -> None:
        self.project_id = project_id
        self.project_config = project_config
        self._session_factory = session_factory
        self.config = config

    # ------------------------------------------------------------------
    # Public methods (called by Daemon._poll_cycle)
    # ------------------------------------------------------------------

    def monitor_running_steps(self) -> None:
        """Check health of all running step_runs and active fix cycles."""
        from orch.daemon import fix_cycle, step_monitor  # noqa: PLC0415

        with self._session_factory() as db:
            step_monitor.monitor_running_steps(
                db,
                self.project_id,
                self.config,
                self.project_config,
            )
            fix_cycle.check_active_fix_cycles(
                db,
                self.project_id,
                self.project_config,
                self.config,
            )

    def process_batches(self) -> None:
        """Find approved/executing batches and advance their items."""
        with self._session_factory() as db:
            # C3: Recover items that are stuck in setting_up due to a prior daemon crash.
            # Must run BEFORE the launch loop so the stuck items are cleared first.
            try:
                self._timeout_stuck_setting_up_items(db)
            except Exception:
                logger.exception("[%s] Error in _timeout_stuck_setting_up_items", self.project_id)

            batches = (
                db.query(Batch)
                .filter(
                    Batch.project_id == self.project_id,
                    Batch.status.in_([BatchStatus.approved, BatchStatus.executing]),
                )
                .all()
            )

            for batch in batches:
                if batch.status == BatchStatus.approved:
                    batch.status = BatchStatus.executing
                    db.commit()
                    _emit_event(
                        db,
                        self.project_id,
                        "batch_executing",
                        batch.id,
                        "batch",
                        f"Batch {batch.id} now executing",
                    )

                try:
                    self._process_batch(db, batch)
                except Exception:
                    logger.exception("[%s] Error processing batch %s", self.project_id, batch.id)

    def process_merge_queue(self) -> None:
        """Squash-merge completed batch items to main, one at a time."""
        from orch.daemon import merge_queue  # noqa: PLC0415

        with self._session_factory() as db:
            merge_queue.process_merge_queue(db, self.project_id, self.project_config, self.config)

    def check_auto_publish(self) -> None:
        """Push to origin for completed batches with auto_publish=true.

        Step 09 implementation.
        """
        logger.debug("[%s] check_auto_publish (stub)", self.project_id)

    # ------------------------------------------------------------------
    # C3: stuck setting_up recovery
    # ------------------------------------------------------------------

    def _timeout_stuck_setting_up_items(self, db: Session) -> None:
        """Transition BatchItems stuck in setting_up past the threshold to setup_failed.

        When the daemon crashes between worktree_setup.sh completion and
        worktree_compose.up() success, a BatchItem may be left in 'setting_up'
        with worktree_compose_path=NULL.  _reattach_worktrees only re-attaches
        items where worktree_compose_path IS NOT NULL, so without this recovery
        method those items would be stuck forever.

        Timing heuristic (in order of preference):
        1. item.started_at (set when transitioning to 'executing') — but items
           that never reached 'executing' will have NULL here.
        2. Earliest daemon_event of type 'item_setup_started' for the item.
        3. If neither exists → skip the item (safe default: don't false-positive).
        """
        from sqlalchemy import text  # noqa: PLC0415

        threshold_secs = getattr(
            self.config, "setting_up_threshold", _DEFAULT_SETTING_UP_THRESHOLD_SECS
        )
        now = datetime.now(UTC)

        stuck_items = (
            db.query(BatchItem)
            .filter(
                BatchItem.project_id == self.project_id,
                BatchItem.status == BatchItemStatus.setting_up,
            )
            .all()
        )

        for item in stuck_items:
            # Determine when this item entered setting_up
            ref_time = item.started_at  # set at 'executing' transition — may be NULL

            if ref_time is None:
                # Fall back to the earliest item_setup_started daemon event
                row = db.execute(
                    text(
                        "SELECT MIN(created_at) FROM daemon_events "
                        "WHERE project_id = :project_id "
                        "  AND event_type = 'item_setup_started' "
                        "  AND entity_id = :entity_id"
                    ),
                    {"project_id": self.project_id, "entity_id": item.work_item_id},
                ).scalar_one_or_none()
                if row is None:
                    # No reference time — skip to avoid false-positives
                    logger.debug(
                        "[%s] setting_up item %s has no ref time — skipping timeout check",
                        self.project_id,
                        item.work_item_id,
                    )
                    continue
                ref_time = row

            # Ensure ref_time is timezone-aware for comparison
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=UTC)

            elapsed = (now - ref_time).total_seconds()
            if elapsed < threshold_secs:
                continue  # Not yet timed out

            logger.warning(
                "[%s] BatchItem %s (work_item=%s) stuck in setting_up for %.0fs "
                "(threshold=%ds) — transitioning to setup_failed",
                self.project_id,
                item.id,
                item.work_item_id,
                elapsed,
                threshold_secs,
            )

            # Transition item to setup_failed
            item.status = BatchItemStatus.setup_failed
            item.notes = f"Setting up exceeded {threshold_secs}s — likely daemon crash mid-setup"

            # Revert the WorkItem to failed
            work_item = (
                db.query(WorkItem)
                .filter_by(project_id=self.project_id, id=item.work_item_id)
                .first()
            )
            if work_item is not None:
                work_item.status = WorkItemStatus.failed

            db.commit()

            _emit_event(
                db,
                self.project_id,
                "item_failed",
                item.work_item_id,
                "work_item",
                f"Setting up exceeded {threshold_secs}s — likely daemon crash mid-setup",
                {"phase": "setup", "reason": "setup_timeout"},
            )

            # Best-effort compose down to clean up any partial bring-up state
            try:
                compose_path = (
                    Path(item.worktree_compose_path) if item.worktree_compose_path else None
                )
                worktree_compose.down(str(item.id), compose_path)
            except Exception:
                logger.warning(
                    "[%s] worktree_compose.down failed for stuck item %s (non-fatal)",
                    self.project_id,
                    item.id,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # F-00076: policy-allowed event helper
    # ------------------------------------------------------------------

    def _emit_overlap_allowed_by_policy_if_needed(
        self,
        db: Session,
        item: BatchItem,
        candidate_paths: list[str],
        in_flight_scopes: list[tuple[str, list[str]]],
    ) -> None:
        """Emit ``item_overlap_allowed_by_policy`` if the launch was released by a
        non-default policy that the strict default would have blocked.

        Called exactly once per launch decision — i.e. only when the candidate
        actually transitions to launching (setting_up → executing).
        """
        cfg = self.project_config
        # Only run the expensive double-check when the project actually
        # customised its policy (avoids redundant work for the common case).
        if list(cfg.overlap_block_patterns) != list(scope_overlap.DEFAULT_BLOCK_PATTERNS) or list(
            cfg.overlap_allow_patterns
        ) != list(scope_overlap.DEFAULT_ALLOW_PATTERNS):
            default_blocked = scope_overlap.find_blocking_items(
                candidate_paths,
                in_flight_scopes,
                block_patterns=list(scope_overlap.DEFAULT_BLOCK_PATTERNS),
                allow_patterns=list(scope_overlap.DEFAULT_ALLOW_PATTERNS),
            )
            if default_blocked:
                _emit_event(
                    db,
                    self.project_id,
                    "item_overlap_allowed_by_policy",
                    item.work_item_id,
                    "work_item",
                    f"Allowed: {item.work_item_id} overlapped with "
                    f"{', '.join(bid for bid, _ in default_blocked)} but policy released it",
                    {
                        "candidate_item_id": item.work_item_id,
                        "in_flight_item_ids": [bid for bid, _ in default_blocked],
                        "dropped_block_globs": sorted(
                            {g for _, globs in default_blocked for g in globs}
                        ),
                        "matched_allow_patterns": sorted(
                            {
                                p
                                for p in cfg.overlap_allow_patterns
                                if any(
                                    scope_overlap._matches(g, p)  # noqa: SLF001
                                    for _, globs in default_blocked
                                    for g in globs
                                )
                            }
                        ),
                    },
                )

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def _collect_in_flight_scopes(self, db: Session) -> list[tuple[str, list[str]]]:
        """Gather all non-Research, in-flight items across the project.

        Returns list[tuple[work_item_id, impacted_paths]] for items whose
        BatchItem status is setting_up, executing, or merging.

        Used by the cross-batch conflict gate in _process_batch.
        Excludes Research items per F-00076 design (scope conflicts there
        are low-risk; parallelism is more important).
        """
        in_flight_statuses = (
            BatchItemStatus.setting_up,
            BatchItemStatus.executing,
            BatchItemStatus.merging,
        )
        rows = (
            db.query(WorkItem.id, WorkItem.impacted_paths)
            .join(BatchItem, BatchItem.work_item_id == WorkItem.id)
            .filter(
                BatchItem.project_id == self.project_id,
                BatchItem.status.in_(in_flight_statuses),
                WorkItem.type != WorkItemType.Research,
            )
            .all()
        )
        return [(work_item_id, list(impacted_paths or [])) for work_item_id, impacted_paths in rows]

    def _process_batch(self, db: Session, batch: Batch) -> None:
        """Advance all items in a batch: detect completions, launch pending."""
        items = (
            db.query(BatchItem)
            .filter(
                BatchItem.project_id == self.project_id,
                BatchItem.batch_id == batch.id,
            )
            .order_by(BatchItem.execution_group, BatchItem.id)
            .all()
        )

        # Check executing items: did an agent finish a step?
        for item in items:
            if item.status == BatchItemStatus.executing:
                self._check_executing_item(db, item)

        # Re-count after possible status changes above
        executing_count = sum(
            1 for i in items if i.status in (BatchItemStatus.setting_up, BatchItemStatus.executing)
        )

        # F-00076: gather in-flight items across the project (any batch) for the
        # cross-batch conflict gate. Excludes Research items per design.
        in_flight_scopes = self._collect_in_flight_scopes(db)

        current_group = _current_execution_group(items)
        if current_group is None:
            # All items in terminal state — check if batch is done
            self._check_batch_completion(db, batch, items)
            return

        # Block the current group from launching if any earlier group has an
        # implementation-failure item.
        # Blocking statuses: failed, stalled, skipped, migration_rolled_back.
        # Non-blocking: merged (success), setup_failed (infrastructure failure — CR-00096:
        # worktree never started, no impl output; retryable via iw item-retry),
        # merge_failed / migration_invalid / migration_rebase_failed (operator-recoverable,
        # CR-00028).
        failed_in_prior_group = any(
            i.status in _BLOCKING_TERMINAL_STATUSES and i.execution_group < current_group
            for i in items
        )
        if failed_in_prior_group:
            # Mark all pending items in the current (and later) groups as failed.
            for item in items:
                if item.execution_group >= current_group and item.status == BatchItemStatus.pending:
                    item.status = BatchItemStatus.failed
                    item.notes = (
                        f"Skipped: a dependency in execution_group "
                        f"{item.execution_group - 1} failed before this item could start"
                    )
            db.commit()
            _emit_event(
                db,
                self.project_id,
                "batch_dependency_failed",
                batch.id,
                "batch",
                f"Batch {batch.id}: failed items in group {current_group - 1} "
                f"block execution_group {current_group}+",
            )
            logger.warning(
                "[%s] Batch %s: implementation dependency failure in group %d"
                " — marking pending items failed",
                self.project_id,
                batch.id,
                current_group,
            )
            return

        # Launch pending items in the current group up to max_parallel
        for item in items:
            if item.execution_group != current_group:
                continue
            if item.status != BatchItemStatus.pending:
                continue

            # F-00076: scope overlap gate — hold items that conflict with
            # in-flight work from any batch in the same project.
            work_item = db.get(WorkItem, (self.project_id, item.work_item_id))
            if work_item is None:
                continue
            candidate_paths: list[str] = []
            if work_item.type != WorkItemType.Research:
                candidate_paths = list(work_item.impacted_paths or [])
                cfg = self.project_config
                blocked_by = scope_overlap.find_blocking_items(
                    candidate_paths,
                    in_flight_scopes,
                    block_patterns=cfg.overlap_block_patterns,
                    allow_patterns=cfg.overlap_allow_patterns,
                )
                if blocked_by:
                    # CR-00078: filter against per-batch ignore set
                    ignored_pairs: set[tuple[str, str]] = {
                        (row.blocking_item_id, row.file_pattern)
                        for row in db.execute(
                            select(BatchOverlapIgnore).where(
                                BatchOverlapIgnore.project_id == self.project_id,
                                BatchOverlapIgnore.batch_id == batch.id,
                                BatchOverlapIgnore.held_item_id == item.work_item_id,
                            )
                        ).scalars()
                    }
                    filtered_blocked_by = filter_blocked_by_ignores(blocked_by, ignored_pairs)
                    if not filtered_blocked_by and ignored_pairs:
                        _emit_event(
                            db,
                            self.project_id,
                            "batch_overlap_allowed_by_ignore",
                            item.work_item_id,
                            "work_item",
                            f"Allowed: {item.work_item_id} — all overlaps ignored by operator",
                            {
                                "candidate_item_id": item.work_item_id,
                                "ignored_pairs": [
                                    {"blocking_item_id": b, "file_pattern": f}
                                    for (b, f) in sorted(ignored_pairs)
                                ],
                            },
                        )
                        db.commit()
                    # Always narrow blocked_by to the surviving (non-ignored) entries.
                    # When every pair was ignored this is [], so the held branch below is
                    # skipped and the item falls through to the launch path. When only some
                    # pairs were ignored it holds the remainder; when there were no ignores
                    # it is unchanged. Forgetting this assignment on the cleared path is the
                    # classic bug — the held branch would still see the original non-empty
                    # list and the item would never launch.
                    blocked_by = filtered_blocked_by

                if blocked_by:
                    for blocking_id, conflicting_globs in blocked_by:
                        _emit_event(
                            db,
                            self.project_id,
                            "item_held_for_scope",
                            item.work_item_id,
                            "work_item",
                            f"Held: {item.work_item_id} overlaps with {blocking_id} on "
                            f"{', '.join(conflicting_globs[:3])}",
                            {
                                "candidate_item_id": item.work_item_id,
                                "blocking_item_id": blocking_id,
                                "conflicting_globs": conflicting_globs,
                            },
                        )
                    db.commit()
                    continue  # leave status=pending; do not consume slot

            if executing_count >= batch.max_parallel:
                break
            # Launch decision made — emit policy-allowed event if the project
            # customised its policy AND the strict default would have blocked.
            self._emit_overlap_allowed_by_policy_if_needed(
                db, item, candidate_paths, in_flight_scopes
            )
            self._launch_item(db, item)
            executing_count += 1
            # F-00076: append this item's scope so subsequent items in the same
            # poll cycle see it (prevents same-group items from both launching
            # when their globs overlap and neither is in flight at cycle start).
            work_item = db.get(WorkItem, (self.project_id, item.work_item_id))
            if work_item is not None:
                in_flight_scopes.append((item.work_item_id, list(work_item.impacted_paths or [])))

    def _check_executing_item(self, db: Session, batch_item: BatchItem) -> None:
        """Detect whether the agent finished a step and advance if so."""
        # setting_up items are mid-launch (worktree setup or compose up in progress).
        # _launch_item owns the transition setting_up → executing; _check_executing_item
        # must not interfere with that window by treating them as completed.
        if batch_item.status == BatchItemStatus.setting_up:
            return

        has_active = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == self.project_id,
                WorkflowStep.work_item_id == batch_item.work_item_id,
                WorkflowStep.status == StepStatus.in_progress,
            )
            .first()
        )
        if has_active:
            return  # Step still running — step_monitor handles it

        has_failed = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == self.project_id,
                WorkflowStep.work_item_id == batch_item.work_item_id,
                WorkflowStep.status.in_([StepStatus.failed, StepStatus.needs_fix]),
            )
            .order_by(WorkflowStep.step_number)
            .first()
        )
        if has_failed:
            # needs_fix means a fix cycle is already in progress — wait for it
            if has_failed.status == StepStatus.needs_fix:
                return

            # Soft-step semantics: self_assess failures never block merge.
            # The StepRun row records the actual failure for reporting, but
            # the item proceeds to the next step (or merge) without any fix
            # cycle, retry, or human-review signal.
            from orch.self_assess import is_soft_step_failure  # noqa: PLC0415

            if is_soft_step_failure(has_failed.step_type, has_failed.status):
                # Treat as terminal-success for batch progression; row stays failed
                logger.info(
                    "[%s] self_assess step %s/%s failed (soft) — proceeding without fix cycle",
                    self.project_id,
                    batch_item.work_item_id,
                    has_failed.step_id,
                )
                self._launch_next_step(db, batch_item.work_item_id, batch_item.worktree_info or {})
                return

            # Step failed — attempt a fix cycle if the step type supports it
            from orch.daemon import fix_cycle  # noqa: PLC0415

            # SPEC_MISMATCH: the V step asks for something the design doc
            # explicitly excludes.  No code fix can satisfy it — escalate to
            # human review immediately without creating a FixCycle.
            failure_reason = fix_cycle._latest_failure_reason(db, has_failed)  # noqa: SLF001
            if fix_cycle.is_spec_mismatch_failure(failure_reason):
                fix_cycle.handle_spec_mismatch_escalation(
                    db,
                    has_failed,
                    self.project_id,
                    failure_reason,
                )
                return

            if fix_cycle.should_attempt_fix(db, has_failed, self.project_config):
                worktree_info = batch_item.worktree_info or {}
                fix_cycle.attempt_fix_cycle(
                    db,
                    has_failed,
                    self.project_id,
                    self.project_config,
                    self.config,
                    worktree_info,
                )
            elif fix_cycle.should_retry_step(db, has_failed, self.project_config):
                # Transient failure (e.g. browser_verification env not ready) — retry
                fix_cycle.retry_step(db, has_failed, self.project_id)
            else:
                # Step is not fixable and not retryable, or retries exhausted
                fix_cycle.handle_recovery_exhausted_escalation(
                    db,
                    has_failed,
                    self.project_id,
                    failure_reason,
                )
                batch_item.status = BatchItemStatus.failed
                work_item = (
                    db.query(WorkItem)
                    .filter_by(project_id=self.project_id, id=batch_item.work_item_id)
                    .first()
                )
                if work_item is not None:
                    work_item.status = WorkItemStatus.failed
                db.commit()
            return

        # No active or failed steps → advance to next step (or complete item)
        self._launch_next_step(db, batch_item.work_item_id, batch_item.worktree_info or {})

    # ------------------------------------------------------------------
    # Item launch
    # ------------------------------------------------------------------

    def _launch_item(self, db: Session, batch_item: BatchItem) -> None:
        """Two-phase launch: worktree setup + compose up, then first step."""
        item_id = batch_item.work_item_id

        # R4 — re-check before any worktree is created
        status = check_db_at_head()
        if not status.ok:
            batch_item.status = BatchItemStatus.setup_failed
            batch_item.notes = remediation_message(status)
            db.commit()
            _emit_event(
                db,
                self.project_id,
                "item_failed",
                item_id,
                "work_item",
                remediation_message(status),
                {
                    "phase": "alembic_guard",
                    "reason": "db_behind_head",
                    "current_rev": status.current_rev,
                    "head_rev": status.head_rev,
                    "pending": status.pending,
                },
            )
            return

        # Phase 1: Worktree setup
        batch_item.status = BatchItemStatus.setting_up
        db.commit()
        _emit_event(
            db,
            self.project_id,
            "item_setup_started",
            item_id,
            "work_item",
            f"Setting up worktree for {item_id}",
        )

        try:
            worktree_info = self._setup_worktree(item_id)
        except WorktreeSetupError as e:
            batch_item.status = BatchItemStatus.setup_failed
            batch_item.notes = f"Worktree setup failed: {e}"
            work_item = db.query(WorkItem).filter_by(project_id=self.project_id, id=item_id).one()
            work_item.status = WorkItemStatus.failed
            db.commit()
            _emit_event(
                db,
                self.project_id,
                "item_failed",
                item_id,
                "work_item",
                str(e),
                {"phase": "setup", "reason": "setup_failed"},
            )
            return

        worktree_path = Path(worktree_info["path"])

        # I-00083: Launch-time sibling-scope check (WARN only — v1).
        # Query in-flight siblings and compute how many of their declared
        # impacted_paths globs match files present in B's base tree without
        # the sibling having a merge_commit_sha yet. Emits exactly one INFO
        # line per worktree-create event so operators can detect drift early.
        self._emit_sibling_drift_log(db, item_id, worktree_path)

        # Phase 1b: Compose lifecycle (opt-in per worktree)
        if not worktree_compose.has_iw_config(worktree_path):
            batch_item.worktree_db_port = None
            batch_item.worktree_app_port = None
            batch_item.worktree_compose_path = None
            # I-00062: no compose stack → no per-worktree DB credentials
            batch_item.worktree_db_host = None
            batch_item.worktree_db_name = None
            batch_item.worktree_db_user = None
            batch_item.worktree_db_password = None
        else:
            try:
                cfg = worktree_compose.load_config(
                    str(batch_item.id),
                    self.project_id,
                    worktree_path,
                )
                up_result = worktree_compose.up(cfg)
                if up_result.success:
                    batch_item.worktree_compose_path = str(cfg.rendered_compose_path)
                    up_db_port = up_result.discovered_ports.get("IW_CORE_DB_PORT")
                    up_app_port = up_result.discovered_ports.get("IW_CORE_DASHBOARD_PORT")
                    batch_item.worktree_db_port = (
                        int(up_db_port) if up_db_port is not None else None
                    )
                    batch_item.worktree_app_port = (
                        int(up_app_port) if up_app_port is not None else None
                    )
                    # I-00062: persist per-worktree DB credentials from compose-up
                    creds = up_result.discovered_db_credentials or {}
                    batch_item.worktree_db_host = creds.get("IW_CORE_DB_HOST")
                    batch_item.worktree_db_name = creds.get("IW_CORE_DB_NAME")
                    batch_item.worktree_db_user = creds.get("IW_CORE_DB_USER")
                    batch_item.worktree_db_password = creds.get("IW_CORE_DB_PASSWORD")
                else:
                    batch_item.status = BatchItemStatus.setup_failed
                    batch_item.notes = f"Compose up failed: {up_result.error_message}"
                    batch_item.worktree_db_port = None
                    batch_item.worktree_app_port = None
                    batch_item.worktree_compose_path = None
                    # I-00062: no successful compose-up → no credentials
                    batch_item.worktree_db_host = None
                    batch_item.worktree_db_name = None
                    batch_item.worktree_db_user = None
                    batch_item.worktree_db_password = None
                    work_item = (
                        db.query(WorkItem).filter_by(project_id=self.project_id, id=item_id).one()
                    )
                    work_item.status = WorkItemStatus.failed
                    db.commit()
                    _emit_event(
                        db,
                        self.project_id,
                        "item_failed",
                        item_id,
                        "work_item",
                        f"Compose up failed: {up_result.error_message}",
                        {
                            "phase": "compose_up",
                            "reason": "setup_failed",
                            "seed_stderr_tail": up_result.seed_stderr_tail,
                        },
                    )
                    worktree_compose.down(str(batch_item.id), cfg.rendered_compose_path)
                    return
            except Exception as exc:
                batch_item.status = BatchItemStatus.setup_failed
                batch_item.notes = f"Compose up error: {exc}"
                batch_item.worktree_db_port = None
                batch_item.worktree_app_port = None
                batch_item.worktree_compose_path = None
                # I-00062: no successful compose-up → no credentials
                batch_item.worktree_db_host = None
                batch_item.worktree_db_name = None
                batch_item.worktree_db_user = None
                batch_item.worktree_db_password = None
                work_item = (
                    db.query(WorkItem).filter_by(project_id=self.project_id, id=item_id).one()
                )
                work_item.status = WorkItemStatus.failed
                db.commit()
                _emit_event(
                    db,
                    self.project_id,
                    "item_failed",
                    item_id,
                    "work_item",
                    f"Compose up error: {exc}",
                    {"phase": "compose_up", "reason": "setup_failed"},
                )
                return

        # Phase 2: Transition to executing
        batch_item.status = BatchItemStatus.executing
        batch_item.worktree_info = worktree_info
        batch_item.started_at = datetime.now(UTC)
        db.commit()
        _emit_event(
            db,
            self.project_id,
            "item_setup_completed",
            item_id,
            "work_item",
            f"Worktree ready for {item_id}",
            {"worktree_path": worktree_info.get("path")},
        )

        # Embed per-worktree stack info into worktree_info so _launch_step
        # can substitute placeholders and set IW_CORE_PER_WORKTREE_DB without
        # needing an extra DB lookup.
        if batch_item.worktree_compose_path is not None:
            worktree_info["worktree_compose_path"] = batch_item.worktree_compose_path
            worktree_info["worktree_db_port"] = str(batch_item.worktree_db_port)
            worktree_info["worktree_app_port"] = str(batch_item.worktree_app_port)
            # I-00062: pass per-worktree DB credentials for explicit env injection
            worktree_info["worktree_db_host"] = batch_item.worktree_db_host or ""
            worktree_info["worktree_db_name"] = batch_item.worktree_db_name or ""
            worktree_info["worktree_db_user"] = batch_item.worktree_db_user or ""
            worktree_info["worktree_db_password"] = batch_item.worktree_db_password or ""
            worktree_info["batch_item_id"] = str(batch_item.id)
            worktree_info["project_name"] = batch_item.project_id

        self._compute_qv_baselines(db, batch_item, worktree_info)

        # Launch first pending step
        self._launch_next_step(db, item_id, worktree_info)

    def _setup_worktree(self, item_id: str) -> dict[str, str]:
        """Call worktree_setup.sh. Returns {path, branch, created_at}."""
        script = str(_EXECUTOR_DIR / "worktree_setup.sh")
        cmd = ["bash", script, item_id, self.project_config.working_dir]  # noqa: S607
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # noqa: S603
        if result.returncode != 0:
            raise WorktreeSetupError(result.stderr.strip() or f"exit code {result.returncode}")

        worktree_path = (
            Path(self.project_config.working_dir) / self.project_config.worktree_base / item_id
        )
        return {
            "path": str(worktree_path),
            "branch": f"agent/{item_id}",
            "created_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # I-00083: Launch-time sibling-scope drift check
    # ------------------------------------------------------------------

    def _list_worktree_files(self, worktree_path: Path) -> frozenset[str]:
        """Return all git-tracked files in the worktree as a frozenset of paths.

        Uses `git ls-tree -r --name-only HEAD` which lists the files in the
        commit tree (not the working directory), so untracked files are excluded.
        Falls back to an empty set if git is unavailable or the path is not a
        git repo.
        """
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "ls-tree", "-r", "--name-only", "HEAD"],  # noqa: S607
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return frozenset(result.stdout.splitlines())
        except Exception:  # noqa: BLE001
            logger.debug(
                "[I-00083] git ls-tree failed for worktree %s — treating as empty",
                worktree_path,
                exc_info=True,
            )
        return frozenset()

    def _glob_matches_any(self, glob_pattern: str, file_paths: frozenset[str]) -> list[str]:
        """Return the subset of file_paths that match the gitignore-style glob_pattern.

        Supports:
          - Exact paths: "orch/foo.py" → matches only that exact path
          - Single-star globs: "orch/*.py" → matches one path segment
          - Double-star globs: "tests/**" → matches any depth under tests/

        Uses pathlib.PurePath.match() for simple patterns and fnmatch for
        glob-style matching with **. This is intentionally a v1 approximation;
        full gitignore semantics are out of scope.
        """
        import fnmatch
        from pathlib import PurePath

        matched: list[str] = []
        for fp in file_paths:
            # PurePath.match() handles "**" and single-segment patterns correctly
            # when matching against the full path.
            try:
                if PurePath(fp).match(glob_pattern):
                    matched.append(fp)
                    continue
            except Exception:  # noqa: BLE001
                logger.debug(
                    "[I-00083] PurePath.match failed for pattern=%r path=%r",
                    glob_pattern,
                    fp,
                    exc_info=True,
                )
            # Fallback: plain fnmatch (handles ** as wildcard across segments)
            try:
                if fnmatch.fnmatch(fp, glob_pattern):
                    matched.append(fp)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "[I-00083] fnmatch failed for pattern=%r path=%r",
                    glob_pattern,
                    fp,
                    exc_info=True,
                )
        return matched

    def _collect_in_flight_sibling_items(self, db: Session, current_item_id: str) -> list[WorkItem]:
        """Return WorkItems that are actively in-flight (via BatchItem) for this project.

        In-flight is defined as BatchItem.status in {setting_up, executing, merging}.
        Excludes the current item being launched (current_item_id).

        Used by the I-00083 sibling-scope drift check.
        """
        in_flight_statuses = (
            BatchItemStatus.setting_up,
            BatchItemStatus.executing,
            BatchItemStatus.merging,
        )
        rows = (
            db.query(WorkItem)
            .join(BatchItem, BatchItem.work_item_id == WorkItem.id)
            .filter(
                WorkItem.project_id == self.project_id,
                BatchItem.project_id == self.project_id,
                BatchItem.status.in_(in_flight_statuses),
                WorkItem.id != current_item_id,
            )
            .distinct()
            .all()
        )
        return list(rows)

    def _emit_sibling_drift_log(self, db: Session, item_id: str, worktree_path: Path) -> None:
        """Emit exactly one INFO line per worktree-create event (I-00083).

        Format:
          worktree create: item=<ID> base=<sha> in_flight_siblings=[<sib1>,...]
          sibling_paths_without_merge=<N> details=[<sib1>:<count>,...]

        v1 approximation: a sibling contributes to the drift count when it has
        no merge_commit_sha (not yet merged) AND its impacted_paths globs match
        at least one file present in the new worktree's HEAD tree.

        Behaviour: WARN only. Worktree creation is never blocked.
        """
        # Resolve the worktree's HEAD SHA (best-effort; falls back to "unknown")
        base_sha = self._resolve_worktree_base_sha(str(worktree_path)) or "unknown"

        # Gather in-flight siblings from the DB
        siblings = self._collect_in_flight_sibling_items(db, item_id)
        sibling_ids = [s.id for s in siblings]

        if not siblings:
            logger.info(
                "worktree create: item=%s base=%s in_flight_siblings=[] "
                "sibling_paths_without_merge=0",
                item_id,
                base_sha,
            )
            return

        # List all git-tracked files in the new worktree's HEAD tree
        worktree_files = self._list_worktree_files(worktree_path)

        # For each sibling with no merge_commit_sha, count matching files
        details: list[tuple[str, int]] = []
        total_drift = 0
        for sibling in siblings:
            # v1 approximation: sibling contributes when it has no merge_commit_sha
            if sibling.merge_commit_sha is not None:
                # Sibling already merged — its files are legitimately in main
                details.append((sibling.id, 0))
                continue

            globs = list(sibling.impacted_paths or [])
            matched_files: set[str] = set()
            for glob_pat in globs:
                matched_files.update(self._glob_matches_any(glob_pat, worktree_files))

            count = len(matched_files)
            details.append((sibling.id, count))
            total_drift += count

        if total_drift > 0:
            detail_str = "[" + ",".join(f"{sid}:{cnt}" for sid, cnt in details if cnt > 0) + "]"
            logger.info(
                "worktree create: item=%s base=%s in_flight_siblings=%s "
                "sibling_paths_without_merge=%d details=%s",
                item_id,
                base_sha,
                sibling_ids,
                total_drift,
                detail_str,
            )
            logger.warning(
                "[I-00083] Drift detected: item=%s base tree contains %d file(s) "
                "from un-merged sibling(s) %s — these files may be in a broken "
                "pre-impl state. Review before running QV gates.",
                item_id,
                total_drift,
                [sid for sid, cnt in details if cnt > 0],
            )
        else:
            logger.info(
                "worktree create: item=%s base=%s in_flight_siblings=%s "
                "sibling_paths_without_merge=0",
                item_id,
                base_sha,
                sibling_ids,
            )

    def _compute_qv_baselines(
        self, db: Session, batch_item: BatchItem, worktree_info: dict[str, Any]
    ) -> None:
        """Compute and persist QV baseline fingerprints at worktree setup time.

        Runs each qv-gate's command at the base SHA and stores the resulting
        failure fingerprint so subsequent runs can subtract pre-existing failures.
        """
        if not self.config.baseline_qv_enabled:
            logger.debug("[F-00061] baseline_qv_enabled=False — skipping baseline compute")
            return

        item_id = batch_item.work_item_id
        worktree_path = worktree_info.get("path", "")
        if not worktree_path:
            logger.warning("[F-00061] No worktree path for %s — skipping baseline compute", item_id)
            return

        base_sha = self._resolve_worktree_base_sha(worktree_path)
        if not base_sha:
            logger.warning(
                "[F-00061] Could not resolve base SHA for %s — skipping baseline compute",
                item_id,
            )
            return

        # CR-00023: manifest is the legacy fallback for items registered before
        # the DB columns existed. Read it lazily — DB-first lookups hit it only
        # when both step.command and step.gate are NULL.
        manifest_steps = self._read_workflow_manifest(item_id, worktree_path)

        steps = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == self.project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_type == StepType.quality_validation,
            )
            .all()
        )
        if not steps:
            return

        from orch.daemon.qv_baseline import (  # noqa: PLC0415
            fingerprint_to_jsonable,
            parser_for_gate,
        )

        for step in steps:
            # CR-00023: DB-first; manifest fallback for legacy NULL rows.
            gate: str
            command: str
            if step.command:
                gate = step.gate or step.step_id
                command = step.command
            else:
                if manifest_steps is None:
                    continue
                step_manifest = next(
                    (s for s in manifest_steps if s.get("step") == step.step_id), None
                )
                if not step_manifest:
                    continue
                gate = str(step_manifest.get("gate", step.step_id))
                manifest_command = step_manifest.get("command")
                if not manifest_command:
                    continue
                command = str(manifest_command)

            parser = parser_for_gate(gate)

            try:
                output = self._run_gate_command(command, worktree_path, gate)
                fp = parser(output)
                payload = fingerprint_to_jsonable(fp)
                self._upsert_qv_baseline(db, step.id, gate, base_sha, payload)
            except Exception as e:
                logger.warning(
                    "[F-00061] Baseline compute failed for %s/%s (gate=%s): %s",
                    item_id,
                    step.step_id,
                    gate,
                    e,
                )
                continue

        db.commit()

    def _resolve_worktree_base_sha(self, worktree_path: str) -> str | None:
        """Resolve the worktree's base SHA via git merge-base HEAD main."""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "merge-base", "HEAD", "main"],  # noqa: S607
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:  # noqa: S110
            pass
        return None

    def _read_workflow_manifest(
        self, item_id: str, worktree_path: str
    ) -> list[dict[str, Any]] | None:
        """Read and parse the workflow-manifest.json for a work item."""
        import json

        manifest_path = (
            Path(worktree_path) / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        )
        if not manifest_path.exists():
            return None
        try:
            data = json.loads(manifest_path.read_text())
            steps = data.get("steps", [])
            if isinstance(steps, list):
                return [dict(s) for s in steps]
            return None
        except Exception:
            return None

    def _run_gate_command(self, command: str, worktree_path: str, gate: str) -> str:  # noqa: ARG002
        """Run a gate command and return combined stdout+stderr.

        Uses start_new_session=True so the shell and all its descendants share
        a new process group. On TimeoutExpired the entire group is SIGKILL'd
        before draining pipes, preventing the FD-inheritance deadlock that
        blocks the daemon thread indefinitely.
        """
        with subprocess.Popen(  # noqa: S602  # nosec B602
            command,
            shell=True,  # nosec B602  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — trusted quality-gate command (e.g. `make test-unit`) from server-side config, no untrusted input on argv
            cwd=worktree_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env=_agent_subprocess_env(),
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=900)
                return stdout.decode(errors="replace") + stderr.decode(errors="replace")
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                stdout, stderr = proc.communicate()
                return stdout.decode(errors="replace") + stderr.decode(errors="replace")

    def _upsert_qv_baseline(
        self,
        db: Session,
        step_id: int,
        gate_name: str,
        base_sha: str,
        fingerprint: dict[str, object],
    ) -> None:
        """Upsert a QvBaseline row (on conflict, update fingerprint + computed_at).

        Only one baseline per (step_id, gate_name) is valid at any time. Stale
        rows from a previous base_sha (e.g. after a rebase) are deleted first
        so scalar_one_or_none() in fix_cycle.py never sees duplicates.
        """
        from sqlalchemy import text

        # Delete any stale rows with a different SHA before checking for an exact match.
        # This ensures at most one row exists per (step_id, gate_name).
        db.execute(
            text(
                "DELETE FROM qv_baselines WHERE step_id = :step_id "
                "AND gate_name = :gate_name AND base_sha != :base_sha"
            ),
            {"step_id": step_id, "gate_name": gate_name, "base_sha": base_sha},
        )

        existing = db.execute(
            text(
                "SELECT id FROM qv_baselines WHERE step_id = :step_id "
                "AND gate_name = :gate_name AND base_sha = :base_sha"
            ),
            {"step_id": step_id, "gate_name": gate_name, "base_sha": base_sha},
        ).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing:
            db.execute(
                text(
                    "UPDATE qv_baselines SET fingerprint = :fingerprint, "
                    "computed_at = :computed_at WHERE id = :id"
                ),
                {
                    "fingerprint": json.dumps(fingerprint, default=str),
                    "computed_at": now,
                    "id": existing,
                },
            )
        else:
            baseline = QvBaseline(
                step_id=step_id,
                gate_name=gate_name,
                base_sha=base_sha,
                fingerprint=fingerprint,
                computed_at=now,
            )
            db.add(baseline)

    # ------------------------------------------------------------------
    # Step launch
    # ------------------------------------------------------------------

    def _launch_next_step(self, db: Session, item_id: str, worktree_info: dict[str, Any]) -> None:
        """Find the next pending step and launch it, or complete the item."""
        step = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == self.project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.status == StepStatus.pending,
            )
            .order_by(WorkflowStep.step_number)
            .first()
        )

        if step is None:
            self._complete_item(db, item_id)
            return

        # Guard: all steps before this one must be in a terminal state.
        # If a lower-numbered step is still pending/in_progress/failed/needs_fix,
        # launching this step would create an out-of-order execution.
        terminal_statuses = frozenset({StepStatus.completed, StepStatus.skipped})
        blocking = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == self.project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_number < step.step_number,
                WorkflowStep.status.notin_(list(terminal_statuses)),
            )
            .order_by(WorkflowStep.step_number)
            .first()
        )
        if blocking:
            logger.error(
                "[%s] Step ordering violation for %s: want to launch %s (step_number=%d) "
                "but %s (step_number=%d) is not terminal (status=%s) — holding",
                self.project_id,
                item_id,
                step.step_id,
                step.step_number,
                blocking.step_id,
                blocking.step_number,
                blocking.status.value,
            )
            return

        self._launch_step(db, step, worktree_info)

    def _launch_step(self, db: Session, step: WorkflowStep, worktree_info: dict[str, Any]) -> None:
        """Start the agent process and record everything in DB."""
        from orch.agent_runtime.resolver import resolve_runtime  # noqa: PLC0415
        from orch.daemon import browser_env  # noqa: PLC0415
        from orch.daemon.step_monitor import get_timeout  # noqa: PLC0415

        worktree_path = worktree_info.get("path", "")

        # I-00116: cumulative per-item cap on review-step relaunches.
        # Check before launching another review step run so the item transitions
        # to failed before yet another agent is spun up.
        if step.step_type in (StepType.code_review, StepType.code_review_final):
            from orch.daemon import fix_cycle as fc  # noqa: PLC0415

            relaunch_count = fc.count_review_relaunches(db, self.project_id, step.work_item_id)
            if relaunch_count >= fc.get_max_review_relaunches():
                fc.transition_item_to_failed_for_loop(
                    db, self.project_id, step.work_item_id, relaunch_count
                )
                return

        # F-00081: Resolve the runtime (cli_tool, model) option via cascade.
        # _load_item is called to get the work_item for the resolver.
        work_item = (
            db.query(WorkItem).filter_by(project_id=self.project_id, id=step.work_item_id).first()
        )
        runtime_option = resolve_runtime(
            db,
            step=step,
            item=work_item,
            project=self.project_config,
        )
        resolved_cli_tool = runtime_option.cli_tool
        resolved_model = runtime_option.model

        # ------------------------------------------------------------------
        # browser_verification pre-hook: bring up the test environment
        # ------------------------------------------------------------------
        agent_env: dict[str, str] | None = None
        bv_env: dict[str, str] | None = None
        if browser_env.is_browser_verification_step(step.step_type):
            bv_env = browser_env.allocate_browser_env(
                self.project_config,
                self.project_id,
                step.work_item_id,
                worktree_path,
            )
            if bv_env is not None:
                success, log_path = browser_env.run_env_up_hook(
                    self.project_config,
                    worktree_path,
                    bv_env,
                    step.work_item_id,
                    step.step_id,
                )
                if not success:
                    # Fail the step — don't launch the agent
                    now = datetime.now(UTC)
                    log_tail = ""
                    container_crash_logs = ""
                    if log_path and log_path.exists():
                        compose_output = log_path.read_text(errors="replace")
                        lines = compose_output.splitlines()
                        log_tail = "\n".join(lines[-20:])
                        container_crash_logs = browser_env._capture_crashed_container_logs(  # noqa: SLF001
                            compose_output
                        )
                    run_number = _next_run_number(db, step)
                    error_msg = f"browser env setup failed: {log_tail}{container_crash_logs}"
                    run = StepRun(
                        step_id=step.id,
                        run_number=run_number,
                        status=RunStatus.failed,
                        error_message=error_msg,
                        worktree_path=worktree_path,
                        cli_tool=resolved_cli_tool,
                        log_file=str(log_path),
                        started_at=now,
                        completed_at=now,
                        timeout_secs=get_timeout(
                            self.project_config, step.step_type.value, step=step
                        ),
                    )
                    db.add(run)
                    step.status = StepStatus.failed
                    step.started_at = now
                    step.completed_at = now
                    db.commit()
                    _emit_event(
                        db,
                        self.project_id,
                        "step_failed",
                        step.work_item_id,
                        "work_item",
                        f"Step {step.step_id} failed: browser env setup failed",
                        {
                            "reason": "browser_env_setup_failed",
                            "log": str(log_path),
                            "step_id": step.step_id,
                        },
                    )
                    db.commit()
                    logger.warning(
                        "[%s] browser env_up failed for %s/%s — step marked failed",
                        self.project_id,
                        step.work_item_id,
                        step.step_id,
                    )
                    # H11: best-effort teardown of any partial bring-up state
                    # (containers, sessions) so they do not leak after a failed env-up.
                    try:
                        browser_env.run_env_down_hook(
                            self.project_config,
                            worktree_path,
                            bv_env,
                            step.work_item_id,
                            step.step_id,
                        )
                    except Exception:
                        logger.warning(
                            "[%s] browser env_down after failed env_up raised (non-fatal)",
                            self.project_id,
                            exc_info=True,
                        )
                    return

                # Apply per-item fixtures AFTER env_up so the browser agent
                # always sees deterministic seed data — on initial provision AND
                # every fix-cycle re-provision.  Runs inside the e2e-dashboard
                # container via docker compose exec.  Silent no-op when the
                # fixtures directory does not exist (most work items).
                compose_project_name = bv_env.get("COMPOSE_PROJECT_NAME", "")
                if compose_project_name:
                    try:
                        browser_env._apply_per_item_fixtures(  # noqa: SLF001
                            step.work_item_id,
                            compose_project_name,
                            worktree_path,
                        )
                    except Exception as fixture_exc:
                        now = datetime.now(UTC)
                        run_number = _next_run_number(db, step)
                        run = StepRun(
                            step_id=step.id,
                            run_number=run_number,
                            status=RunStatus.failed,
                            error_message=f"per-item fixture apply failed: {fixture_exc}",
                            worktree_path=worktree_path,
                            cli_tool=resolved_cli_tool,
                            started_at=now,
                            completed_at=now,
                            timeout_secs=get_timeout(
                                self.project_config, step.step_type.value, step=step
                            ),
                        )
                        db.add(run)
                        step.status = StepStatus.failed
                        step.started_at = now
                        step.completed_at = now
                        db.commit()
                        _emit_event(
                            db,
                            self.project_id,
                            "step_failed",
                            step.work_item_id,
                            "work_item",
                            f"Step {step.step_id} failed: per-item fixture apply failed",
                            {
                                "reason": "per_item_fixture_failed",
                                "item_id": step.work_item_id,
                                "step_id": step.step_id,
                                "error": str(fixture_exc),
                            },
                        )
                        db.commit()
                        logger.warning(
                            "[%s] per-item fixture apply failed for %s/%s — tearing down stack",
                            self.project_id,
                            step.work_item_id,
                            step.step_id,
                        )
                        try:
                            browser_env.run_env_down_hook(
                                self.project_config,
                                worktree_path,
                                bv_env,
                                step.work_item_id,
                                step.step_id,
                            )
                        except Exception:
                            logger.warning(
                                "[%s] browser env_down after fixture failure raised (non-fatal)",
                                self.project_id,
                                exc_info=True,
                            )
                        return

                agent_env = bv_env

        # Quality validation gates run as plain bash subprocesses — no LLM. The
        # wrapper script writes a QvGate-format report and finalises the step
        # via `iw step-done` / `iw step-fail`, preserving the existing StepRun
        # lifecycle. Legacy items registered before CR-00023 (no step.command)
        # fall through to the LLM path below.
        prompt_file: Path | None = None
        if step.step_type == StepType.quality_validation and step.command:
            command = _build_qv_direct_command(
                item_id=step.work_item_id,
                step_id=step.step_id,
                gate_name=step.gate or step.step_id,
                gate_command=step.command,
                agent_label=step.agent_label,
                worktree_path=worktree_path,
            )
        else:
            # Build prompt from the step's manifest prompt file (shared by all CLI tools)
            prompt = self._build_claude_prompt(step, worktree_path)
            if agent_env is not None:
                prompt = browser_env.render_prompt_substitutions(prompt, agent_env)
            prompt = substitute_worktree_placeholders(prompt, worktree_info)
            prompt_file = (
                Path(worktree_path) / ".tmp" / f"{step.work_item_id}_{step.step_id}.prompt"
            )
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            write_agent_prompt(prompt_file, prompt)

            # NOTE: the fix-agent launcher in ``fix_cycle._launch_fix_agent``
            # builds the same `opencode run "$(cat …)"` / `claude -p "$(cat …)"`
            # / `pi -p "$(cat …)"` form — keep the two in sync (F-00081 changed
            # this site but missed the fix-cycle copy; see I-00074).
            agent_name = step.opencode_agent or step.agent_label
            agent_args = f"--agent {agent_name}" if agent_name else ""
            command = _build_initial_command(
                cli_tool=resolved_cli_tool,
                prompt_file=str(prompt_file),
                resolved_model=resolved_model,
                worktree_path=worktree_path,
                item_id=step.work_item_id,
                step_id=step.step_id,
                agent_args=agent_args,
            )

        # CR-00023: prefer the DB column (populated at register time). Fall
        # back to a manifest read for items registered before CR-00023.
        step_config: dict[str, Any] | None = None
        if step.timeout_secs is not None:
            step_config = {"timeout_secs": step.timeout_secs}
        else:
            manifest_path = (
                Path(worktree_path)
                / "ai-dev"
                / "active"
                / step.work_item_id
                / "workflow-manifest.json"
            )
            if manifest_path.exists():
                import json

                manifest = json.loads(manifest_path.read_text())
                for s in manifest.get("steps", []):
                    if s.get("step") == step.step_id:
                        if "timeout" in s:
                            step_config = {"timeout_secs": int(s["timeout"])}
                        break
        # CR-00024: pass step so get_timeout consults step.gate for QV gates.
        timeout = get_timeout(
            self.project_config, step.step_type.value, step_config=step_config, step=step
        )

        log_dir = Path(worktree_path) / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        run_number = _next_run_number(db, step)
        log_file = log_dir / f"{step.work_item_id}_{step.step_id}_run{run_number}.log"

        agent_env = _agent_subprocess_env()
        if bv_env is not None:
            agent_env = {**agent_env, **bv_env}
        if worktree_info.get("worktree_compose_path") is not None:
            agent_env["IW_CORE_PER_WORKTREE_DB"] = "true"
            # I-00062: inject per-worktree DB credentials from worktree_info
            # (populated at compose-up from UpResult.discovered_db_credentials).
            db_port = worktree_info.get("worktree_db_port")
            db_host = worktree_info.get("worktree_db_host") or ""
            db_name = worktree_info.get("worktree_db_name") or ""
            db_user = worktree_info.get("worktree_db_user") or ""
            db_password = worktree_info.get("worktree_db_password") or ""
            if db_port and db_host and db_name and db_user and db_password:
                agent_env["IW_CORE_DB_HOST"] = db_host
                agent_env["IW_CORE_DB_PORT"] = str(db_port)
                agent_env["IW_CORE_DB_NAME"] = db_name
                agent_env["IW_CORE_DB_USER"] = db_user
                agent_env["IW_CORE_DB_PASSWORD"] = db_password
            else:
                # Defensive: refuse to launch with incomplete per-worktree DB
                # credentials. Crash loudly rather than fall back to inherited
                # daemon env (which the strip in _agent_subprocess_env already
                # cleaned, but this is belt-and-suspenders).
                raise RuntimeError(
                    f"I-00062: per-worktree DB compose stack is up for "
                    f"{worktree_info.get('batch_item_id')} but credentials are "
                    f"incomplete (host={bool(db_host)}, port={bool(db_port)}, "
                    f"name={bool(db_name)}, user={bool(db_user)}, "
                    f"password={bool(db_password)}). Refusing to launch."
                )
        # Always inject IW_STEP_ID and IW_ITEM_ID so agents can call
        # `iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID"` without hardcoding.
        agent_env["IW_STEP_ID"] = step.step_id
        agent_env["IW_ITEM_ID"] = step.work_item_id
        # F-00081: belt-and-suspenders env vars in case the CLI flag is silently ignored.
        # The daemon always passes --model <resolved_model> via the launch command;
        # these are secondary fallbacks.
        agent_env["OPENCODE_MODEL"] = resolved_model
        agent_env["ANTHROPIC_MODEL"] = resolved_model

        proc_env = agent_env

        with log_file.open("w") as log_fh:
            proc = subprocess.Popen(  # noqa: S602  # nosec B602
                command,
                shell=True,  # nosec B602  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — trusted agent-launch command built from server-side step config, no untrusted input on argv
                cwd=worktree_path,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach: daemon restart won't kill agents
                env=proc_env,
            )

        now = datetime.now(UTC)

        # AC2 (CR-00056): snapshot the prompt content into StepRun.prompt_text.
        # None for QV-gate steps (direct-command path, no prompt_file).
        # IO errors are swallowed — the column stays NULL and the step proceeds.
        prompt_text_val: str | None = None
        if "prompt" in dir() and prompt:
            prompt_text_val = prompt
        elif prompt_file is not None and prompt_file.exists():
            try:
                prompt_text_val = prompt_file.read_text()
            except (OSError, UnicodeDecodeError):
                logger.warning(
                    "[%s] Could not read prompt file for %s/%s: %s",
                    self.project_id,
                    step.work_item_id,
                    step.step_id,
                    str(prompt_file),
                )

        run = StepRun(
            step_id=step.id,
            run_number=run_number,
            status=RunStatus.running,
            pid=proc.pid,
            pid_alive=True,
            command=command,
            worktree_path=worktree_path,
            cli_tool=resolved_cli_tool,
            agent_runtime_option_id=runtime_option.id,
            log_file=str(log_file),
            started_at=now,
            last_heartbeat=now,
            timeout_secs=timeout,
            prompt_text=prompt_text_val,
        )
        db.add(run)

        step.status = StepStatus.in_progress
        step.started_at = now

        # Transition work item approved → in_progress on first step launch
        work_item = (
            db.query(WorkItem).filter_by(project_id=self.project_id, id=step.work_item_id).first()
        )
        if work_item and work_item.status == WorkItemStatus.approved:
            work_item.status = WorkItemStatus.in_progress

        db.commit()

        _emit_event(
            db,
            self.project_id,
            "step_launched",
            step.work_item_id,
            "work_item",
            f"Step {step.step_id} launched (PID {proc.pid})",
            {"step_id": step.step_id, "pid": proc.pid, "timeout_secs": timeout},
        )
        logger.info(
            "[%s] Launched step %s/%s (PID %d, timeout %ds)",
            self.project_id,
            step.work_item_id,
            step.step_id,
            proc.pid,
            timeout,
        )

    def _build_claude_prompt(self, step: WorkflowStep, worktree_path: str) -> str:
        """Build a direct prompt for claude that includes step instructions.

        DB-first per CR-00023: prefers the WorkflowStep columns (prompt_file,
        command, gate, description) and falls back to the on-disk manifest
        only for legacy items registered before those columns existed.
        """
        item_id = step.work_item_id
        step_id = step.step_id
        design_dir = Path(worktree_path) / "ai-dev" / "active" / item_id

        prompt_content = ""

        # CR-00023: DB-first — qv-gate steps read command from the row.
        if step.command:
            gate_name = step.gate or step_id
            description = step.description or ""
            prompt_content = (
                f"Run the following quality gate and report results.\n\n"
                f"**Gate**: {gate_name}\n"
                f"**Command**: `{step.command}`\n"
                f"**Description**: {description}\n\n"
                f"Execute exactly: `{step.command}`\n"
                f"Capture the output. If exit code is 0, the gate passed. "
                f"Otherwise it failed.\n"
                f"Report PASS or FAIL with the relevant output.\n"
                f"Do NOT call `iw step-start`, `iw step-done`, or `iw step-fail` — "
                f"those are handled by the orchestrator."
            )
        elif step.prompt_file:
            prompt_path = design_dir / step.prompt_file
            if prompt_path.exists():
                prompt_content = prompt_path.read_text()

        # Legacy fallback: manifest read for items registered before CR-00023.
        if not prompt_content:
            manifest_path = design_dir / "workflow-manifest.json"
            if manifest_path.exists():
                import json  # noqa: PLC0415

                manifest = json.loads(manifest_path.read_text())
                for s in manifest.get("steps", []):
                    if s.get("step") == step_id:
                        prompt_rel = s.get("prompt", "")
                        if prompt_rel:
                            prompt_path = design_dir / prompt_rel
                            if prompt_path.exists():
                                prompt_content = prompt_path.read_text()
                        elif s.get("command"):
                            gate_cmd = s["command"]
                            gate_name = s.get("gate", step_id)
                            description = s.get("description", "")
                            prompt_content = (
                                f"Run the following quality gate and report results.\n\n"
                                f"**Gate**: {gate_name}\n"
                                f"**Command**: `{gate_cmd}`\n"
                                f"**Description**: {description}\n\n"
                                f"Execute exactly: `{gate_cmd}`\n"
                                f"Capture the output. If exit code is 0, the gate passed. "
                                f"Otherwise it failed.\n"
                                f"Report PASS or FAIL with the relevant output.\n"
                                f"Do NOT call `iw step-start`, `iw step-done`, or `iw step-fail` — "
                                f"those are handled by the orchestrator."
                            )
                        break

        if not prompt_content:
            prompt_content = (
                f"Execute step {step_id} for work item {item_id}. "
                f"Check ai-dev/active/{item_id}/ for design docs and instructions."
            )

        report_dir = f"ai-dev/active/{item_id}/reports"
        report_file = f"{report_dir}/{item_id}_{step_id}_{step.agent_label}_report.md"
        return (
            f"You are executing step {step_id} for work item {item_id}.\n\n"
            f"## Step Instructions\n\n{prompt_content}\n\n"
            f"## Lifecycle Commands\n\n"
            f"When you START working on this step, run:\n"
            f"```bash\nuv run iw step-start {item_id} --step {step_id}\n```\n\n"
            f"When you COMPLETE this step successfully:\n"
            f"1. Write a brief markdown report to `{report_file}` summarising:\n"
            f"   - What was done\n"
            f"   - Files changed\n"
            f"   - Test results (if applicable)\n"
            f"   - Any issues or observations\n"
            f"2. Run:\n"
            f"```bash\nmkdir -p {report_dir}\n"
            f"uv run iw step-done {item_id} --step {step_id} --report {report_file}\n```\n\n"
            f"If this step FAILS, run:\n"
            f"```bash\nuv run iw step-fail {item_id} --step {step_id} "
            f'--reason "brief reason"\n```\n\n'
            f"IMPORTANT: You MUST call step-done (with --report) or step-fail before exiting."
        )

    # ------------------------------------------------------------------
    # Item / batch completion
    # ------------------------------------------------------------------

    def _complete_item(self, db: Session, item_id: str) -> None:
        """Mark work item and batch_item as completed; merge queue picks it up."""
        now = datetime.now(UTC)

        item = (
            db.query(WorkItem)
            .filter(WorkItem.project_id == self.project_id, WorkItem.id == item_id)
            .one()
        )
        item.status = WorkItemStatus.completed
        item.completed_at = now

        batch_item = (
            db.query(BatchItem)
            .filter(
                BatchItem.project_id == self.project_id,
                BatchItem.work_item_id == item_id,
                BatchItem.status == BatchItemStatus.executing,
            )
            .first()
        )
        if batch_item is not None:
            # CR-00036: gate — load the parent batch to check auto_merge
            batch = db.get(Batch, (self.project_id, batch_item.batch_id))
            if batch is not None and not batch.auto_merge:
                batch_item.status = BatchItemStatus.awaiting_merge_approval
                db.commit()
                _emit_event(
                    db,
                    self.project_id,
                    "batch_item_awaiting_merge_approval",
                    item_id,
                    "work_item",
                    f"All steps done for {item_id} — awaiting operator merge approval",
                    {"batch_id": batch_item.batch_id, "work_item_id": item_id},
                )
                logger.info(
                    "[%s] Item %s completed — awaiting merge approval (auto_merge=false)",
                    self.project_id,
                    item_id,
                )
            else:
                batch_item.status = BatchItemStatus.completed
                db.commit()
                _emit_event(
                    db,
                    self.project_id,
                    "item_completed",
                    item_id,
                    "work_item",
                    f"All steps done for {item_id} — entering merge queue",
                )
                logger.info("[%s] Item %s completed — queued for merge", self.project_id, item_id)

    def _check_batch_completion(self, db: Session, batch: Batch, items: list[BatchItem]) -> None:
        """Transition batch to completed or completed_with_errors when all items are done."""
        statuses = [i.status for i in items]
        now = datetime.now(UTC)

        if all(s == BatchItemStatus.merged for s in statuses):
            batch.status = BatchStatus.completed
            batch.completed_at = now
            db.commit()
            _emit_event(
                db,
                self.project_id,
                "batch_completed",
                batch.id,
                "batch",
                f"Batch {batch.id} completed — all items merged",
            )
            logger.info("[%s] Batch %s completed", self.project_id, batch.id)

        elif all(
            s in (BatchItemStatus.merged, BatchItemStatus.failed, BatchItemStatus.skipped)
            for s in statuses
        ):
            batch.status = BatchStatus.completed_with_errors
            batch.completed_at = now
            db.commit()
            failed = [i.work_item_id for i in items if i.status == BatchItemStatus.failed]
            _emit_event(
                db,
                self.project_id,
                "batch_completed_with_errors",
                batch.id,
                "batch",
                f"Batch {batch.id} done with errors: {failed}",
                {"failed_items": failed},
            )
            logger.warning(
                "[%s] Batch %s completed with errors: %s", self.project_id, batch.id, failed
            )


# ---------------------------------------------------------------------------
# Module-level helpers (pure / easily testable)
# ---------------------------------------------------------------------------

_WORKTREE_PLACEHOLDER_RE = re.compile(r"\$\{((?:WORKTREE_|BATCH_|PROJECT_)[A-Z_]+)\}")


class UnresolvedWorktreePlaceholderError(ValueError):
    """Raised when a ${WORKTREE_*} placeholder cannot be resolved for a legacy item."""


def substitute_worktree_placeholders(
    prompt: str,
    worktree_info: dict[str, Any],
) -> str:
    """Replace ${WORKTREE_*} placeholders in prompt with values from worktree_info.

    Substitutes the following placeholders when the corresponding value is set:
        ${WORKTREE_APP_PORT}   → str(worktree_info["worktree_app_port"])
        ${WORKTREE_DB_PORT}    → str(worktree_info["worktree_db_port"])
        ${WORKTREE_PATH}       → str(worktree_info["worktree_path"])
        ${BATCH_ITEM_ID}       → str(worktree_info["batch_item_id"])
        ${PROJECT_NAME}        → str(worktree_info["project_name"])

    For legacy-mode items (worktree_compose_path is None), placeholders are left
    untouched so prompts can use safe defaults. However, if a prompt contains a
    ${WORKTREE_*} placeholder for a legacy item, a clear error is raised to
    prompt the operator to add iw-config or fix the prompt.

    Unknown placeholders (not in the known set above) are preserved verbatim.
    """

    def _replace(m: re.Match[str]) -> str:
        """Substitute a single placeholder match with its resolved value.

        Handles the known WORKTREE_*/BATCH_*/PROJECT_* keys, raises
        UnresolvedWorktreePlaceholderError for WORKTREE_* keys on legacy
        (no-compose) items, and returns the original match text for unknown keys.
        """
        key = m.group(1)
        known_keys = (
            "WORKTREE_APP_PORT",
            "WORKTREE_DB_PORT",
            "WORKTREE_PATH",
            "BATCH_ITEM_ID",
            "PROJECT_NAME",
        )
        if key not in known_keys:
            return m.group(0)

        is_worktree_placeholder = key.startswith("WORKTREE_")
        is_legacy = worktree_info.get("worktree_compose_path") is None

        if is_legacy and is_worktree_placeholder:
            raise UnresolvedWorktreePlaceholderError(
                f"Prompt contains ${{{key}}} but item is running in legacy mode "
                f"(no per-worktree compose stack). Add ai-dev/iw-config/ to the "
                f"project or remove this placeholder from the prompt."
            )

        value = worktree_info.get(key.lower())
        if value is None:
            return m.group(0)
        return str(value)

    return _WORKTREE_PLACEHOLDER_RE.sub(_replace, prompt)


# Max bytes for a prompt that is later embedded on a shell command line as
# ``"$(cat <file>)"`` (the form both _launch_step and fix_cycle._launch_fix_agent
# use). Linux's MAX_ARG_STRLEN caps a *single* argv element at 128 KiB; a prompt
# larger than that makes ``execve`` fail with E2BIG ("Argument list too long")
# and the agent process never starts. Cap well below it.
#
# Diagnosed in I-00074: a QV fix-cycle prompt that embedded a full ``pytest -v``
# dump (~2700 PASSED lines routed to the "unparseable" bucket) was ~349 KB, so
# every one of the 5 fix cycles died on launch with
# ``bash: line 1: /usr/bin/timeout: Argument list too long`` and the item ground
# to ``failed``. parse_pytest now keeps that output small; this is the belt-and-
# suspenders cap so no future bloat source can re-trigger E2BIG.
MAX_PROMPT_BYTES = 96 * 1024


def write_agent_prompt(path: Path, text: str) -> None:
    """Write an agent prompt file, truncating its middle if it would overflow execve.

    The file is consumed as ``"$(cat <path>)"`` on a shell command line, so it
    must stay under :data:`MAX_PROMPT_BYTES`. When it doesn't, keep the head
    (task framing) and tail (usually the actionable summary), drop the middle,
    and log a warning so the bloat source is visible in the daemon log.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_PROMPT_BYTES:
        path.write_text(text, encoding="utf-8")
        return
    marker = (
        f"\n\n...[prompt truncated: {len(encoded)} bytes exceeds the "
        f"{MAX_PROMPT_BYTES}-byte launch-argument limit; middle removed — see the "
        f"step log for the full gate output]...\n\n"
    )
    keep = max(0, (MAX_PROMPT_BYTES - len(marker.encode("utf-8"))) // 2)
    head = encoded[:keep].decode("utf-8", errors="ignore")
    tail = encoded[-keep:].decode("utf-8", errors="ignore") if keep else ""
    logger.warning(
        "Agent prompt %s truncated from %d to ~%d bytes (execve arg limit)",
        path,
        len(encoded),
        MAX_PROMPT_BYTES,
    )
    path.write_text(head + marker + tail, encoding="utf-8")


def _agent_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build the env for any subprocess that runs agent or QV-gate code.

    Strips the daemon's allow-list flags so the child cannot bypass the
    live-DB guard, then arms agent context. Any caller that needs more
    vars (e.g. browser env, per-worktree DB ports) merges them via `extra`.

    See I-00041 for context. The leak this prevents was the proximate
    cause of the 4-hour dashboard outage on 2026-04-26.
    """
    import os  # noqa: PLC0415

    env = os.environ.copy()
    # Strip allow-list flags — agents are NEVER trusted to write to live DB.
    env.pop("IW_CORE_DAEMON_CONTEXT", None)
    env.pop("IW_CORE_OPERATOR_APPLY", None)
    # Agents run inside worktrees that have their own .venv; inheriting the
    # daemon's VIRTUAL_ENV (pointing at the main repo's .venv) causes uv to
    # emit a mismatch warning on every invocation.
    env.pop("VIRTUAL_ENV", None)

    # I-00062: BEFORE stripping IW_CORE_DB_*, snapshot the daemon's orch DB
    # values into IW_CORE_ORCH_DB_*. This generalises the snapshot that
    # orch.daemon.browser_env._build_env already does for browser-
    # verification steps to ALL agent launches, so the fail-fast guard in
    # orch/config.py (Layer 3) always has a known orch reference to compare
    # IW_CORE_DB_PORT against — including for legacy (no-compose-stack)
    # worktrees whose .env still carries IW_CORE_DB_PORT=5433.
    for src, dst in (
        ("IW_CORE_DB_HOST", "IW_CORE_ORCH_DB_HOST"),
        ("IW_CORE_DB_PORT", "IW_CORE_ORCH_DB_PORT"),
        ("IW_CORE_DB_NAME", "IW_CORE_ORCH_DB_NAME"),
        ("IW_CORE_DB_USER", "IW_CORE_ORCH_DB_USER"),
        ("IW_CORE_DB_PASSWORD", "IW_CORE_ORCH_DB_PASSWORD"),
    ):
        val = env.get(src)
        # setdefault: if a caller (or browser_env) has already injected
        # IW_CORE_ORCH_DB_*, do NOT overwrite it.
        if val:
            env.setdefault(dst, val)

    # I-00062: strip IW_CORE_DB_* so agents cannot inherit credentials for
    # the daemon's source-of-truth DB. Per-worktree DB env is injected
    # explicitly in _launch_step when the worktree has a compose stack;
    # otherwise the agent sources values from its worktree's .env via
    # load_dotenv (and the Layer 3 guard catches a legacy mirror of
    # IW_CORE_DB_PORT=5433 because of the snapshot above).
    for key in (
        "IW_CORE_DB_HOST",
        "IW_CORE_DB_PORT",
        "IW_CORE_DB_NAME",
        "IW_CORE_DB_USER",
        "IW_CORE_DB_PASSWORD",
    ):
        env.pop(key, None)

    # Arm refused-context for the child.
    env["IW_CORE_AGENT_CONTEXT"] = "true"
    if extra:
        env.update(extra)
    return env


def _build_agent_env(cli_tool: str, item_id: str, worktree_path: str) -> dict[str, str]:  # noqa: ARG001
    """Build the subprocess environment for an agent launch.

    Inherits the current process environment so PATH, credentials, and
    IW_CORE_* vars are available to the agent.  cli_tool / item_id are
    accepted for call-site symmetry but not currently used.
    """
    return _agent_subprocess_env()


def _current_execution_group(items: list[BatchItem]) -> int | None:
    """Return the lowest execution_group with non-terminal items, or None."""
    # CR-00028: merge_failed, migration_invalid, and migration_rebase_failed are treated as
    # non-terminal so a group containing one of these statuses keeps its execution_group open —
    # dependents in later groups stay paused (not cascaded) until the operator retries or abandons.
    for item in sorted(items, key=lambda i: i.execution_group):
        if item.status in (
            BatchItemStatus.pending,
            BatchItemStatus.setting_up,
            BatchItemStatus.executing,
            BatchItemStatus.completed,
            BatchItemStatus.merging,
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ):
            return item.execution_group
    return None


def _next_run_number(db: Session, step: WorkflowStep) -> int:
    """Return the next run_number for a step (existing count + 1)."""
    count = db.query(StepRun).filter(StepRun.step_id == step.id).count()
    return count + 1


# CR-00065 / BATCH-00122 incident (2026-05-20): the `pi` CLI (<=0.75.x) has no
# project-root flag and no environment block. Its only signal for "where am I"
# is AGENTS.md / CLAUDE.md discovery, which walks *up* the directory tree with
# no worktree boundary. Worktrees are created nested inside the project repo
# (`<repo>/.worktrees/<item>/`), so pi also finds the parent repo's CLAUDE.md
# and reports the *main checkout* as the project root — the agent then edits
# the main working tree instead of its own worktree. opencode and claude anchor
# on their launch cwd and are unaffected.
_PI_WORKTREE_PIN_TEXT = (
    "WORKTREE ISOLATION (IW AI Core): your current working directory is the "
    "root of your project and it is a git worktree. Every file you read, "
    "write, edit, or run a shell command against MUST stay inside this "
    "working directory. Never cd to, read, or write any path outside it. A "
    "separate checkout of this same repository may exist at a parent or "
    "sibling path on disk; it is NOT your project. Ignore it entirely and use "
    "paths relative to your working directory."
)
# Absolute path (via _EXECUTOR_DIR) so the guard resolves regardless of the
# step's cwd. A worktree-relative "executor/..." only existed in iw-ai-core's
# OWN worktree, so every other project's Pi step crashed (file not found).
_PI_NARRATION_GUARD_SCRIPT = str(_EXECUTOR_DIR / "pi_narration_guard.py")


def _pi_worktree_isolation_args(worktree_path: str) -> str:
    """Return extra ``pi`` flags that pin the agent to ``worktree_path``.

    ``--no-context-files`` disables pi's own (worktree-unaware) AGENTS.md /
    CLAUDE.md discovery; the worktree's own CLAUDE.md / AGENTS.md are then
    re-injected verbatim via ``--append-system-prompt`` so project guidance is
    preserved without leaking the main-repo path; a final ``--append-system-
    prompt`` carries the explicit working-directory pin. See
    ``_PI_WORKTREE_PIN_TEXT`` for the incident this prevents.

    Every argument is ``shlex.quote``-d so the fragment is safe to splice into
    the ``"$(cat …)"``-style shell command line the daemon launches.
    """
    parts = ["--no-context-files"]
    worktree = Path(worktree_path)
    for ctx_name in ("CLAUDE.md", "AGENTS.md"):
        ctx_file = worktree / ctx_name
        if ctx_file.is_file():
            parts.append(f"--append-system-prompt {shlex.quote(str(ctx_file))}")
    parts.append(f"--append-system-prompt {shlex.quote(_PI_WORKTREE_PIN_TEXT)}")
    return " ".join(parts)


def _build_initial_command(
    cli_tool: str,
    prompt_file: str,
    resolved_model: str,
    worktree_path: str,
    item_id: str = "",
    step_id: str = "",
    agent_args: str = "",
) -> str:
    """Build the shell command launched for a step's initial agent run.

    Keep in sync with ``fix_cycle._build_fix_inner_command`` — they encode the
    same per-runtime argv shape and any drift between them re-creates I-00074.
    """
    if cli_tool == "opencode":
        return (
            f'opencode run "$(cat {prompt_file})" --model {resolved_model} '
            f"--dangerously-skip-permissions {agent_args}"
        ).strip()
    if cli_tool == "claude":
        return (
            f'claude -p "$(cat {prompt_file})" --model {resolved_model} '
            f"--dangerously-skip-permissions"
        )
    if cli_tool == "pi":
        # CR-00062: pi.dev print-mode mirrors `claude -p`. Pi gates capabilities
        # via extension permissions, not a CLI switch — so no
        # `--dangerously-skip-permissions` / `--permission-mode bypassPermissions`
        # flag. See R-00072 §7.
        # CR-00065 follow-up: pin pi to its worktree (see _pi_worktree_isolation_args).
        base_pi_cmd = (
            f'pi -p "$(cat {prompt_file})" --model {resolved_model} '
            f"{_pi_worktree_isolation_args(worktree_path)}"
        )
        # I-00114/S03: guard is only usable when both IDs are present.
        # Keep the legacy bare-pi shape for helper/test call-sites that omit IDs.
        if not item_id or not step_id:
            return base_pi_cmd
        return (
            f"python {_PI_NARRATION_GUARD_SCRIPT} "
            f"--item-id {shlex.quote(item_id)} --step-id {shlex.quote(step_id)} "
            f"--max-reprompts 5 -- "
            f"{base_pi_cmd}"
        )
    raise ValueError(f"Unknown cli_tool: {cli_tool!r}")


def _build_qv_direct_command(
    item_id: str,
    step_id: str,
    gate_name: str,
    gate_command: str,
    agent_label: str,
    worktree_path: str,
) -> str:
    """Build the launch command for a quality_validation step that runs without an LLM.

    Writes two helper scripts under ``<worktree>/.tmp/`` and returns the
    shell command that invokes the wrapper:

      - ``<item>_<step>.qv-gate.sh``  — the gate command, verbatim.
      - ``<item>_<step>.qv-wrap.sh``  — runs the gate, writes a QvGate-format
        report, and finalises the step via ``iw step-done`` / ``iw step-fail``.

    The wrapper preserves the existing StepRun lifecycle (PID monitoring,
    timeouts, log capture, fix cycle) — only the LLM is removed.
    """
    worktree = Path(worktree_path)
    tmp_dir = worktree / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    gate_script = tmp_dir / f"{item_id}_{step_id}.qv-gate.sh"
    gate_script.write_text(f"#!/usr/bin/env bash\n{gate_command}\n")
    gate_script.chmod(0o755)
    gate_script_rel = str(gate_script.relative_to(worktree))

    report_dir_rel = f"ai-dev/active/{item_id}/reports"
    report_file_rel = f"{report_dir_rel}/{item_id}_{step_id}_{agent_label}_report.md"

    wrap_script = tmp_dir / f"{item_id}_{step_id}.qv-wrap.sh"
    wrap_script_rel = str(wrap_script.relative_to(worktree))

    item_q = shlex.quote(item_id)
    step_q = shlex.quote(step_id)
    gate_name_q = shlex.quote(gate_name)
    gate_disp_q = shlex.quote(gate_command)
    report_dir_q = shlex.quote(report_dir_rel)
    report_file_q = shlex.quote(report_file_rel)
    gate_script_q = shlex.quote(gate_script_rel)

    wrapper = rf"""#!/usr/bin/env bash
# QV direct-exec wrapper for {item_id} {step_id} ({gate_name}).
# Auto-generated by orch.daemon.batch_manager — do not edit by hand.
# Runs the gate, writes a QvGate-format report, and finalises the step
# via `iw step-done` or `iw step-fail`. No LLM is involved.

ITEM_ID={item_q}
STEP_ID={step_q}
GATE_NAME={gate_name_q}
GATE_DISPLAY={gate_disp_q}
REPORT_DIR={report_dir_q}
REPORT_FILE={report_file_q}
GATE_SCRIPT={gate_script_q}

mkdir -p "$REPORT_DIR"
RAW_LOG=$(mktemp)
START_TS=$(date +%s)

bash "$GATE_SCRIPT" >"$RAW_LOG" 2>&1
RC=$?

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))
TAIL_OUTPUT=$(tail -200 "$RAW_LOG" 2>/dev/null || true)
cat "$RAW_LOG"
rm -f "$RAW_LOG"

if [ "$RC" -eq 0 ]; then
    RESULT=PASS
    VERDICT=pass
else
    RESULT=FAIL
    VERDICT=fail
fi

cat > "$REPORT_FILE" <<REPORTEOF
# $ITEM_ID $STEP_ID QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | $GATE_NAME      |
| Command      | \`$GATE_DISPLAY\` |
| Exit code    | $RC             |
| Result       | $RESULT         |
| Duration (s) | $DURATION       |

## Output (tail)

\`\`\`
$TAIL_OUTPUT
\`\`\`

## Verdict

\`\`\`
$VERDICT
\`\`\`
REPORTEOF

if [ "$RC" -eq 0 ]; then
    uv run iw step-done "$ITEM_ID" --step "$STEP_ID" --report "$REPORT_FILE"
else
    uv run iw step-fail "$ITEM_ID" --step "$STEP_ID" \
        --reason "$GATE_NAME failed: exit=$RC" --report "$REPORT_FILE"
fi

exit $RC
"""
    wrap_script.write_text(wrapper)
    wrap_script.chmod(0o755)

    return f"bash {shlex.quote(wrap_script_rel)}"


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
