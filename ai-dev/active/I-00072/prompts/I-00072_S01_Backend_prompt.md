# I-00072_S01_Backend_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Step**: S01
**Agent**: Backend

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

This step does NOT require any migration. The PG enum already contains
every BatchItemStatus label this fix references (per I-00042 and
F-00062). If you find yourself reaching for `alembic`, STOP — you are
off-scope.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00072 --json`. The `workflow-manifest.json` file is a design-time snapshot.
- `ai-dev/active/I-00072/I-00072_Issue_Design.md` — Design document (read first; the Root Cause Analysis section contains the file:line references you need).
- `ai-dev/active/I-00072/I-00072_Functional.md` — Plain-language summary of the user-visible change.

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_S01_Backend_report.md` — Step report (see Subagent Result Contract below).

## Context

You are implementing the backend fix for **iw merge-queue retry-merge rejects items in merge_failed status**.

The CLI command `iw merge-queue retry-merge` and the dashboard endpoint `POST /actions/item/{item_id}/restart-merge` are two surfaces of the same operator action. They have drifted: the dashboard accepts `merge_failed`, `migration_invalid`, and `migration_rebase_failed` (CR-00028); the CLI only accepts `failed` and `migration_rebase_failed`. Read the Root Cause Analysis section of the design doc for the full diagnosis with file:line refs.

Your job is to align them via a single shared constant — no behaviour change beyond the alignment itself.

## Requirements

### 1. Define the shared constant

In `orch/daemon/merge_queue.py`, add a module-level public constant:

```python
OPERATOR_RECOVERABLE_MERGE_STATUSES: frozenset[BatchItemStatus] = frozenset({
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
    BatchItemStatus.migration_rolled_back,
})
```

- Place it near the other module-level constants in `merge_queue.py` (this is the daemon-side authority on merge-queue concepts).
- Use `frozenset` so callers cannot mutate the set.
- The constant name is non-negotiable — `tests/` and `dashboard/routers/actions.py` will both import it by this name.
- Include a one-line comment above the constant explaining its purpose: "Statuses an operator can recover from via retry-merge / restart-merge. Cascade is NOT triggered for these — see CR-00028."

### 2. Wire the CLI to use the constant

In `orch/cli/merge_queue_commands.py`, in the `merge_queue_retry` function (around lines 197-303):

- Import the new constant: `from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES`.
- Delete the local `_retryable = (BatchItemStatus.failed, BatchItemStatus.migration_rebase_failed,)` tuple.
- Change the SQL filter to: `BatchItem.status.in_(list(OPERATOR_RECOVERABLE_MERGE_STATUSES))`.
- **Add the legacy back-compat path** (mirroring `dashboard/routers/actions.py:947-972`): if the first lookup returns `None`, do a second lookup for a row in `BatchItemStatus.failed` whose `notes` (treated as empty string when None) starts with `"Merge failed"`. If that legacy row exists, treat it as the retry target. If neither path matches, surface a clear error: "No retryable batch item found for {item_id} (status must be one of {recoverable set} or legacy failed-with-merge-notes)".
- **Reject plain `failed` rows without merge notes.** When a `failed` row is found via the legacy lookup but its notes do not start with `"Merge failed"`, return a non-zero exit with a message that names the actual notes prefix and points the operator toward `iw <something else>` for non-merge failures (look at how the dashboard's HTTP 422 message phrases this and use the same wording).
- Preserve all other existing behaviour: worktree-path existence check, BatchItem→completed flip, WorkItem reset (failed→completed), `merge_retry_requested` audit event, JSON output mode.

### 3. Wire the dashboard to use the constant

In `dashboard/routers/actions.py` (around lines 922-1004):

- Add the import: `from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES`.
- Delete the local `_ALLOWED_RETRY_STATUSES = {…}` set definition.
- Replace the reference at `BatchItem.status.in_(list(_ALLOWED_RETRY_STATUSES))` with `BatchItem.status.in_(list(OPERATOR_RECOVERABLE_MERGE_STATUSES))`.
- Leave the rest of `restart_merge` untouched — its legacy back-compat block, batch-reopen logic, and audit event already work.
- Audit the file for any other `_ALLOWED_RETRY_STATUSES` reference (`abandon_merge` at line 1015 has its own status list — leave it alone unless you find an actual reuse opportunity; do NOT widen this PR).

### 4. Keep scope minimal

- Do NOT refactor `abandon_merge`, the cascade logic, or any unrelated merge-queue code path.
- Do NOT add a 5th status to the constant unless you find a producer for it in the daemon.
- Do NOT touch tests — that is S03's job.
- The total diff should be: ~6 lines added in `merge_queue.py`, ~10 lines changed in `merge_queue_commands.py` (including the legacy path), ~3 lines changed in `actions.py` (replace local set with import).

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:

- ORM style: SQLAlchemy 2.0, `Mapped[]` declarative, sync sessions.
- `BatchItemStatus` lives in `orch/db/models.py` — already imported by both target files.
- `DaemonEvent.metadata` is named `event_metadata` in Python (the column is still `metadata`); `merge_queue_commands.py` already uses `event_metadata=` correctly — keep it that way.
- The CLI uses `output_error(ctx, msg, EXIT_*)` helpers from `orch/cli/utils.py` for error paths — reuse them, do not raw-`click.echo` to stderr.

## TDD Requirement

The **failing test** for this fix is being written in S03. To respect TDD ordering:

1. **Before** changing any production code, mentally run through the reproduction test from the design doc and confirm it would fail against current `main`. (You don't need to write it — that's S03.)
2. **Implement** the changes above.
3. **Verify**: run `make test-unit` — existing CLI tests in `tests/unit/test_merge_queue_cli.py` (covering `freeze`/`unfreeze`/`status`) must still pass; no new failures.
4. The new reproduction test will be written in S03 and will turn GREEN against your fix.

If you find yourself rewriting test fixtures or seeding helpers, STOP — that's S03 territory. Your output is production code only.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix anything they report on the files you touched:

1. **`make format`** — auto-fix formatting drift; inspect the diff.
2. **`make typecheck`** — must report zero errors involving `orch/daemon/merge_queue.py`, `orch/cli/merge_queue_commands.py`, `dashboard/routers/actions.py`. Pre-existing errors elsewhere are not your problem; note them in your report.
3. **`make lint`** — must report zero errors. Pay attention to import ordering — the new `from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES` line must group correctly with other `orch.*` imports.

If a tool isn't available in your worktree, STOP and raise a blocker.

In your Subagent Result Contract, populate the `preflight` object recording:
- `"ok"` — ran cleanly
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit`.
2. Confirm zero new failures. The S03 reproduction test does not exist yet, so a `merge_queue_retry` test class with new failures should NOT appear — if it does, you've broken something.
3. Do **NOT** report `tests_passed: true` unless ALL existing unit tests pass.
4. If existing tests fail, fix them before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/merge_queue.py",
    "orch/cli/merge_queue_commands.py",
    "dashboard/routers/actions.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Constant defined in merge_queue.py; CLI and dashboard import it; CLI legacy back-compat path added."
}
```

- `completion_status`: `complete` only when all 3 files are changed, all 4 statuses are in the constant, the legacy CLI path is in place, and quality gates pass.
- `blockers`: anything that prevents the alignment (e.g., circular import that forces moving the constant). Surface it; do not work around silently.
- `notes`: anything S02 (review) or S03 (tests) should know about edge cases you considered.
