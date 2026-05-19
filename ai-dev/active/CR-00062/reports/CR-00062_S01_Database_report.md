# CR-00062 — S01 Database Report

## What was done

Wrote one Alembic revision (`6d78323d0954` → `21de61b41cec`) that seeds two
`agent_runtime_options` rows for Pi (pi.dev) as a third runtime, and refreshed
the `cli_tool` column comment on `step_runs` and `batches` to enumerate the new
value. Updated the matching `comment="..."` strings on the SQLAlchemy models so
`Base.metadata.create_all()` stays in parity with the live schema (the
migration-check round-trip gate enforces this).

No DDL changes — the `agent_runtime_options` table, its unique constraint
(`uq_agent_runtime_options_cli_model`), the partial unique index on
`is_default`, and the CHECK constraint introduced by F-00081 (revision
`ff23f562353b`) are all untouched.

## Files changed

| File | Change |
|------|--------|
| `orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py` | **NEW** — seed migration + column-comment alters |
| `orch/db/models.py` | `StepRun.cli_tool.comment` updated; `Batch.cli_tool` gains an explicit `comment=` (server_default `'opencode'` unchanged) |

## Migration shape

- `upgrade()`:
  1. `setval(pg_get_serial_sequence('agent_runtime_options', 'id'), GREATEST(MAX(id), 1), true)` — same realignment used by `d1e2f3gpt53c`, prevents `pkey` collisions when applied against per-worktree DBs restored from `pg_dump`.
  2. Two `INSERT ... ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model DO UPDATE` statements — idempotent under repeated `upgrade head` (the `EXCLUDED.*` re-applies the latest copy without ever turning the row into the default).
  3. `op.alter_column("step_runs", "cli_tool", comment=..., existing_comment=...)` — three-value enumeration replaces the two-value one.
  4. `op.alter_column("batches", "cli_tool", comment=..., existing_server_default=text("'opencode'"))` — adds the comment (no prior comment existed); `server_default` preserved.
- `downgrade()`:
  1. Reverts both `op.alter_column` calls (batches → `comment=None`, step_runs → old two-value comment).
  2. Two per-`(cli_tool='pi', model=<exact model>)` `DELETE` statements (explicit per-model — no blanket `WHERE cli_tool = 'pi'`).

| cli_tool | model | display_name | sort_order |
|----------|-------|--------------|------------|
| `pi` | `minimax/MiniMax-M2.7` | `Pi + MiniMax 2.7` | `25` |
| `pi` | `openai/gpt-5.3-codex` | `Pi + GPT-5.3 Codex` | `26` |

Both rows are `enabled=true`, `is_default=false`. The existing MiniMax 2.7
default (the `(opencode, minimax)` row seeded by F-00081) is untouched, so the
CHECK constraint `ck_agent_runtime_options_default_must_be_enabled` and the
partial unique index `uq_agent_runtime_options_one_default` are both
unaffected.

## Test results

- `make format` → ok (`772 files already formatted`)
- `make lint` → ok (`scripts/check_templates.py` + `ruff check` — `All checks passed!`)
- `make typecheck` → ok (`mypy orch/ dashboard/` — `Success: no issues found in 257 source files`)
- `make migration-check` → ok (3 passed in 8.49s)
  - `test_alembic_schema_matches_create_all` — `create_all()` parity holds with the new column comments
  - `test_alembic_downgrade_base_then_upgrade_head` — round-trip clean
  - `test_alembic_upgrade_head_succeeds_from_empty` — head applies on a fresh DB

## Observations

- `make format` is `format --check` — it does not auto-fix. The migration file
  was written formatter-clean on the first try, so no follow-up `ruff format`
  was needed.
- The downgrade reverses the column-comment alters **before** deleting the
  rows. Reason: if a future operator has pinned a step/item/batch to a Pi
  runtime option, the `ON DELETE RESTRICT` FK aborts the delete; doing the
  comment-revert first means even a partial downgrade leaves the schema in a
  consistent, non-stale-comment state.
- `Batch.cli_tool` had no explicit `comment=` before this CR — the migration
  uses `op.alter_column(..., comment=...)` without `existing_comment=` for the
  upgrade and `comment=None` for the downgrade, which is the correct Alembic
  shape for adding a previously-absent column comment.
- Revision id `6d78323d0954`, down_revision `21de61b41cec` (the prior head,
  CR-00056's `add_prompt_text_and_fix_prompt_text_to_step_runs`).

## Result contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py",
    "orch/db/models.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok",
    "migration_check": "ok"
  },
  "tests_passed": true,
  "test_summary": "3 passed in 8.49s (make migration-check)",
  "tdd_red_evidence": "n/a — data-only seed migration: two new agent_runtime_options rows plus column-comment alters on step_runs.cli_tool / batches.cli_tool. No new behavioural code path is introduced by this step; the new `pi` value is exercised by S03 (dispatch sites) and S05 (test surface), where the RED evidence lives (e.g. tests/unit/test_pi_runtime_dispatch.py::test_build_initial_command_pi_uses_pi_print_mode). Schema parity verified by the migration-check round-trip.",
  "blockers": [],
  "notes": "Migration follows the d1e2f3gpt53c pattern: setval realignment + ON CONFLICT ON CONSTRAINT DO UPDATE on the unique-constraint name (cli_tool, model), making upgrade idempotent under repeat application against per-worktree DBs restored from pg_dump. Downgrade reverts column comments first and then deletes rows; an FK-RESTRICT-aborted partial downgrade therefore leaves a consistent (non-stale-comment) schema. No CHECK constraint added — the allowlist is code-only in orch/daemon/project_registry.py (S03)."
}
```
