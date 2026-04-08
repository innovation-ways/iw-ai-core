# Step 05: CLI Remaining Commands

## Context

Core CLI commands and step/batch commands are complete. Now implement the remaining commands: migration lock, archive, search, item-status, daemon control, and project listing.

Read these documents:
- `IW_AI_Core_CLI_Spec.md` — sections 3.5 (migration lock), 3.7 (search), 3.8 (daemon control), 3.9 (projects)
- `IW_AI_Core_CLI_Spec.md` — section 3.2 (`archive`, `item-status`)
- `IW_AI_Core_Database_Schema.md` — sections 2.9 (migration_locks), 2.10 (daemon_events)

## Task

### 1. Migration Lock (`orch/cli/lock_commands.py`)

Click subgroup: `iw migration-lock`

#### `iw migration-lock acquire <item_id> [--branch <name>]`
- Atomic lock via `SELECT ... FOR UPDATE` on `migration_locks`
- If `current_holder IS NULL`: set holder, branch, locked_at → success
- If already held: return error (exit 4) with current holder info

#### `iw migration-lock release <item_id>`
- Validates current_holder matches item_id
- Sets current_holder = NULL

#### `iw migration-lock status`
- Shows current lock state: free or held by whom

### 2. Archive (`orch/cli/item_commands.py`)

#### `iw archive <id> [--all-completed] [--no-cleanup]`
- Implemented as a thin CLI wrapper around `orch.archive.archiver` (archive module will be built in step 10)
- For now: implement the CLI command structure, argument parsing, and DB updates (Tier 1 content storage)
- Tier 2 compression will be added in step 10 — stub it with a TODO
- Tier 1 logic: read design doc from disk → store in `design_doc_content`, read reports → store in `report_content`, update `archived_at`

### 3. Search (`orch/cli/search_commands.py`)

#### `iw search <query> [--project <id>] [--type <type>] [--limit <n>]`
- Builds PostgreSQL tsquery from the search terms
- Queries `work_items` with `design_doc_search @@ to_tsquery()`
- Ranks by `ts_rank()`
- Human output: formatted results with title, summary snippet, project, type, date
- JSON output: array of results with relevance score

### 4. Item Status (`orch/cli/item_commands.py`)

#### `iw item-status <id>`
- Shows: title, status, phase, step progress (N/M completed), current step info, batch, worktree, timestamps
- Human output: formatted summary (see CLI Spec)
- JSON output: full item state with steps

### 5. Daemon Control (`orch/cli/daemon_commands.py`)

Click subgroup: `iw daemon`

#### `iw daemon start [--foreground]`
- Reads PID file — if process alive, exit with error
- If `--foreground`: call daemon main loop directly
- Otherwise: fork/spawn daemon process, write PID file
- Note: actual daemon logic is step 06 — this just starts/stops it

#### `iw daemon stop`
- Read PID from file, send SIGTERM, wait up to 30s, remove PID file

#### `iw daemon status`
- Check PID file, check if process alive
- Query DB for daemon stats: last poll time (from daemon_events), running step count, active batch count

### 6. Projects (`orch/cli/project_commands.py`)

Click subgroup: `iw projects`

#### `iw projects list`
- Query all projects from DB
- Human output: table with ID, name, enabled, item count, active batch count
- JSON output: array of project objects

### 7. Tests (TDD)

**Integration tests** (`tests/integration/test_migration_lock.py`):
- Test: acquire succeeds when lock is free
- Test: acquire fails when lock is held (returns holder info)
- Test: release succeeds when holder matches
- Test: release fails when holder doesn't match
- Test: concurrent acquisition — only one wins

**Integration tests** (`tests/integration/test_search.py`):
- Test: insert 3 work items with content, search by keyword, verify ranking
- Test: search with project filter returns only that project's items
- Test: search with type filter works
- Test: search returns empty for non-matching query

**Unit tests** (`tests/unit/test_daemon_commands.py`):
- Test: daemon start detects existing process
- Test: daemon stop reads PID and sends signal (mocked)

## Acceptance Criteria

- [ ] `iw migration-lock acquire I001` works, second acquire fails with holder info
- [ ] `iw search "template"` returns ranked results
- [ ] `iw item-status I001` shows formatted status summary
- [ ] `iw daemon status --json` returns daemon health info
- [ ] `iw projects list` shows registered projects
- [ ] `make test` passes, `make quality` passes
