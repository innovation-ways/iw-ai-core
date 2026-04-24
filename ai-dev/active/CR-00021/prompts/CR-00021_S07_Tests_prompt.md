# CR-00021_S07_Tests_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. No `docker compose up/down/stop/kill/rm`. `./ai-core.sh` / `make` fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Inside testcontainer fixtures is the only valid place to apply/rollback migrations. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (AC1–AC7 are the spec for this test suite)
- `ai-dev/active/CR-00021/reports/CR-00021_S03_Backend_report.md` — `migration_rebase.py` contract
- `ai-dev/active/CR-00021/reports/CR-00021_S05_Backend_report.md` — wiring contract
- `orch/daemon/migration_rebase.py`, `orch/daemon/migration_pipeline.py`, `orch/daemon/merge_queue.py`, `orch/db/safe_migrate.py` — modules under test
- `tests/conftest.py` — testcontainer fixture (`pg_engine`, `pg_session`), FTS DDL rules, testcontainer URL replace (`psycopg2://` → `psycopg://`)
- `tests/CLAUDE.md` — testing conventions (no DB mocking in integration, no live DB, no `importlib.reload(orch.config)`)
- `tests/unit/daemon/test_migration_pipeline.py`, `tests/unit/daemon/test_migration_rebase.py`, `tests/unit/daemon/test_safe_migrate.py`, `tests/unit/daemon/test_merge_queue.py` — existing / S03-S05 additions to extend
- Any existing `tests/integration/test_*migration*.py` as style reference for testcontainer-based migration tests

## Output Files

- `tests/unit/daemon/test_migration_rebase.py` (extended from S03's local version) — full coverage
- `tests/unit/daemon/test_migration_pipeline.py` (extended) — worktree_path threading
- `tests/unit/daemon/test_safe_migrate.py` (extended if needed) — script_location + old_revision
- `tests/integration/test_parallel_migrations.py` (new) — AC6 end-to-end happy path
- `tests/integration/test_migration_rebase_conflict.py` (new) — AC7 end-to-end conflict path
- `ai-dev/active/CR-00021/reports/CR-00021_S07_Tests_report.md` — step report

## Context

Build the full test suite covering AC1–AC7 from the design document. S03 and S05 wrote some local tests; your job is to complete coverage, add integration tests, and ensure the test suite catches regressions for both the new rebase phase and the worktree-aware dry-run.

**Key constraints**: no DB mocking in integration tests (FOR UPDATE locking is real); testcontainer URL must have `psycopg2://` replaced with `psycopg://`; after `Base.metadata.create_all()` in testcontainers you must execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (per `tests/CLAUDE.md`).

## Requirements

### 1. Unit tests — `tests/unit/daemon/test_migration_rebase.py`

Build on whatever local tests S03 added. Target coverage (AC1-AC4 from the design):

**Fixture helpers** (module-level, reusable across tests):

- `scratch_repo(tmp_path) -> Path` — initialises a git repo with `main` branch containing:
  - `orch/db/migrations/versions/rev1_initial.py` with `revision = "rev1"`, `down_revision = None`
  - Commits `rev1` on main
- `scratch_branch(repo, branch_name, main_head, migration_spec) -> None` — creates a branch from `main_head`, adds `migration_spec` as a new migration file, commits.
- `advance_main(repo, new_migration_spec) -> str` — adds a new migration on main, commits, returns the new revision id.

**Test cases**:

1. `test_rewrite_single_migration_stale_down_revision` (AC1):
   - Scratch repo at rev1. Advance main to rev2a. Create worktree branch off rev1 with `revB(down="rev1")`.
   - Call `run_pre_merge_rebase(batch_id=1, worktree_path=<wt>, repo_root=<repo>)`.
   - Assert: `result.success=True`, `result.rebased=True`, `result.rewrites == [Rewrite('revB','rev1','rev2a')]`.
   - Assert: the file on disk now has `down_revision = "rev2a"` (exact string match).
   - Assert: a new commit exists on the worktree branch with message starting `"chore(migration-rebase)"`.

2. `test_no_op_when_down_revision_matches_main_head` (AC2):
   - Scratch repo at rev2a. Worktree off rev2a with `revB(down="rev2a")`.
   - Call `run_pre_merge_rebase`.
   - Assert: `result.success=True`, `result.rebased=False`, `result.rewrites == []`.
   - Assert: no new commit on the branch (HEAD SHA unchanged).
   - Assert: DaemonEvent emitted with `rebase_needed=False`.

3. `test_multiple_migrations_preserve_internal_chain` (AC3):
   - Scratch repo at rev1. Advance main to rev2a. Worktree off rev1 with `revB1(down="rev1")`, `revB2(down="revB1")`.
   - Call `run_pre_merge_rebase`.
   - Assert: `revB1` rewritten (`down="rev2a"`), `revB2` untouched (`down="revB1"`).
   - Assert: `result.rewrites` contains exactly one entry, for revB1.

4. `test_rebase_conflict_returns_migration_rebase_failed` (AC4):
   - Scratch repo at rev1. Advance main by editing `orch/db/models.py` line 10. Worktree off rev1 also edits `orch/db/models.py` line 10 (conflicting).
   - Call `run_pre_merge_rebase`.
   - Assert: `result.success=False`, `result.error_message` contains "rebase" or "conflict".
   - Assert: worktree's HEAD SHA is restored to its pre-rebase value (rebase --abort ran).

5. `test_parse_migration_failure`:
   - Worktree migration file with no `down_revision` line at all.
   - Assert: `result.success=False`, error message mentions parse / down_revision.

6. `test_fetch_failure`:
   - Remove the remote origin before calling; `git fetch origin main` fails.
   - Assert: `result.success=False`, error message mentions fetch.

6a. `test_latest_main_revision_excludes_batch_files`:
   - Scratch repo at rev1. Advance main to rev2a. Worktree off rev1 with `revB(down="rev1")`.
   - Pre-condition assertion: `ScriptDirectory.get_current_head()` against the post-rebase worktree's raw `versions/` dir would raise `MultipleHeadsError` (demonstrates WHY the helper must exclude batch files).
   - Call the helper directly (or call `run_pre_merge_rebase` and inspect `result.rewrites[0].new_down_revision`); assert main's head is identified as `rev2a` (NOT `revB`).
   - Assert the tmp directory is cleaned up (no leftover `cr21-main-head-*` dirs in the system tmp).

6b. `test_latest_main_revision_preexisting_multi_head_fails_cleanly`:
   - Scratch repo where main itself has two heads (e.g., advance main with two commits that each add a migration with `down_revision="rev1"` — a pre-existing bad state outside this CR's fault).
   - Worktree off rev1 with a new `revB`.
   - Call `run_pre_merge_rebase`; assert `result.success=False` and `error_message` mentions "multiple heads" / "manual intervention".
   - Assert no migration file was rewritten (helper fails before step 8).

7. `test_pending_migration_log_written_on_rewrite`:
   - Use the testcontainer `pg_session` fixture (this test is still "unit" in the sense of testing the module, but requires a DB for the log write — OR use a separate pg_session fixture per project convention).
   - Call `run_pre_merge_rebase` against a stale worktree.
   - Query `PendingMigrationLog` — assert exactly one row with `phase='rebase'`, `revision='revB'`, `old_revision='rev1'`, `success=True`.

8. `test_daemon_event_always_emitted`:
   - Even in the idempotent no-op case (AC2), a DaemonEvent with `event_type='migration_rebase'` must exist in the `daemon_events` table afterwards.

If any of tests 7-8 need a DB, place them in an `@pytest.mark.integration` section or in `tests/integration/` — follow the project's convention for DB-touching unit tests (grep `tests/unit/daemon/test_migration_pipeline.py` for precedent).

### 2. Unit tests — `tests/unit/daemon/test_migration_pipeline.py` (extend)

Add / ensure:

1. `test_run_pre_merge_dry_run_threads_worktree_path`:
   - Monkeypatch `orch.daemon.migration_pipeline.safe_dry_run` to a recording stub.
   - Call `run_pre_merge_dry_run(batch_id=1, worktree_path="/tmp/wt")`.
   - Assert the stub was called with `script_location="/tmp/wt/orch/db/migrations"`.

2. `test_run_pre_merge_dry_run_backward_compat`:
   - Call `run_pre_merge_dry_run(batch_id=1)` (no `worktree_path`).
   - Assert the stub was called with `script_location=None`.

### 3. Unit tests — `tests/unit/daemon/test_safe_migrate.py` (extend if needed)

Add:

1. `test_build_alembic_config_override_respected`:
   - Call `_build_alembic_config(db_url="...", script_location="/foo")` — assert `cfg.get_main_option("script_location") == "/foo"`.
   - Call `_build_alembic_config(db_url="...")` — assert it falls back to `MIGRATIONS_SCRIPT_LOCATION`.

2. `test_write_migration_log_old_revision_persisted` (requires pg_session):
   - Call `_write_migration_log(revision="revB", direction="upgrade", phase="rebase", batch_id=1, success=True, stdout_tail="", stderr_tail="", error_message=None, old_revision="rev1")`.
   - Query back — assert `phase='rebase'`, `old_revision='rev1'`.

3. `test_write_migration_log_backward_compat_no_old_revision`:
   - Call without `old_revision` (existing call sites). Row has `old_revision IS NULL`.

### 4. Integration tests — `tests/integration/test_parallel_migrations.py` (new, AC6)

**Scope**: end-to-end exercise of the full merge pipeline for two parallel batches with disjoint schema changes.

Approach:

1. Use the `pg_engine` testcontainer fixture plus a `scratch_repo` factory that creates a temporary git repo with the project's `orch/db/migrations/versions/` initialised to a known starting point (rev1).
2. Create two worktrees branched off rev1. In worktree A, add `revA_add_col_a.py` with `op.add_column("users", sa.Column("col_a", sa.Text(), nullable=True))`. In worktree B, add `revB_add_col_b.py` with the `col_b` equivalent.
3. Drive batch A through the full pipeline: `run_pre_merge_rebase(A)` → `run_pre_merge_dry_run(A, worktree_path=<A>)` → invoke `worktree_commit.sh` (use a bash subprocess against the scratch repo) → `run_post_merge_apply(A)`.
4. After A completes: assert `alembic current` against the testcontainer returns revA; assert `users.col_a` exists in the schema.
5. Drive batch B through the full pipeline. Critical assertion: after `run_pre_merge_rebase(B)`, the `revB_add_col_b.py` file in worktree B has `down_revision = "revA"` (not `"rev1"`).
6. After B completes: assert `alembic current` returns revB; `alembic history` shows rev1 → revA → revB linearly; `users.col_b` exists in the schema; both `col_a` and `col_b` are present.
7. Assert `batch_items.status == 'merged'` for both A and B.

**Fixture utilities** may live in `tests/integration/conftest.py` or in the new test file's module-level helpers — whichever matches the project's integration test style.

### 5. Integration tests — `tests/integration/test_migration_rebase_conflict.py` (new, AC7)

Same scaffolding, but this time both batches add the SAME column (`users.duplicate`):

1. Drive batch A to completion. Assert `col_duplicate` exists.
2. For batch B: `run_pre_merge_rebase(B)` SUCCEEDS (rebase + rewrite revB.down_revision='revA'). Then `run_pre_merge_dry_run(B, worktree_path=<B>)` FAILS (the testcontainer already has `col_duplicate` from revA; revB tries to add it again).
3. Simulate `merge_queue._merge_item`'s response: set `batch_item.status='migration_invalid'`.
4. Assert: `pending_migration_log` has a `phase='rebase' success=true` row for revB with `old_revision='rev1'`, AND a `phase='dry_run' success=false` row for this batch.
5. Assert: main branch's HEAD is unchanged from the batch-A merge commit (no batch-B merge landed).
6. Assert: the merge queue can still be processed — call `process_merge_queue` with a third dummy batch item and verify it proceeds (queue NOT frozen).

### 6. Updated / regression tests

Grep the test suite for:
- `run_pre_merge_dry_run(` — any test calling without `worktree_path` should still pass (backward compat). Do NOT change their signatures; just confirm they still run.
- `_write_migration_log(` — any test asserting row contents by positional tuple access must be switched to named column access (the new `old_revision` column shifts tuple order).

If `process_merge_queue` / `_merge_item` tests exist in `tests/unit/daemon/test_merge_queue.py` from S05, ensure they:
- Stub `run_pre_merge_rebase` — do NOT actually run git in unit tests.
- Stub `run_pre_merge_dry_run` — do NOT actually spin testcontainers in unit tests.

## Project Conventions

- No DB mocking in integration tests (CLAUDE.md rule).
- `tests/conftest.py` provides `pg_engine` and `pg_session`; use them — do NOT create new engines.
- Testcontainer URL must have `psycopg2://` → `psycopg://` replacement (CLAUDE.md rule).
- After `Base.metadata.create_all()` in testcontainers, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`.
- Never `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- Tests isolated: each test function gets a fresh schema (or a fresh transaction that's rolled back — match existing fixture style).
- Integration test names descriptive: `test_parallel_batches_with_disjoint_migrations_both_merge_linearly`, not `test_e2e_1`.
- File headers follow the existing project style (license banner if present, module docstring).

## TDD Requirement

You are writing the tests. Follow Red-Green-Refactor in the sense that:

1. Write each test to fail first against a `pytest.fail("not implemented")` stub (RED).
2. Verify the module under test (already implemented in S03/S05) makes the test pass (GREEN).
3. Refactor for clarity — extract helpers, name assertions.

If any test fails against the current implementation, that's a genuine regression — report it in the blockers, do NOT "fix" the implementation.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass
2. `make test-integration` — must pass (the new integration tests run here)
3. `make lint` / `make format` / `make typecheck` — must pass
4. Report accurately, with integration + unit counts separate.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_migration_rebase.py",
    "tests/unit/daemon/test_migration_pipeline.py",
    "tests/unit/daemon/test_safe_migrate.py",
    "tests/integration/test_parallel_migrations.py",
    "tests/integration/test_migration_rebase_conflict.py"
  ],
  "tests_passed": true,
  "test_summary": "unit X passed; integration Y passed; 0 failed",
  "blockers": [],
  "notes": ""
}
```
