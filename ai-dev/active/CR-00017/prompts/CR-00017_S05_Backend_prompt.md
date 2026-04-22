# CR-00017_S05_Backend_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
## ⛔ You MUST NOT run `alembic upgrade head` against the live DB

Your work in this step lives in the daemon's merge pipeline. The daemon itself
will call `safe_migrate.apply()` at runtime — your job is to write the
daemon-side orchestration code. During development, test with testcontainers.

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — Design (Desired Behavior points 1–4, AC2, AC3, AC4, AC5)
- `ai-dev/active/CR-00017/reports/CR-00017_S04_CodeReview_report.md` — safe_migrate landed
- `orch/daemon/merge_queue.py` — current merge logic (squash-merge path)
- `orch/daemon/batch_merge_hooks.py` — pre/post-merge hook points
- `orch/daemon/batch_manager.py` — agent spawning (this is where `IW_CORE_AGENT_CONTEXT=true` gets set)
- `orch/daemon/state_machine.py` — batch-state definitions
- `orch/daemon/main.py` — daemon loop
- `orch/db/safe_migrate.py` (from S03)
- `orch/db/models.py` — `PendingMigrationLog` + `DaemonEvent`
- `orch/CLAUDE.md` — daemon conventions
- `docs/IW_AI_Core_Daemon_Design.md` — daemon design doc

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S05_Backend_report.md`
- `orch/daemon/migration_pipeline.py` (new — the 3-phase orchestration module)
- `orch/daemon/merge_queue.py` (modified — calls into `migration_pipeline`)
- `orch/daemon/batch_merge_hooks.py` (modified — migration hook registered)
- `orch/daemon/batch_manager.py` (modified — sets `IW_CORE_AGENT_CONTEXT=true` in agent env)
- `orch/daemon/state_machine.py` (modified — new batch states / frozen flag helpers)
- `orch/db/models.py` (possibly modified — new batch_status enum values if applicable)

## Context

You're the core wiring. The daemon currently squash-merges batches with no migration awareness; you add the 3-phase pipeline around the merge.

Read the design doc's Desired Behavior section carefully — the exact phase-by-phase behavior on happy path, dry-run failure, apply failure, rollback success, and rollback failure is all specified.

## Requirements

### 1. `orch/daemon/migration_pipeline.py` — new module

Public API:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class PipelineResult:
    phase: Literal["dry_run", "apply", "rollback"]
    success: bool
    final_batch_state: str   # one of the batch-status enum values
    frozen: bool              # True iff merge_queue_frozen was just set
    message: str

def run_pre_merge_dry_run(batch_id: int) -> PipelineResult:
    """Phase 1. Spin testcontainer, apply pending revisions, run integration
    tests. On fail → return success=False, final_batch_state='MIGRATION_INVALID'.
    On pass → return success=True, final_batch_state='proceed_to_merge'."""

def run_post_merge_apply(batch_id: int) -> PipelineResult:
    """Phase 2. Call safe_migrate.apply(live_url). On fail → trigger Phase 3."""

def run_rollback(batch_id: int) -> PipelineResult:
    """Phase 3. Call safe_migrate.rollback(live_url, steps=1). On success →
    final_batch_state='MIGRATION_ROLLED_BACK'. On failure → set
    merge_queue_frozen flag, return frozen=True."""

def is_merge_queue_frozen() -> bool:
    """Read the latest daemon_events row with event_type='merge_queue_frozen'
    and return its metadata.active field (default False)."""

def set_merge_queue_frozen(active: bool, reason: str, acknowledged_by: str | None = None) -> None:
    """Write a daemon_events row. Used by Phase 3 (on rollback fail) and by
    the `iw merge-queue unfreeze` CLI (active=False + reason=ack + acknowledged_by)."""
```

### 2. Testcontainer spin for Phase 1

Use the existing testcontainer pattern from `tests/conftest.py` — do NOT spin it via raw `docker` calls (see the R1 Docker rule). Import the fixture helper if one exists, or add a small helper to `orch/daemon/` that uses the `testcontainers` Python library (same package the tests use). This testcontainer is daemon-initiated and short-lived — Ryuk will clean it up.

Phase 1 steps:

1. Create a testcontainer Postgres.
2. Run the project's migrations against it from scratch (`alembic upgrade head` via `safe_migrate.dry_run(tempdb_url, batch_id)`).
3. Run the project's integration test suite subset that exercises migrations (you can use an env var filter, or run the full `make test-integration` — pick the cheaper path; documenting the choice in the report).
4. Tear down the testcontainer.
5. Report success / failure.

### 3. Merge-queue integration (`merge_queue.py`)

The existing merge flow roughly looks like: "pick next approved batch → pre-merge checks → git squash-merge → post-merge cleanup". Insert hooks:

- **Before squash-merge**: call `run_pre_merge_dry_run(batch_id)`. On fail → update batch status to `MIGRATION_INVALID`, skip the merge, move to next batch.
- **After squash-merge**: call `run_post_merge_apply(batch_id)`. On fail → `run_rollback(batch_id)` which handles the rest.
- **Before any merge cycle**: check `is_merge_queue_frozen()`. If true → log a `daemon_events` entry noting the skip and return (no merges processed until unfreeze).

Implement Phase 1 and 2 as async-safe as the rest of the daemon (match existing sync vs async style — the daemon is single-threaded sync per `orch/CLAUDE.md`, but confirm).

### 4. Batch state additions

Add new batch states (if the project's batch-state machinery allows enum extension):

- `MIGRATION_INVALID` — Phase 1 rejected the migration.
- `MIGRATION_ROLLED_BACK` — Phase 2 failed, Phase 3 rolled back successfully.

If batch states are a Postgres ENUM (likely), you'll need a tiny follow-up migration to add the values. If that's substantial, raise as a blocker so it can be split; if it's trivial, handle it inline in S05 and update the S01 migration (but prefer a fresh chained migration to keep phases clean).

### 5. `IW_CORE_AGENT_CONTEXT` in agent subprocess env (`batch_manager.py`)

Find where the daemon spawns the opencode / claude-code subprocess for an agent. Set `IW_CORE_AGENT_CONTEXT=true` in the subprocess's environment. Confirm it propagates through any wrapping (bash `eval`, `sh -c`, etc.).

### 6. `daemon_events` integration

Every phase start/end writes a `DaemonEvent` row:

- `event_type`: `"migration_pipeline"` with `event_metadata.phase` distinguishing `dry_run` / `apply` / `rollback`.
- `event_type`: `"merge_queue_frozen"` for freeze/unfreeze transitions. `event_metadata.active` boolean, `event_metadata.reason` string, `event_metadata.acknowledged_by` optional.

Do NOT re-implement the DaemonEvent writer — there's almost certainly a helper in the daemon already; reuse it.

### 7. Smoke test

Smoke-test locally against the live daemon (but DO NOT allow a failing migration to reach Phase 2 on the live DB in your testing). Approach: write a no-op migration in a test worktree, approve a fake batch referencing it, run the pipeline steps via the new module's entry points, confirm the happy path. Document your smoke approach in the report.

## Project Conventions

- Sync SQLAlchemy throughout the daemon.
- `logging.getLogger(__name__)`.
- No cross-layer imports (daemon → db / config OK; daemon → dashboard NOT OK).
- Match the existing hook registration pattern in `batch_merge_hooks.py` — don't invent a new pattern.

## TDD Requirement

Full integration tests land in S11. For this step, write smoke-level unit tests inline to validate the module's contract:

- `is_merge_queue_frozen` returns False by default (no events row yet) and True after a write.
- `set_merge_queue_frozen` writes the expected daemon_events row shape.
- `run_pre_merge_dry_run` dispatches to `safe_migrate.dry_run` (mock it).
- `run_rollback` on rollback-fail sets frozen=True.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make lint` — pass.
3. `make test-integration` — no regressions on existing daemon tests.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "CR-00017",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "...",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S05
uv run iw step-done CR-00017 --step S05 --report ai-dev/active/CR-00017/reports/CR-00017_S05_Backend_report.md
```
