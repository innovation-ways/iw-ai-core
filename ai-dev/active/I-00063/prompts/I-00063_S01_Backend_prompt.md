# I-00063_S01_Backend_prompt

**Work Item**: I-00063 — Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session
**Step**: S01
**Agent**: backend-impl

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

This issue does NOT add or modify any migration. The fix lives in
Python only. You MUST NOT run `alembic upgrade`, `downgrade`, or
`stamp` against the live orch DB. Test code may run alembic against
testcontainer URLs only.

If you find yourself wanting to add a migration to "test the fix",
STOP — the fix is verified against the live orch DB by the operator
post-merge, and against testcontainers by the S03 tests step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00063 --json`. The `workflow-manifest.json` file is a design-time snapshot.
- `ai-dev/active/I-00063/I-00063_Issue_Design.md` — Design document. Read **all** sections, especially Root Cause Analysis, Acceptance Criteria (AC1-AC5), and Notes.
- `orch/CLAUDE.md` — orch package layer rules
- `tests/CLAUDE.md` — test patterns (reference only; no test code in this step)
- `docs/IW_AI_Core_Daemon_Design.md` — daemon and 3-phase pipeline design

## Output Files

- `orch/daemon/merge_queue.py` (modified)
- `orch/db/safe_migrate.py` (modified)
- `ai-dev/active/I-00063/reports/I-00063_S01_Backend_report.md` — Step report

## Context

I-00063 is a self-deadlock in the daemon's merge pipeline. After a
successful squash-merge, `_merge_item` keeps the orchestration `Session`
open with uncommitted reads on `projects` and `batch_items`, then
invokes `run_post_merge_apply()` in the same process. Phase 2's
`ALTER TABLE` requests `AccessExclusiveLock` and blocks behind the
daemon's own `AccessShareLock`. The deadlock is silent (alembic just
sits in `psycopg.connection.execute`), so the daemon hangs for hours
until an operator notices.

You are implementing the fix. Read the design document end-to-end
**before writing any code**. The design specifies exactly what behavior
must hold (AC1-AC5) and which files to change.

## Requirements

### 1. Discipline `_merge_item`'s session lifecycle (AC1, primary fix)

In `orch/daemon/merge_queue.py:_merge_item`, before the call to
`run_post_merge_apply(batch_item.batch_id)` at line 290:

- `db.commit()` — flush the pending `_emit_event` insert and any
  uncommitted ORM state, releasing all session-level locks
- `db.close()` — release the connection back to the pool

After `run_post_merge_apply` returns, if any post-apply bookkeeping is
needed in the same function (review carefully — the current code
emits a `migration_pipeline` event on failure at line 298), open a
**fresh** session for that work. Do not reuse the closed `db`.

The minimal correct shape is:

```python
# ... existing code through line 286 (trigger_doc_regeneration_on_merge)
db.commit()
db.close()

# Phase 2: apply migrations to live DB
if batch_item.batch_id is not None:
    apply_result = run_post_merge_apply(batch_item.batch_id)
    if not apply_result.success:
        rollback_result = run_rollback(batch_item.batch_id)
        # Need a fresh session here to write the rollback event
        with SessionLocal() as fresh_db:
            _emit_event(
                fresh_db, project_id, "migration_pipeline", item_id,
                "work_item",
                f"Phase 2 apply failed, rollback result: {rollback_result.message}",
                {...},
            )
            fresh_db.commit()
        if rollback_result.frozen:
            logger.error(...)
```

Carefully check the surrounding `try/except` at line 319 onwards —
if `db` is closed and an exception is raised later, the existing
`except` blocks reference `db.commit()` (line 338) and assume `db` is
still usable. You must either:

- Reopen `db` after the `run_post_merge_apply` block (preferred —
  preserves the existing exception handling shape), or
- Refactor the exception handlers to use a fresh session each (more
  invasive)

Choose the minimal-blast-radius option. Document your choice in your
step report. Re-test the merge_failed path mentally — does it still
work end to end?

### 2. Set `lock_timeout` on the alembic apply connection (AC3)

In `orch/db/safe_migrate.py:apply()`, set `lock_timeout` on the
alembic apply session before invoking `command.upgrade()`. The
defensive default is 30 seconds; the operator can override via
`IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` (set to `0` to disable; not
recommended).

Implementation note: alembic's `command.upgrade(cfg, "head")` opens
its own connection internally via `EnvironmentContext`. The cleanest
hook is to register a `connect` event listener on the engine that
issues `SET lock_timeout = '<N>s'` on every new connection. Look at
how `pool_pre_ping` is wired in `orch/db/session.py:safe_create_engine`
and follow the same pattern.

Alternative: build the engine yourself in `apply()` (replacing
`_build_alembic_config`'s implicit engine creation) so you control
the connection lifecycle. Choose whichever option is smaller.

The `SET lock_timeout` SQL must run on the **apply** connection, not
on the `migration_locks` lock-acquisition connection. Verify by
reading `_acquire_migration_lock` and `_run_alembic_upgrade` and
tracing which engine is in play at each step.

### 3. Self-blocker detection in `safe_migrate.apply()` (AC4)

Add a helper `_assert_no_self_blockers(db_url, target_tables=...)`
that runs before `command.upgrade()`. The helper should:

- Connect to the live DB (its own short-lived connection, separate
  from the alembic apply connection).
- Query `pg_stat_activity` JOIN `pg_locks` for any session in state
  `idle in transaction` whose backend's parent process is the same
  as the current process (or, simpler and sufficient: any backend
  whose `application_name` matches the daemon's expected
  `application_name`, or any backend from `client_addr` matching
  ours, holding an `AccessShareLock` on a relation we will alter).

Alternatives that are also acceptable:

- Compare `pg_stat_activity.client_port` for connections from
  127.0.0.1 with the same parent PID via `/proc`.
- Use `pg_blocking_pids(pg_backend_pid())` after the apply connection
  is established and just before `command.upgrade()`. If any blocker
  PID's `application_name` or process tree resolves back to the
  daemon, raise.

The simplest robust signal: set the engine's `application_name` to a
distinctive value (e.g. `iw-ai-core-daemon-apply` and
`iw-ai-core-daemon-main`), then check whether any blocker's
`application_name` is `iw-ai-core-daemon-main`. Same process,
different connection — that's the self-deadlock.

Define a new exception class `SelfBlockerError(RuntimeError)` in
`safe_migrate.py` and raise it with a message like:

```
Phase 2 apply blocked by daemon's own session — backend PID 126431
(application_name=iw-ai-core-daemon-main) holds AccessShareLock on
batch_items. Caller must commit and close its session before invoking
apply(). See I-00063 for context.
```

The error must be caught by the existing exception handler at
`safe_migrate.py:563` (`except Exception as exc`) so the audit log
captures it. Confirm by re-reading the `try/finally` structure.

### 4. Add `IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` to `orch/config.py`

If `orch/config.py` exposes a `Config` dataclass or similar, add the
new setting there with a default of `30`. If config is read ad-hoc via
`os.environ.get`, just read it inside `apply()`. Match the existing
pattern in `orch/config.py` — do not introduce a new style.

Update `.env.example` (or whatever the project convention is for
documenting env vars) if the project has one. Check `CLAUDE.md` for
convention; if not documented, skip and note in your report.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:

- **Sync SQLAlchemy 2.0** — no `async`. Use `SessionLocal()` /
  `with SessionLocal() as db:` patterns.
- **psycopg v3** — never psycopg2. Connection URLs use
  `postgresql+psycopg://` not `postgresql+psycopg2://`.
- **Append-only event tables** — `daemon_events` is append-only. Do
  not UPDATE existing rows.
- **DaemonEvent.metadata is `event_metadata` in Python** — SQLAlchemy
  reserves `metadata` on `DeclarativeBase`. Use the Python attribute,
  not the column name.
- Match existing logger names (`logger = logging.getLogger(__name__)`)
  and log levels (INFO for happy path, WARNING for fail-fast errors,
  ERROR for unrecoverable).
- The orchestration DB lives at port 5433. Tests use testcontainers
  (different port). `safe_create_engine` enforces this.

When in doubt, read the surrounding code in `orch/daemon/` and
`orch/db/` and match style.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED** is owned by S03 — the reproduction integration test will
   be written there. You do NOT need to write it in S01. However:
   - Mentally run the deadlock scenario through your patched code
     before reporting complete.
   - If you can write small unit tests next to your changes (e.g. for
     `_assert_no_self_blockers` happy/error paths against a mock or
     against `pg_locks` on a testcontainer), do so — they belong in
     `tests/unit/` or `tests/integration/db/` and are additive to S03.
2. **GREEN**: implement the minimal fix. The fix should be small —
   no refactors of unrelated code, no abstraction extraction, no
   "while I'm here" cleanups.
3. **REFACTOR**: only if your initial implementation is ugly. Keep
   the diff focused.

The S03 reproduction test must FAIL on a checkout of the pre-S01
code (verifiable by `git stash` your S01 changes and re-running the
test) and PASS on your post-S01 code. Confirm this in your step
report.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in
order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats
   files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files
   you touched. Errors elsewhere are pre-existing — note them in your
   report but do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker —
do not silently skip.

In your Subagent Result Contract, populate the `preflight` object
recording the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — should pass; the S03 reproduction
   test does not exist yet, so this is a sanity check that you have
   not broken anything else.
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass
   with zero failures.
4. If tests fail in files you did not modify, surface them as
   `notes` — they are pre-existing, not regressions you introduced
   (but verify by running `git stash && make test-…` if uncertain).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/merge_queue.py",
    "orch/db/safe_migrate.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Document the choice for session reopen vs handler refactor; document the chosen self-blocker detection mechanism (application_name vs pg_blocking_pids vs other); note any pre-existing test failures observed."
}
```

- `completion_status`: `complete` only if all four requirements above
  are met and pre-flight gates pass.
- `notes`: explicitly call out which approach you chose for each of:
  (a) reopen-vs-refactor in `_merge_item`, (b) `lock_timeout` wiring
  (engine-level vs in-line SET), (c) self-blocker detection signal
  (application_name vs pg_blocking_pids vs other). The reviewer in
  S02 needs this to evaluate your trade-offs.
