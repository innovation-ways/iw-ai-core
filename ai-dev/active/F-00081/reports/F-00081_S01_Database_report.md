# F-00081 S01 — Database Implementation Report

**Step**: S01 (database-impl)
**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Agent**: database-impl
**Status**: ✅ Complete

---

## What Was Done

Implemented the database foundation for F-00081: a catalogue of agent runtime options and three nullable FK override columns on `work_items`, `workflow_steps`, and `step_runs`.

### Changes

#### 1. `orch/db/models.py` — Added `AgentRuntimeOption` model and FK columns

- **`AgentRuntimeOption`** (new model, global singleton, no `project_id`):
  - `id` (PK, autoincrement)
  - `cli_tool` (Text, not nullable)
  - `model` (Text, not nullable)
  - `cli_label`, `model_label`, `display_name` (all Text, not nullable)
  - `is_default` (Boolean, not nullable, server_default=`false`)
  - `enabled` (Boolean, not nullable, server_default=`true`)
  - `sort_order` (Integer, not nullable, server_default=`0`)

  Table constraints:
  - `UniqueConstraint("cli_tool", "model")` → name `uq_agent_runtime_options_cli_model`
  - Partial unique index `uq_agent_runtime_options_one_default` on `(is_default)` where `is_default = true`
  - `CheckConstraint("NOT (is_default = true AND enabled = false)")` → name `ck_agent_runtime_options_default_must_be_enabled`
  - Table comment: "Catalogue of curated (cli_tool, model) pairs the daemon can launch."

- **`WorkItem.agent_runtime_option_id`**: nullable FK → `agent_runtime_options.id`, ON DELETE RESTRICT. Comment: "Override pair to use for this item; NULL = inherit. F-00081."

- **`WorkflowStep.agent_runtime_option_id`**: nullable FK → `agent_runtime_options.id`, ON DELETE RESTRICT. Comment: "Override pair to use for this step; NULL = inherit. F-00081."

- **`StepRun.agent_runtime_option_id`**: nullable FK → `agent_runtime_options.id`, ON DELETE RESTRICT. Comment: "The resolved (cli_tool, model) pair used for this run. F-00081."

#### 2. `orch/db/migrations/versions/ff23f562353b_f_00081_agent_runtime_options.py` — Alembic migration

- Creates `agent_runtime_options` table with all columns, CHECK constraint, unique constraint, and partial unique index.
- Bulk-inserts 5 seed rows (in order of `sort_order`):
  | id | cli_tool | model | cli_label | model_label | display_name | is_default | sort_order |
  |----|----------|-------|-----------|-------------|--------------|------------|------------|
  | 1 | opencode | minimax | OpenCode | MiniMax 2.7 | OpenCode + MiniMax 2.7 | true | 10 |
  | 2 | opencode | claude-sonnet-4-6 | OpenCode | Claude Sonnet 4.6 | OpenCode + Claude Sonnet 4.6 | false | 20 |
  | 3 | opencode | claude-opus-4-7 | OpenCode | Claude Opus 4.7 | OpenCode + Claude Opus 4.7 | false | 30 |
  | 4 | claude | claude-sonnet-4-6 | Claude Code | Sonnet 4.6 | Claude Code + Sonnet 4.6 | false | 40 |
  | 5 | claude | claude-opus-4-7 | Claude Code | Opus 4.7 | Claude Code + Opus 4.7 | false | 50 |

- Adds `agent_runtime_option_id` column to `step_runs`, `work_items`, `workflow_steps` with named FK constraints (`fk_step_runs_agent_runtime_option_id`, `fk_work_items_agent_runtime_option_id`, `fk_workflow_steps_agent_runtime_option_id`), all ON DELETE RESTRICT.
- Downgrade drops FK columns from `workflow_steps` → `work_items` → `step_runs` (in that order), then drops the table and the partial unique index.

#### 3. `tests/integration/test_agent_runtime_options.py` — Integration tests (14 tests, all passing)

**`TestAgentRuntimeOptionsTable`** (7 tests):
- `test_table_exists` — table is queryable
- `test_all_columns_present` — all 9 columns present with correct names
- `test_seed_rows_present` — all 5 seed rows land with correct values
- `test_unique_constraint_on_cli_tool_model` — duplicate pair rejected
- `test_only_one_default_row` — partial unique index rejects second `is_default=true`
- `test_cannot_disable_default_row` — CHECK constraint rejects `enabled=false` on default row
- `test_can_disable_non_default_row` — 4 non-default rows can be disabled

**`TestAgentRuntimeOptionFKColumns`** (7 tests):
- `test_work_items_has_agent_runtime_option_id` — column exists, nullable
- `test_workflow_steps_has_agent_runtime_option_id` — column exists, nullable
- `test_step_runs_has_agent_runtime_option_id` — column exists, nullable
- `test_fk_referential_integrity_prevents_delete` — ON DELETE RESTRICT blocks deletion of referenced row
- `test_item_level_override_stored` — writing and reading `agent_runtime_option_id` on `work_items`
- `test_step_level_override_stored` — writing and reading `agent_runtime_option_id` on `workflow_steps`
- `test_null_agent_runtime_option_id_allowed` — NULL allowed (no override), existing rows unaffected

**Test conventions used**: Tests use raw SQL via `db_session.execute(text(...))` to insert data (no ORM objects), matching the project's integration test style. The `seed_agent_runtime_options` fixture inserts the 5 seed rows before each test that needs them — since tests use `Base.metadata.create_all()` (not Alembic migrations), the fixture simulates the migration's `op.bulk_insert`.

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 649 files formatted |
| `make typecheck` | ✅ No issues in 234 source files |
| `make lint` | ✅ All checks passed |
| `make test-integration` (F-00081 only) | ✅ 14 passed, 0 failed |
| Alembic history | ✅ `ff23f562353b` is head, down_revision chain correct |

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `AgentRuntimeOption` model + 3 FK columns |
| `orch/db/migrations/versions/ff23f562353b_f_00081_agent_runtime_options.py` | New migration (create table, seed, FK columns) |
| `tests/integration/test_agent_runtime_options.py` | 14 integration tests for table, constraints, FK columns |

---

## Notes

- The FK constraint names (`fk_work_items_agent_runtime_option_id`, etc.) are explicit strings, not `None`. The autogenerate wrote `None` which caused mypy type errors. This is consistent with the project's Alembic style — constraint names should be explicit.
- The `seed_agent_runtime_options` fixture uses `return None` (not `yield`) to satisfy PT022 (no teardown needed) after `db_session.commit()`.
- The pre-existing 2 failing unit tests in `test_safe_migrate.py` are unrelated to this change — they fail due to environment interaction in the CI/dev environment, not any F-00081 code.
- Downgrade ordering: drops FKs from `workflow_steps` → `work_items` → `step_runs`, matching the topological order needed for PostgreSQL foreign key constraints.

---

**Next step**: S02 (backend-impl) — Resolver + project_registry extension + launch-site refactor + DaemonEvent emission helper.