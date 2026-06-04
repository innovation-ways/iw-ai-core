# Step 04: CLI Step Lifecycle & Batch Commands

## Context

CLI core is complete (next-id, register, approve). Now implement the step lifecycle commands (used by agents during execution) and batch management commands.

Read these documents:
- `IW_AI_Core_CLI_Spec.md` — sections 3.3 (step lifecycle), 3.4 (batch management)
- `IW_AI_Core_Database_Schema.md` — sections 2.4-2.5 (workflow_steps, step_runs), 2.7-2.8 (batches, batch_items), state machines 3.3-3.6

## Task

### 1. Step Lifecycle Commands (`orch/cli/step_commands.py`)

#### `iw step-start <item_id> --step <step_id>`
- Validates step exists for this item and project
- Validates step status is `pending`
- Updates `workflow_steps.status = 'in_progress'`, `started_at = now()`

#### `iw step-done <item_id> --step <step_id> [--report <path>]`
- Validates step is `in_progress`
- Updates status to `completed`, `completed_at = now()`
- If `--report`: stores path in `report_file`

#### `iw step-fail <item_id> --step <step_id> --reason <text>`
- Validates step is `in_progress`
- Updates status to `failed`
- Stores reason — this will be displayed in the dashboard

### 2. Batch Commands (`orch/cli/batch_commands.py`)

#### `iw batch-create <item_ids...> [--max-parallel <n>] [--auto-publish]`
- Allocates batch ID via `next-id --type batch`
- Validates all items are `approved` and not in another active batch
- Analyzes dependencies: reads `work_items.depends_on` for each item
- Builds execution groups: items with no unresolved dependencies → group 0, items depending on group 0 → group 1, etc.
- Creates `batches` row with status `planning`
- Creates `batch_items` rows with execution_group assignments
- Human output: shows batch ID, execution plan with groups
- JSON output: full batch + items + groups

#### `iw batch-approve <batch_id>`
- Validates batch is in `planning` status
- Updates to `approved`
- Emits `batch_approved` daemon event

#### `iw batch-status <batch_id>`
- Shows batch details: status, items with their current status/step/duration
- Human output: formatted table (see CLI Spec section 3.4)
- JSON output: full batch state

#### `iw batch-pause <batch_id>`
- Validates batch is `executing`
- Updates to `paused`

#### `iw batch-resume <batch_id>`
- Validates batch is `paused`
- Updates to `executing`

### 3. Tests (TDD)

**Unit tests** (`tests/unit/test_cli_steps.py`):
- Test: step-start rejects non-pending step
- Test: step-done rejects non-in_progress step
- Test: step-fail stores reason correctly

**Unit tests** (`tests/unit/test_batch_planner.py`):
- Test: no dependencies → all items in group 0
- Test: A depends on B → B in group 0, A in group 1
- Test: chain A→B→C → groups 0, 1, 2
- Test: diamond dependency → correct grouping
- Test: circular dependency → error

**Integration tests** (`tests/integration/test_cli_steps.py`):
- Test: full step lifecycle: start → done
- Test: full step lifecycle: start → fail
- Test: step-done with --report stores path

**Integration tests** (`tests/integration/test_cli_batches.py`):
- Test: batch-create with 3 independent items → all in group 0
- Test: batch-create with dependencies → correct groups
- Test: batch-create rejects items not in approved status
- Test: batch-create rejects item already in active batch
- Test: batch lifecycle: create → approve → pause → resume

## Acceptance Criteria

- [ ] `iw step-start I001 --step S01` works against a registered item with steps
- [ ] `iw batch-create I001 I002 I003` creates batch with correct execution groups
- [ ] `iw batch-status BATCH-001 --json` returns full state
- [ ] All state transitions validated (invalid ones rejected with clear errors)
- [ ] `make test` passes, `make quality` passes
