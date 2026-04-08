# IW AI Core — Database Schema DDL

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft
**Database**: `iw_orch` (PostgreSQL 15+)

---

## 1. Overview

This document contains the complete SQL DDL for the IW AI Core platform database. It serves as the specification for the Alembic initial migration.

**Design principles:**
- DB is the single source of truth for all operational state
- Every table uses `project_id` for multi-project isolation
- Composite primary keys `(project_id, id)` for work items and batches
- Atomic ID allocation via `FOR UPDATE` row locks
- Append-only for audit trails (`step_runs`, `fix_cycles`, `daemon_events`)
- All timestamps in UTC with timezone (`TIMESTAMPTZ`)
- No hardcoded values — all configurable via application layer

---

## 2. Complete DDL

### 2.1. Projects

The registry of all managed software projects.

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    repo_root       TEXT NOT NULL,
    dev_clone       TEXT,
    config          JSONB NOT NULL DEFAULT '{}',
    enabled         BOOLEAN NOT NULL DEFAULT true,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE projects IS 'Registry of software projects managed by IW AI Core';
COMMENT ON COLUMN projects.id IS 'Unique project identifier (e.g., "innoforge")';
COMMENT ON COLUMN projects.display_name IS 'Human-readable project name';
COMMENT ON COLUMN projects.repo_root IS 'Absolute path to the main clone repo root';
COMMENT ON COLUMN projects.dev_clone IS 'Absolute path to the development clone (optional)';
COMMENT ON COLUMN projects.config IS 'Full .iw-orch.json content as JSONB';
COMMENT ON COLUMN projects.enabled IS 'Whether the daemon processes this project';
```

### 2.2. ID Sequences

Atomic, race-condition-free ID allocation. Replaces markdown tracking files.

```sql
CREATE TABLE id_sequences (
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    prefix          TEXT NOT NULL,
    next_number     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, prefix)
);

COMMENT ON TABLE id_sequences IS 'Atomic sequential ID allocation per project and type';
COMMENT ON COLUMN id_sequences.prefix IS 'ID prefix: "F" (Feature), "I" (Issue), "CR" (ChangeRequest), "BATCH"';
COMMENT ON COLUMN id_sequences.next_number IS 'Next number to allocate (incremented atomically via FOR UPDATE)';
```

**Allocation query:**
```sql
-- Atomic ID allocation (used by `iw next-id`)
BEGIN;
SELECT next_number FROM id_sequences
  WHERE project_id = :project_id AND prefix = :prefix
  FOR UPDATE;
UPDATE id_sequences SET next_number = next_number + 1
  WHERE project_id = :project_id AND prefix = :prefix;
COMMIT;
-- Returns: prefix || lpad(next_number::text, 3, '0')  e.g., "I001"
```

### 2.3. Work Items

Features, Incidents, and Change Requests.

```sql
CREATE TYPE work_item_type AS ENUM ('Feature', 'Issue', 'ChangeRequest');
CREATE TYPE work_item_status AS ENUM ('draft', 'approved', 'in_progress', 'completed', 'failed', 'paused');
CREATE TYPE work_item_phase AS ENUM ('active', 'work', 'done');

CREATE TABLE work_items (
    project_id              TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    id                      TEXT NOT NULL,
    type                    work_item_type NOT NULL,
    title                   TEXT NOT NULL,
    status                  work_item_status NOT NULL DEFAULT 'draft',
    phase                   work_item_phase NOT NULL DEFAULT 'active',
    config                  JSONB NOT NULL DEFAULT '{}',
    depends_on              TEXT[] DEFAULT '{}',
    blocks                  TEXT[] DEFAULT '{}',
    design_doc_path         TEXT,

    -- Tier 1: Always viewable in dashboard (stored on archive)
    design_doc_content      TEXT,
    design_doc_search       TSVECTOR,
    summary                 TEXT,

    -- Tier 2: Compressed archive reference
    archive_path            TEXT,
    archive_size_bytes      BIGINT,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,
    archived_at             TIMESTAMPTZ,

    PRIMARY KEY (project_id, id)
);

COMMENT ON TABLE work_items IS 'Features, Incidents, and Change Requests across all projects';
COMMENT ON COLUMN work_items.config IS 'Item-level config: fix_cycle_max, browser_verification, etc.';
COMMENT ON COLUMN work_items.depends_on IS 'Array of work item IDs this item depends on';
COMMENT ON COLUMN work_items.blocks IS 'Array of work item IDs this item blocks';
COMMENT ON COLUMN work_items.design_doc_path IS 'Relative path to design doc in project repo (active items)';
COMMENT ON COLUMN work_items.design_doc_content IS 'Full markdown of design doc (Tier 1 — stored on archive for instant dashboard rendering)';
COMMENT ON COLUMN work_items.design_doc_search IS 'PostgreSQL tsvector for full-text search across design docs';
COMMENT ON COLUMN work_items.summary IS 'AI-generated 2-3 line summary for list views and search results';
COMMENT ON COLUMN work_items.archive_path IS 'Relative path to .tar.zst in archive directory (Tier 2)';
COMMENT ON COLUMN work_items.archive_size_bytes IS 'Compressed archive file size in bytes';
COMMENT ON COLUMN work_items.archived_at IS 'When the item was archived (Tier 1 + Tier 2 stored, active files deleted)';

-- Indexes
CREATE INDEX idx_work_items_status ON work_items(project_id, status);
CREATE INDEX idx_work_items_phase ON work_items(project_id, phase);
CREATE INDEX idx_work_items_type ON work_items(project_id, type);
CREATE INDEX idx_work_items_fts ON work_items USING GIN(design_doc_search);
CREATE INDEX idx_work_items_created ON work_items(project_id, created_at DESC);
```

**Full-text search update trigger:**
```sql
-- Auto-update tsvector when design_doc_content changes
CREATE OR REPLACE FUNCTION work_items_fts_update() RETURNS trigger AS $$
BEGIN
    IF NEW.design_doc_content IS NOT NULL THEN
        NEW.design_doc_search := to_tsvector('english', NEW.title || ' ' || NEW.design_doc_content);
    ELSE
        NEW.design_doc_search := to_tsvector('english', NEW.title);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_work_items_fts
    BEFORE INSERT OR UPDATE OF title, design_doc_content
    ON work_items
    FOR EACH ROW
    EXECUTE FUNCTION work_items_fts_update();
```

### 2.4. Workflow Steps

The step pipeline for each work item.

```sql
CREATE TYPE step_type AS ENUM (
    'implementation', 'code_review', 'code_review_fix',
    'code_review_final', 'code_review_fix_final',
    'quality_validation', 'qv_fix', 'browser_verification'
);
CREATE TYPE step_status AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'needs_fix', 'skipped');

CREATE TABLE workflow_steps (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL,
    work_item_id    TEXT NOT NULL,
    step_number     INTEGER NOT NULL,
    step_id         TEXT NOT NULL,
    agent_label     TEXT NOT NULL,
    opencode_agent  TEXT,
    step_type       step_type NOT NULL,
    description     TEXT,
    status          step_status NOT NULL DEFAULT 'pending',
    prompt_file     TEXT,
    report_file     TEXT,

    -- Tier 1: Always viewable in dashboard (stored on archive)
    report_content  TEXT,

    -- Timestamps
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    FOREIGN KEY (project_id, work_item_id) REFERENCES work_items(project_id, id) ON DELETE CASCADE,
    UNIQUE (project_id, work_item_id, step_number)
);

COMMENT ON TABLE workflow_steps IS 'Workflow step definitions for each work item';
COMMENT ON COLUMN workflow_steps.step_id IS 'Step identifier within the item (e.g., "S01", "S02")';
COMMENT ON COLUMN workflow_steps.agent_label IS 'Agent label for file naming (e.g., "Backend", "CodeReview_Backend")';
COMMENT ON COLUMN workflow_steps.opencode_agent IS 'OpenCode/Claude agent to invoke (e.g., "backend-impl", "code-review-impl")';
COMMENT ON COLUMN workflow_steps.prompt_file IS 'Relative path to the prompt file in the project repo';
COMMENT ON COLUMN workflow_steps.report_file IS 'Relative path to the report file (latest run)';
COMMENT ON COLUMN workflow_steps.report_content IS 'Full report markdown (Tier 1 — stored on archive for instant dashboard rendering)';

CREATE INDEX idx_workflow_steps_item ON workflow_steps(project_id, work_item_id);
CREATE INDEX idx_workflow_steps_status ON workflow_steps(project_id, work_item_id, status);
```

### 2.5. Step Runs — The Execution Control Plane

Each execution attempt of a step. Append-only — never update or delete previous runs.

```sql
CREATE TYPE run_status AS ENUM ('pending', 'running', 'completed', 'failed', 'timeout', 'killed', 'stalled');

CREATE TABLE step_runs (
    id              SERIAL PRIMARY KEY,
    step_id         INTEGER NOT NULL REFERENCES workflow_steps(id) ON DELETE CASCADE,
    run_number      INTEGER NOT NULL,
    status          run_status NOT NULL DEFAULT 'pending',

    -- Process control
    pid             INTEGER,
    pid_alive       BOOLEAN DEFAULT false,
    command         TEXT,
    worktree_path   TEXT,
    cli_tool        TEXT,
    last_heartbeat  TIMESTAMPTZ,
    timeout_secs    INTEGER,
    error_message   TEXT,

    -- Output
    exit_code       INTEGER,
    log_file        TEXT,
    report_file     TEXT,

    -- Timestamps
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_secs   FLOAT,

    UNIQUE (step_id, run_number)
);

COMMENT ON TABLE step_runs IS 'Execution attempts for workflow steps. Append-only — each retry creates a new row.';
COMMENT ON COLUMN step_runs.pid IS 'OS process ID of the LLM session (for kill -0 and SIGTERM)';
COMMENT ON COLUMN step_runs.pid_alive IS 'Whether the process is currently alive (set by daemon every poll cycle)';
COMMENT ON COLUMN step_runs.command IS 'Exact shell command used to launch (enables one-click restart)';
COMMENT ON COLUMN step_runs.worktree_path IS 'Full path to the git worktree where the agent runs';
COMMENT ON COLUMN step_runs.cli_tool IS 'LLM CLI tool used: "opencode" or "claude"';
COMMENT ON COLUMN step_runs.last_heartbeat IS 'Last time daemon confirmed PID was alive (for stall detection)';
COMMENT ON COLUMN step_runs.timeout_secs IS 'Dynamic timeout for this step type (not a global constant)';
COMMENT ON COLUMN step_runs.error_message IS 'Human-readable reason for failure, timeout, or kill';

CREATE INDEX idx_step_runs_step ON step_runs(step_id);
CREATE INDEX idx_step_runs_status ON step_runs(status) WHERE status IN ('pending', 'running', 'stalled');
```

### 2.6. Fix Cycles

Review-triggered retry loops. Append-only.

```sql
CREATE TYPE fix_trigger AS ENUM ('code_review', 'code_review_final', 'quality_validation');
CREATE TYPE fix_status AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'escalated');

CREATE TABLE fix_cycles (
    id              SERIAL PRIMARY KEY,
    step_id         INTEGER NOT NULL REFERENCES workflow_steps(id) ON DELETE CASCADE,
    cycle_number    INTEGER NOT NULL,
    trigger_type    fix_trigger NOT NULL,
    trigger_report  TEXT,
    fix_prompt      TEXT,
    fix_report      TEXT,
    status          fix_status NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    UNIQUE (step_id, cycle_number)
);

COMMENT ON TABLE fix_cycles IS 'Fix cycle attempts triggered by code review or QV failures. Append-only.';
COMMENT ON COLUMN fix_cycles.trigger_report IS 'Path to the review/QV report that triggered this fix cycle';
COMMENT ON COLUMN fix_cycles.fix_prompt IS 'Path to the generated fix prompt';
COMMENT ON COLUMN fix_cycles.fix_report IS 'Path to the fix agent report';

CREATE INDEX idx_fix_cycles_step ON fix_cycles(step_id);
```

### 2.7. Batches

Groups of work items scheduled for parallel execution.

```sql
CREATE TYPE batch_status AS ENUM (
    'planning', 'approved', 'executing', 'paused',
    'completed', 'completed_with_errors',
    'publishing', 'published', 'publish_failed',
    'blocked', 'archived'
);

CREATE TABLE batches (
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    id              TEXT NOT NULL,
    status          batch_status NOT NULL DEFAULT 'planning',
    max_parallel    INTEGER NOT NULL DEFAULT 4,
    cli_tool        TEXT NOT NULL DEFAULT 'opencode',
    auto_publish    BOOLEAN NOT NULL DEFAULT false,
    plan_path       TEXT,
    diagram_path    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,

    PRIMARY KEY (project_id, id)
);

COMMENT ON TABLE batches IS 'Groups of work items scheduled for parallel execution';
COMMENT ON COLUMN batches.max_parallel IS 'Maximum number of items executing simultaneously';
COMMENT ON COLUMN batches.auto_publish IS 'Whether to auto-push to origin after all items merged';
COMMENT ON COLUMN batches.plan_path IS 'Path to the batch execution plan document';

CREATE INDEX idx_batches_status ON batches(project_id, status);
```

### 2.8. Batch Items

Mapping of work items to batches with execution tracking.

```sql
CREATE TYPE batch_item_status AS ENUM (
    'pending', 'setting_up', 'executing',
    'completed', 'merged', 'failed', 'stalled',
    'skipped'
);

CREATE TABLE batch_items (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL,
    batch_id        TEXT NOT NULL,
    work_item_id    TEXT NOT NULL,
    execution_group INTEGER NOT NULL DEFAULT 0,
    status          batch_item_status NOT NULL DEFAULT 'pending',
    pid             INTEGER,
    started_at      TIMESTAMPTZ,
    merged_at       TIMESTAMPTZ,
    notes           TEXT,
    stall_count     INTEGER DEFAULT 0,
    last_progress   TEXT,
    worktree_info   JSONB DEFAULT '{}',
    merge_info      JSONB DEFAULT '{}',

    FOREIGN KEY (project_id, batch_id) REFERENCES batches(project_id, id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, work_item_id) REFERENCES work_items(project_id, id) ON DELETE CASCADE,
    UNIQUE (project_id, batch_id, work_item_id)
);

COMMENT ON TABLE batch_items IS 'Work items assigned to a batch with execution group and status tracking';
COMMENT ON COLUMN batch_items.execution_group IS 'Parallel execution group (0-based). Items in the same group run concurrently.';
COMMENT ON COLUMN batch_items.worktree_info IS 'Worktree metadata: path, branch, created_at';
COMMENT ON COLUMN batch_items.merge_info IS 'Merge metadata: commit_hash, conflict_files, merged_by';

CREATE INDEX idx_batch_items_status ON batch_items(project_id, batch_id, status);
CREATE INDEX idx_batch_items_work_item ON batch_items(project_id, work_item_id);
```

### 2.9. Migration Locks

Ensures only one work item per project can create Alembic migrations at a time.

```sql
CREATE TABLE migration_locks (
    project_id      TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    current_holder  TEXT,
    branch          TEXT,
    locked_at       TIMESTAMPTZ,
    head_revision   TEXT
);

COMMENT ON TABLE migration_locks IS 'Exclusive lock per project for Alembic migration creation';
COMMENT ON COLUMN migration_locks.current_holder IS 'Work item ID holding the lock (NULL = unlocked)';
COMMENT ON COLUMN migration_locks.head_revision IS 'Alembic head revision at lock time (for conflict detection)';
```

**Lock acquisition query:**
```sql
-- Atomic lock acquisition (used by `iw migration-lock acquire`)
BEGIN;
SELECT current_holder FROM migration_locks
  WHERE project_id = :project_id
  FOR UPDATE;
-- If current_holder IS NULL: lock is free
UPDATE migration_locks
  SET current_holder = :item_id, branch = :branch, locked_at = now()
  WHERE project_id = :project_id AND current_holder IS NULL;
COMMIT;
```

### 2.10. Daemon Events

Audit trail for all significant state transitions. Append-only. Powers dashboard notifications and analytics.

```sql
CREATE TABLE daemon_events (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT,
    event_type      TEXT NOT NULL,
    entity_id       TEXT,
    message         TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE daemon_events IS 'Audit trail of orchestration events. Append-only. Powers notifications and analytics.';
COMMENT ON COLUMN daemon_events.project_id IS 'NULL for system-level events (daemon start/stop, quota warnings)';
COMMENT ON COLUMN daemon_events.event_type IS 'Event category (see event type catalog below)';
COMMENT ON COLUMN daemon_events.entity_id IS 'Related entity: work item ID, batch ID, or step ID';

CREATE INDEX idx_daemon_events_recent ON daemon_events(created_at DESC);
CREATE INDEX idx_daemon_events_project ON daemon_events(project_id, created_at DESC);
CREATE INDEX idx_daemon_events_type ON daemon_events(event_type, created_at DESC);
```

---

## 3. State Machines

### 3.1. Work Item Status

```
draft ──(approve)──> approved ──(daemon picks up)──> in_progress
  ^                     |                               |
  |                     |                               ├──(all steps done)──> completed
  └──(unapprove)───────┘                               ├──(step failed, max cycles)──> failed
                                                        └──(user pauses)──> paused ──(resume)──> in_progress
```

**Valid transitions:**

| From | To | Trigger |
|------|----|---------|
| `draft` | `approved` | `iw approve` |
| `approved` | `draft` | `iw unapprove` (only if not in a batch) |
| `approved` | `in_progress` | Daemon starts first step |
| `in_progress` | `completed` | All workflow steps completed |
| `in_progress` | `failed` | Step failed after max fix cycles |
| `in_progress` | `paused` | User pauses from dashboard |
| `paused` | `in_progress` | User resumes from dashboard |
| `failed` | `in_progress` | User restarts step from dashboard |

### 3.2. Work Item Phase

```
active ──(execution starts)──> work ──(archived)──> done
```

| From | To | Trigger |
|------|----|---------|
| `active` | `work` | Worktree created, execution begins |
| `work` | `done` | `iw archive` stores content in DB + compresses artifacts |

### 3.3. Workflow Step Status

```
pending ──(launch)──> in_progress ──(pass)──> completed
                          |
                          ├──(review fail)──> needs_fix ──(fix cycle)──> in_progress
                          |                       |
                          |                       └──(max cycles)──> failed
                          └──(crash/timeout)──> failed
                                                  |
                                                  ├──(user restart)──> pending
                                                  └──(user skip)──> skipped
```

| From | To | Trigger |
|------|----|---------|
| `pending` | `in_progress` | Daemon launches step |
| `in_progress` | `completed` | `iw step-done` |
| `in_progress` | `failed` | `iw step-fail`, timeout, crash |
| `in_progress` | `needs_fix` | Code review finds mandatory fixes |
| `needs_fix` | `in_progress` | Fix cycle launched |
| `needs_fix` | `failed` | Max fix cycles reached |
| `failed` | `pending` | User clicks [Restart] |
| `failed` | `skipped` | User clicks [Skip] |

### 3.4. Step Run Status

```
pending ──(daemon launches)──> running ──(agent completes)──> completed
                                  |
                                  ├──(agent fails)──> failed
                                  ├──(timeout exceeded)──> timeout
                                  ├──(user kills)──> killed
                                  └──(no progress)──> stalled
```

| From | To | Trigger |
|------|----|---------|
| `pending` | `running` | Daemon launches process, records PID |
| `running` | `completed` | Agent reports success via `iw step-done` |
| `running` | `failed` | Agent reports failure or PID dies unexpectedly |
| `running` | `timeout` | Daemon detects elapsed > timeout_secs |
| `running` | `killed` | User clicks [Kill] from dashboard |
| `running` | `stalled` | PID alive but no heartbeat for stall_threshold |

### 3.5. Batch Status

```
planning ──(approve)──> approved ──(daemon starts)──> executing
                                                        |
                                    ┌───────────────────┤
                                    |                   |
                                    v                   ├──(all merged)──> completed
                                  paused                |                     |
                                    |                   ├──(some failed)──> completed_with_errors
                                    └──(resume)─────────┘
                                                        completed ──(auto_publish)──> publishing
                                                                                        |
                                                                                        ├──> published
                                                                                        └──> publish_failed
```

| From | To | Trigger |
|------|----|---------|
| `planning` | `approved` | Human approves (`make batch-launch` or dashboard) |
| `approved` | `executing` | Daemon picks up batch |
| `executing` | `paused` | User pauses from dashboard |
| `paused` | `executing` | User resumes from dashboard |
| `executing` | `completed` | All items merged successfully |
| `executing` | `completed_with_errors` | Some items merged, some failed |
| `completed` | `publishing` | auto_publish=true, daemon starts publish |
| `publishing` | `published` | Push + CI succeeded |
| `publishing` | `publish_failed` | Push or CI failed |
| Any terminal | `archived` | User archives batch |

### 3.6. Batch Item Status

```
pending ──(setup)──> setting_up ──(launch)──> executing
                                                |
                                                ├──(all steps done)──> completed ──(merge)──> merged
                                                ├──(step failed)──> failed ──(requeue)──> pending
                                                └──(no progress)──> stalled ──(reset)──> pending
```

| From | To | Trigger |
|------|----|---------|
| `pending` | `setting_up` | Daemon starts worktree creation |
| `setting_up` | `executing` | Worktree ready, agent launched |
| `executing` | `completed` | All workflow steps completed |
| `executing` | `failed` | Workflow failed (escalated) |
| `executing` | `stalled` | No progress for extended period |
| `completed` | `merged` | Daemon squash-merges to main |
| `failed` | `pending` | User re-queues from dashboard |
| `stalled` | `pending` | User resets from dashboard |

---

## 4. Event Type Catalog

Events written to `daemon_events.event_type`:

| Event Type | Entity | Description |
|-----------|--------|-------------|
| `daemon_started` | — | Daemon process started |
| `daemon_stopped` | — | Daemon process stopped (graceful) |
| `project_discovered` | project_id | New project registered from projects.toml |
| `project_disabled` | project_id | Project disabled in projects.toml |
| `batch_approved` | batch_id | Batch approved for execution |
| `batch_executing` | batch_id | Daemon started processing batch |
| `batch_paused` | batch_id | Batch paused by user |
| `batch_resumed` | batch_id | Batch resumed by user |
| `batch_completed` | batch_id | All items in batch merged |
| `batch_completed_with_errors` | batch_id | Batch finished with some failures |
| `item_setup_started` | work_item_id | Worktree creation started |
| `item_setup_completed` | work_item_id | Worktree ready, agent launching |
| `item_completed` | work_item_id | All steps passed |
| `item_failed` | work_item_id | Item failed (escalated to human) |
| `item_merged` | work_item_id | Squash-merged to main |
| `item_archived` | work_item_id | Archived to DB (Tier 1) + disk (Tier 2) |
| `step_launched` | step_id | Step execution started (PID recorded) |
| `step_completed` | step_id | Step finished successfully |
| `step_failed` | step_id | Step failed (agent error) |
| `step_timeout` | step_id | Step exceeded dynamic timeout |
| `step_killed` | step_id | Step killed by user from dashboard |
| `step_stalled` | step_id | Step detected as stalled |
| `step_restarted` | step_id | Step restarted by user |
| `step_skipped` | step_id | Step skipped by user |
| `fix_cycle_started` | step_id | Fix cycle triggered by review |
| `fix_cycle_completed` | step_id | Fix cycle resolved the issue |
| `fix_cycle_escalated` | step_id | Max fix cycles reached |
| `merge_started` | work_item_id | Squash-merge initiated |
| `merge_completed` | work_item_id | Merge successful |
| `merge_conflict` | work_item_id | Merge conflict detected |
| `publish_started` | batch_id | Auto-publish initiated |
| `publish_completed` | batch_id | Push + CI succeeded |
| `publish_failed` | batch_id | Push or CI failed |
| `quota_warning` | — | LLM quota threshold exceeded |
| `orphan_detected` | — | Orphaned worktree or zombie PID found on startup |

---

## 5. Seed Data

Initial data inserted after migration for a fresh installation:

```sql
-- No seed data required for a fresh installation.
-- Projects are registered via `iw init-project`.
-- ID sequences are created when a project is registered.
-- All other data is created through normal operation.
```

When a project is registered via `iw init-project`, the following seed data is created:

```sql
-- Called by `iw init-project --id innoforge`
INSERT INTO projects (id, display_name, repo_root, config)
VALUES (:id, :display_name, :repo_root, :config);

INSERT INTO id_sequences (project_id, prefix, next_number) VALUES
    (:id, 'F', 1),
    (:id, 'I', 1),
    (:id, 'CR', 1),
    (:id, 'BATCH', 1);

INSERT INTO migration_locks (project_id, current_holder) VALUES (:id, NULL);
```

---

## 6. Notes

### 6.1. Why ENUMs Instead of TEXT

Status columns use PostgreSQL ENUMs (`CREATE TYPE ... AS ENUM`) instead of plain TEXT:
- **Compile-time validation**: Invalid status values are rejected by the DB, not silently stored
- **Self-documenting**: The schema itself documents all valid values
- **Storage efficiency**: ENUMs are stored as 4 bytes internally (vs variable-length TEXT)
- **Indexing**: More efficient B-tree indexes on ENUM vs TEXT

**Trade-off**: Adding a new enum value requires an `ALTER TYPE ... ADD VALUE` migration. This is acceptable — status values change infrequently and must be deliberate.

### 6.2. Why ON DELETE CASCADE

All foreign keys use `ON DELETE CASCADE`:
- When a project is deleted, all its work items, batches, steps, and events are deleted
- This is the correct behavior for a platform where project removal means full cleanup
- In practice, projects are rarely deleted — they're disabled via `enabled = false`

### 6.3. Future: pgvector for RAG

When semantic search is needed, add:

```sql
-- Requires: CREATE EXTENSION vector;
ALTER TABLE work_items ADD COLUMN design_doc_embedding vector(1536);
CREATE INDEX idx_work_items_embedding ON work_items
    USING ivfflat(design_doc_embedding vector_cosine_ops);
```

The schema is designed so this is a non-breaking addition. No existing queries or indexes are affected.

### 6.4. Partial Index on Running Steps

The `idx_step_runs_status` index only covers `pending`, `running`, and `stalled` statuses:

```sql
CREATE INDEX idx_step_runs_status ON step_runs(status)
    WHERE status IN ('pending', 'running', 'stalled');
```

This is a partial index — it only indexes the rows the daemon actively queries (running and actionable steps). Completed, failed, and killed runs are not indexed, keeping the index small and fast even with thousands of historical runs.
