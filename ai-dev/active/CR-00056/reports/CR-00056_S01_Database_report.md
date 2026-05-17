# CR-00056 S01 — Database Report

**Work Item**: CR-00056 — Surface step prompts in dashboard
**Step**: S01 (database-impl)
**Agent**: database-impl

## What was done

Added two nullable `TEXT` columns to the `StepRun` ORM model and generated the corresponding Alembic migration file. The columns store the prompt content snapshot captured at step launch time, enabling the dashboard to display the prompt for historical items whose worktrees have been reaped.

## Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `prompt_text` and `fix_prompt_text` columns to `StepRun` class (lines 873–891) |
| `orch/db/migrations/versions/21de61b41cec_cr_00056_add_prompt_text_and_fix_prompt_.py` | New migration: adds both columns with PostgreSQL `comment` attributes |

## Schema changes

- **`step_runs.prompt_text`** — `TEXT`, `NULL`, with comment `"Snapshot of the prompt content captured at step launch. Set by the daemon when this StepRun is created. NULL for pre-CR-00056 rows. Append-only — never updated after creation. (CR-00056)"`
- **`step_runs.fix_prompt_text`** — `TEXT`, `NULL`, with comment `"Snapshot of the fix-cycle prompt content for retry runs. Set by the daemon when a fix-cycle StepRun is created. NULL for non-fix-cycle runs and pre-CR-00056 rows. Append-only. (CR-00056)"`

No indexes added — these columns are display-only and never appear in `WHERE` clauses. Existing path columns (`WorkflowStep.prompt_file`, `FixCycle.fix_prompt`) are preserved for debugging.

## Migration verification

**`make migration-check`**: ✅ All 3 tests passed
- `test_alembic_upgrade_head_succeeds_from_empty` — PASSED
- `test_alembic_schema_matches_create_all` — PASSED
- `test_alembic_downgrade_base_then_upgrade_head` — PASSED

The migration correctly:
- Upgrades by adding both columns (in either order)
- Downgrades by dropping in reverse order (`fix_prompt_text` → `prompt_text`)
- Has `down_revision = d1e2f3gpt53c` pointing at the current head

## Preflight

| Check | Result |
|-------|--------|
| `make format` | Fixed — reformatted the migration file (`ruff format`) |
| `make typecheck` | OK — zero errors in 251 source files |
| `make lint` | OK — all checks passed |

## TDD note

No behavioural tests added at this step (schema-only column addition). The S11 (tests-impl) step will add a unit test constructing `StepRun(..., prompt_text="...", fix_prompt_text="...")` as RED-first evidence. This is consistent with project convention for pure schema steps.

## Notes

- Migration file is **unapplied** — daemon will apply it via `iw migrations apply` in the merge pipeline. Agents never call `alembic upgrade` against port 5433.
- Migration comments in the file match the ORM model comments exactly, so `psql \d+ step_runs` will show descriptive PostgreSQL-level comments.
- No other tables/columns/triggers were modified.
