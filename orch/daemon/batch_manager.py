"""BatchManager — per-project batch orchestration.

Handles the full lifecycle of batch execution:
  approved → executing → (item setup → step launch → step completion) → merge queue
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.daemon import worktree_compose
from orch.db.alembic_guard import check_db_at_head, remediation_message
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
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
    # Batch processing
    # ------------------------------------------------------------------

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

        current_group = _current_execution_group(items)
        if current_group is None:
            # All items in terminal state — check if batch is done
            self._check_batch_completion(db, batch, items)
            return

        # Block the current group from launching if any earlier group has failed items.
        # A failed dependency means successor items cannot safely proceed.
        failed_in_prior_group = any(
            i.status == BatchItemStatus.failed and i.execution_group < current_group for i in items
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
                "[%s] Batch %s: dependency failure blocks group %d — marking pending items failed",
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
            if executing_count >= batch.max_parallel:
                break
            self._launch_item(db, item)
            executing_count += 1

    def _check_executing_item(self, db: Session, batch_item: BatchItem) -> None:
        """Detect whether the agent finished a step and advance if so."""
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

            # Step failed — attempt a fix cycle if the step type supports it
            from orch.daemon import fix_cycle  # noqa: PLC0415

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
                logger.warning(
                    "[%s] Step %s/%s failed and cannot be auto-recovered — needs human review",
                    self.project_id,
                    batch_item.work_item_id,
                    has_failed.step_id,
                )
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

        # Phase 1b: Compose lifecycle (opt-in per worktree)
        if not worktree_compose.has_iw_config(worktree_path):
            batch_item.worktree_db_port = None
            batch_item.worktree_app_port = None
            batch_item.worktree_compose_path = None
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
                else:
                    batch_item.status = BatchItemStatus.setup_failed
                    batch_item.notes = f"Compose up failed: {up_result.error_message}"
                    batch_item.worktree_db_port = None
                    batch_item.worktree_app_port = None
                    batch_item.worktree_compose_path = None
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
            GATE_PARSERS,
            fingerprint_to_jsonable,
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

            parser = GATE_PARSERS.get(gate)
            if parser is None:
                logger.warning(
                    "[F-00061] Unknown gate '%s' for step %s/%s — skipping baseline",
                    gate,
                    item_id,
                    step.step_id,
                )
                continue

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
            result = subprocess.run(
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
        """Run a gate command and return combined stdout+stderr."""
        result = subprocess.run(  # noqa: S602
            command,
            shell=True,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=300,
            env=_agent_subprocess_env(),
        )
        return result.stdout + result.stderr

    def _upsert_qv_baseline(
        self,
        db: Session,
        step_id: int,
        gate_name: str,
        base_sha: str,
        fingerprint: dict[str, object],
    ) -> None:
        """Upsert a QvBaseline row (on conflict, update fingerprint + computed_at)."""
        from sqlalchemy import text

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
                {"fingerprint": fingerprint, "computed_at": now, "id": existing},
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
        from orch.daemon import browser_env  # noqa: PLC0415
        from orch.daemon.step_monitor import get_timeout  # noqa: PLC0415

        worktree_path = worktree_info.get("path", "")
        cli_tool = self.project_config.cli_tool

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
                    if log_path and log_path.exists():
                        lines = log_path.read_text(errors="replace").splitlines()
                        log_tail = "\n".join(lines[-20:])
                    run_number = _next_run_number(db, step)
                    error_msg = f"browser env setup failed: {log_tail}"
                    run = StepRun(
                        step_id=step.id,
                        run_number=run_number,
                        status=RunStatus.failed,
                        error_message=error_msg,
                        worktree_path=worktree_path,
                        cli_tool=cli_tool,
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
                    return
                agent_env = bv_env

        # Build prompt from the step's manifest prompt file (shared by all CLI tools)
        prompt = self._build_claude_prompt(step, worktree_path)
        if agent_env is not None:
            prompt = browser_env.render_prompt_substitutions(prompt, agent_env)
        prompt = substitute_worktree_placeholders(prompt, worktree_info)
        prompt_file = Path(worktree_path) / ".tmp" / f"{step.work_item_id}_{step.step_id}.prompt"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt)

        if cli_tool == "opencode":
            agent_name = step.opencode_agent or step.agent_label
            agent_args = f"--agent {agent_name}" if agent_name else ""
            command = (
                f'opencode run "$(cat {prompt_file})" --dangerously-skip-permissions {agent_args}'
            ).strip()
        else:
            command = f'claude -p "$(cat {prompt_file})" --dangerously-skip-permissions'

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

        proc_env = agent_env

        with log_file.open("w") as log_fh:
            proc = subprocess.Popen(  # noqa: S602
                command,
                shell=True,
                cwd=worktree_path,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach: daemon restart won't kill agents
                env=proc_env,
            )

        now = datetime.now(UTC)
        run = StepRun(
            step_id=step.id,
            run_number=run_number,
            status=RunStatus.running,
            pid=proc.pid,
            pid_alive=True,
            command=command,
            worktree_path=worktree_path,
            cli_tool=cli_tool,
            log_file=str(log_file),
            started_at=now,
            last_heartbeat=now,
            timeout_secs=timeout,
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
    for item in sorted(items, key=lambda i: i.execution_group):
        if item.status in (
            BatchItemStatus.pending,
            BatchItemStatus.setting_up,
            BatchItemStatus.executing,
            BatchItemStatus.completed,
        ):
            return item.execution_group
    return None


def _next_run_number(db: Session, step: WorkflowStep) -> int:
    """Return the next run_number for a step (existing count + 1)."""
    count = db.query(StepRun).filter(StepRun.step_id == step.id).count()
    return count + 1


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
