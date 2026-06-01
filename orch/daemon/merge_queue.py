"""Merge queue — sequential squash-merges of completed batch items.

Called every poll cycle for each project. Merges one item at a time
(the oldest completed item) to keep git history linear and conflict-free.

Migration pipeline integration (CR-00017):
- Before any merge cycle: check is_merge_queue_frozen() — if frozen, skip entirely.
- Before squash-merge: run_pre_merge_dry_run() (Phase 1) — on fail, mark MIGRATION_INVALID.
- After squash-merge: run_post_merge_apply() (Phase 2). On fail *after* one or
  more revisions were applied → run_rollback() (Phase 3). On fail *before* any
  revision was applied (SelfBlockerError, lock timeout, …) → defer; do NOT roll
  back — a `downgrade -1` would clobber a previously-applied migration (the
  post-merge rollback regression seen after the BATCH-00089 merge, 2026-05-11).
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.auto_merge_aggregator import resolve_project_config
from orch.daemon import auto_merge, worktree_compose
from orch.daemon.migration_pipeline import (
    is_merge_queue_frozen,
    run_post_merge_apply,
    run_pre_merge_dry_run,
    run_rollback,
)
from orch.daemon.migration_rebase import run_pre_merge_rebase
from orch.db.models import BatchItem, BatchItemStatus, DaemonEvent, WorkItem, WorkItemStatus
from orch.utils.branch_resolver import resolve_branch_for_project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# Executor scripts: iw-ai-core/executor/
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"

# Maximum bytes kept in merge_info["stdout"] for audit log
_MERGE_INFO_STDOUT_LIMIT = 8000

# F-00076: capture conflict file list emitted by worktree_commit.sh after
# auto-resolving rebase conflicts.
_CONFLICT_MARKER_RE = re.compile(
    r"^\[worktree_commit\] CONFLICT_FILES (\[.*\])$",
    re.MULTILINE,
)

# Statuses an operator can recover from via retry-merge / restart-merge.
# Cascade is NOT triggered for these — see CR-00028.
OPERATOR_RECOVERABLE_MERGE_STATUSES: frozenset[BatchItemStatus] = frozenset(
    {
        BatchItemStatus.merge_failed,
        BatchItemStatus.migration_invalid,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.migration_rolled_back,
    }
)


class MergeError(RuntimeError):
    """Raised when worktree_commit.sh exits non-zero."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def process_merge_queue(
    db: Session,
    project_id: str,
    project_config: ProjectConfig,
    config: DaemonConfig,  # noqa: ARG001  (reserved for future throttling)
) -> None:
    """Merge the oldest completed batch item, if no merge is already in progress."""
    if is_merge_queue_frozen(db):
        logger.debug("[%s] Merge queue is frozen — skipping this cycle", project_id)
        _emit_event(
            db,
            project_id,
            "merge_queue_frozen_skipped",
            None,
            None,
            "Merge queue is frozen — no merges processed",
        )
        db.commit()
        return

    # One merge at a time: bail if another is already running
    merging = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.status == BatchItemStatus.merging,
        )
        .first()
    )
    if merging:
        logger.debug(
            "[%s] Merge already in progress (batch_item %d) — waiting", project_id, merging.id
        )
        return

    # Find oldest completed item (ordered by started_at so first-in first-out)
    ready = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.status == BatchItemStatus.completed,
        )
        .order_by(BatchItem.started_at)
        .first()
    )
    if ready is None:
        return

    _merge_item(db, ready, project_id, project_config)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _revert_work_item(db: Session, project_id: str, item_id: str) -> None:
    """Revert WorkItem.status to failed and clear completed_at after a merge failure.

    Only touches the WorkItem if its current status is completed — guards against
    double-application and preserves any status already set by other code paths.
    """
    work_item = db.query(WorkItem).filter_by(project_id=project_id, id=item_id).one_or_none()
    if work_item is not None and work_item.status == WorkItemStatus.completed:
        work_item.status = WorkItemStatus.failed
        work_item.completed_at = None


def _merge_item(
    db: Session,
    batch_item: BatchItem,
    project_id: str,
    project_config: ProjectConfig,
) -> None:
    """Squash-merge a completed item's branch to main via worktree_commit.sh."""
    from orch.daemon.batch_merge_hooks import trigger_doc_regeneration_on_merge
    from orch.db.models import Project

    item_id = batch_item.work_item_id
    worktree_path = (batch_item.worktree_info or {}).get("path")

    if not worktree_path:
        # CR-00028: intentionally produce `failed` here (not `merge_failed`).
        # This branch indicates a data-integrity issue — no worktree was ever
        # recorded for this batch item. Keeping it as `failed` ensures the
        # cascade fires so the batch is correctly marked with a hard failure.
        batch_item.status = BatchItemStatus.failed
        batch_item.notes = "No worktree path recorded — cannot merge"
        db.commit()
        logger.error("[%s] Cannot merge %s: no worktree path", project_id, item_id)
        return

    batch_item.status = BatchItemStatus.merging
    db.commit()
    _emit_event(
        db,
        project_id,
        "merge_started",
        item_id,
        "work_item",
        f"Merging {item_id} from {worktree_path}",
    )
    logger.info("[%s] Merging %s (worktree: %s)", project_id, item_id, worktree_path)

    if batch_item.batch_id is not None:
        rebase_result = run_pre_merge_rebase(
            batch_item.batch_id, worktree_path, project_config.working_dir
        )
        if not rebase_result.success:
            batch_item.status = BatchItemStatus.migration_rebase_failed
            # `notes` is single-line for the badge/list views; keep it short.
            first_line = (rebase_result.error_message or "").splitlines()[0:1]
            short = first_line[0] if first_line else (rebase_result.message or "rebase failed")
            batch_item.notes = f"Pre-merge rebase failed: {short}"
            # `merge_info` is rendered in the Squash Merge log section — store the
            # full diagnostic so operators can read the actual git output.
            batch_item.merge_info = {
                "phase": "rebase",
                "success": False,
                "summary": rebase_result.message,
                "error_message": rebase_result.error_message,
                "worktree_base_sha": rebase_result.worktree_base_sha,
                "current_main_sha": rebase_result.current_main_sha,
            }
            # C4: revert WorkItem so it is not orphaned as completed
            _revert_work_item(db, project_id, item_id)
            db.commit()
            compose_path = (
                Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None
            )
            worktree_compose.down(str(batch_item.id), compose_path)
            _emit_event(
                db,
                project_id,
                "migration_pipeline",
                item_id,
                "work_item",
                f"Pre-merge rebase failed: {rebase_result.error_message}",
                {
                    "phase": "rebase",
                    "success": False,
                    "batch_id": batch_item.batch_id,
                    "worktree_base_sha": rebase_result.worktree_base_sha,
                    "current_main_sha": rebase_result.current_main_sha,
                },
            )
            logger.warning(
                "[%s] Pre-merge rebase failed for %s (batch %s): %s",
                project_id,
                item_id,
                batch_item.batch_id,
                rebase_result.error_message,
            )
            return

    # Phase 1: dry-run migration against testcontainer
    if batch_item.batch_id is not None:
        dry_result = run_pre_merge_dry_run(batch_item.batch_id, worktree_path=worktree_path)
        if not dry_result.success:
            batch_item.status = BatchItemStatus.migration_invalid
            batch_item.notes = f"Phase 1 dry-run failed: {dry_result.message}"
            # C4: revert WorkItem so it is not orphaned as completed
            _revert_work_item(db, project_id, item_id)
            db.commit()
            compose_path = (
                Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None
            )
            worktree_compose.down(str(batch_item.id), compose_path)
            _emit_event(
                db,
                project_id,
                "migration_pipeline",
                item_id,
                "work_item",
                f"Phase 1 dry-run failed: {dry_result.message}",
                {"phase": "dry_run", "success": False, "batch_id": batch_item.batch_id},
            )
            logger.warning(
                "[%s] Phase 1 dry-run failed for %s — batch item %s marked MIGRATION_INVALID",
                project_id,
                item_id,
                batch_item.batch_id,
            )
            return

    result: subprocess.CompletedProcess[str] | None = None
    conflict_files: list[str] = []  # defined before try so except block can reference

    # I-00126: resolve the project's default branch before merging.
    # Guard: refuse to merge if the repo's HEAD is not on that branch (exit 3).
    # This prevents silent wrong-branch merges (I-00126 root cause A).
    branch_info = resolve_branch_for_project(project_config.working_dir)
    if not branch_info.is_on_default:
        batch_item.status = BatchItemStatus.merge_failed
        batch_item.notes = (
            f"Repo HEAD is on '{branch_info.current_branch}', not the default branch "
            f"'{branch_info.default_branch}' — merge refused. Switch to the default branch "
            f"before merging."
        )
        db.commit()
        _emit_event(
            db,
            project_id,
            "merge_refused_wrong_branch",
            item_id,
            "work_item",
            batch_item.notes,
            {
                "item_id": item_id,
                "expected_branch": branch_info.default_branch,
                "actual_branch": branch_info.current_branch,
            },
        )
        logger.error(
            "[%s] Merge refused for %s: HEAD is on '%s', not '%s'",
            project_id,
            item_id,
            branch_info.current_branch,
            branch_info.default_branch,
        )
        return

    try:
        cmd = [
            "bash",
            str(_EXECUTOR_DIR / "worktree_commit.sh"),
            item_id,
            project_config.working_dir,
            branch_info.default_branch,
        ]  # noqa: S607
        # Pass scope-gate toggle and default branch via env. Default off —
        # projects opt in via .iw-orch.json {"scope_gate_enabled": true}.
        # See ProjectConfig.
        merge_env = {
            **os.environ,
            "IW_SCOPE_GATE_ENABLED": "true" if project_config.scope_gate_enabled else "false",
            "IW_DEFAULT_BRANCH": branch_info.default_branch,
        }
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=120, env=merge_env
        )
        # I-00126 guard: exit code 3 means worktree_commit.sh refused because
        # the repo was on the wrong branch (race between branch check above and
        # script execution). Surface clearly without marking merged.
        if result.returncode == 3:
            batch_item.status = BatchItemStatus.merge_failed
            batch_item.notes = (
                f"Merge refused: repo HEAD is not on the default branch "
                f"'{branch_info.default_branch}'."
            )
            db.commit()
            _emit_event(
                db,
                project_id,
                "merge_refused_wrong_branch",
                item_id,
                "work_item",
                batch_item.notes,
                {
                    "item_id": item_id,
                    "expected_branch": branch_info.default_branch,
                    "actual_branch": branch_info.current_branch,
                    "script_stderr": result.stderr[:500],
                },
            )
            logger.error(
                "[%s] worktree_commit.sh refused %s: exit 3 (wrong branch)",
                project_id,
                item_id,
            )
            return

        if result.returncode != 0:
            raise MergeError(result.stderr.strip() or f"exit code {result.returncode}")

        batch_item.status = BatchItemStatus.merged
        batch_item.merged_at = datetime.now(UTC)
        # M2: keep up to 8000 chars; flag when output was truncated
        stdout = result.stdout
        # F-00076: parse CONFLICT_FILES marker from worktree_commit.sh output
        m = _CONFLICT_MARKER_RE.search(stdout)
        if m:
            with suppress(_json.JSONDecodeError):
                conflict_files = _json.loads(m.group(1))
        batch_item.merge_info = {
            "stdout": stdout[:_MERGE_INFO_STDOUT_LIMIT],
            "stdout_truncated": len(stdout) > _MERGE_INFO_STDOUT_LIMIT,
            "conflict_files": conflict_files,
        }
        db.commit()
        _emit_event(
            db, project_id, "item_merged", item_id, "work_item", f"Merged {item_id} successfully"
        )
        logger.info("[%s] Merged %s", project_id, item_id)

        worktree_compose.down(
            str(batch_item.id),
            Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None,
        )
        _cleanup_worktree(item_id, worktree_path, project_config.working_dir)

        project = db.get(Project, project_id)
        if project is not None:
            trigger_doc_regeneration_on_merge(db, batch_item, project)

        # I-00063: Commit the orchestration session before Phase 2 to release
        # AccessShareLocks acquired by the reads above. Phase 2's ALTER TABLE
        # requires AccessExclusiveLock and would self-deadlock against our own
        # idle-in-transaction session.
        #
        # We commit but do NOT close: the caller (process_merge_queue → batch
        # manager) owns the session lifecycle via its own context manager, and
        # downstream tests pass in a long-lived fixture session that they
        # continue to use after _merge_item returns.
        #
        # We also capture batch_item.batch_id into a local primitive BEFORE
        # the commit. After commit the ORM object's attributes are expired
        # (default expire_on_commit=True), so accessing batch_item.batch_id
        # would trigger a refresh — opening a new transaction and re-acquiring
        # the share lock we just released. The whole point of the commit is
        # to NOT hold any locks during run_post_merge_apply().
        batch_id_for_apply = batch_item.batch_id
        db.commit()

        # F-00079: Capture aggregate diff from the squash commit (AC8).
        # Done after the main commit releases locks; re-queried WorkItem is fresh.
        # Must NOT roll back the merge if capture fails (Invariant 5).
        try:
            from orch.diff_service import (
                _git_diff_merge_commit,
                _git_rev_parse_head,
                parse_diff_summary,
            )

            work_item = (
                db.query(WorkItem).filter_by(project_id=project_id, id=item_id).one_or_none()
            )
            if work_item is not None and project is not None:
                head_sha = _git_rev_parse_head(project.repo_root)
                diff_text = (
                    _git_diff_merge_commit(project.repo_root, head_sha) if head_sha else None
                )
                if diff_text:
                    work_item.diff_text = diff_text
                    work_item.diff_summary = parse_diff_summary(diff_text)
                    work_item.merge_commit_sha = head_sha
                    db.commit()
        except Exception:
            logger.warning(
                "[%s] merge_queue: aggregate diff capture failed for %s",
                project_id,
                item_id,
                exc_info=True,
            )
            _emit_event(
                db,
                project_id,
                "diff_capture_failed",
                item_id,
                "work_item",
                f"Aggregate diff capture failed for {item_id}",
                {"item_id": item_id},
            )
            db.commit()

        # Phase 2: apply migrations to live DB
        if batch_id_for_apply is not None:
            apply_result = run_post_merge_apply(batch_id_for_apply)
            if not apply_result.success and apply_result.revisions_applied:
                # A migration actually started applying and then failed —
                # Phase 3 rollback is warranted.
                logger.warning(
                    "[%s] Phase 2 apply failed for batch %s after applying %s — running rollback",
                    project_id,
                    batch_id_for_apply,
                    apply_result.revisions_applied,
                )
                rollback_result = run_rollback(batch_id_for_apply)
                _emit_event(
                    db,
                    project_id,
                    "migration_pipeline",
                    item_id,
                    "work_item",
                    f"Phase 2 apply failed, rollback result: {rollback_result.message}",
                    {
                        "phase": "rollback",
                        "success": rollback_result.success,
                        "batch_id": batch_id_for_apply,
                        "frozen": rollback_result.frozen,
                    },
                )
                db.commit()
                if rollback_result.frozen:
                    logger.error(
                        "[%s] Merge queue FROZEN after rollback failure for batch %s",
                        project_id,
                        batch_id_for_apply,
                    )
            elif not apply_result.success:
                # Apply failed *before* touching the live DB (SelfBlockerError
                # pre-flight, lock timeout, …). Nothing was committed, so a
                # `downgrade -1` here would clobber a previously-applied
                # migration (the post-merge rollback regression seen after the
                # BATCH-00089 merge, 2026-05-11). Leave the DB as-is; the daemon
                # retries Phase 2 on the next merge cycle and the dashboard
                # alembic guard surfaces any genuinely-pending revision in the
                # meantime.
                logger.warning(
                    "[%s] Phase 2 apply deferred for batch %s (no revision applied): %s",
                    project_id,
                    batch_id_for_apply,
                    apply_result.message,
                )
                _emit_event(
                    db,
                    project_id,
                    "migration_pipeline",
                    item_id,
                    "work_item",
                    f"Phase 2 apply deferred (no rollback): {apply_result.message}",
                    {
                        "phase": "apply",
                        "success": False,
                        "deferred": True,
                        "batch_id": batch_id_for_apply,
                    },
                )
                db.commit()

    except (MergeError, subprocess.TimeoutExpired) as e:
        # CR-00028: use merge_failed so the cascade is NOT triggered.
        # Dependents in later execution groups stay pending — the operator
        # can retry via restart-merge or abandon via abandon-merge.
        batch_item.status = BatchItemStatus.merge_failed
        batch_item.notes = f"Merge failed: {e}"
        # C4: revert WorkItem so it is not orphaned as completed
        _revert_work_item(db, project_id, item_id)
        # F-00076: parse CONFLICT_FILES marker even on failure (it may have
        # been emitted before the failure, e.g. from a partial --continue).
        if result is not None:
            output = result.stdout + result.stderr
            m = _CONFLICT_MARKER_RE.search(output)
            if m:
                with suppress(_json.JSONDecodeError):
                    conflict_files = _json.loads(m.group(1))
        batch_item.merge_info = {
            "conflict_files": conflict_files,
        }

        # F-00084: parse new auto-resolve markers emitted by worktree_commit.sh.
        # Event order: attempted → (per-file LLM) → resolved|failed|skipped → merge_conflict.
        # Invariants:
        #   - merge_conflict event MUST still fire (below).
        #   - BatchItem.status = merge_failed MUST still execute (already set above).
        #   - All new code is wrapped in try/except so failures never block the merge path.
        if result is not None:
            _output = result.stdout + result.stderr
            _auto_resolve_request = auto_merge.parse_auto_resolve_marker(_output)
            _auto_skip = auto_merge.parse_auto_skip_marker(_output)

            if _auto_skip is not None:
                try:
                    auto_merge.emit_skipped_event(db, project_id, item_id, _auto_skip)
                except Exception as _exc:
                    logger.exception(
                        "[%s] auto_merge emit_skipped_event error for %s: %s",
                        project_id,
                        item_id,
                        _exc,
                    )
            elif _auto_resolve_request is not None:
                try:
                    _orch_root = Path(__file__).resolve().parent.parent.parent
                    _config, _parse_error = auto_merge.AutoMergeConfig.load(
                        str(_orch_root / "executor" / "auto_merge.toml")
                    )
                    if _parse_error:
                        auto_merge.emit_config_invalid_event(db, project_id, item_id, _parse_error)
                    _resolved_cfg = resolve_project_config(db, project_id, _config)
                    _config = auto_merge.AutoMergeConfig(
                        phase=_resolved_cfg.phase,
                        runtime_option_id=_resolved_cfg.runtime_option_id,
                        allowlist_patterns=_config.allowlist_patterns,
                        refuselist_patterns=_config.refuselist_patterns,
                        max_conflict_hunk_lines=_config.max_conflict_hunk_lines,
                        max_conflicted_files_per_merge=_config.max_conflicted_files_per_merge,
                        max_file_size_bytes=_config.max_file_size_bytes,
                        max_event_metadata_bytes=_config.max_event_metadata_bytes,
                        llm_call_timeout_seconds=_config.llm_call_timeout_seconds,
                        health_probe_interval_seconds=_config.health_probe_interval_seconds,
                        health_failure_rate_threshold_per_day=_config.health_failure_rate_threshold_per_day,
                    )

                    _classification = auto_merge.classify_conflicts(
                        worktree_path=Path(worktree_path),
                        conflict_files=list(_auto_resolve_request.get("eligible_files", [])),
                        config=_config,
                    )

                    if _classification.skipped_reason is not None:
                        auto_merge.emit_skipped_event(
                            db,
                            project_id,
                            item_id,
                            {
                                "reason": _classification.skipped_reason,
                                "eligible_files": list(
                                    _auto_resolve_request.get("eligible_files", [])
                                ),
                                "deferred_files": list(_classification.deferred_files),
                                "refuse_files": list(_classification.refuse_files),
                                "binary_files": list(_classification.binary_files),
                                "oversized_files": list(_classification.oversized_files),
                                "oversized_hunks": list(_classification.oversized_hunks),
                            },
                        )
                    else:
                        # Fetch work item title/description for the prompt
                        _wi = (
                            db.query(WorkItem)
                            .filter_by(project_id=project_id, id=item_id)
                            .one_or_none()
                        )
                        _wi_title = (_wi.title if _wi is not None else "") or ""
                        _wi_desc = (_wi.design_doc_content if _wi is not None else "") or ""
                        _branch_name = _auto_resolve_request.get("branch", "")
                        _main_sha = _auto_resolve_request.get("main_sha", "")

                        auto_merge.attempt_resolution(
                            db=db,
                            project_id=project_id,
                            item_id=item_id,
                            item_title=_wi_title,
                            item_description=_wi_desc,
                            worktree_path=str(worktree_path),
                            main_sha=_main_sha,
                            branch_name=_branch_name,
                            eligible_files=list(_classification.eligible_files),
                            deferred_files=list(_classification.deferred_files),
                            config=_config,
                        )
                        # Phase 1: result.success is always False — fall through to merge_failed.
                except Exception as _exc:
                    logger.exception(
                        "[%s] auto_merge attempt_resolution error for %s: %s",
                        project_id,
                        item_id,
                        _exc,
                    )
                    with suppress(Exception):
                        auto_merge.emit_event(
                            db,
                            project_id,
                            item_id,
                            auto_merge.EVENT_AUTO_RESOLUTION_FAILED,
                            {"reason": "internal_error", "error": str(_exc)},
                        )

        db.commit()
        worktree_compose.down(
            str(batch_item.id),
            Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None,
        )
        _emit_event(db, project_id, "merge_conflict", item_id, "work_item", str(e))
        logger.error("[%s] Merge failed for %s: %s", project_id, item_id, e)


def _cleanup_worktree(item_id: str, worktree_path: str, repo_root: str) -> None:
    """Remove the git worktree and prune the reference."""
    try:
        subprocess.run(  # noqa: S603, S607
            ["git", "worktree", "remove", "--force", worktree_path],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )
        logger.info("Cleaned up worktree %s for %s", worktree_path, item_id)
    except Exception:
        logger.warning("Failed to clean up worktree %s for %s", worktree_path, item_id)


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
