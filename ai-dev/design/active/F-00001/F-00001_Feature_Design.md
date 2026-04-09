# F-00001: Batch Archive with Post-Merge Actions

**Type**: Feature
**Priority**: High
**Created**: 2026-04-09
**Status**: Draft

---

## Description

Enable the Archive button on completed batches in the dashboard. When clicked, it kicks off a background task that transitions the batch to `archived`, runs per-project post-archive commands (e.g., `alembic upgrade head`, `docker compose up -d --build`), and archives all work items using the existing two-tier archiver. A toast notification appears via SSE when complete.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Scope

### In Scope

- New `orch/archive/batch_archiver.py` — orchestrates batch-level archiving (state transition + post-archive commands + per-item archiving)
- New dashboard POST endpoint `/project/{project_id}/api/batch/{batch_id}/archive` — launches archive as background thread, returns immediate toast
- Wire Archive button in `batch_detail.html` to htmx confirmation dialog
- Add `batch_archived` event type to SSE toast events for async completion notification
- Add `archive` entry to `_BATCH_ACTION_LABELS` for confirmation dialog
- Extend `.iw-orch.json` schema to support `post_archive_commands` list
- Read `post_archive_commands` from `Project.config` JSONB at archive time
- Unit tests for batch archiver logic
- Integration tests for the archive endpoint and state transitions

### Out of Scope

- Worktree cleanup (already handled at merge time)
- Changes to the existing work-item archiver (`orch/archive/archiver.py`)
- New database migrations (no schema changes needed — uses existing `BatchStatus.archived` enum value and existing `Project.config` JSONB column)
- CLI `iw archive-batch` command (dashboard-only for now)

## Architecture References

| Component | File | What to reference |
|-----------|------|-------------------|
| Work-item archiver | `orch/archive/archiver.py` | `archive_work_item()` — called per-item within batch archive |
| Batch actions | `dashboard/routers/actions.py` | Pattern for confirm dialog + POST handler + `_action_response()` |
| SSE events | `dashboard/routers/sse.py` | `_TOAST_EVENTS` / `_TOAST_SEVERITY` — add `batch_archived` |
| State machine | `orch/daemon/state_machine.py` | `_BATCH_STATUS` already allows `completed → archived` and `completed_with_errors → archived` |
| Project config | `orch/daemon/project_registry.py` | `.iw-orch.json` loaded into `Project.config` JSONB |
| Batch detail template | `dashboard/templates/pages/project/batch_detail.html` | Lines 73-78 — disabled Archive button placeholder |
| Batch model | `orch/db/models.py` | `Batch`, `BatchItem`, `BatchStatus` |

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Batch archiver service (`orch/archive/batch_archiver.py`) — orchestrates archive flow | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | API | Dashboard archive endpoint + confirmation dialog wiring | — |
| S04 | Frontend | Enable Archive button with htmx, add SSE event type | — |
| S05 | CodeReview | Review S03 + S04 output | — |
| S06 | Tests | Unit + integration tests for batch archiver and endpoint | — |
| S07 | CodeReview | Review S06 output | — |
| S08 | CodeReview_Final | Global review of all work | — |
| S09..S13 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration needed. `BatchStatus.archived` already exists in the enum. `Project.config` JSONB already stores `.iw-orch.json` content. `post_archive_commands` is read from that JSONB at runtime.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/api/confirm-batch/archive/{batch_id}` — confirmation dialog fragment
  - `POST /project/{project_id}/api/batch/{batch_id}/archive` — triggers background archive
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `batch_detail.html` — replace disabled Archive button with htmx-wired button targeting confirmation dialog

## File Manifest

All files for this work item live under `ai-dev/design/active/F-00001/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00001_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00001_S01_Backend_prompt.md` | Prompt | Batch archiver service implementation |
| `prompts/F-00001_S02_CodeReview_prompt.md` | Prompt | Review backend archiver |
| `prompts/F-00001_S03_API_prompt.md` | Prompt | Dashboard endpoint implementation |
| `prompts/F-00001_S04_Frontend_prompt.md` | Prompt | Template + SSE wiring |
| `prompts/F-00001_S05_CodeReview_prompt.md` | Prompt | Review API + Frontend |
| `prompts/F-00001_S06_Tests_prompt.md` | Prompt | Test implementation |
| `prompts/F-00001_S07_CodeReview_prompt.md` | Prompt | Review tests |
| `prompts/F-00001_S08_CodeReview_Final_prompt.md` | Prompt | Global review |

Reports are created during execution in `ai-dev/work/F-00001/reports/`.

## Acceptance Criteria

### AC1: Archive completed batch from dashboard

```
Given a batch in "completed" status with all items merged
When the user clicks Archive and confirms
Then the batch transitions to "archived", post-archive commands run, all work items are archived, and a success toast appears via SSE
```

### AC2: Archive completed_with_errors batch

```
Given a batch in "completed_with_errors" status
When the user clicks Archive and confirms
Then the batch transitions to "archived", post-archive commands run, merged items are archived (failed items are skipped), and a success toast appears
```

### AC3: Archive button not shown for non-terminal batches

```
Given a batch in "executing" or "approved" status
When the user views the batch detail page
Then no Archive button is displayed
```

### AC4: Post-archive commands execute from project config

```
Given a project with .iw-orch.json containing post_archive_commands: ["alembic upgrade head"]
When a batch is archived for that project
Then "alembic upgrade head" is executed in the project's repo_root directory
```

### AC5: Async notification via SSE

```
Given a user has the batch detail page open
When the background archive task completes
Then a toast notification appears without page refresh (via SSE batch_archived event)
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Batch not in archivable state | Status is `executing` | Return 422 with clear error message |
| Post-archive command fails | `alembic upgrade head` returns non-zero | Log error, emit warning toast, still mark batch as archived |
| No post_archive_commands configured | `.iw-orch.json` has no `post_archive_commands` key | Skip command execution, proceed to item archiving |
| Empty post_archive_commands list | `"post_archive_commands": []` | Skip command execution, proceed to item archiving |
| Work item has no design doc on disk | File deleted after merge | Tier 1 stores null, Tier 2 skipped for that item (existing archiver behavior) |
| Batch has 0 items | Edge case | Transition to archived, no items to archive |
| Archive already in progress | User clicks Archive twice rapidly | First request starts archive, second gets 422 (batch already transitioning) |
| Project repo_root does not exist | Stale config | Log error, skip post-archive commands, still archive items in DB |

## Invariants

1. After archiving, `batch.status` MUST be `BatchStatus.archived`
2. All merged work items in the batch MUST have `archived_at` set and `phase = done`
3. Post-archive command failure MUST NOT prevent batch from being marked archived
4. The Archive button MUST only appear for batches in `completed` or `completed_with_errors` status
5. The archive operation MUST be non-blocking (runs in background thread)

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests**: Test `archive_batch()` function with mocked DB session — verify state transitions, per-item archiving calls, command execution. Test edge cases (no items, failed commands, missing config).
- **Integration tests**: Test the full archive endpoint with testcontainers — create batch + items, POST archive, verify final DB state. Test SSE event emission.
- **Edge cases**: Test with `completed_with_errors` batches (mixed merged/failed items), test with no `post_archive_commands` in config, test concurrent archive attempts.

## Notes

- The state machine (`orch/daemon/state_machine.py` line 77-89) already allows all terminal states → `archived`. No state machine changes needed.
- Post-archive commands run with `subprocess.run()` in the project's `repo_root` as cwd. They inherit the daemon's environment. Stdout/stderr are captured and logged.
- The background thread approach matches the pattern used by the daemon — FastAPI runs sync endpoints in a threadpool anyway, and the archive thread uses its own DB session.
- `.iw-orch.json` `post_archive_commands` example:
  ```json
  {
    "post_archive_commands": [
      "uv run alembic upgrade head",
      "docker compose up -d --build web"
    ]
  }
  ```
