# CR-00017: Daemon-only migration application

**Type**: Change Request
**Priority**: Critical
**Reason**: Today any agent in any worktree can apply an arbitrary Alembic migration to the live orchestration DB on port 5433 by running `uv run alembic upgrade head`. The `iw migration-lock` serializes concurrent applies but does not validate correctness — a bad migration from any agent is applied immediately to production state with no review gate. This is the largest remaining single-actor blast-radius in the architecture. CR-00014 (fingerprint), CR-00015 (compose split), and CR-00016 (Docker rule) close the passive and active surface-area risks; this CR closes the final architectural one.
**Created**: 2026-04-22
**Status**: Draft

---

## Description

Shift migration *application* from agents to the daemon. Agents continue to **generate** migration files in their worktree's `orch/db/migrations/versions/`, but they no longer touch the live DB. The daemon runs a three-phase migration pipeline as part of its merge queue: (1) **pre-merge dry-run** against a short-lived testcontainer DB to validate the migration; (2) **post-squash-merge apply** to the live DB under `iw migration-lock`; (3) on apply failure, **automatic rollback** via `alembic downgrade -1`, with the merge queue frozen if rollback also fails. A new `safe_migrate` library wrapper refuses any migration operation when the environment has `IW_CORE_AGENT_CONTEXT=true`, a flag the daemon sets when launching agents. A new `iw migrations {list-pending|dry-run|apply}` CLI gives operators the safe surface for manual intervention.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key facts:
- All orchestration state lives in the DB (`docs/IW_AI_Core_Database_Schema.md`).
- The daemon drives batches end-to-end: worktree → agents → review → squash-merge (`docs/IW_AI_Core_Daemon_Design.md`).
- Tests use testcontainers (never the live DB — `tests/CLAUDE.md`).
- CR-00014 added a DB instance-identity fingerprint; CR-00015 removed the docker-compose foot-gun; CR-00016 forbids docker container management from agent contexts.

## Current Behavior

### How migrations are applied today

- Agents in a Database step run `uv run alembic upgrade head` against the live DB (port 5433 from `.env`).
- Serialized by `iw migration-lock` (acquire at step start, release at step end).
- `alembic upgrade head` sees the live DB's current revision and applies every pending revision in order.
- If the migration breaks (syntax error, constraint violation, data incompatibility), the live DB ends up at whatever revision the error happened — possibly partially applied.
- No review gate. No dry-run. No test against a disposable DB.
- Rollback is manual (`alembic downgrade ...` by the operator).
- The daemon's merge queue (`orch/daemon/merge_queue.py`, `orch/daemon/batch_merge_hooks.py`) squashes worktree branches into `main` but does not interact with migrations explicitly — whatever the agent did to the DB is already done by the time the merge happens.

### Concrete integration points

- `ai-core.sh` — `cmd_start` runs `uv run alembic upgrade head` at startup (operator-run, fine).
- `Makefile` — `db-migrate` / `migrate` targets run `alembic upgrade head` (operator-run, fine).
- Every Database-step prompt template currently tells the agent to run migrations.
- `orch/daemon/merge_queue.py` — squash-merge logic; no migration hook.
- `orch/daemon/batch_merge_hooks.py` — pre/post-merge hooks; no migration hook.
- `orch/daemon/batch_manager.py` — launches agents; currently does NOT set `IW_CORE_AGENT_CONTEXT`.
- `orch/db/session.py` — exposes `engine` / `SessionLocal`; no guard on migration operations.
- `docs/IW_AI_Core_Migration_Checklist.md` — tells agents to `alembic upgrade head`.
- `docs/IW_AI_Core_Tech_Stack.md` — documents the agent-run migration model.
- `docs/reference/03_merge_fix_automation.md` — mentions running `alembic upgrade head` to verify.

## Desired Behavior

### New contract

1. **Agents GENERATE migrations. Daemon APPLIES migrations.** Any attempt by an agent to apply migrations is blocked by construction (via `IW_CORE_AGENT_CONTEXT` env flag + `safe_migrate` guard).

2. **Three-phase pipeline** on every batch with a pending migration, driven by the daemon's merge queue:

   **Phase 1 — Pre-merge dry-run.** The daemon spins a disposable testcontainer Postgres, applies every pending revision on it, runs the project's integration tests against that testcontainer, and then discards it. If any step fails → batch marked `MIGRATION_INVALID`, the batch does NOT merge to `main`. An entry is written to `pending_migration_log` with `phase = 'dry_run'`.

   **Phase 2 — Post-squash-merge apply.** After the squash-merge lands, the daemon acquires the `iw migration-lock`, applies pending revisions against the live DB with `alembic upgrade head`, releases the lock. Entry in `pending_migration_log` with `phase = 'apply'`.

   **Phase 3 — Rollback on apply failure.** If Phase 2 fails, the daemon attempts `alembic downgrade -1` once. If rollback succeeds → batch marked `MIGRATION_ROLLED_BACK`, merge queue continues. If rollback also fails → `merge_queue_frozen` flag set; subsequent merges halted until an operator runs `iw merge-queue unfreeze --ack "<reason>"`. Entry in `pending_migration_log` with `phase = 'rollback'`.

3. **`safe_migrate` library wrapper** (`orch/db/safe_migrate.py`). All migration operations that ever touch the live DB must go through it. The wrapper:
   - Raises `AgentContextForbidden` if `os.environ.get("IW_CORE_AGENT_CONTEXT") == "true"`.
   - Detects multi-head alembic state and refuses with a clear message (daemon converts this to `MIGRATION_INVALID` status).
   - Logs every phase to `pending_migration_log` under a fresh short-lived session.

4. **`IW_CORE_AGENT_CONTEXT` flag.** The daemon sets this to `"true"` in the subprocess environment whenever it launches an agent (opencode / claude-code). Agent-run shells inherit it. The guard in `safe_migrate` refuses based on it.

5. **`iw migrations` CLI for operators.**
   - `iw migrations list-pending` — read-only. Returns the list of alembic revisions present in files but not yet applied to the live DB. Safe for anyone.
   - `iw migrations dry-run` — spins a testcontainer, applies pending revisions, reports success/failure. Safe for anyone; never touches live DB.
   - `iw migrations apply --i-am-operator` — applies pending revisions to the live DB. Requires the explicit `--i-am-operator` flag (operator ack). Refuses if `IW_CORE_AGENT_CONTEXT=true`.

6. **`iw merge-queue` CLI for operators.**
   - `iw merge-queue status` — reports the current frozen/unfrozen state with the last `pending_migration_log` entry if relevant.
   - `iw merge-queue unfreeze --ack "<reason>"` — clears the frozen flag. Refuses if `IW_CORE_AGENT_CONTEXT=true`. Ack reason is logged in `daemon_events`.

7. **Prompt templates updated.** Every Database-step prompt pattern explicitly says "Agents MUST NOT run `alembic upgrade head` or any alembic command that modifies the live DB. Write the migration file; the daemon applies it post-merge." The rule is embedded in the same style as CR-00016's Docker rule, with a unique marker phrase grep-tested (extending CR-00016's coverage test).

### Observability

- `pending_migration_log` rows surface in the dashboard's batch detail view.
- `daemon_events` records each phase start/finish/fail.
- Dashboard shows a prominent banner when `merge_queue_frozen` is true.
- `ai-core.sh status` prints the merge-queue state (frozen / OK).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|---|---|---|
| `orch/db/safe_migrate.py` | Does not exist | New library wrapper with guard + 3-phase helpers |
| `orch/db/migrations/versions/{hash}_add_pending_migration_log.py` | Does not exist | New migration |
| `orch/db/models.py` | No `PendingMigrationLog` model | Adds `PendingMigrationLog` |
| `orch/daemon/merge_queue.py` | Squash-merges without migration hook | Three-phase pipeline integrated |
| `orch/daemon/batch_merge_hooks.py` | Pre/post hooks exist but no migration handling | Adds migration-apply hook |
| `orch/daemon/batch_manager.py` | Launches agents without `IW_CORE_AGENT_CONTEXT` | Sets env flag when spawning agents |
| `orch/daemon/state_machine.py` | Batch states `queued/running/complete/failed/...` | Adds `MIGRATION_INVALID`, `MIGRATION_ROLLED_BACK`, and `merge_queue_frozen` concept |
| `orch/cli/migrations_commands.py` | Does not exist | New CLI group: list-pending / dry-run / apply |
| `orch/cli/merge_queue_commands.py` | Does not exist | New CLI group: status / unfreeze |
| `orch/cli/__init__.py` | Registers existing groups | Registers new groups |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Agents run migrations | Explicitly forbids it |
| All design templates (`CR_Design_Template`, `Feature_Design_Template`, `Issue_Design_Template`) | Mention running migrations | Updated |
| `CLAUDE.md` (root) | Critical Rules list | Adds migration-apply rule bullet |
| `orch/CLAUDE.md` | Mentions alembic upgrade head | Rewritten to new contract |
| `docs/IW_AI_Core_Migration_Checklist.md` | Agent checklist includes `alembic upgrade head` | Rewritten: agents stop after writing the file |
| `docs/IW_AI_Core_Tech_Stack.md` | Documents agent-applies model | Documents daemon-applies model |
| `docs/reference/03_merge_fix_automation.md` | Includes manual migration verification | Updated |
| `docs/IW_AI_Core_Agent_Constraints.md` (from CR-00016) | Has R1 (Docker) | Adds R2 (Migrations) |
| `tests/integration/test_agent_constraints_coverage.py` (from CR-00016) | Checks Docker marker | Extended to check migration marker |
| `ai-core.sh` | `cmd_start` runs `alembic upgrade head` | Unchanged — operator path, still allowed |
| `Makefile` | `db-migrate` target | Unchanged — operator path, still allowed |
| `scripts/e2e_dashboard_entrypoint.sh` | Runs `alembic upgrade head` in e2e container | Unchanged — isolated environment |

### Breaking Changes

**Yes**, by design:

1. **Any in-flight Database step** whose prompt says "run `alembic upgrade head`" will fail via the `safe_migrate` guard. F-00058 S01 is the concrete example — after CR-00017 lands, its prompt needs re-authoring to match the new contract. This is the intended shape.
2. **`iw migration-lock`** semantics shift from agent-owned to daemon-owned. The CLI surface (`iw migration-lock acquire/release/status`) is preserved for operator debugging, but agent prompts no longer call it.
3. **Agent-run `alembic upgrade head`** is now forbidden. Prompts that still instruct it are broken until rewritten (CR-00017 S09 rewrites all templates).

### Data Migration

- **One new table** `pending_migration_log`. Append-only, no FKs inbound, one optional FK to `batches` outbound. Schema:

  ```
  CREATE TABLE pending_migration_log (
    id               BIGSERIAL PRIMARY KEY,
    revision         TEXT NOT NULL,
    direction        TEXT NOT NULL CHECK (direction IN ('upgrade', 'downgrade')),
    phase            TEXT NOT NULL CHECK (phase IN ('dry_run', 'apply', 'rollback')),
    batch_id         BIGINT REFERENCES batches(id) ON DELETE SET NULL,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    success          BOOLEAN,
    stdout_tail      TEXT,                  -- last 16KB
    stderr_tail      TEXT,                  -- last 16KB
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX ix_pending_migration_log_batch ON pending_migration_log (batch_id, started_at DESC);
  CREATE INDEX ix_pending_migration_log_revision ON pending_migration_log (revision, phase);
  ```

- **Merge-queue-frozen flag**: implemented as a row in `daemon_events` with a specific `event_type = 'merge_queue_frozen'` and `event_metadata.active = true|false` — avoids a new singleton table. Queryable by `SELECT ... ORDER BY created_at DESC LIMIT 1`.
- Reversible migration: downgrade drops the table; daemon_events entries are append-only but the `merge_queue_frozen` events become inert without the consuming code path.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Migration for `pending_migration_log` table + ORM model. Reversible. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | `orch/db/safe_migrate.py` library wrapper (guard, 3-phase helpers, multi-head detection, log writer). Unit-test smoke coverage. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | backend-impl | Daemon integration: wire `safe_migrate` into merge-queue pipeline; `MIGRATION_INVALID` / `MIGRATION_ROLLED_BACK` batch states; `merge_queue_frozen` flag read/write; `IW_CORE_AGENT_CONTEXT=true` in agent subprocess env. | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | backend-impl | `iw migrations {list-pending|dry-run|apply}` and `iw merge-queue {status|unfreeze}` CLI. Operator-ack flag + `IW_CORE_AGENT_CONTEXT` refusal. | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | template-impl | Rewrite Database-step prompt patterns in all 11 templates. Extend `docs/IW_AI_Core_Agent_Constraints.md` with R2 (Migrations). Update CLAUDE.md files, Migration_Checklist, Tech_Stack doc, merge_fix_automation doc. Grep for stale `alembic upgrade head` references in agent-facing content. | — |
| S10 | code-review-impl | Review S09 | — |
| S11 | tests-impl | Unit (safe_migrate guard, multi-head detection, log writes). Integration (3-phase pipeline happy path; dry-run fails → batch invalid; apply fails + rollback succeeds; apply fails + rollback fails → queue frozen; queue-frozen blocks subsequent merges; CLI exit codes; daemon sets env flag). Extend CR-00016's coverage test for the new marker phrase. | — |
| S12 | code-review-impl | Review S11 | — |
| S13 | code-review-final-impl | Global cross-layer review. AC coverage, rollback plan, CR-00014/15/16 compatibility, stale refs. | — |
| S14 | qv-gate (lint) | `make lint` | — |
| S15 | qv-gate (format) | `uv run ruff format --check .` | — |
| S16 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S17 | qv-gate (unit-tests) | `make test-unit` | — |
| S18 | qv-gate (integration-tests) | `make test-integration` | — |

### Database Changes

- **New tables**: `pending_migration_log`
- **Modified tables**: None
- **Migration notes**: Single new migration; chains from the then-latest head (expected to be CR-00014's revision after that CR merges). Autogenerate-clean.

### API Changes

No HTTP endpoints. Two new CLI groups (`iw migrations`, `iw merge-queue`).

### Frontend Changes

- Dashboard banner component for `merge_queue_frozen` state (HTMX partial). Not a new page — an extension to the existing batches view. Read-only display.
- This is a small but user-visible change — keep it minimal and in the same visual style as existing alert banners.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00017/`:

| File | Type | Purpose |
|---|---|---|
| `CR-00017_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00017_S01_Database_prompt.md` | Prompt | Migration + ORM model |
| `prompts/CR-00017_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00017_S03_Backend_prompt.md` | Prompt | safe_migrate library |
| `prompts/CR-00017_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00017_S05_Backend_prompt.md` | Prompt | Daemon integration |
| `prompts/CR-00017_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00017_S07_Backend_prompt.md` | Prompt | CLI |
| `prompts/CR-00017_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00017_S09_Template_prompt.md` | Prompt | Prompt templates + docs |
| `prompts/CR-00017_S10_CodeReview_prompt.md` | Prompt | Review S09 |
| `prompts/CR-00017_S11_Tests_prompt.md` | Prompt | Full test suite |
| `prompts/CR-00017_S12_CodeReview_prompt.md` | Prompt | Review S11 |
| `prompts/CR-00017_S13_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: Agent-context guard blocks application

```
Given IW_CORE_AGENT_CONTEXT=true is set in the environment
When any caller invokes safe_migrate.apply() or iw migrations apply
Then AgentContextForbidden is raised (library) or the CLI exits non-zero
 And no changes are made to the live DB
 And an entry MAY be logged in pending_migration_log with phase='apply', success=false, error_message referencing the guard
```

### AC2: Phase 1 dry-run rejects broken migrations

```
Given a worktree adds a migration whose upgrade() raises an exception
When the daemon's merge queue reaches that batch
Then Phase 1 dry-run runs against a fresh testcontainer, fails
 And the batch is marked MIGRATION_INVALID
 And the batch is NOT squash-merged to main
 And a pending_migration_log row is written with phase='dry_run', success=false
 And daemon_events records the rejection
```

### AC3: Phase 2 applies on happy path

```
Given a batch with a valid migration has passed Phase 1 and been squash-merged
When Phase 2 runs
Then `iw migration-lock` is acquired (daemon-owned)
 And `alembic upgrade head` is invoked via safe_migrate against the live DB
 And the lock is released
 And pending_migration_log records phase='apply', success=true
 And the live DB is at the new head
 And CR-00014 identity check still passes (iw_core_instance row unchanged)
```

### AC4: Phase 3 rollback on apply failure

```
Given Phase 2 raises during apply (e.g. constraint violation post-autogen drift)
When Phase 3 triggers
Then `alembic downgrade -1` is attempted once
 And IF downgrade succeeds: batch marked MIGRATION_ROLLED_BACK, queue continues,
     pending_migration_log records phase='rollback', success=true
 And IF downgrade fails: merge_queue_frozen=true is set (daemon_events),
     pending_migration_log records phase='rollback', success=false,
     subsequent merges halt with a clear reason
```

### AC5: Frozen merge queue requires operator ack to resume

```
Given merge_queue_frozen=true
When the daemon's merge queue runs
Then no batches are merged
 And daemon_events shows the current frozen reason
 And dashboard displays a prominent banner
When an operator runs: iw merge-queue unfreeze --ack "manually restored DB to rev X"
Then merge_queue_frozen=false, subsequent merges resume
 And the ack reason is logged in daemon_events
When an agent (IW_CORE_AGENT_CONTEXT=true) runs: iw merge-queue unfreeze
Then the CLI refuses non-zero; the flag remains set
```

### AC6: Multi-head state rejected cleanly

```
Given the alembic revision graph has multiple heads
When safe_migrate.list_pending_revisions() is called (by any phase)
Then it raises MultipleHeadsError with a clear message naming the heads
 And the daemon marks the batch MIGRATION_INVALID with the same message
 And no merge proceeds until an operator creates a merge revision
```

### AC7: CLI surface behaves correctly

```
- iw migrations list-pending       → 0 exit, JSON/table of pending revisions
- iw migrations dry-run            → 0 on pass / non-0 on fail, testcontainer teardown clean
- iw migrations apply              → refuses without --i-am-operator flag
- iw migrations apply --i-am-operator  → applies, 0 on success, non-0 on failure
- iw merge-queue status            → 0 exit, current frozen state
- iw merge-queue unfreeze          → refuses without --ack "..." flag
- Any of the above with IW_CORE_AGENT_CONTEXT=true → refuses non-zero

Exit codes canonical:
  0  = success
  2  = agent-context guard (AgentContextForbidden)
  3  = missing operator flag
  4  = multi-head
  5  = migration failure
  1  = unknown
```

### AC8: Prompt templates forbid agent application

```
Given the extended agent-constraints coverage test runs
Then every prompt template in ai-dev/templates/ contains the new marker phrase
 And R2 exists in docs/IW_AI_Core_Agent_Constraints.md
 And a grep for `alembic upgrade head` in agent-facing content (templates,
     agent-facing CLAUDE.md, agent-facing docs) returns zero hits (excluding
     operator/ops documentation that explicitly allows the operator path)
```

### AC9: Observability

```
- `pending_migration_log` rows are queryable and surface in the dashboard's batch detail.
- `daemon_events` captures each phase start/finish/fail and frozen-state transitions.
- `ai-core.sh status` prints the merge-queue state (OK / FROZEN).
- Dashboard shows a visible banner when frozen.
```

### AC10: No regression

```
- CR-00014 identity check remains green.
- CR-00015 compose split intact.
- CR-00016 Docker rule intact; coverage test still passes (extended, not replaced).
- make check green.
- ai-core.sh start / status / stop behave unchanged from the operator's perspective.
```

## Rollback Plan

- **Database**: `alembic downgrade -1` drops `pending_migration_log`. `daemon_events` entries with `event_type='merge_queue_frozen'` become inert without the consuming code. No cascading breakage.
- **Code**: Revert the squash-merge. Daemon returns to no-migration-hook behavior. Agent-run `alembic upgrade head` works again. `IW_CORE_AGENT_CONTEXT` becomes a no-op flag.
- **Prompts / docs**: Revert restores the "agent applies" instruction. F-00058 and other Database steps work as before.
- **Data**: No existing data modified. Only the new `pending_migration_log` table is populated, and it is lost cleanly on downgrade (append-only audit, not referenced by other tables).
- **Operational**: If `merge_queue_frozen=true` at rollback time, the flag is in `daemon_events`. Post-revert, no code path reads it, so it becomes historical audit. No cleanup needed.

## Dependencies

- **Depends on**:
  - **CR-00014** — identity check is a safety net (catches any DB-swap that slips through during pre-merge dry-run).
  - **CR-00015** — compose split; clarifies "live DB" vs "testcontainer" operationally.
  - **CR-00016** — R1 (Docker) is the precedent pattern; R2 (Migrations) extends the same policy doc + grep test.
- **Blocks**: Follow-on CRs that depend on the "agents generate, daemon applies" contract for other shared-state operations.

## TDD Approach

### Unit tests

- `tests/unit/test_safe_migrate.py`:
  - `AgentContextForbidden` raised on each public method when `IW_CORE_AGENT_CONTEXT=true`.
  - Multi-head detection raises `MultipleHeadsError` with both head names in the message.
  - `list_pending_revisions` returns expected revisions when no live DB available (mock).
  - Log writer writes to `pending_migration_log` via a fresh session (testcontainer).
- `tests/unit/test_migrations_cli.py`:
  - `iw migrations apply` refuses without `--i-am-operator` (exit 3).
  - `iw migrations apply --i-am-operator` with `IW_CORE_AGENT_CONTEXT=true` exits 2.
  - `iw migrations list-pending` returns structured output (JSON and table modes).
- `tests/unit/test_merge_queue_cli.py`:
  - `iw merge-queue unfreeze` refuses without `--ack "..."`.
  - `iw merge-queue status` output parseable.

### Integration tests

- `tests/integration/test_migration_pipeline.py`:
  - Happy path: agent writes valid migration → daemon Phase 1 pass → merges → Phase 2 applies → revision advances.
  - Dry-run fail: broken migration → Phase 1 fails → batch marked MIGRATION_INVALID → no merge.
  - Apply fail + rollback success: Phase 2 raises → Phase 3 downgrades → batch marked MIGRATION_ROLLED_BACK.
  - Apply fail + rollback fail: `merge_queue_frozen=true` → subsequent merges halt → operator unfreeze resumes.
  - Multi-head: detected in dry-run, batch marked MIGRATION_INVALID.
  - Daemon subprocess env: assert `IW_CORE_AGENT_CONTEXT=true` in the env that reaches the agent process.
- `tests/integration/test_agent_migrate_guard.py`:
  - With `IW_CORE_AGENT_CONTEXT=true`, running `uv run iw migrations apply --i-am-operator` exits 2.
  - With it unset, same command succeeds.

### Updated tests

- `tests/integration/test_agent_constraints_coverage.py` (from CR-00016) extended with a new marker phrase for R2 ("Agents MUST NOT apply migrations" or similar unique string).
- `tests/unit/test_batch_archiver.py` — if any test still uses `post_archive_commands: ["alembic upgrade head"]` as a fixture, update to match the new contract or skip with a note.

## Notes

- **Why not apply pre-merge against the live DB?** Because a bad migration pre-merge still brick the live DB, and the whole point is to discover brokenness *before* touching live state. The testcontainer dry-run is the airlock.
- **Why apply post-merge instead of pre-merge (against the live DB)?** A migration applied pre-merge to the live DB but then the merge fails creates a drift between DB state and `main` branch. Post-merge apply keeps them in lockstep: merge succeeds → DB advances.
- **Multi-head handling**: the current system already uses `iw migration-lock` as a proxy for "one migration at a time". With parallel worktrees, two can create siblings (both with `down_revision = <previous head>`). Alembic normally requires a manual merge revision. The daemon detects multi-head in Phase 1 and refuses; the operator resolves by creating the merge revision (which is itself a one-off CR if needed).
- **Frozen queue is intentional friction**: a frozen queue means "something broke, don't make it worse automatically". The operator's ack is the explicit decision to proceed. This is better than silent retry.
- **F-00058 is a concrete blocker**: its S01 prompt instructs `alembic upgrade head`. After CR-00017 lands, F-00058 either (a) is re-prompted (recommended) or (b) its step fails via the guard. The daemon's fix-cycle may catch this and request a fresh prompt — out of scope here.
- **`iw migration-lock` ownership shift**: the lock's schema stays. Semantics: the daemon acquires it for Phase 2 apply; agents no longer acquire it. The `iw migration-lock` CLI remains for operator debugging.
- **Operator path preserved**: `ai-core.sh cmd_start` and `Makefile db-migrate` still run `alembic upgrade head` — these are operator-invoked entry points, not agent-invoked. They do NOT set `IW_CORE_AGENT_CONTEXT`, so the guard doesn't fire. Documented in the new Migration Checklist.
- **e2e dashboard entrypoint**: `scripts/e2e_dashboard_entrypoint.sh` runs `alembic upgrade head` inside the disposable e2e container against a disposable DB. Unaffected — not touching live DB.
- **Future work**: a companion CR could replace the "three-phase pipeline" with a WAL-archiving + point-in-time-recovery backup strategy for richer rollback. Out of scope here.
