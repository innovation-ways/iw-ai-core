# I-00063: Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session

**Type**: Issue
**Severity**: High
**Created**: 2026-05-04
**Reported By**: sergio (operator) — observed live on iw-ai-core orch DB during I-00062 / BATCH-00075 merge
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

This issue does NOT add or modify any migration. It only changes the
daemon's session lifecycle around `run_post_merge_apply()`.

Standard rule still applies: agents must never run `alembic upgrade`,
`downgrade`, or `stamp` against the live orch DB. Test code may run
alembic against testcontainer URLs only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The daemon's merge pipeline self-deadlocks: after a successful squash-merge,
`_merge_item` keeps the orchestration `Session` open with uncommitted reads on
`projects` and `batch_items`, then immediately invokes `run_post_merge_apply()`
in the same process. Phase 2's `command.upgrade(cfg, "head")` opens a
**separate** connection and requests `AccessExclusiveLock` for the migration's
DDL. That ALTER blocks behind the daemon's own idle-in-transaction session.
PostgreSQL's lock-grant queue then blocks every subsequent reader of the
target table behind the pending exclusive — exhausting the dashboard
connection pool and freezing the merge queue.

User-visible impact: dashboard banner "Orch DB schema is behind head", every
page that touches `batch_items` hangs (project home, batches, item detail),
daemon stops processing batches. Recovery requires SIGKILL + manual SQL +
`make db-migrate`.

## Project Context

Read `CLAUDE.md` and `orch/CLAUDE.md` for architecture, layer rules, and
non-negotiables (psycopg v3 only, sync SQLAlchemy 2.0, append-only
event tables, etc.). Read `docs/IW_AI_Core_Daemon_Design.md` for the
3-phase migration pipeline (dry-run → apply → rollback).

## Steps to Reproduce

1. Approve any batch whose head migration takes `AccessExclusiveLock` on
   a table the merge-queue post-merge path reads (e.g. any DDL on
   `batch_items`, `batches`, `projects`, `work_items`). I-00062's
   migration `4cc043748e92` (`ALTER TABLE batch_items ADD COLUMN
   worktree_db_host TEXT` ×4) reproduces it.
2. Daemon runs the batch, all steps complete, daemon enters merge queue.
3. `_merge_item` calls `worktree_commit.sh`, marks the item merged
   (`db.commit()` at `merge_queue.py:272`), then issues
   `_emit_event(...)` (uncommitted insert) and `db.get(Project, ...)` and
   `trigger_doc_regeneration_on_merge(db, batch_item, project)`. These
   reads acquire `AccessShareLock` on `projects` and `batch_items` in the
   daemon's outer session, which is now **idle in transaction**.
4. `_merge_item` calls `run_post_merge_apply(batch_item.batch_id)` at
   `merge_queue.py:290`. This opens a **separate** alembic connection
   and runs `ALTER TABLE batch_items ADD COLUMN ...`. The ALTER requests
   `AccessExclusiveLock`, which is incompatible with the daemon's own
   `AccessShareLock` from step 3.

**Expected**: Phase 2 apply completes within seconds; DB advances to head;
daemon continues processing the next merge.

**Actual**: ALTER blocks indefinitely. Daemon log goes silent — alembic
sits in `psycopg.connection.execute` waiting for the lock, and the
daemon's main thread is single-threaded, so nothing else runs. After
3+ hours the operator notices the dashboard is unresponsive (every
read of `batch_items` is also queued behind the pending exclusive),
the migration banner is showing, and recovery requires SIGKILL of the
daemon, manual `UPDATE migration_locks SET current_holder=NULL`,
`make db-migrate`, then daemon restart.

## Root Cause Analysis

### The deadlock chain (verified in source)

`orch/daemon/merge_queue.py:_merge_item`:

| Line | Operation | Effect on daemon session |
|------|-----------|--------------------------|
| 272 | `db.commit()` after marking item merged | Closes one transaction; **next statement opens a new one implicitly** |
| 273-275 | `_emit_event(db, ...)` | Adds an `INSERT INTO daemon_events` to the new transaction (per docstring at line 370: "Insert a DaemonEvent (caller commits)") |
| 282 | `_cleanup_worktree(...)` | Subprocess; no DB activity |
| 284 | `project = db.get(Project, project_id)` | `SELECT projects.* WHERE id=...` → `AccessShareLock` on `projects` |
| 286 | `trigger_doc_regeneration_on_merge(db, batch_item, project)` | Reads from `batch_items` and may insert into `doc_generation_jobs`. Whatever it does, it shares `db`'s session and lock set |
| 290 | `apply_result = run_post_merge_apply(batch_item.batch_id)` | Calls `safe_migrate.apply(get_db_url(), batch_id=...)`, which opens its **own** engine and runs `command.upgrade(cfg, "head")` |

By line 290, the outer `db` is **idle in transaction** holding:

- Pending insert from `_emit_event` (uncommitted DaemonEvent row)
- `AccessShareLock` on `projects` and `projects_pkey`
- `AccessShareLock` on `batch_items` and `batch_items_pkey` (via `batch_item` ORM relationship loads and via `trigger_doc_regeneration_on_merge`)
- (Possibly more from `trigger_doc_regeneration_on_merge`)

The alembic upgrade then executes:

```sql
ALTER TABLE batch_items ADD COLUMN worktree_db_host TEXT;
```

`ALTER TABLE ... ADD COLUMN` requires `AccessExclusiveLock` on `batch_items`.
The lock-grant queue order is:

1. **Holder** — daemon's outer `db` session: `AccessShareLock` (granted)
2. **Waiter** — daemon's alembic session: `AccessExclusiveLock` (pending)
3. **Subsequent readers** (dashboard, daemon pollers): `AccessShareLock`
   (queued behind the waiter, even though they would otherwise be
   compatible with the holder, because PostgreSQL grants in queue order
   to prevent writer starvation)

The daemon process never runs anything else while alembic is blocked, so
the outer transaction is never committed, so the ALTER never advances,
so all subsequent `batch_items` readers stack up behind it.

### Observed evidence (2026-05-04 incident)

`pg_stat_activity` snapshot at 13:02:50 (3h16m into the hang):

| PID | State | Last query started | Query |
|-----|-------|--------------------|-------|
| 126431 | `idle in transaction` | 09:46:06.977859 | `SELECT projects.id, projects.display_name, projects.repo_root, ...` |
| 126928 | `active`, `wait_event=relation` | 09:46:06.999368 (22 ms later) | `ALTER TABLE batch_items ADD COLUMN worktree_db_host TEXT` |
| 12+ others | `active`, `wait_event=relation` | 09:46:09 onwards | various reads on `batch_items` |

`migration_locks` row for `iw-ai-core`: `current_holder='daemon'`,
`locked_at=2026-05-04 09:46:06.984339+00` — acquired by
`_acquire_migration_lock()` at `safe_migrate.py:533`, never released
because the apply never completed.

Daemon log timeline:

```
10:46:06  orch.daemon.merge_queue: [iw-ai-core] Merged I-00062
10:46:06  orch.daemon.worktree_compose: compose stack torn down for 145
10:46:06  orch.daemon.merge_queue: Cleaned up worktree …
10:46:06  orch.daemon.migration_pipeline: [pipeline] Phase 2 apply starting for batch BATCH-00075
10:46:06  alembic.runtime.migration: Running upgrade e53ce8e86a3c -> 4cc043748e92, …
            <silence for 3h17m until operator SIGKILL>
```

### Why the existing 3-phase design didn't catch this

The Phase 1 dry-run uses a **fresh testcontainer** with no other
connections, so the migration applies cleanly there. Phase 2 is the
first time the migration meets a real database with the daemon's
session pool — and the deadlock only manifests when the post-merge
path has issued reads against the exact table the migration alters.
The dry-run cannot detect it.

### Why this is reproducible, not a fluke

Every batch run touches `batch_items` (the merge-queue post-merge path
needs `batch_item` to mark it merged, write `merge_info`, and pass it
to `worktree_compose.down`). Any future migration that takes an
exclusive lock on `batch_items`, `batches`, `projects`, `work_items`,
or `daemon_events` will repeat this incident. F-00076's
`add impacted_paths` migration was on `work_items` — it just happened
to ship after work_items had already had its access pattern softened
by F-00077's chat memory work. We have been getting lucky.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/merge_queue.py` (`_merge_item`) | Holds idle-in-transaction session across `run_post_merge_apply()` call — primary root cause |
| `orch/daemon/migration_pipeline.py` (`run_post_merge_apply`) | Has no defense against being invoked while caller holds incompatible locks |
| `orch/db/safe_migrate.py` (`apply`) | Hangs silently when blocked; no `lock_timeout` on the apply connection; no self-blocker detection |
| Daemon main poll loop | Single-threaded — when alembic blocks, the entire daemon stops processing batches, doc jobs, code-index jobs, keep-alive |
| Dashboard | Every query on the locked table queues behind the pending exclusive; pool exhausts; users see hung pages |
| `migration_locks` row | Stays held by `daemon` indefinitely; subsequent attempts to retry the apply fail until cleared by operator |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Fix `_merge_item` to commit-and-close the orchestration session before invoking `run_post_merge_apply()`; set `lock_timeout` on the alembic apply connection in `safe_migrate.apply()`; add same-process self-blocker detection that aborts before invoking `command.upgrade` | — |
| S02 | code-review-impl | Review S01 (backend) | — |
| S03 | tests-impl | Reproduction integration test (DDL self-deadlock against testcontainer) + regression tests for session lifecycle, lock_timeout, and self-blocker detection | — |
| S04 | code-review-impl | Review S03 (tests) | — |
| S05 | code-review-final-impl | Global cross-cutting review | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make test-integration` (timeout 900s) | — |

No `database-impl` step — this fix changes Python, not schema. No
`api-impl`, `frontend-impl`, `pipeline-impl`, or `template-impl` —
the symptoms are user-visible but the entire fix lives in the daemon.
No `qv-browser` step — backend-only.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This issue intentionally adds NO migration. Any
  schema work would defeat the purpose — we'd be testing the fix on
  itself.

### Code Changes

- **Files to modify**:
  - `orch/daemon/merge_queue.py` — discipline `db` lifecycle around
    `run_post_merge_apply`. Commit and close the session before the
    apply call; reopen a fresh session (or pass a callback to the
    pipeline that re-opens its own) for any post-apply bookkeeping.
  - `orch/db/safe_migrate.py` — set `lock_timeout` (default 30s) on
    the alembic apply connection's session via `event.listen` or by
    issuing `SET lock_timeout = '30s'` immediately after the apply
    engine connects. Add `_assert_no_self_blockers()` helper that
    queries `pg_locks` JOIN `pg_stat_activity` for blockers from the
    same `application_name` (or same `pg_backend_pid()`'s parent
    process) and raises a clear `SelfBlockerError` before calling
    `command.upgrade`.
- **Nature of change**: Defensive lifecycle and instrumentation. No
  behavior change on the happy path.

## File Manifest

All files for this work item live under `ai-dev/active/I-00063/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00063_Issue_Design.md` | Design | This document |
| `I-00063_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00063_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00063_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00063_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00063_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00063_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |

Reports are created during execution in `ai-dev/active/I-00063/reports/`.

## Test to Reproduce

The reproduction test must use a real PostgreSQL testcontainer (per
`tests/CLAUDE.md`: "NEVER mock the database in integration tests — FOR
UPDATE locking can't be tested otherwise"). It must demonstrate that,
under the **current (unfixed)** code path, opening an outer session
that has read `batch_items` and then invoking `run_post_merge_apply`
(or its equivalent in-test wiring) on the same DB hangs.

The test will use `pytest`'s `timeout` marker and a `concurrent.futures`
or threaded harness so the deadlock surfaces as a timeout rather than
hanging the whole test session.

```python
# tests/integration/daemon/test_phase2_apply_no_self_deadlock.py
import pytest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from sqlalchemy import select, text

from orch.db.models import BatchItem
from orch.db.safe_migrate import apply as safe_apply


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock(
    pg_container_url, alembic_at_head_minus_one, seeded_batch_item
):
    """
    Reproduces I-00063: Phase 2 apply must not hang when the caller's
    outer session holds AccessShareLock on a table the migration alters.

    Pre-fix: the apply blocks indefinitely (test times out at 60s).
    Post-fix: the apply either (a) succeeds because the caller has been
    disciplined to commit+close before invoking apply, or (b) raises
    SelfBlockerError quickly via the new self-blocker detection, or
    (c) raises a lock_timeout error within ~30s.
    """
    # Arrange: open an outer session that simulates _merge_item's state
    # right before run_post_merge_apply — idle in transaction, holding
    # AccessShareLock on batch_items.
    from orch.db.session import SessionLocal
    outer = SessionLocal()
    _ = outer.execute(select(BatchItem).limit(1)).all()  # AccessShareLock

    # Act: invoke apply in a separate thread so the test can time out
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(safe_apply, pg_container_url, batch_id=None)
        try:
            result = future.result(timeout=45)
        except FutTimeout:
            # CRITICAL: this is the unfixed-code path — apply hung
            outer.rollback()
            outer.close()
            pytest.fail(
                "I-00063 reproduction: safe_apply hung for >45s while "
                "caller held AccessShareLock. Fix did not land."
            )

    # Assert: result reached us in finite time
    assert result is not None
    # Either succeeded, or failed fast with a recognisable error
    if not result.success:
        assert (
            "lock_timeout" in (result.error_message or "").lower()
            or "self" in (result.error_message or "").lower()
        ), f"Unexpected failure: {result.error_message}"

    outer.rollback()
    outer.close()
```

## Acceptance Criteria

### AC1: Bug is fixed — no self-deadlock

```
Given the daemon has just merged a batch whose head migration alters
      a table the post-merge path reads (e.g. batch_items)
When  Phase 2 (run_post_merge_apply) executes
Then  the migration applies successfully without blocking on the
      daemon's own outer session, OR fails fast (within ~30s) with a
      clear error that triggers Phase 3 rollback rather than a silent
      hang
```

### AC2: Regression test exists

```
Given the fix is applied
When  `make test-integration` runs
Then  tests/integration/daemon/test_phase2_apply_no_self_deadlock.py
      passes within its 60s timeout, AND
      tests/integration/db/test_safe_migrate_self_blocker.py passes
      (covers lock_timeout setter and SelfBlockerError raising)
```

### AC3: Defensive lock_timeout in place

```
Given safe_migrate.apply() is invoked against a live DB
When  the apply connection is established
Then  it issues SET lock_timeout = '30s' (or the value of
      IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS if set) before any DDL,
      so any future regression of the same class fails fast with a
      lock_timeout error captured in pending_migration_log instead
      of hanging the daemon silently
```

### AC4: Self-blocker detection in place

```
Given safe_migrate.apply() is invoked while the same Python process
      already holds an AccessShareLock on a relation that the pending
      migration will alter
When  apply() runs its pre-flight check
Then  it queries pg_locks/pg_stat_activity to detect blockers from
      the same process and raises SelfBlockerError with a message
      identifying the blocking PID and relation, BEFORE invoking
      command.upgrade()
```

### AC5: pending_migration_log captures the failure

```
Given a Phase 2 apply fails (lock_timeout, self_blocker, or any other
      failure mode)
When  the apply returns
Then  a row exists in pending_migration_log with phase='apply',
      success=false, and a non-null error_message — so operators can
      see the failure in the audit trail without parsing daemon.log
```

## Regression Prevention

1. **Discipline `_merge_item`'s session lifecycle** — the post-merge
   path must commit-and-close `db` before invoking
   `run_post_merge_apply`. Open a fresh session afterward only if
   needed for follow-up work. This is the structural fix.
2. **`lock_timeout` on the apply connection** — bound the maximum
   silent-hang duration to ~30s. Any future regression of this class
   fails loudly with a lock_timeout error rather than silently for
   hours.
3. **Self-blocker detection in `safe_migrate.apply()`** — query
   `pg_locks` JOIN `pg_stat_activity` for blockers from the same
   process before invoking `command.upgrade()`. Raise
   `SelfBlockerError` immediately. This catches the bug at source
   instead of waiting for `lock_timeout`.
4. **Reproduction test in CI** — `test_phase2_apply_no_self_deadlock`
   runs on every integration test suite. Any future change that
   reintroduces the deadlock fails CI.
5. **Optional follow-up (out of scope)** — instrument the daemon main
   loop with a heartbeat so future hangs are visible from
   `daemon.log` without needing `pg_stat_activity`. Filed as a
   separate hardening item if useful.

## Dependencies

- **Depends on**: None
- **Blocks**: None — but every future migration that takes an exclusive
  lock on `batch_items`, `batches`, `projects`, `work_items`, or
  `daemon_events` is at risk until this fix lands. Effectively a
  blocker for any near-term DDL work on those tables.

## Impacted Paths

- `orch/daemon/merge_queue.py`
- `orch/daemon/migration_pipeline.py`
- `orch/db/safe_migrate.py`
- `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`
- `tests/integration/db/test_safe_migrate_self_blocker.py`

## TDD Approach

- **Reproducing test**:
  `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`
  fails (times out) against the current code; passes after the fix.
- **Unit tests** (alongside `safe_migrate.py`):
  - `lock_timeout` is set on the apply connection (verifiable by
    mocking `cfg.attributes['connection']` and asserting the
    `SET lock_timeout` SQL was executed).
  - `_assert_no_self_blockers()` returns cleanly when no blockers
    exist; raises `SelfBlockerError` when a blocker from the same
    backend (or same parent PID) is detected.
- **Integration tests**:
  - End-to-end: outer session holds `AccessShareLock` on `batch_items`
    → `safe_apply()` either succeeds (because `_merge_item` was
    fixed and the pre-condition won't happen in real flow) or fails
    fast with `SelfBlockerError`/`lock_timeout` (synthetic harness
    that bypasses the fixed `_merge_item` and calls `safe_apply`
    directly while holding the lock).
  - `pending_migration_log` row recorded on failure with
    `success=false` and a useful `error_message`.

## Notes

- **Why not just `rollback()` on `db` before the apply call?** That
  would release the locks but leave the uncommitted `_emit_event`
  insert lost. The fix must `commit()` first (to persist the
  `item_merged` event), then `close()` to release locks. A simple
  `db.commit(); db.close()` immediately before line 290 is the
  minimal-blast-radius fix.
- **Why not change `_emit_event` to commit on its own?** That would
  break the documented "caller commits" contract used elsewhere in
  the daemon and create double-commit risk. Local fix at the call
  site is preferred.
- **Why `SET lock_timeout` instead of `statement_timeout`?**
  `statement_timeout` would also bound legitimate slow migrations;
  `lock_timeout` only bounds time spent waiting for a lock. DDL
  itself can run as long as it needs once granted.
- **`IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` env var** — defaults to 30
  if unset. Operators can raise it for genuinely slow migrations on
  large tables; setting it to 0 disables the timeout (NOT
  recommended; documented as escape hatch only).
- The S01 prompt should reference this design doc by section name so
  the implementing agent has unambiguous targets for AC1-AC5.
