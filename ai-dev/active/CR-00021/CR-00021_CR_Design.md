# CR-00021: Rebase alembic `down_revision` at merge time to prevent multi-head failures across parallel batches

**Type**: Change Request
**Priority**: Medium
**Reason**: Two concurrent schema-changing batches each autogenerate a migration with the same `down_revision`, then the second one to merge trips `MultipleHeadsError` at Phase 1 and is marked `MIGRATION_INVALID` — operator has to run `alembic merge` by hand. Also fixes a pre-existing correctness hole: Phase 1 dry-run currently tests the daemon's main-repo migrations directory, not the worktree's — so the batch's new migrations aren't actually exercised before merge.
**Created**: 2026-04-24
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in the S01 Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against a
testcontainer, post-merge apply to live DB). If the migration is broken,
the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Insert a new daemon phase — `run_pre_merge_rebase` — into `merge_queue._merge_item()`, after the batch item's branch is already picked up for merge and before Phase 1 dry-run. This phase fetches main, rebases the branch, identifies the batch's own migration files via `git diff merge-base..HEAD`, rewrites their `down_revision` strings to point at main's current head when stale, and commits the edit. Then Phase 1 dry-run is rewired to run against the **worktree's** migrations directory (not the daemon's main repo) so it exercises the real post-squash-merge chain. One additive Alembic migration carries the schema changes (new batch-item status value, new log phase, new log column). No schema lock, no DB-backed revision ledger — parallelism is preserved.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references:

- `CLAUDE.md` — daemon / dashboard / orch layout; Alembic + psycopg conventions
- `orch/CLAUDE.md` — daemon module table (merge_queue, migration_pipeline, batch_manager, state_machine), ORM patterns, append-only tables, gotchas
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL, no DB mocking in integration tests
- `docs/IW_AI_Core_Agent_Constraints.md` — R1/R2 (docker / migration off-limits)
- `docs/IW_AI_Core_Daemon_Design.md` — merge queue / migration pipeline lifecycle (new phase must be documented here)
- `docs/IW_AI_Core_Database_Schema.md` — `batch_item_status` enum, `pending_migration_log` table + CHECK constraint (must reflect the schema changes)

Precedent CRs for comparable daemon-phase / migration-pipeline work:

- **CR-00017** introduced the 3-phase migration pipeline (`run_pre_merge_dry_run`, `run_post_merge_apply`, `run_rollback`) plus `pending_migration_log` + `migration_locks`. This CR follows that pattern exactly — new phase module + dispatch from `merge_queue` + audit log entry — with the same shape of `RebaseResult` dataclass.
- **CR-00019** added `batch_item_status` enum values (`awaiting_review`, `discarded`) via an additive Alembic migration. Use it as the style reference for enum additions.

## Current Behavior

1. **Worktree creation (`batch_manager._setup_worktree`)**: a git worktree is branched off main at worktree setup time. Every parallel worktree sees whatever main pointed at when its batch was launched.
2. **Database step in worktree**: agent runs `alembic revision --autogenerate -m "..."` inside the worktree, which produces a migration file with `down_revision = "<head-as-seen-in-worktree>"`. Because the worktree's `orch/db/migrations/versions/` was forked from main at setup time, this `down_revision` is the main head **at the moment the worktree was created**, not the main head at merge time.
3. **Merge queue (`merge_queue._merge_item`)** runs three serial steps for each completed batch item, in this order:
   a. `run_pre_merge_dry_run(batch_id)` — spins a blank PostgreSQL testcontainer, builds an `AlembicConfig` with `script_location = MIGRATIONS_SCRIPT_LOCATION`, and runs `alembic upgrade head`. The constant `MIGRATIONS_SCRIPT_LOCATION` in `orch/daemon/migration_pipeline.py:30` and `orch/db/safe_migrate.py:55` is derived from `__file__`, which resolves to the **daemon's** repo clone — **not** the batch's worktree. So the dry-run applies only migrations that are already on main's `orch/db/migrations/versions/`; it ignores the migration the batch just wrote. New migrations are not exercised.
   b. `executor/worktree_commit.sh` — Step 2.5 rebases the branch onto main (`git rebase main`), Step 5 squash-merges into main. The rebase picks up any migration files that previous batches merged into main, but **git rebase does not rewrite string content inside migration files**. So after the rebase, the worktree's `versions/` contains rev1 (from base), rev2a (picked up from main via rebase), and the batch's own rev2b with `down_revision = "rev1"` — two heads.
   c. `run_post_merge_apply(batch_id)` — after squash-merge, `safe_apply()` calls `list_pending_revisions()` which reads `script_location = MIGRATIONS_SCRIPT_LOCATION` (again, the daemon's repo — but this is fine here, because the squash-merge has already landed the files onto main). If the chain now has `>1` heads, `MultipleHeadsError` fires, `run_rollback` runs, and the batch is marked `migration_rolled_back`. In practice, Phase 1 has already silently passed (see 3a), so the first signal of trouble is this post-merge failure.
4. **Failure recovery**: an operator must manually run `alembic merge -m "merge branches" rev2a rev2b`, commit that merge revision to main, then re-trigger the pipeline. No automation.
5. **Observability**: `pending_migration_log` records dry-run / apply / rollback entries, but nothing about rebase need or rewrite. `DaemonEvent.event_type='migration_pipeline'` covers phase events. There is no preflight signal that a batch's base SHA is now stale.

## Desired Behavior

1. **Worktree creation and agent-side database step are unchanged.** Agents still run `alembic revision --autogenerate` inside their worktree; they produce a migration with whatever `down_revision` their worktree sees. They do not need any new coordination logic.
2. **New phase `run_pre_merge_rebase(batch_id, worktree_path, repo_root)`** runs inside `merge_queue._merge_item`, after `batch_item.status = merging` and before `run_pre_merge_dry_run`. It:
   a. Resolves an **effective main ref** by attempting `git fetch origin main` first. If the fetch succeeds, the effective ref is `origin/main` (authoritative, includes any external pushes). If the fetch fails (no `origin` remote configured, network unreachable, etc.), fall back to the local `main` ref — safe because this daemon is the sole mutator of `main` in the current architecture. Record which ref was used in the preflight DaemonEvent metadata as `effective_ref` so operators can tell the two paths apart. Then: `worktree_base_sha = git merge-base HEAD <effective_ref>`, `current_main_sha = git rev-parse <effective_ref>`. Emits a `DaemonEvent(event_type="migration_rebase", metadata={worktree_base_sha, current_main_sha, effective_ref, fetch_succeeded, rebase_needed})` — this is the preflight signal.
   b. Runs `git rebase <effective_ref>` inside the worktree (i.e., `git rebase origin/main` on the happy path, `git rebase main` on the fetch-fallback path). On conflict, `git rebase --abort`, return `RebaseResult(success=False, error_message=...)`.
   c. After rebase, lists the batch's own migration files as `git diff $(git merge-base HEAD <effective_ref>)..HEAD --name-only --diff-filter=A -- orch/db/migrations/versions/`. Parses each file to extract `revision = "..."` and `down_revision = "..."`.
   d. The batch's rebased chain is ordered by dependency: the file whose `down_revision` is NOT another file written by this batch is the **chain root**; any other files' `down_revision` references stay as internal chain links. For each of the batch's migration files in dependency order, determine the expected `down_revision`:
      - Chain root → `current_main_head`. To compute main's head reliably without hitting `MultipleHeadsError` (post-rebase the worktree's `versions/` contains both main's migrations and the batch's, so the chain has either multiple heads OR a single head that IS the batch's own file — neither helpful), copy every `.py` under `{worktree_path}/orch/db/migrations/versions/` EXCEPT the batch's own files (from the `--diff-filter=A` list in step c) into a `tempfile.TemporaryDirectory`, mirror `env.py` + `script.py.mako` alongside, run `ScriptDirectory.from_config(...).get_current_head()` there, clean up. If the tmp chain has > 1 head → `RebaseResult(success=False)` (pre-existing multi-head on main, operator intervention required). If empty → root's expected `down_revision` is `None`.
      - Non-root files → the previous file in the batch's own chain (unchanged).
   e. If the file's on-disk `down_revision` does not match the expected value, rewrite it in-place (regex replace on the `down_revision = "..."` line; preserve surrounding whitespace and comments). Record `(revision, old_down, new_down)` in `result.rewrites` and write a `PendingMigrationLog` entry with `phase="rebase"`, `direction="upgrade"`, `revision=<revision>`, `old_revision=<old_down>`, `success=True`.
   f. If any rewrites were performed, `git add orch/db/migrations/versions/*.py` + `git commit --no-verify -m "chore(migration-rebase): rewrite down_revision for <revs>"`.
   g. Return `RebaseResult(success=True, rebased=bool, rewrites=[...])`. If no stale `down_revision` was found, `rewrites=[]` and no commit is made (idempotent no-op).
3. **Phase 1 dry-run** becomes worktree-aware: `run_pre_merge_dry_run(batch_id, worktree_path)` passes `script_location = f"{worktree_path}/orch/db/migrations"` into `safe_migrate.dry_run(tempdb_url, batch_id, script_location=...)`. `safe_migrate._build_alembic_config(db_url, script_location=None)` uses the override when provided, else falls back to the main-repo `MIGRATIONS_SCRIPT_LOCATION` (backward-compat for operator CLI uses). The dry-run now walks the **full post-squash chain**: rev1 → rev2a (from main, picked up by rebase) → rev2b (this batch, with rewritten `down_revision`). Real conflicts (dropped column already dropped, column already added, etc.) surface here.
4. **Failure semantics**:
   - Rebase fails (conflict during `git rebase`, parse error on a migration file, or the batch's own migration chain is malformed) → `batch_item.status = migration_rebase_failed`, `notes = <reason>`, emit `DaemonEvent(event_type="migration_pipeline", metadata={"phase": "rebase", "success": False, ...})`, return. **Queue is NOT frozen** — the problem is isolated to this branch; subsequent batches can still merge.
   - `git fetch origin main` failing is NOT a rebase failure — it triggers the local-`main` fallback described in 2a. Operators can still detect this from the preflight DaemonEvent (`fetch_succeeded=false`, `effective_ref="main"`).
   - Rebased dry-run fails → `batch_item.status = migration_invalid` (existing behaviour, unchanged), queue NOT frozen.
   - Phase 2 apply fails → existing rollback path (unchanged), queue frozen only on rollback failure.
5. **`executor/worktree_commit.sh` is unchanged**. Its Step 2.5 rebases onto local `main` (line ~173: `git rebase main`). After `run_pre_merge_rebase` has already rebased the branch onto the effective ref (usually `origin/main`, equal to or ahead of local `main`), local `main` is by definition an ancestor of HEAD, so the bash's `merge-base HEAD main == MAIN_SHA` check at line ~168 succeeds and the rebase is skipped. This holds for both the happy path (rebased onto `origin/main`) and the fallback path (rebased onto local `main`, which obviously makes local `main` the merge-base). No bash edits are required.
6. **Audit trail**: every rewrite appears as a `pending_migration_log` row with `phase='rebase'` + populated `old_revision`. The original `DaemonEvent(event_type="migration_rebase")` gives a concise operator signal visible in the dashboard's daemon-events feed.
7. **Restart clean-up**: unchanged by design. When a work item is restarted, the previous worktree is discarded; its migration file was never on main, so nothing to clean up either in git or in the DB. `pending_migration_log` rows from the aborted run stay as historical log entries (the CR does not add any ledger to orphan).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `BatchItemStatus` enum (Python + PG) | 11 values, last added `migration_invalid`, `migration_rolled_back` | 12 values — new `migration_rebase_failed` |
| `pending_migration_log.phase` CHECK constraint | Allows `{'dry_run','apply','rollback'}` | Allows `{'dry_run','apply','rollback','rebase'}` |
| `pending_migration_log` columns | `revision, direction, phase, batch_id, started_at, completed_at, success, stdout_tail, stderr_tail, error_message` | Plus `old_revision TEXT NULL` — captures the previous `down_revision` when the rebase phase rewrites a file |
| `orch/daemon/migration_rebase.py` | Does not exist | New module — `RebaseResult` dataclass + `run_pre_merge_rebase(batch_id, worktree_path, repo_root)` |
| `orch/daemon/migration_pipeline.py:run_pre_merge_dry_run` | `run_pre_merge_dry_run(batch_id)` | `run_pre_merge_dry_run(batch_id, worktree_path: str \| None = None)` — passes through to safe_migrate |
| `orch/db/safe_migrate.py:dry_run` | `dry_run(tempdb_url, batch_id=None)` | `dry_run(tempdb_url, batch_id=None, script_location: str \| None = None)` |
| `orch/db/safe_migrate.py:_build_alembic_config` | Always reads module-level `MIGRATIONS_SCRIPT_LOCATION` | Accepts optional override, defaults to the module-level constant |
| `orch/db/safe_migrate.py:_write_migration_log` | Writes `PendingMigrationLog` without `old_revision` | Writes optional `old_revision` when caller supplies it |
| `orch/daemon/merge_queue.py:_merge_item` | Order: set-merging → dry-run → squash → apply | Order: set-merging → **rebase** → dry-run (with worktree path) → squash → apply |
| `executor/worktree_commit.sh` | Step 2.5 runs `git rebase main` unconditionally | Unchanged code; becomes a no-op when the branch has already been rebased by the new phase |
| `docs/IW_AI_Core_Daemon_Design.md` | Documents 3-phase migration pipeline | Documents 4 steps (rebase + 3 phases), failure matrix, queue-not-frozen rule |
| `docs/IW_AI_Core_Database_Schema.md` | Documents `batch_item_status` (11 values), `pending_migration_log` (9 columns, 3-value phase CHECK) | 12-value enum, 10-column table, 4-value phase CHECK |
| `CLAUDE.md` Quick Navigation table | Lists daemon, merge queue, migration pipeline | Adds `orch/daemon/migration_rebase.py` row |
| `orch/CLAUDE.md` Daemon Modules table | Lists `merge_queue.py`, `migration_pipeline.py` | Adds `migration_rebase.py` entry |

### Breaking Changes

- **None at the agent / CLI level.** Agents still run `alembic revision --autogenerate` as before. The new phase runs entirely inside the daemon's merge-queue critical section, post-completion.
- **None at the operator CLI level.** `uv run iw migrations dry-run` and `iw migrations apply --i-am-operator` keep their existing signatures; the new `script_location` kwarg on `safe_migrate.dry_run` is optional and defaults to the daemon's repo location (backward-compat).
- **None at the HTTP / dashboard level.** No new endpoints, no existing routes changed; new `DaemonEvent(event_type="migration_rebase")` rows flow through the existing daemon-events feed.
- **Enum additions are additive.** Nothing reads "enum value not in allow-list" logic today; adding `migration_rebase_failed` to both Python and Postgres is a pure union.
- **Rebase commit on the batch branch**: adds one `chore(migration-rebase): …` commit to the batch branch before squash-merge. The squash-merge collapses everything into one commit on main anyway, so main history sees no extra commit. The scope gate in `worktree_commit.sh` Step 2.25 already allows `orch/db/migrations/versions/*.py` to be edited (they're declared as allowed paths in the Database step's scope), so the rewrite does not violate scope.

### Data Migration

- **Schema migration**: single Alembic file via `alembic revision --autogenerate -m "CR-00021 migration-rebase pipeline phase"` that performs:
  1. `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_rebase_failed'` (per-value, Postgres is strict — must run outside a transaction via `op.execute` with an explicit `COMMIT`-free statement, see CR-00019 precedent).
  2. `ALTER TABLE pending_migration_log DROP CONSTRAINT ck_pending_migration_log_phase` + recreate with the 4-value allow-list.
  3. `ALTER TABLE pending_migration_log ADD COLUMN old_revision TEXT` (nullable, no default).
- **No data backfill**: existing `pending_migration_log` rows have `old_revision = NULL` (the default) and that is correct — no prior rebase-phase event occurred. Existing `batch_item.status` values are unaffected.
- **Reversibility**: full. `downgrade()` drops the column, restores the 3-value CHECK constraint, and leaves the enum in place (Postgres does not support removing an enum value; the `migration_rebase_failed` label becomes dormant but orphaned, which is harmless — same trade-off as CR-00019). Note this in the migration's downgrade docstring.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `BatchItemStatus.migration_rebase_failed` Python enum value + Alembic migration that adds the PG enum value, relaxes `ck_pending_migration_log_phase` to 4 values, and adds `pending_migration_log.old_revision TEXT NULL`; update `docs/IW_AI_Core_Database_Schema.md` | — |
| S02 | code-review-impl | Review S01 (additive migration shape, CR-00019-style `ALTER TYPE … ADD VALUE` outside tx, CHECK recreate atomicity, reversibility note, docs reflect new enum + column) | — |
| S03 | backend-impl | Create `orch/daemon/migration_rebase.py`: `RebaseResult` dataclass, `run_pre_merge_rebase`, helper internals (git fetch/rebase/diff, parse migration file, rewrite `down_revision`, commit). Idempotent when no rewrite needed. Emits `DaemonEvent(event_type="migration_rebase")` + per-rewrite `PendingMigrationLog(phase="rebase")`. | — |
| S04 | code-review-impl | Review S03 (subprocess safety — `shell=False`, timeouts, `check=False`; idempotency when rewrites=[] → no commit; git rebase conflict → abort + graceful failure; `_write_migration_log` call includes `old_revision`; no-op happy path matches precedent from migration_pipeline.py) | — |
| S05 | backend-impl | Modify `orch/db/safe_migrate.py` (`dry_run` + `_build_alembic_config` + `_write_migration_log` accept optional `script_location` and `old_revision`; backward-compat defaults), `orch/daemon/migration_pipeline.py` (`run_pre_merge_dry_run(batch_id, worktree_path=None)` threads script_location through), `orch/daemon/merge_queue.py` (insert `run_pre_merge_rebase` before Phase 1; pass `worktree_path` into dry-run; handle `migration_rebase_failed` status) | S03 — can run after S03 lands |
| S06 | code-review-impl | Review S05 (signature backward-compat on operator call sites, correct error-path wiring in merge_queue, preservation of queue-not-frozen rule, no regression to Phase 2 semantics, `_write_migration_log` callers updated consistently) | — |
| S07 | tests-impl | Unit tests: `tests/unit/daemon/test_migration_rebase.py` (rewrite happy path, idempotent no-op, multi-file chain preserves internal links, rebase conflict returns rebase_failed, parse error, fetch failure). Extend `tests/unit/daemon/test_migration_pipeline.py` with `test_dry_run_threads_worktree_script_location` + `test_dry_run_fails_on_worktree_bad_migration`. Integration tests: `tests/integration/test_parallel_migrations.py` (two worktrees, disjoint column adds → both merge cleanly and alembic chain is linearised) and `tests/integration/test_migration_rebase_conflict.py` (both batches add same column → rebase rewrites, dry-run fails, status=migration_invalid, main untouched) | — |
| S08 | code-review-impl | Review S07 (AC coverage map, no DB mocks in integration, testcontainer fixtures reused, deterministic migration revision IDs in fixtures, scope gate not breached by test fixtures, realistic multi-head simulation) | — |
| S09 | backend-impl | Docs updates: `docs/IW_AI_Core_Daemon_Design.md` (insert "Phase 0: Pre-merge rebase" subsection, update failure-matrix table), `docs/IW_AI_Core_Database_Schema.md` (update `batch_item_status` enum + `pending_migration_log` CHECK + columns — S01 already did the schema row, S09 tightens the narrative), `CLAUDE.md` Quick Navigation (new row: "Migration rebase phase — `orch/daemon/migration_rebase.py`"), `orch/CLAUDE.md` Daemon Modules table (new `migration_rebase.py` row) | S03 / S05 / S07 gates complete |
| S10 | code-review-final-impl | Cross-layer review: trace AC1–AC7 through schema → module → wiring → tests → docs; verify queue-not-frozen holds for both new failure states; verify `safe_migrate.dry_run` stays backward-compatible for operator entry points; no regression to existing CR-00017 paths | — |
| S11 | qv-gate | lint (`make lint`) | — |
| S12 | qv-gate | format (`uv run ruff format --check .`) | — |
| S13 | qv-gate | typecheck (`make typecheck`) | — |
| S14 | qv-gate | unit-tests (`make test-unit`) | — |
| S15 | qv-gate | integration-tests (`make test-integration`) | — |

No `qv-browser` step — this CR is backend-only (daemon + schema + docs). `browser_verification: false` in the manifest.

### Database Changes

- **New tables**: none
- **Modified tables**: `pending_migration_log` — add `old_revision TEXT NULL`, update `ck_pending_migration_log_phase` to allow `'rebase'`
- **Modified enums**: `batch_item_status` — add `migration_rebase_failed`
- **Migration notes**: `ALTER TYPE … ADD VALUE` cannot run inside the same transaction that uses it; follow CR-00019 precedent by running the enum add as a raw `op.execute(...)` statement with the Alembic migration's autocommit-block (`with op.get_context().autocommit_block():`) or — preferred — split it into its own migration step at the top of `upgrade()`. Recreate the CHECK constraint atomically (drop + add within the same migration; drop-then-add is safe because no concurrent writer emits `phase='rebase'` until S03/S05 deploy). Reversibility note: Postgres cannot drop an enum label; `downgrade()` leaves `migration_rebase_failed` as a dormant orphan and restores the 3-value CHECK. Document this in the migration's module docstring.

### API Changes

- **New endpoints**: none
- **Modified endpoints**: none
- **Removed endpoints**: none

### Frontend Changes

- **New components**: none
- **Modified components**: none (the dashboard already renders `DaemonEvent` rows generically and `BatchItem.status` via existing status-pill styling; the new status value flows through unchanged)
- **Removed components**: none

## File Manifest

All files for this work item live under `ai-dev/active/CR-00021/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00021_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator (+ `scope.allowed_paths`) |
| `prompts/CR-00021_S01_Database_prompt.md` | Prompt | Schema changes — enum add, CHECK relax, new column, docs |
| `prompts/CR-00021_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00021_S03_Backend_prompt.md` | Prompt | `migration_rebase.py` module — rebase + rewrite + log |
| `prompts/CR-00021_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00021_S05_Backend_prompt.md` | Prompt | `safe_migrate` / `migration_pipeline` / `merge_queue` wiring |
| `prompts/CR-00021_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00021_S07_Tests_prompt.md` | Prompt | Unit + integration test suite |
| `prompts/CR-00021_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00021_S09_Backend_prompt.md` | Prompt | Docs updates (design, schema, navigation) |
| `prompts/CR-00021_S10_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |

Reports are written during execution in `ai-dev/active/CR-00021/reports/`.

Expected production-code files to be created/modified by implementation steps:

- `orch/db/models.py` — add `BatchItemStatus.migration_rebase_failed`, add `PendingMigrationLog.old_revision` column (modify)
- `orch/db/migrations/versions/<hash>_cr_00021_rebase_pipeline_phase.py` — Alembic migration (new)
- `orch/daemon/migration_rebase.py` — new module
- `orch/daemon/migration_pipeline.py` — add worktree_path parameter to `run_pre_merge_dry_run` (modify)
- `orch/daemon/merge_queue.py` — insert rebase phase, thread worktree_path, handle new status (modify)
- `orch/db/safe_migrate.py` — optional `script_location` / `old_revision` wiring (modify)
- `tests/unit/daemon/test_migration_rebase.py` — new
- `tests/unit/daemon/test_migration_pipeline.py` — extend (modify)
- `tests/integration/test_parallel_migrations.py` — new
- `tests/integration/test_migration_rebase_conflict.py` — new
- `docs/IW_AI_Core_Daemon_Design.md` — new "Phase 0: pre-merge rebase" subsection (modify)
- `docs/IW_AI_Core_Database_Schema.md` — enum + column + CHECK updates (modify, starts in S01 and finalised in S09)
- `CLAUDE.md` — Quick Navigation row (modify)
- `orch/CLAUDE.md` — Daemon Modules table row (modify)

## Acceptance Criteria

### AC1: Rebase rewrites stale `down_revision` and commits the edit

```
Given a worktree branched off main at rev1, with the batch's own migration file
      versions/rev2b_add_col_b.py containing down_revision = "rev1",
  and main has since advanced to rev2a (another batch merged rev2a → applied),
  and `git fetch origin main` succeeds (origin is reachable)
When run_pre_merge_rebase(batch_id, worktree_path, repo_root) runs
Then the effective ref resolves to 'origin/main' (fetch_succeeded=true), AND
     the worktree's branch is rebased onto origin/main's current tip (rev2a now reachable), AND
     versions/rev2b_add_col_b.py now has down_revision = "rev2a" (exact string replacement), AND
     a single git commit is added to the branch with message starting
       "chore(migration-rebase): rewrite down_revision for rev2b", AND
     pending_migration_log has one new row with
       phase='rebase', direction='upgrade', revision='rev2b',
       old_revision='rev1', success=true, AND
     a DaemonEvent with event_type='migration_rebase' is written with
       event_metadata.worktree_base_sha, .current_main_sha, .effective_ref='origin/main',
       .fetch_succeeded=true, .rebase_needed=true, AND
     RebaseResult(success=true, rebased=true,
       rewrites=[('rev2b','rev1','rev2a')]) is returned.
```

### AC2: Rebase is idempotent when `down_revision` already matches main head

```
Given a worktree branched off main at rev2a, with the batch's migration file
      having down_revision = "rev2a",
  and main is still at rev2a (no other batch has merged since)
When run_pre_merge_rebase runs
Then no migration file is rewritten, AND
     no git commit is created by the rebase phase, AND
     no pending_migration_log row with phase='rebase' is written for this batch, AND
     a DaemonEvent(event_type='migration_rebase') is written with
       event_metadata.rebase_needed=false (for observability), AND
     RebaseResult(success=true, rebased=false, rewrites=[]) is returned.
```

### AC3: Multi-file batch preserves internal chain links

```
Given a worktree whose batch added two migration files in order:
      revB1.py with down_revision = "rev1"   (chain root)
      revB2.py with down_revision = "revB1"  (internal link)
  and main has advanced to rev2a
When run_pre_merge_rebase runs
Then revB1.py now has down_revision = "rev2a", AND
     revB2.py still has down_revision = "revB1" (unchanged — internal link preserved), AND
     pending_migration_log has exactly one phase='rebase' row (for revB1), AND
     RebaseResult.rewrites == [('revB1','rev1','rev2a')].
```

### AC4: Rebase conflict aborts cleanly and flips status to `migration_rebase_failed`

```
Given a worktree whose branch has a conflicting edit on a file also changed on main
      (e.g., both edited orch/db/models.py on the same lines)
When the merge-queue calls run_pre_merge_rebase
Then `git rebase main` fails, `git rebase --abort` restores the branch to its
     pre-rebase state, AND
     the worktree's migration files are NOT rewritten, AND
     batch_item.status is updated to 'migration_rebase_failed' with notes
     containing the conflict description, AND
     a DaemonEvent(event_type='migration_pipeline') is emitted with
       event_metadata.phase='rebase', .success=false, AND
     the merge queue is NOT frozen — process_merge_queue in the next poll
     cycle picks up the next completed batch item and proceeds with ITS rebase.
```

### AC5: Phase 1 dry-run uses the worktree's migrations directory

```
Given a worktree whose versions/ contains a migration that intentionally fails
      to apply (e.g., drops a column that doesn't exist at rev2a)
  and the daemon's main-repo versions/ contains ONLY rev1 → rev2a (no failure)
When run_pre_merge_dry_run(batch_id, worktree_path) runs after a successful rebase
Then safe_migrate.dry_run is invoked with
       script_location = f"{worktree_path}/orch/db/migrations", AND
     the testcontainer applies rev1 → rev2a → <broken migration> and fails, AND
     pending_migration_log has a phase='dry_run' row with success=false
     whose error_message cites the broken operation, AND
     the call returns PipelineResult(phase='dry_run', success=false,
       final_batch_state='MIGRATION_INVALID'), AND
     the merge queue is NOT frozen.
```

### AC6: Two parallel batches with disjoint schema changes both merge successfully

```
Given main at rev1
  and batch A (worktree A) adds migration revA with down_revision='rev1'
      (adds column users.col_a)
  and batch B (worktree B) adds migration revB with down_revision='rev1'
      (adds column users.col_b)
  and both batches complete their implementation + QV steps
When batch A reaches the merge queue first and completes the full pipeline
  (rebase → dry-run → squash-merge → apply)
  and then batch B reaches the merge queue
Then after batch A merges, main is at revA with col_a applied to the live DB, AND
     when batch B runs run_pre_merge_rebase:
       its worktree is rebased onto main (revA now reachable),
       revB's down_revision is rewritten from 'rev1' to 'revA', AND
     batch B's Phase 1 dry-run (now testing the worktree's migrations) applies
       rev1 → revA → revB successfully, AND
     batch B's squash-merge lands onto main and Phase 2 applies revB to live DB, AND
     after both merges, `alembic current` returns revB, `alembic history` shows
       a linear chain rev1 → revA → revB, AND
     both batch_items end with status='merged'.
```

### AC7: Two parallel batches with conflicting schema changes — rebase rewrites, Phase 1 catches the real conflict

```
Given main at rev1
  and batch A adds migration revA that adds column users.duplicate
  and batch B adds migration revB that also adds column users.duplicate
  and batch A has already merged (main at revA with col_duplicate applied)
When batch B enters the merge queue
Then run_pre_merge_rebase succeeds (rebase + rewrite revB.down_revision='revA'), AND
     pending_migration_log has a phase='rebase' row for revB
       with old_revision='rev1', success=true, AND
     run_pre_merge_dry_run(batch_id, worktree_path) FAILS because the testcontainer
       already has col_duplicate from revA when it tries to run revB, AND
     pending_migration_log has a phase='dry_run' row with success=false
       whose error_message references the duplicate-column failure, AND
     batch_item.status = 'migration_invalid' (not 'migration_rebase_failed'), AND
     main has NOT been touched (no squash-merge ran), AND
     the merge queue is NOT frozen — next batch can still merge.
```

## Rollback Plan

- **Database**: Alembic `downgrade -1` drops `pending_migration_log.old_revision`, restores the 3-value `ck_pending_migration_log_phase` CHECK constraint, and leaves the `migration_rebase_failed` enum label in the PG enum (Postgres cannot drop enum values; the label becomes dormant — same trade-off as CR-00019). The Python `BatchItemStatus.migration_rebase_failed` member is removed with the code revert. The daemon will not emit the label once the code is reverted, so no live rows carry it.
- **Code**: revert the merge commit. `merge_queue._merge_item` returns to the pre-CR order (dry-run → squash → apply) and the missing `script_location` parameter on `safe_migrate.dry_run` falls back to the main-repo location it used before. No feature flag needed — the rollback is a straight revert.
- **Data**: no data loss. `pending_migration_log` rows with `phase='rebase'` written between deploy and revert become invisible to the post-revert code path (they are historical log entries; the dashboard and operators read by `phase IN ('dry_run','apply','rollback')` in the post-revert view). If the dormant rebase rows must be purged, a one-off `DELETE FROM pending_migration_log WHERE phase='rebase'` is safe.
- **In-flight batches at revert time**: any batch that has already been rebased by the new phase but not yet merged will keep its rewritten `down_revision` (the edit is a committed git change on the branch). After revert, the batch's rebase has effectively been done for free; `worktree_commit.sh` Step 2.5 will re-rebase (no-op), Phase 1 dry-run will behave as before (main's migrations only — the pre-existing bug returns until a future CR re-fixes it), and Phase 2 apply will succeed if the chain is single-head. No operator intervention required.

## Dependencies

- **Depends on**: CR-00017 (3-phase migration pipeline is the precondition — this CR extends it).
- **Blocks**: None currently planned. A potential future CR could add a DB-backed revision allocation ledger for richer observability; this CR does not introduce or require it.

## TDD Approach

### Unit tests (no live DB; may use `tmp_path` + `subprocess` against a scratch git repo)

`tests/unit/daemon/test_migration_rebase.py`:

- `test_rewrite_single_migration_stale_down_revision` — bootstrap a scratch git repo with main at `rev2a` and a batch branch at `rev1` with a migration `revB(down='rev1')`; run `run_pre_merge_rebase`; assert the file is rewritten to `down='rev2a'`, one git commit added, `RebaseResult.rewrites == [('revB','rev1','rev2a')]`.
- `test_no_op_when_down_revision_matches_main_head` — worktree already on `rev2a` base, migration `down='rev2a'`; assert no rewrite, no commit, `rewrites=[]`, but `DaemonEvent` with `rebase_needed=false` still emitted.
- `test_multiple_migrations_preserve_internal_chain` — batch added `revB1(down='rev1')` + `revB2(down='revB1')`; main at `rev2a`; assert only `revB1` rewritten (to `down='rev2a'`), `revB2` untouched.
- `test_rebase_conflict_returns_migration_rebase_failed` — conflicting edit on both branches; `git rebase main` fails; assert `result.success=False`, `result.error_message` populated, `git rebase --abort` ran (verify by checking worktree is back on the pre-rebase SHA).
- `test_parse_migration_failure` — malformed migration file (missing `down_revision` assignment); assert `result.success=False` with a clear parse-error message.
- `test_fetch_failure_falls_back_to_local_main` — stub `git fetch origin main` to fail (e.g., remove the remote or misconfigure it); assert `result.success=True` (the phase continues), `result.rebased` reflects the rebase against local `main`, the preflight DaemonEvent has `event_metadata.fetch_succeeded=false` and `.effective_ref="main"`, and any stale `down_revision` is still rewritten (because local `main` IS authoritative in the current architecture).
- `test_pending_migration_log_has_old_revision` — after a successful rewrite, assert exactly one `PendingMigrationLog` row with `phase='rebase'`, `revision='revB'`, `old_revision='rev1'`, `success=True`.

`tests/unit/daemon/test_migration_pipeline.py` (extend):

- `test_dry_run_threads_worktree_script_location` — monkeypatch `safe_migrate.dry_run`; call `run_pre_merge_dry_run(batch_id, worktree_path="/wt")`; assert the `script_location="/wt/orch/db/migrations"` kwarg was passed.
- `test_dry_run_backward_compat_without_worktree_path` — call without `worktree_path`; assert `safe_migrate.dry_run` receives `script_location=None`.

### Integration tests (testcontainer, no DB mocking)

`tests/integration/test_parallel_migrations.py` — AC6 happy path:

- Seed testcontainer at `rev1` (shared base).
- Build two scratch worktrees (via `tmp_path` + git worktree), each adds a distinct disjoint migration (`add users.col_a`, `add users.col_b`).
- Drive the merge pipeline end-to-end for batch A: rebase → dry-run → squash → apply. Assert live DB schema has `col_a`.
- Drive the merge pipeline for batch B against the same DB and repo. Assert after rebase that `revB.down_revision == revA`, dry-run succeeds, squash-merge succeeds, apply succeeds. Assert `alembic current` reflects `revB` and history is linear.
- Assert both `batch_items.status == 'merged'`.

`tests/integration/test_migration_rebase_conflict.py` — AC7:

- Seed testcontainer at `rev1`.
- Two worktrees, both add `users.duplicate` column (same name, same type).
- Merge batch A fully.
- Drive batch B: rebase succeeds + rewrites `down_revision='revA'`, dry-run FAILS on duplicate-column error. Assert `batch_items.status == 'migration_invalid'`, `pending_migration_log` has `phase='rebase' success=true` and `phase='dry_run' success=false` rows for this batch, main is unchanged (git log on main == revA's merge commit), merge queue is NOT frozen.

### Updated tests

- Existing tests calling `run_pre_merge_dry_run(batch_id)` (no worktree arg) must still pass — the new parameter is optional. S07 audits and updates any test that should switch to the worktree-aware call.
- Tests that consume `pending_migration_log` rows (filtering by phase or asserting column count) may need to tolerate the new `old_revision` column; update assertions to use named columns, not positional.

## Notes

- **Why no schema lock?** A schema lock would serialise every batch touching any migration, even disjoint ones. The merge queue already serialises merging; the only missing piece is the `down_revision` rewrite at merge time — which runs in the merge-queue critical section and is cheap. Parallelism during implementation stays intact.
- **Why rebase the branch at the phase level instead of relying on `worktree_commit.sh`?** The bash script already rebases, but it runs AFTER `run_pre_merge_dry_run`. Moving the rebase earlier is what lets Phase 1 see the real post-squash chain. The script's own rebase becomes a no-op (branch's merge-base already equals main's SHA) without any bash edits — lower blast radius than modifying the deterministic bash.
- **Why `origin/main` with a local-`main` fallback rather than just local `main`?** At time of writing, the daemon is the sole mutator of `main` (`check_auto_publish` is a stub and no `git fetch/pull/push` exists in `orch/` or `executor/`), so local `main` == authoritative `main` in practice. Using `origin/main` as the primary target is forward-compatible: the day someone wires up daemon push/pull or a coworker pushes to the same repo, the rebase phase stays correct without a code change. The fetch-failure fallback to local `main` ensures the phase still works in projects without an `origin` remote configured (self-hosted scratch repos, tests).
- **Why `git rebase` instead of `git merge --no-ff`?** Rebase keeps the branch linear (one batch = one squash commit = one main commit). Merge commits would complicate the squash-merge downstream. Rebase failure semantics are well-understood and matches the existing worktree_commit.sh behavior.
- **Parsing migration files**: the parser only needs to read `revision = "..."` and `down_revision = "..." | None` near the top of the file (before the `def upgrade()` block). Use a simple regex — don't `ast.parse` or `importlib` the file (module import would re-execute arbitrary code and produce noisy side effects on test runs).
- **Observability follow-up**: a future CR could add a dashboard filter on `event_type='migration_rebase'` to surface rebase activity. Not in scope here — the existing daemon-events feed already renders the events.
- **Risks**:
  - **Rebase latency in merge queue**: `git fetch` + `git rebase` add seconds to the critical section. Acceptable for current batch cadence.
  - **Models.py three-way merge ambiguity**: git auto-merges disjoint edits safely, but two batches editing the same model class on nearby lines can produce a conflict. AC4 covers the rebase-conflict path. True semantic conflicts (two batches agreeing syntactically but producing a broken schema together) would be caught by Phase 1 — this is exactly what AC7 verifies.
  - **Scope-gate interaction**: the rebase phase writes a commit that edits `orch/db/migrations/versions/*.py`. S01 ensures the Database step's workflow manifest lists `orch/db/migrations/versions/*.py` as in-scope for the pipeline agents. The rebase commit itself is made by the daemon (not an agent), and the scope gate runs against the final branch diff — it already sees these files as modified, so adding one more hunk in the same file does not expand the diff's file set. No scope-gate bypass needed.
  - **Alembic autogenerate in a subsequent batch**: after a rewrite, if the batch then regenerates the migration (e.g., during a fix cycle that re-runs `alembic revision --autogenerate`), the rewritten file might be replaced with a fresh `down_revision` pointing at whatever the worktree's then-current head is. This is the correct behaviour — the rebase phase will simply rewrite the new file at its next merge-queue attempt. Idempotent.
