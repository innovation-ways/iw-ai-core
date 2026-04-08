# Step 03: CLI Core Commands

## Context

You are building the `iw` CLI for IW AI Core. Foundation (config, models, migrations) is complete.

Read these documents:
- `IW_AI_Core_CLI_Spec.md` — sections 2 (global behavior), 3.1 (ID management), 3.2 (work item management)
- `IW_AI_Core_Database_Schema.md` — section 2.2 (id_sequences), 2.3 (work_items), section 3.1-3.2 (state machines)

## Task

### 1. CLI Entry Point (`orch/cli/main.py`)

- Create the Click group `cli` with global options: `--project/-p`, `--json/-j`, `--verbose/-v`
- Implement project auto-detection: walk up from cwd looking for `.iw-orch.json`, read `project_id`
- If `--project` provided, use it. Otherwise auto-detect. If neither works, exit code 3.
- Register all command subgroups.

### 2. `iw current-project` (`orch/cli/id_commands.py`)

- Prints the auto-detected project ID
- JSON mode: `{"project_id": "...", "repo_root": "..."}`

### 3. `iw next-id` (`orch/cli/id_commands.py`)

- `--type`: required, choices: feature, incident, cr, batch
- Maps type to prefix: feature→F, incident→I, cr→CR, batch→BATCH
- Executes atomic allocation: `SELECT ... FOR UPDATE` on `id_sequences`, increment, return formatted ID
- Format: `{prefix}{number:03d}` for F/I/CR, `BATCH-{number:03d}` for batch
- Human output: just the ID (e.g., `I001`)
- JSON output: `{"id": "I001", "project_id": "innoforge", "prefix": "I", "number": 1}`

### 4. `iw register` (`orch/cli/item_commands.py`)

- Args: `id` (positional), `title` (positional)
- Options: `--type` (required: feature, incident, cr), `--design-doc` (optional path), `--steps-from` (optional manifest path)
- Validates ID prefix matches type
- Inserts into `work_items` with status=draft, phase=active
- If `--steps-from`: parse the workflow-manifest.json and insert `workflow_steps` rows
- Idempotent: ON CONFLICT DO NOTHING, report "Already registered" if exists
- JSON output includes `created: true/false`

### 5. `iw approve` (`orch/cli/item_commands.py`)

- Args: `id` (positional)
- Validates current status is `draft`
- Updates to `approved`, sets `updated_at`
- Error if item not found (exit 1), error if wrong status (exit 1 with message)

### 6. `iw unapprove` (`orch/cli/item_commands.py`)

- Args: `id` (positional)
- Validates current status is `approved`
- Validates item is NOT in any active batch (query batch_items)
- Updates to `draft`
- Error if in active batch (exit 4 with batch ID)

### 7. Tests (TDD — write these FIRST)

**Unit tests** (`tests/unit/test_cli_core.py`):
- Test: auto-detection finds .iw-orch.json in parent directories
- Test: auto-detection fails gracefully when no .iw-orch.json
- Test: ID format is correct for each type (F001, I001, CR001, BATCH-001)
- Test: register validates prefix matches type (I001 with type=feature → error)
- Test: approve rejects invalid status transitions (approved → approved)
- Test: unapprove rejects item in active batch

**Integration tests** (`tests/integration/test_cli_core.py`):
- Test: `next-id` allocates sequential IDs (I001, I002, I003)
- Test: `next-id` under concurrency — 10 threads, all get unique IDs, no gaps
- Test: `register` creates work item in DB, idempotent on second call
- Test: `register --steps-from` creates workflow_steps rows
- Test: `approve` transitions draft → approved
- Test: full flow: next-id → register → approve

## Acceptance Criteria

- [ ] `iw --help` shows all command groups
- [ ] `iw next-id --type incident --json` returns `{"id": "I001", ...}`
- [ ] `iw register I001 "Test item" --type incident` creates DB row
- [ ] `iw approve I001` transitions to approved
- [ ] Concurrent `next-id` calls produce no duplicates (integration test)
- [ ] `make test` passes, `make quality` passes
