# IW AI Core — `iw` CLI Specification

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Overview

`iw` is the command-line interface that bridges LLM agents, human operators, and the IW AI Core database. It is the **only** way agents update operational state — they never write to state files or access the DB directly.

**Installation:**
```bash
cd /path/to/iw-ai-core
pip install -e .
# Entry point: iw (added to PATH via pyproject.toml [project.scripts])
```

**Configuration:**
- Reads `.env` from the iw-ai-core repo root (via `python-dotenv`)
- Auto-detects current project from `.iw-orch.json` up the directory tree
- All DB connection parameters come from environment variables

---

## 2. Global Behavior

### 2.1. Project Auto-Detection

Most commands require a `--project` parameter. If omitted, `iw` walks up the directory tree from the current working directory looking for `.iw-orch.json` and reads the `project_id` from it.

```bash
# Explicit project
iw next-id --type incident --project innoforge

# Auto-detected (when cwd is inside the InnoForge repo)
cd /home/sergiog/dev/iw-doc-plan/main/iw-doc-plan
iw next-id --type incident
# Finds .iw-orch.json in cwd → project_id = "innoforge"
```

If no `.iw-orch.json` is found and `--project` is not provided, the command exits with error code 2.

### 2.2. Output Modes

Every command supports two output modes:

| Mode | Flag | Format | Use Case |
|------|------|--------|----------|
| Human | (default) | Colored text, tables via Rich | Interactive terminal use |
| Machine | `--json` | JSON to stdout | Skills, scripts, piping |

```bash
# Human output
iw next-id --type incident
# → I001

# Machine output
iw next-id --type incident --json
# → {"id": "I001", "project_id": "innoforge", "prefix": "I", "number": 1}
```

### 2.3. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command execution error (DB error, invalid state transition, etc.) |
| 2 | Usage error (missing required arguments, invalid flags) |
| 3 | Configuration error (missing env vars, DB not reachable, project not found) |
| 4 | Conflict (ID already registered, lock held by another item) |

### 2.4. Error Output

Errors are written to stderr in human mode, and included in the JSON response in `--json` mode:

```bash
# Human mode
iw approve I999
# stderr: Error: Work item I999 not found in project innoforge
# exit code: 1

# JSON mode
iw approve I999 --json
# stdout: {"error": "Work item I999 not found in project innoforge", "code": 1}
# exit code: 1
```

### 2.5. Common Flags

| Flag | Short | Description | Applies To |
|------|-------|-------------|-----------|
| `--project` | `-p` | Project ID (overrides auto-detection) | All commands |
| `--json` | `-j` | Machine-readable JSON output | All commands |
| `--help` | `-h` | Show command help | All commands |
| `--verbose` | `-v` | Show debug-level details | All commands |

---

## 3. Command Reference

### 3.1. ID Management

#### `iw next-id`

Atomically allocate the next sequential ID for a work item type.

```
iw next-id --type <type> [--project <id>] [--json]
```

| Parameter | Required | Values | Description |
|-----------|----------|--------|-------------|
| `--type` | Yes | `feature`, `incident`, `cr`, `batch` | Work item type |
| `--project` | No | Project ID | Auto-detected if omitted |

**Behavior:**
1. Connects to DB
2. Executes `SELECT ... FOR UPDATE` on `id_sequences` row
3. Increments `next_number`
4. Returns formatted ID (e.g., `I001`, `F042`, `CR003`, `BATCH-012`)

**Output (human):**
```
I001
```

**Output (JSON):**
```json
{"id": "I001", "project_id": "innoforge", "prefix": "I", "number": 1}
```

**Errors:**
- Project not found → exit 3
- DB unreachable → exit 3
- Invalid type → exit 2

---

#### `iw current-project`

Print the current project ID (from `.iw-orch.json` auto-detection).

```
iw current-project [--json]
```

**Output (human):**
```
innoforge
```

**Output (JSON):**
```json
{"project_id": "innoforge", "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan"}
```

**Errors:**
- No `.iw-orch.json` found → exit 3 with "No .iw-orch.json found in directory tree"

---

### 3.2. Work Item Management

#### `iw register`

Register a new work item in the database.

```
iw register <id> <title> --type <type> [--design-doc <path>] [--project <id>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `id` | Yes | Work item ID (e.g., `I001`) — must match an allocated ID |
| `title` | Yes | One-line description |
| `--type` | Yes | `feature`, `incident`, `cr` |
| `--design-doc` | No | Relative path to design document in the project repo |
| `--steps-from` | No | Path to workflow-manifest.json to import step definitions |

**Behavior:**
1. Validates that the ID format matches the type prefix
2. Inserts into `work_items` with status `draft`, phase `active`
3. If `--steps-from` provided: parses manifest, inserts into `workflow_steps`
4. Idempotent: `ON CONFLICT (project_id, id) DO NOTHING`

**Output (human):**
```
Registered I001: Fix template rendering timeout [draft]
```

**Output (JSON):**
```json
{"project_id": "innoforge", "id": "I001", "title": "Fix template rendering timeout", "status": "draft", "created": true}
```

If already registered:
```json
{"project_id": "innoforge", "id": "I001", "status": "draft", "created": false, "message": "Already registered"}
```

---

#### `iw approve`

Approve a work item for execution.

```
iw approve <id> [--project <id>] [--json]
```

**Behavior:**
1. Validates current status is `draft`
2. Updates status to `approved`
3. Updates `updated_at`

**Errors:**
- Item not found → exit 1
- Item not in `draft` status → exit 1 with "Cannot approve: current status is 'in_progress'"

---

#### `iw unapprove`

Revert an approved item back to draft.

```
iw unapprove <id> [--project <id>] [--json]
```

**Behavior:**
1. Validates current status is `approved`
2. Validates item is NOT in any active batch
3. Updates status to `draft`

**Errors:**
- Item in active batch → exit 4 with "Cannot unapprove: item is in batch BATCH-003"

---

#### `iw archive`

Archive a completed work item (Tier 1 DB + Tier 2 compressed).

```
iw archive <id> [--project <id>] [--json]
iw archive --all-completed [--project <id>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `id` | Yes (unless `--all-completed`) | Work item ID |
| `--all-completed` | No | Archive all completed items in the project |
| `--no-cleanup` | No | Store in DB + archive but don't delete active files |

**Behavior:**
1. Read design doc from `design_doc_path` → store in `design_doc_content` (Tier 1)
2. Read each step report → store in `workflow_steps.report_content` (Tier 1)
3. Update `design_doc_search` tsvector
4. Compress work item folder to `archive/<project_id>/<id>.tar.zst` (Tier 2)
5. Record `archive_path`, `archive_size_bytes`, `archived_at`
6. Delete `ai-dev/design/active/<id>/` from project repo (unless `--no-cleanup`)
7. Update phase to `done`

**Output (human):**
```
Archived I001:
  Tier 1: Design doc (12.4 KB) + 4 reports stored in DB
  Tier 2: I001.tar.zst (38.2 KB) → archive/innoforge/I001.tar.zst
  Cleanup: ai-dev/design/active/I001/ deleted
```

---

#### `iw item-status`

Show the current status of a work item.

```
iw item-status <id> [--project <id>] [--json]
```

**Output (human):**
```
I001: Fix template rendering timeout
  Status: in_progress | Phase: work
  Steps: 3/7 completed | Current: S04 CodeReview_Final (running, 12m 34s)
  Batch: BATCH-003 | Worktree: .worktrees/I001
  Created: 2026-04-07 10:30 | Updated: 2026-04-07 11:15
```

**JSON shape (CR-00023):** the `--json` form is the runtime source of truth
for step state — preferred over reading `workflow-manifest.json`. Each entry
in the `steps[]` array contains a true superset of the manifest's per-step
fields plus runtime status:

| Key | Source | Notes |
|-----|--------|-------|
| `step_id` | DB | e.g. `"S01"` |
| `step_number` | DB | derived from `step_id` |
| `label` / `agent_label` | DB | identical values; `label` retained for back-compat |
| `opencode_agent` | DB | manifest `agent` slug, e.g. `"qv-gate"` |
| `type` / `step_type` | DB | identical values |
| `step_label` | DB | optional human-readable label |
| `status` | DB | `pending`/`in_progress`/`completed`/`failed`/`skipped`/`needs_fix` |
| `description` | DB | from manifest at register time |
| `prompt_file` | DB | manifest `prompt` path; null for qv-gate steps |
| `command` | DB | qv-gate command (e.g. `"make lint"`); null for impl steps |
| `gate` | DB | qv-gate name (e.g. `"lint"`); null for impl steps |
| `timeout_secs` | DB | per-step timeout override; null = project default |

Items registered before CR-00023 keep `command`/`gate`/`timeout_secs`/`prompt_file`
as `null`; the daemon falls back to reading the on-disk manifest for those
rows.

**Contract for future schema changes:** any new field added to
`workflow-manifest.json` that is needed at runtime MUST be added to
`WorkflowStep` and surfaced here as part of the same change. Do not let
runtime data live in the manifest only.

---

#### `iw item approve-merge`

Approve a manual merge for a batch item that is awaiting approval (CR-00036). Used when `Batch.auto_merge = false` to release a parked item into the merge queue.

```
iw item approve-merge <item_id> [--project <id>] [--json]
```

**Behavior:**
1. Validates the batch item exists and is in `awaiting_merge_approval` status
2. Transitions `BatchItem.status` to `completed`
3. Emits `DaemonEvent(event_type='merge_approved_by_operator', ...)`
4. The next daemon poll cycle picks the item up via the merge queue

**Exit codes:**
| Code | Meaning |
|------|---------|
| 0 | Success — item transitioned to `completed` |
| 4 | Invalid state — item is not in `awaiting_merge_approval` |

**Output (human):**
```
Approved merge for F-00001
```

**Output (JSON):**
```json
{"item_id": "F-00001", "status": "completed"}
```

---

### 3.3. Step Lifecycle

These commands are called by LLM agents (via the `/execute` skill) during step execution. They update the database through the `iw` CLI — agents never write state files.

#### `iw step-start`

Mark a step as started.

```
iw step-start <item_id> --step <step_id> [--project <id>] [--json]
```

**Behavior:**
1. Validates step exists and is in `pending` status
2. Updates `workflow_steps.status = 'in_progress'`
3. Updates `workflow_steps.started_at = now()`

---

#### `iw step-done`

Mark a step as completed successfully.

```
iw step-done <item_id> --step <step_id> [--report <path>] [--project <id>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--report` | No | Relative path to the report file produced by the agent |

**Behavior:**
1. Validates step is in `in_progress` status
2. Updates `workflow_steps.status = 'completed'`
3. Updates `workflow_steps.completed_at = now()`
4. If `--report`: stores path in `workflow_steps.report_file`

---

#### `iw step-fail`

Mark a step as failed.

```
iw step-fail <item_id> --step <step_id> --reason <text> [--project <id>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--reason` | Yes | Human-readable failure reason (stored in step_runs.error_message) |

**Behavior:**
1. Validates step is in `in_progress` status
2. Updates `workflow_steps.status = 'failed'`
3. Stores reason in the current `step_runs.error_message`

---

### 3.4. Batch Management

#### `iw batch-create`

Create a new batch with specified work items.

```
iw batch-create <item_ids...> [--max-parallel <n>] [--auto-publish] [--auto-merge | --no-auto-merge] [--project <id>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `item_ids` | Yes | One or more work item IDs (space-separated) |
| `--max-parallel` | No | Maximum concurrent items (default: 4) |
| `--auto-publish` | No | Auto-push to origin after all items merged |
| `--auto-merge` / `--no-auto-merge` | No | Auto-merge each item to main on success (default: from project's `auto_merge` in projects.toml, which itself defaults to `true`) |

**Behavior:**
1. Allocates next batch ID via `iw next-id --type batch`
2. Validates all items exist and are `approved`
3. Validates no item is already in an active batch
4. Analyzes dependencies (`depends_on` fields) to build execution groups
5. Creates `batches` row with status `planning`
6. Creates `batch_items` rows with execution groups
7. Returns batch ID and execution plan

**Output (human):**
```
Created BATCH-003 with 4 items (max parallel: 4)
  Group 0: I001, I002, I003 (parallel)
  Group 1: I004 (depends on I001)
Status: planning (approve with: iw batch-approve BATCH-003)
```

**Output (JSON):**
```json
{
  "batch_id": "BATCH-003",
  "project_id": "innoforge",
  "status": "planning",
  "max_parallel": 4,
  "groups": [
    {"group": 0, "items": ["I001", "I002", "I003"]},
    {"group": 1, "items": ["I004"]}
  ]
}
```

---

#### `iw batch-approve`

Approve a batch for execution. The daemon will pick it up on the next poll cycle.

```
iw batch-approve <batch_id> [--project <id>] [--json]
```

**Behavior:**
1. Validates batch is in `planning` status
2. Updates batch status to `approved`
3. Emits `batch_approved` daemon event

---

#### `iw batch-status`

Show the current status of a batch.

```
iw batch-status <batch_id> [--project <id>] [--json]
```

**Output (human):**
```
BATCH-003 [executing] — InnoForge
  Items: 4 total | 2 merged | 1 executing | 1 pending
  +-------+--------+-----------+----------+-----------+
  | Item  | Group  | Status    | Step     | Duration  |
  +-------+--------+-----------+----------+-----------+
  | I001  | 0      | merged    | —        | 45m 12s   |
  | I002  | 0      | merged    | —        | 38m 05s   |
  | I003  | 0      | executing | S03 CR   | 12m 34s   |
  | I004  | 1      | pending   | —        | —         |
  +-------+--------+-----------+----------+-----------+
  Created: 2026-04-07 22:00 | Running: 1h 23m
```

---

#### `iw batch-pause`

Pause a running batch. In-progress items continue, no new items launch.

```
iw batch-pause <batch_id> [--project <id>] [--json]
```

---

#### `iw batch-resume`

Resume a paused batch.

```
iw batch-resume <batch_id> [--project <id>] [--json]
```

---

#### `iw batch-cancel`

Cancel a batch and fan out to its non-terminal items. Allowed from
`planning, approved, executing, paused, blocked, publish_failed`.

```
iw batch-cancel <batch_id> [--reset-items] [--reason <text>] [--project <id>] [--json]
```

**Behaviour:**
1. For every `batch_item` not already in a terminal state:
   - Send SIGTERM to any running `step_runs.pid` and mark those rows `killed` (append-only).
   - Mark any pending / in-progress `workflow_steps` rows as `skipped`.
   - Best-effort: `worktree_compose.down` and `git worktree remove --force` for the per-item stack.
   - Set `batch_items.status = 'skipped'` with a note pointing to the batch.
2. For every member `WorkItem`:
   - **Default**: push to `cancelled` (terminal, never overwrites `completed`).
   - **`--reset-items`**: push back to `draft` and reset every `workflow_steps` row to `pending` (timestamps cleared). `step_runs` history is preserved.
3. Set `batches.status = 'cancelled'`, emit `daemon_events(event_type='batch_cancelled')` with the reason, killed PIDs, and reset list in `metadata`.

Side-effects are best-effort: a failed compose-down or worktree-remove is recorded in the `teardown_errors` JSON field and does not block the DB transition.

---

#### `iw item-cancel`

Cancel a single work item that is **not** in an active batch. Refuses with exit 4 if the item is in a non-terminal batch — the operator must run `iw batch-cancel` instead so the cross-batch scope-overlap gate stays consistent.

```
iw item-cancel <item_id> [--to-draft] [--reason <text>] [--project <id>] [--json]
```

- **Default**: pushes to `cancelled` (terminal).
- **`--to-draft`**: also resets all `workflow_steps` to `pending` so the item can be redesigned and re-approved.

Allowed from `approved, in_progress, failed, paused`.

---

### 3.5. Migration Lock

Controls which work item can create Alembic migrations (one at a time per project).

#### `iw migration-lock acquire`

```
iw migration-lock acquire <item_id> [--branch <name>] [--project <id>] [--json]
```

**Behavior:**
1. Attempts atomic lock via `SELECT ... FOR UPDATE`
2. If lock is free: acquires it, returns success
3. If lock is held: returns error with current holder info

**Output (success):**
```
Migration lock acquired for I001 on branch agent/I001-fix-template
```

**Output (conflict):**
```json
{"error": "Migration lock held by I003 since 2026-04-07T10:30:00Z", "holder": "I003", "code": 4}
```

---

#### `iw migration-lock release`

```
iw migration-lock release <item_id> [--project <id>] [--json]
```

**Behavior:**
1. Validates current holder matches `item_id`
2. Sets `current_holder = NULL`

---

#### `iw migration-lock status`

```
iw migration-lock status [--project <id>] [--json]
```

**Output:**
```
Migration lock: held by I003 (branch: agent/I003-add-field) since 2026-04-07 10:30
```

---

### 3.6. Skills Management

#### `iw sync-skills`

Sync platform skills to a project's `.claude/skills/` directory.

```
iw sync-skills [--project <id>] [--check] [--force <skill-name>] [--json]
```

| Flag | Description |
|------|-------------|
| `--check` | Show what would be updated without making changes |
| `--force <name>` | Overwrite a project override with the platform version |

**Output (human):**
```
Syncing skills for innoforge...
  iw-new-incident:   2.0.0 → 2.1.0 (updated)
  iw-new-feature:    2.0.0 → 2.1.0 (updated)
  iw-batch-execute:  1.5.0 (up to date)
  innoforge-testing: project override (skipped)
Synced 2 skills. 1 skipped (project override).
```

---

#### `iw init-project`

Initialize a new project for IW AI Core management.

```
iw init-project --id <id> --path <repo-path> --name <display-name> [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--id` | Yes | Unique project identifier (e.g., `my-project`) |
| `--path` | Yes | Absolute path to the project's repo root |
| `--name` | Yes | Human-readable display name |

**Behavior:**
1. Creates `.iw-orch.json` in the repo root
2. Adds entry to `projects.toml` in iw-ai-core
3. Registers project in DB (`projects` table)
4. Creates ID sequences (F, I, CR, BATCH starting at 1)
5. Creates migration lock row (unlocked)
6. Creates `ai-dev/design/active/` directory
7. Creates `ai-dev/workflow.md` from default template
8. Syncs base skills to `.claude/skills/`

**Output:**
```
Project initialized: my-project
  Config: /path/to/repo/.iw-orch.json
  Registry: projects.toml updated
  Database: project + ID sequences + migration lock created
  Skills: 12 base skills synced
  Workflow: ai-dev/workflow.md created from template
Ready. Project will appear in dashboard on next daemon poll.
```

---

### 3.7. Search

#### `iw search`

Full-text search across work items.

```
iw search <query> [--project <id>] [--type <type>] [--limit <n>] [--json]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `query` | Yes | Search terms (PostgreSQL tsquery syntax supported) |
| `--project` | No | Filter to one project (default: all projects) |
| `--type` | No | Filter by type: `feature`, `incident`, `cr` |
| `--limit` | No | Max results (default: 20) |

**Output (human):**
```
3 results for "template rendering timeout":

  I001 [innoforge] Fix template rendering timeout
  Issue | completed | 2026-04-07
  ...timeout occurs when WeasyPrint processes templates with >50 zones...

  I089 [innoforge] Template rendering fails on large invoices
  Issue | done | 2026-03-15
  ...rendering pipeline chokes on invoices with nested zone hierarchies...

  CR012 [innoforge] Increase template rendering timeout config
  ChangeRequest | done | 2026-02-20
  ...add configurable timeout for the WeasyPrint rendering stage...
```

**Output (JSON):**
```json
{
  "query": "template rendering timeout",
  "count": 3,
  "results": [
    {
      "project_id": "innoforge",
      "id": "I001",
      "type": "Issue",
      "title": "Fix template rendering timeout",
      "status": "completed",
      "summary": "Timeout occurs when WeasyPrint processes templates with >50 zones...",
      "relevance": 0.89,
      "created_at": "2026-04-07T10:30:00Z"
    }
  ]
}
```

### 3.8. Regression Classification (F-00090)

#### `iw regression-classify`

Show (or accept) heuristic regression-introducer suggestions for an Incident.

```
iw regression-classify --incident <id> [--project <id>] [--accept <rank>] [--repo <path>]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--incident` | Yes | Incident ID (e.g. `I-00001`) |
| `--project` | No | Project ID (auto-detected from `.iw-orch.json`) |
| `--accept` | No | Rank (1-indexed) of the heuristic suggestion to accept and persist |
| `--repo` | No | Path to the project git repository (default: current working directory) |

**Behavior:**
1. Validates the incident exists and is merged (`status == 'done'`)
2. Runs `git show --name-only` against the incident's merge SHA to discover fix files
3. Runs `git log --oneline` against those files to find prior commits, ranks by frequency + recency
4. Returns up to 10 candidates; cross-project work items are dropped
5. With `--accept N`: persists the Nth candidate as the regression classification with `classified_by = 'heuristic:auto'`

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success (suggestions printed or classification persisted) |
| 2 | Validation error (unknown incident, out-of-range accept rank, etc.) |
| 1 | Unexpected error |

**Output (human):**
```
Suggestions for I-00001:
Rank   SHA          Work Item     Score
------------------------------------------
1      a1b2c3d      F-00042       3
2      e4f5g6h      —             1
```

**Output (JSON):**
```json
{
  "incident": "I-00001",
  "candidates": [
    {"rank": 1, "commit_sha": "a1b2c3d...", "work_item_id": "F-00042", "score": 3},
    {"rank": 2, "commit_sha": "e4f5g6h...", "work_item_id": null, "score": 1}
  ]
}
```

---

### 3.9. Daemon Control

#### `iw daemon start`

Start the orchestration daemon.

```
iw daemon start [--foreground] [--json]
```

| Flag | Description |
|------|-------------|
| `--foreground` | Run in foreground (don't daemonize). Useful for debugging. |

**Behavior:**
1. Checks PID file — if daemon is already running, exit with error
2. Starts daemon process (background by default)
3. Writes PID file
4. Emits `daemon_started` event

---

#### `iw daemon stop`

Stop the running daemon gracefully.

```
iw daemon stop [--json]
```

**Behavior:**
1. Reads PID from PID file
2. Sends SIGTERM
3. Waits up to 30 seconds for graceful shutdown
4. Removes PID file

---

#### `iw daemon status`

Show daemon health.

```
iw daemon status [--json]
```

**Output (human):**
```
Daemon: running (PID 45231, uptime 4h 23m)
  Projects: 3 enabled, 0 disabled
  Last poll: 12s ago | Poll count: 254
  Running steps: 3 across 2 projects
  Batches: 1 executing (BATCH-003), 0 paused
```

**Output (JSON):**
```json
{
  "status": "running",
  "pid": 45231,
  "uptime_secs": 15780,
  "last_poll_at": "2026-04-07T14:52:48Z",
  "poll_count": 254,
  "projects": {"enabled": 3, "disabled": 0},
  "running_steps": 3,
  "active_batches": 1
}
```

---

### 3.9. Project Management

#### `iw projects list`

List all registered projects.

```
iw projects list [--json]
```

**Output (human):**
```
  ID          | Name                    | Enabled | Items | Active Batches
  ------------|-------------------------|---------|-------|---------------
  innoforge   | InnoForge Doc Platform  | yes     | 371   | 1
  project-b   | Project B               | yes     | 12    | 0
  project-c   | Project C               | no      | 0     | 0
```

---

### 3.10. Test Health

#### `iw test-health-capture`

Capture test-health snapshots for a project.

```
iw test-health-capture --project <slug>
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--project`, `-p` | **Required.** Project slug (e.g. `iw-ai-core`) |

**Behavior:**
1. Looks up the project in the registry by slug
2. Reads four artefact sources from the project's repo root:
   - `tests/output/mutation-*.json` — mutation score
   - `coverage.xml` — coverage percentage (via `orch/coverage_service.py`)
   - `tests/output/flake-detect-*.log` — flaky-test count
   - `tests/assertion_free_baseline.txt` — assertion-baseline line count
3. Writes one row per metric to `test_health_snapshots` (idempotent per minute)
4. Creates one `test-health-capture` job row in the unified Jobs view
5. Prints a JSON summary to stdout

**Output (JSON):**
```json
{
  "project": "iw-ai-core",
  "captured": [
    {"metric": "mutation_score", "value": 85.3, "ts": "2026-05-28T10:00:00Z", "source_shape": "cr00080"},
    {"metric": "coverage_pct", "value": 72.1, "ts": "2026-05-28T10:00:00Z", "source_shape": "cobertura"}
  ],
  "skipped": [
    {"metric": "flaky_test_count", "reason": "source not found or not parseable"}
  ]
}
```

**Exit codes:** `0` = success (including no-op captures), `1` = DB error, `2` = project not found.

---

## 4. Command Summary

This tree is the **canonical command list**. It is kept in sync with the actual
Click command tree by `tests/integration/test_cli_spec_conformance.py`, which
fails the build on any drift in either direction (see §7).

```
iw
├── next-id             Atomically allocate the next sequential ID for a work item type
├── current-project     Print the current project ID detected from .iw-orch.json
├── register            Register a new work item in the database (idempotent)
├── approve             Approve a work item for execution (draft → approved)
├── approve-merge       Approve a manual merge for a batch item awaiting approval
├── unapprove           Revert an approved work item back to draft (approved → draft)
├── item-cancel         Cancel a single work item not owned by an active batch
├── item-status         Show the current status of a work item
├── item-report         Generate and write the execution report for a work item
├── archive             Archive completed work items (Tier 1 DB + Tier 2 .tar.zst)
├── step-start          Mark a workflow step as started (pending → in_progress)
├── step-done           Mark a workflow step as completed (in_progress → completed)
├── step-fail           Mark a workflow step as failed (in_progress → failed)
├── step-restart        Restart a failed step: reset to pending so the daemon relaunches it
├── step-restart-from   Reset a step and all subsequent steps to pending
├── step-skip           Skip a failed step (failed → skipped)
├── step-kill           Kill a running step's process and mark it as failed
├── batch-create        Create a new batch from a list of approved work items
├── batch-approve       Approve a batch for execution (planning → approved)
├── batch-status        Show the current status of a batch
├── batch-pause         Pause a running batch (executing → paused)
├── batch-resume        Resume a paused batch (paused → executing)
├── batch-cancel        Cancel a batch and its non-terminal items
├── doc-update          Upsert a project documentation record
├── doc-job-start       Mark a queued DocGenerationJob as running
├── doc-job-done        Mark a running DocGenerationJob as completed (or failed)
├── doc-job-status      Show the full context of a DocGenerationJob (read-only)
├── docs-export         Export project docs as ZIP bundles
├── validate-diagrams   Validate Mermaid/D2 diagrams in a document
├── search              Full-text search across work items
├── regression-classify Show or accept heuristic regression-introducer suggestions for an Incident
├── worktree-status     Show git health of all active agent worktrees
├── sync-skills         Sync platform skills to a project's .claude/skills/ directory
├── sync-agents         Sync platform agents and commands to a project
├── sync-templates      Sync design templates to all registered projects
├── sync-assets         Sync Innovation Ways brand assets to all registered projects
├── init-project        Initialize a new project for IW AI Core management
├── db-identity         Show or verify the orchestration DB instance identity fingerprint
│   ├── show            Show live DB instance UUID, expected UUID, and mode
│   └── check           Verify DB instance identity
├── migration-lock      Control migration lock for Alembic migrations (one holder per project)
│   ├── acquire         Acquire the migration lock for a work item
│   ├── release         Release the migration lock held by a work item
│   └── status          Show the current migration lock status
├── migrations          Manage Alembic migrations with safe operator gates
│   ├── list-pending    Show revisions present in files but not yet applied to the live DB
│   ├── dry-run         Apply pending revisions in a testcontainer, report success/failure
│   └── apply           Apply pending alembic revisions to the live database
├── merge-queue         Show and control the merge queue frozen state
│   ├── status          Show current merge queue frozen state
│   ├── unfreeze        Clear the merge queue frozen flag
│   └── retry-merge     Reset a failed merge so the daemon re-attempts it
├── oss                 OSS compliance workflow management
│   ├── enable          Enable OSS compliance for a project
│   ├── disable         Disable OSS compliance for a project
│   ├── scan            Run OSS compliance scan against a project
│   ├── status          Show the latest OSS scan status for a project
│   ├── install         Probe or install Tier-1 OSS compliance tools
│   └── fix             Preview or apply the auto-fix for a single OSS check
├── daemon              Control the IW AI Core orchestration daemon
│   ├── start           Start the orchestration daemon
│   ├── stop            Stop the running daemon gracefully
│   └── status          Show daemon health and operational statistics
├── projects            Manage registered projects
│   └── list            List all registered projects
└── test-health-capture Capture test-health snapshots (mutation score, coverage, flaky tests, assertion baseline)
```

---

## 5. Usage by Caller

| Caller | Commands Used | Context |
|--------|-------------|---------|
| **Skill** (`/iw-new-incident` etc.) | `next-id`, `register`, `current-project` | Inside Claude Code, in project repo |
| **Agent** (`/execute` orchestrator) | `step-start`, `step-done`, `step-fail`, `migration-lock` | Inside worktree, during execution |
| **Human** (terminal) | `approve`, `archive`, `batch-create`, `batch-approve`, `search`, `daemon`, `projects`, `sync-skills`, `init-project` | Any directory |
| **Dashboard** (API backend) | All commands via Python imports (not CLI subprocess) | Dashboard process |

**Note**: The dashboard backend imports `iw` functions directly as Python — it doesn't shell out to the CLI. The CLI and the dashboard share the same `orch/` package. The CLI is a Click wrapper around the same functions the dashboard calls.

---

## 6. `pyproject.toml` Entry Point

```toml
[project.scripts]
iw = "orch.cli.main:cli"
```

This registers `iw` as a console script. After `pip install -e .`, the `iw` command is available on PATH.
