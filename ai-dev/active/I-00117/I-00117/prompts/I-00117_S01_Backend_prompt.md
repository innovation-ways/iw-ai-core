# I-00117_S01_Backend_prompt

**Work Item**: I-00117 -- Daemon silently dead-ends a non-fixable, non-retryable failed step
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (docker kill/stop/rm/restart, docker compose up/down/restart, volume/system
prune). Exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps/inspect/logs`), and `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migration. Do not generate or apply one. The new
`DaemonEvent` type is a column value, not a schema change.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00117 --json`.
- `ai-dev/active/I-00117/I-00117_Issue_Design.md` — read end-to-end (Root Cause
  Analysis + Fix Plan + Acceptance Criteria).
- Source: `orch/daemon/batch_manager.py` (failed-step handler, ~lines 592-633),
  `orch/daemon/fix_cycle.py` (`handle_spec_mismatch_escalation`, ~line 478, and
  `_emit_event`).

## Output Files

- `ai-dev/active/I-00117/reports/I-00117_S01_Backend_report.md` — step report.

## Context

You are fixing a daemon bug: a failed implementation step that is neither fixable
(not in `_FIXABLE_STEP_TYPES`) nor retryable (retries exhausted) falls into a
silent `else` branch in `batch_manager.py` that only logs a warning and returns —
no `DaemonEvent`, no status change. The item is left `in_progress` and its batch
`executing` forever. Read the design doc's Root Cause Analysis first, then read
`CLAUDE.md` for conventions.

## Requirements

### 1. Add `handle_recovery_exhausted_escalation()` to `orch/daemon/fix_cycle.py`

Mirror `handle_spec_mismatch_escalation` (same signature shape). It MUST:

- Emit a `DaemonEvent` via the module's `_emit_event(...)` helper with
  `event_type="step_recovery_exhausted"`, `entity_id=step.work_item_id`,
  `entity_type="work_item"`, a clear human message naming the step and that no
  fix cycle / retry remains, and a metadata dict
  `{"step_id": step.step_id, "step_type": <value or None>, "failure_reason": <reason or "">}`.
- Accept the failure reason (read via `fix_cycle._latest_failure_reason` at the
  call site, or pass it in — match the spec-mismatch call convention).
- `logger.warning(...)` with item/step/reason (keep the existing log signal).
- **Not** create a `FixCycle`.
- Leave the `WorkflowStep` in `failed` (the caller owns item/batch-item status —
  see requirement 2). Do NOT commit here if the caller commits; match the
  transaction style of the surrounding `batch_manager` code (the spec-mismatch
  handler commits — keep behavior consistent and avoid double-commits).

### 2. Call it from the silent `else` branch in `orch/daemon/batch_manager.py`

In the failed-step handler, the final `else` (after `should_attempt_fix` and
`should_retry_step` both return False) currently does only
`logger.warning("...needs human review")`. Replace it so it:

- Calls `fix_cycle.handle_recovery_exhausted_escalation(db, has_failed, self.project_id, failure_reason)`
  (reuse the `failure_reason` already computed above for the spec-mismatch check).
- Transitions the work item and batch item to a **visible terminal** state:
  `batch_item.status = BatchItemStatus.failed` and the parent
  `work_item.status = WorkItemStatus.failed`. Look at how `setup_failed` paths in
  this same file load the `WorkItem` and set both statuses, and follow that
  pattern (including the `db.commit()`).
- Then `return` (as today).

Use the project's existing state-transition helpers if one is used elsewhere for
marking a batch item failed; otherwise set the status field directly as the
neighboring failure paths do. Do NOT refactor the surrounding routing ladder.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match SQLAlchemy 2.0 style, the
append-only `daemon_events` convention, and the `event_metadata` Python alias for
`DaemonEvent.metadata` (SQLAlchemy reserves `metadata`).

## TDD Requirement

S03 (Tests) writes the reproduction + regression tests. For this step, follow
RED→GREEN where practical, but the authoritative behavioral test is S03. If you
add a quick local check, run it targeted only (`uv run pytest <file> -v`), never
the full suite.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues from, in order:
1. `make format`
2. `make typecheck` (zero errors involving files you touched)
3. `make lint`

Record each in the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Verify only the code path you changed with a **targeted** run, e.g.
`uv run pytest tests/integration/test_fix_cycle.py -v` if you exercise the
handler. **DO NOT** run `make test-integration` or `make test-unit` — full-suite
execution is owned by the downstream QV gate steps. Full quality-gate verification
(`make quality` / `make check`) is NOT this step's responsibility and MUST NOT be
used as a completion gate here.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00117",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/daemon/fix_cycle.py", "orch/daemon/batch_manager.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "n/a — behavioral test authored in S03 (Tests)",
  "blockers": [],
  "notes": ""
}
```
