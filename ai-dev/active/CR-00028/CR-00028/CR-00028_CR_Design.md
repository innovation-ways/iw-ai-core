# CR-00028: Don't cascade merge-time failures to dependent items in later execution groups

**Type**: Change Request
**Priority**: High
**Reason**: Operator-recoverable merge failures (scope-gate violation, conflict, transient git error, migration dry-run failure, pre-merge rebase failure) are currently treated as terminal and cascade to all pending items in later execution_groups. This destroys correctly-implemented work-items that had no dependency relationship beyond execution ordering. Confirmed incident on 2026-05-02 in BATCH-00070: I-00055's scope-gate failure cascade-failed I-00056 within 60s, even though I-00055 was successfully re-merged 35min later.
**Created**: 2026-05-02
**Status**: Draft

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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Introduce `BatchItemStatus.merge_failed` as an operator-recoverable, non-cascading state for merge-time failures, and exclude it (along with the existing operator-recoverable `migration_invalid` and `migration_rebase_failed`) from `_BLOCKING_TERMINAL_STATUSES`. Treat all three as non-terminal in `_current_execution_group` so later execution groups stay paused (not failed) until the operator either retries the merge (existing `restart-merge` action) or explicitly abandons the item via a new `abandon-merge` action.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key relevant files:

- `orch/db/models.py` — `BatchItemStatus` enum, `TERMINAL_BATCH_ITEM_STATUSES` constant
- `orch/daemon/merge_queue.py` — squash-merge driver and failure handling
- `orch/daemon/batch_manager.py` — batch advancement, cascade-failure logic, `_current_execution_group`
- `dashboard/routers/actions.py` — `restart-merge` and (new) `abandon-merge` endpoints
- `dashboard/templates/fragments/` — batch / item status badge rendering

## Current Behavior

When a batch item's squash-merge fails, the daemon transitions it to a terminal failure state and cascade-fails all dependent items.

**Code path** (verified via `logs/daemon.log:503769–503841`, BATCH-00070, 2026-05-02):

1. `orch/daemon/merge_queue.py:289` — on `MergeError` (any non-zero exit from `worktree_commit.sh`):
   ```python
   batch_item.status = BatchItemStatus.failed
   ```
2. `orch/daemon/merge_queue.py:159` — on pre-merge rebase failure: `BatchItemStatus.migration_rebase_failed`
3. `orch/daemon/merge_queue.py:196` — on Phase 1 dry-run failure: `BatchItemStatus.migration_invalid`
4. `orch/daemon/batch_manager.py:59` — `_BLOCKING_TERMINAL_STATUSES = TERMINAL_BATCH_ITEM_STATUSES - {BatchItemStatus.merged}` (only `merged` is excluded; `failed`, `migration_invalid`, `migration_rebase_failed` all block)
5. `orch/daemon/batch_manager.py:312–325` — next poll cycle, `_process_batch` cascades:
   ```python
   failed_in_prior_group = any(
       i.status in _BLOCKING_TERMINAL_STATUSES and i.execution_group < current_group ...)
   if failed_in_prior_group:
       for item in items:
           if item.execution_group >= current_group and item.status == BatchItemStatus.pending:
               item.status = BatchItemStatus.failed
               item.notes = f"Skipped: a dependency in execution_group ..."
   ```
6. `orch/daemon/batch_manager.py:1368–1379` — `_current_execution_group` includes `merging` and `completed` as non-terminal but treats `failed`, `migration_invalid`, `migration_rebase_failed` as terminal (advances past them).

The result: a single recoverable merge error annihilates every dependent batch item within one poll cycle, even when the operator can fix and retry.

## Desired Behavior

Three failure modes change from blocking to non-blocking:

| Failure | New status | Behaviour |
|---------|------------|-----------|
| Squash-merge error (`MergeError`) — scope gate, conflict, transient git | `merge_failed` (NEW) | Item paused, dependents stay `pending`, queue stops advancing this batch |
| Pre-merge rebase failure (existing `migration_rebase_failed`) | unchanged value | Now non-blocking; dependents stay `pending` |
| Phase 1 migration dry-run failure (existing `migration_invalid`) | unchanged value | Now non-blocking; dependents stay `pending` |

Operator workflow:

- **Retry**: existing `POST /actions/{project}/item/{id}/restart-merge` — accepts `merge_failed` (new), `migration_invalid`, `migration_rebase_failed` as preconditions. Resets BatchItem to `completed` so the merge queue picks it up again.
- **Abandon**: NEW `POST /actions/{project}/item/{id}/abandon-merge` — flips `merge_failed` / `migration_invalid` / `migration_rebase_failed` to `failed` so the existing cascade fires intentionally. Operator-explicit "give up on this item, let the rest of the batch fail too" action.

Unchanged (still blocking, still cascade):

- `failed` from worktree-setup error (`merge_queue.py:136` "no worktree path")
- `failed` from in-flight step failure (max-retries-exhausted, scope rejection during fix-cycle)
- `setup_failed`, `stalled`, `skipped`, `migration_rolled_back`

Invariant preserved: setup of item N+1 runs **only** after item N's merge is 100% complete (`merged`) — same as today, just no longer "or cascade-killed".

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `BatchItemStatus` enum (`orch/db/models.py`) | 12 values incl. `failed`, `migration_invalid`, `migration_rebase_failed` | 13 values; adds `merge_failed` |
| Alembic migration | — | New revision: `ALTER TYPE batch_item_status ADD VALUE 'merge_failed'` |
| `merge_queue.py:289` | `BatchItemStatus.failed` on `MergeError` | `BatchItemStatus.merge_failed` |
| `merge_queue.py:136` | `BatchItemStatus.failed` ("no worktree path") | unchanged (truly unrecoverable) |
| `batch_manager.py:59` | `_BLOCKING_TERMINAL_STATUSES = ALL_TERMINAL - {merged}` | `_BLOCKING_TERMINAL_STATUSES = ALL_TERMINAL - {merged, merge_failed, migration_invalid, migration_rebase_failed}` |
| `batch_manager.py:1368` `_current_execution_group` | non-terminal set: `pending, setting_up, executing, completed, merging` | adds `merge_failed, migration_invalid, migration_rebase_failed` |
| `dashboard/routers/actions.py` `restart-merge` precondition | accepts `failed` (legacy) | accepts `merge_failed`, `migration_invalid`, `migration_rebase_failed` (and continues to accept legacy `failed` if it has merge-failure metadata for back-compat with existing rows) |
| `dashboard/routers/actions.py` (new) `abandon-merge` | does not exist | new endpoint: flips `merge_failed/migration_invalid/migration_rebase_failed → failed`, triggers existing cascade |
| `dashboard/routers/actions.py` `_ITEM_ACTION_LABELS` | has `restart-merge` entry | adds `abandon-merge` entry (danger=True) for the confirm-modal pattern |
| `dashboard/routers/sse.py` `_TOAST_EVENTS` / `_TOAST_SEVERITY` | knows `merge_conflict` | adds `merge_abandoned` (severity=warning) so the SSE feed forwards and toasts the event |
| `dashboard/routers/items.py` `_merge_status` | maps `merging`, `completed` → `in_progress`; `failed` → `failed` | also maps `merge_failed`, `migration_invalid`, `migration_rebase_failed` → `merge_failed` (display value used by the badge + button condition) |
| `dashboard/templates/components/status_badge.html` | colors map for `failed`, etc. | adds `merge_failed` color (visually distinct from `failed`) |
| `dashboard/templates/components/action_button.html` | `restart_merge_button` macro | adds `abandon_merge_button` macro using the same `hx-get → /confirm-item/<action>/<id>` modal pattern (NO `hx-confirm`) |
| `dashboard/templates/fragments/item_overview.html` | shows Retry-merge button when `step.step_id == 'MERGE' and step.status == 'failed'` | extends to also show Retry + Abandon when `step.status == 'merge_failed'` |

### Breaking Changes

- **None.** New enum value is additive. Existing `failed` rows keep their semantics (still cascade). Existing `migration_invalid`/`migration_rebase_failed` rows stop cascading — this is the intentional behaviour change but does not break any contract; the operator regains control instead of losing items.

### Data Migration

- **Forward**: `ALTER TYPE batch_item_status ADD VALUE 'merge_failed'`. PostgreSQL enum addition is online and non-blocking on a single-instance DB.
- **No row updates**: historical `failed` rows from past merge errors are not retroactively re-classified. The change applies prospectively.
- **Reversibility**: `ALTER TYPE` value removal is **not natively supported** in PostgreSQL. The `down_revision` should be a no-op with a comment explaining that removing an enum value requires recreating the type. Acceptable because this is an additive change with no data-loss risk on rollback (rows holding `merge_failed` would need manual remediation only if the rollback was attempted while such rows existed).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `merge_failed` to `BatchItemStatus` enum + Alembic migration; update `TERMINAL_BATCH_ITEM_STATUSES` | — |
| S02 | code-review-impl | Review S01 schema change | — |
| S03 | backend-impl | Wire `merge_failed` in `merge_queue.py:289`; update `_BLOCKING_TERMINAL_STATUSES` and `_current_execution_group` to exclude the three non-cascading statuses; update `restart-merge` precondition; add `abandon-merge` endpoint | — |
| S04 | code-review-impl | Review S03 daemon + actions changes | — |
| S05 | frontend-impl | Add `merge_failed` badge styling; surface "Retry merge" + "Abandon" buttons on `merge_failed`/`migration_invalid`/`migration_rebase_failed` rows | — |
| S06 | code-review-impl | Review S05 frontend changes | — |
| S07 | tests-impl | Unit + integration tests for cascade-not-triggered, retry path, abandon path | — |
| S08 | code-review-impl | Review S07 tests | — |
| S09 | code-review-final-impl | Cross-layer global review | — |
| S10 | qv-gate (lint) | `make lint` | — |
| S11 | qv-gate (format) | `make format` | — |
| S12 | qv-gate (typecheck) | `make typecheck` | — |
| S13 | qv-gate (unit-tests) | `make test-unit` | — |
| S14 | qv-gate (integration-tests) | `make allure-integration` | — |
| S15 | qv-browser | End-to-end browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None (enum-only change)
- **Migration notes**: PostgreSQL `ALTER TYPE ... ADD VALUE` is non-transactional in older versions but safe on single-instance DBs. The `down_revision` is a documented no-op.

### API Changes

- **New endpoints**:
  - `POST /actions/{project_id}/item/{item_id}/abandon-merge` — flips `merge_failed`/`migration_invalid`/`migration_rebase_failed` → `failed`. Returns htmx fragment.
- **Modified endpoints**:
  - `POST /actions/{project_id}/item/{item_id}/restart-merge` — precondition extended to accept the three non-cascading statuses.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: New `abandon_merge_button` macro in `action_button.html`. New `merge_failed` color in the `status_badge` dict. New `_ITEM_ACTION_LABELS["abandon-merge"]` entry.
- **Modified components**: `item_overview.html` (synthetic-MERGE-step button condition extended to also show buttons for `merge_failed` display status); `_merge_status` in `dashboard/routers/items.py` (recognizes the three recoverable statuses and maps them to the `merge_failed` display value); `dashboard/routers/sse.py` (`_TOAST_EVENTS` / `_TOAST_SEVERITY` registers the new `merge_abandoned` event).
- **Removed components**: None
- **Convention preserved**: confirm-modal pattern (`hx-get` → `/confirm-item/<action>/<id>` → modal POSTs the action). Do NOT introduce `hx-confirm` on the buttons — it would diverge from the rest of the dashboard.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00028/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00028_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00028_S01_Database_prompt.md` | Prompt | Enum + migration |
| `prompts/CR-00028_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00028_S03_Backend_prompt.md` | Prompt | Daemon + actions |
| `prompts/CR-00028_S04_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00028_S05_Frontend_prompt.md` | Prompt | Badge + buttons |
| `prompts/CR-00028_S06_CodeReview_Frontend_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00028_S07_Tests_prompt.md` | Prompt | Tests |
| `prompts/CR-00028_S08_CodeReview_Tests_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00028_S09_CodeReview_Final_prompt.md` | Prompt | Cross-layer review |
| `prompts/CR-00028_S15_BrowserVerification_prompt.md` | Prompt | qv-browser |

QV gate steps S10–S14 run from declared `command` in the manifest (no prompt file).

Reports are created during execution under `ai-dev/active/CR-00028/reports/`.

## Acceptance Criteria

### AC1: Squash-merge failure transitions to `merge_failed`, not `failed`

```
Given a batch item in status `merging` whose worktree_commit.sh exits non-zero (scope gate, conflict, etc., but worktree path IS recorded)
When the daemon's merge_queue.process_merge_queue runs
Then the batch_item.status becomes `merge_failed` (not `failed`)
And the WorkItem.status becomes `failed` (revert preserved)
And a `merge_conflict` daemon_event is emitted
```

### AC2: `merge_failed` does not cascade to dependents

```
Given a batch with item N (group=1) in status `merge_failed` and item N+1 (group=2) in status `pending`
When the daemon's batch_manager._process_batch runs on the next poll
Then item N+1.status remains `pending`
And no `batch_dependency_failed` daemon_event is emitted for the batch
And the batch.status remains `executing` (not `completed_with_errors`)
```

### AC3: `migration_invalid` and `migration_rebase_failed` also stop cascading

```
Given a batch with item N (group=1) in status `migration_invalid` (or `migration_rebase_failed`) and item N+1 (group=2) in status `pending`
When the daemon's batch_manager._process_batch runs
Then item N+1.status remains `pending`
And the batch is NOT marked completed_with_errors
```

### AC4: "no worktree path" still produces `failed` (unrecoverable cascade preserved)

```
Given a batch item in status `completed` whose worktree_info has no `path` key
When the merge queue tries to merge it
Then the batch_item.status becomes `failed` (NOT `merge_failed`)
And dependents in later groups are cascade-failed as before
```

### AC5: Restart-merge resumes the queue from `merge_failed`

```
Given a batch item in status `merge_failed` and dependents pending
When the operator POSTs /actions/{project}/item/{id}/restart-merge
Then the batch_item.status becomes `completed`
And on the next merge_queue poll the item is re-merged
And on success dependents launch in the next group
```

### AC6: Abandon-merge flips to `failed` and triggers cascade

```
Given a batch item in status `merge_failed` and dependents pending
When the operator POSTs /actions/{project}/item/{id}/abandon-merge
Then the batch_item.status becomes `failed`
And the WorkItem.status remains `failed`
And on the next batch_manager poll the dependents are marked `failed` with the existing "Skipped: a dependency..." note
And a `merge_abandoned` daemon_event is emitted
```

### AC7: Dashboard surfaces new status and actions

```
Given an item-overview page with the synthetic MERGE step in display-status `merge_failed`
When the operator views the page
Then the synthetic MERGE step row renders a `merge_failed` badge (distinct color from `failed`)
And the row displays "Retry merge" and "Abandon" buttons
And clicking "Retry merge" issues hx-get to /confirm-item/restart-merge/{item_id} (confirm-modal pattern)
And confirming in the modal issues POST /api/item/{item_id}/restart-merge
And clicking "Abandon" issues hx-get to /confirm-item/abandon-merge/{item_id} with a danger-styled modal
And confirming in the modal issues POST /api/item/{item_id}/abandon-merge
```

Additionally, on the batch-list and batch-detail pages, the per-row `status_badge` MUST render `merge_failed` with a color visually distinct from `failed` (operator can tell at a glance the item is recoverable).

## Rollback Plan

- **Database**: The Alembic `down_revision` is a documented no-op (PostgreSQL cannot drop enum values). Acceptable because the change is additive: rolling back leaves the new value in the type but the application never writes it post-rollback. Operationally safe.
- **Code**: `git revert` the merge commit. Existing `merge_failed` rows would remain in DB but post-revert code paths would treat the status as unknown — apply manual SQL to update any in-flight rows: `UPDATE batch_items SET status = 'failed', notes = notes || ' (was merge_failed pre-rollback)' WHERE status = 'merge_failed'`.
- **Data**: No data loss on rollback. Worst case: operator-recoverable items get manually re-classified to legacy `failed`.

## Dependencies

- **Depends on**: None
- **Blocks**: None (CR-00029 "Restart Setup button" is independent)

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_merge_queue_merge_failed_status.py` — `_merge_item` writes `merge_failed` not `failed` on `MergeError` (and still writes `failed` on the no-worktree-path branch)
  - `test_batch_manager_blocking_terminal_set.py` — `_BLOCKING_TERMINAL_STATUSES` excludes `merged`, `merge_failed`, `migration_invalid`, `migration_rebase_failed`
  - `test_batch_manager_current_execution_group.py` — group with a `merge_failed` item is treated as non-terminal (returns its group, not the next)
  - `test_actions_restart_merge_preconditions.py` — accepts the three non-cascading statuses
  - `test_actions_abandon_merge.py` — flips `merge_failed → failed`, emits `merge_abandoned` event
- **Integration tests** (`tests/integration/`):
  - `test_merge_failure_does_not_cascade.py` — full scenario: 2-item batch with group 1 failing scope-gate, assert group 2 stays pending
  - `test_abandon_merge_triggers_cascade.py` — same setup but operator abandons, assert dependents become `failed`
- **Updated tests**:
  - Any existing test that asserts `BatchItemStatus.failed` after a scope-gate / merge failure must be updated to expect `merge_failed`.
  - Tests for `_BLOCKING_TERMINAL_STATUSES` membership.

## Notes

- **Why not also `migration_rolled_back`?** A successful rollback is a *resolved* state from the migration pipeline's POV — the operator would need to manually re-apply migrations to recover. Out of scope for this CR; revisit if it becomes a recurring problem.
- **Why not change `merge_queue.py:136` (no worktree path) to `merge_failed`?** That branch indicates a corrupted or never-created worktree (data integrity issue), not an operator-recoverable merge problem. Keeping it as `failed` ensures the cascade fires and the batch is correctly marked as having a hard failure.
- **Naming**: `merge_failed` chosen over `merge_blocked` because it is symmetrical with `migration_invalid` / `migration_rebase_failed` — all three are "failed but recoverable" merge-pipeline states.
