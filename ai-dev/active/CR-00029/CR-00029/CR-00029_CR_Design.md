# CR-00029: Add "Restart" button to the synthetic Worktree Setup (S00) row

**Type**: Change Request
**Priority**: Medium
**Reason**: When a worktree setup fails (or a batch-item ends in `BatchItemStatus.failed` cascaded from a sibling's setup error), there is no per-row recovery affordance. The synthetic S00 step row is excluded from action buttons by `dashboard/templates/fragments/item_overview.html:95` (`{% elif not step.is_synthetic %}`), so the operator's only recovery path is the page-level "Full restart" action — discoverable away from the row that actually shows the failure. This CR closes the UX gap by surfacing a "Restart" button directly on the S00 row.
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

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only `docker ps/inspect/logs`; invoking `./ai-core.sh` or `make`.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB. Your job in a Database step is to WRITE the migration FILE. The daemon applies it.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

---

## Description

Surface a "Restart Setup" button on the synthetic S00 row of the item-overview Step Pipeline whenever the BatchItem is in a setup-recoverable state (`setup_failed`, or `failed` with no step runs progressed past pending). The button delegates to a new `POST /project/{project_id}/api/item/{item_id}/restart-setup` endpoint, which performs the same worktree-cleanup + state-reset as the existing `full_restart_item` but is precondition-gated to setup-only failures and emits a distinct `setup_restarted` daemon event for clearer audit trails.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key relevant files:

- `dashboard/routers/items.py:46–63` — `StepDetail` dataclass
- `dashboard/routers/items.py:562–595` — `_synthetic_setup_step` factory
- `dashboard/routers/items.py:430` — where the synthetic step is injected into the step list
- `dashboard/templates/fragments/item_overview.html:90–107` — the action-button column conditional
- `dashboard/templates/components/action_button.html` — existing macros (`restart_button`, `restart_merge_button`, `kill_button`, `skip_button`) all use the confirm-dialog pattern (`hx-get` to `/api/confirm/...`)
- `dashboard/routers/actions.py:1042–1138` — `full_restart_item` (existing logic to delegate to)
- `dashboard/routers/actions.py:765–843` — `restart_item` (existing related logic for failed-at-setup)

## Current Behavior

When a worktree-setup failure leaves an item in `WorkItemStatus.failed` with `BatchItem.status` ∈ {`setup_failed`, `failed`} and all `WorkflowStep` rows still `pending`:

1. The item-overview page renders a synthetic S00 row labelled "Worktree Setup" with status `failed` and the failure note in the Error column.
2. `dashboard/templates/fragments/item_overview.html:95` checks `{% elif not step.is_synthetic %}` — synthetic steps render zero action buttons.
3. The operator's only recovery path is the page-level "Full restart" button (which lives in the page header / actions menu, not on the S00 row).

The functional restart works (`full_restart_item` deletes the worktree, resets all steps, sets item→approved, re-opens the batch), but the affordance is non-discoverable from the failed row.

## Desired Behavior

When the synthetic S00 row's status is `failed` and the item is in a setup-only failure state:

1. The S00 row's right-most "Action" column renders a `↻ Restart Setup` button styled identically to the existing `restart_merge_button`.
2. Clicking the button opens the standard confirm dialog ("Restart setup {item_id}? This deletes the worktree and resets every step. The daemon will re-run setup from scratch.").
3. Confirming POSTs to `/project/{project_id}/api/item/{item_id}/restart-setup`.
4. The endpoint performs the same operations as `full_restart_item` (delete worktree, clear step runs and log files, reset all steps to `pending`, set item→`approved`, re-open the batch if `completed_with_errors`), but:
   - Precondition gates: BatchItem.status ∈ {`setup_failed`, `failed`} AND no `WorkflowStep` has progressed beyond `pending`. Otherwise 422.
   - Emits a distinct `setup_restarted` daemon event (instead of `item_full_restarted`).
5. The daemon's next poll picks up the item and re-launches the worktree setup.

The button does NOT appear when:
- The item has progressed past setup (any step has `started_at`/`completed_at` set, or status ∈ {`in_progress`, `completed`, `failed`-with-runs, `needs_fix`}).
- The BatchItem is currently `setting_up`, `executing`, `merging`, `merge_failed`, etc.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `StepDetail` dataclass (`dashboard/routers/items.py:46–63`) | 13 fields | adds optional `restartable: bool = False` |
| `_synthetic_setup_step` (`dashboard/routers/items.py:562–595`) | returns StepDetail with `is_synthetic=True` | additionally computes `restartable` based on BatchItem.status + step-pending check |
| `dashboard/routers/actions.py` | has `restart_item` (line 765) and `full_restart_item` (line 1042) | adds new `restart_setup` endpoint sharing internal logic with `full_restart_item` |
| `dashboard/templates/components/action_button.html` | 4 macros | adds `restart_setup_button(project_id, item_id)` macro using the confirm-dialog pattern |
| `dashboard/routers/actions.py` (confirm dialogs) | generic `/confirm-item/{action}/{item_id}` dispatcher dispatches off `_ITEM_ACTION_LABELS` | adds a `restart-setup` entry to `_ITEM_ACTION_LABELS` so the existing dispatcher handles the new dialog (no new GET handler needed) |
| `dashboard/templates/fragments/item_overview.html:90–107` | `{% elif not step.is_synthetic %}` excludes all synthetic rows | adds a branch for synthetic S00 + `step.restartable` rendering the new button |

### Breaking Changes

- **None.** Pure UI addition. The new endpoint is additive (existing `full_restart_item` continues to work for non-synthetic-row triggers).

### Data Migration

- **Not required.** No schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `restartable` field to `StepDetail`; compute it in `_synthetic_setup_step` (true iff BatchItem.status ∈ {setup_failed, failed} AND no WorkflowStep has progressed past pending). Add `POST /project/{project_id}/api/item/{item_id}/restart-setup` endpoint, and register `restart-setup` in `_ITEM_ACTION_LABELS` so the existing `confirm_item_dialog` dispatcher serves the dialog. Refactor `full_restart_item`'s body into a private helper that both endpoints call to avoid duplication. New endpoint emits `setup_restarted` event. | — |
| S02 | code-review-impl | Review S01: precondition correctness, helper extraction, event naming, no behavior change in `full_restart_item` | — |
| S03 | frontend-impl | Add `restart_setup_button` macro in `action_button.html` (mirror `restart_merge_button` style: secondary bg, "↻ Restart Setup" label). Update `item_overview.html:95` to render the button when `step.is_synthetic and step.step_id == 'S00' and step.restartable`. | — |
| S04 | code-review-impl | Review S03: macro reuse, no regression in existing button conditionals, accessibility | — |
| S05 | tests-impl | Unit tests for: `_synthetic_setup_step.restartable` flag (parametrized over BatchItem statuses); `restart_setup` endpoint (precondition pass/fail, worktree deleted, steps reset, batch re-opened, event emitted); template rendering test that the button appears for restartable synthetic S00 rows and not otherwise. | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Cross-step global review | — |
| S08 | qv-gate (lint) | `make lint` | — |
| S09 | qv-gate (format) | `make format` | — |
| S10 | qv-gate (typecheck) | `make typecheck` | — |
| S11 | qv-gate (unit-tests) | `make test-unit` | — |
| S12 | qv-gate (integration-tests) | `make allure-integration` | — |
| S13 | qv-browser | End-to-end browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A — no schema changes.

### API Changes

- **New endpoints**:
  - `POST /project/{project_id}/api/item/{item_id}/restart-setup` — restart setup-only failures.
- **Modified endpoints**:
  - `GET /project/{project_id}/api/confirm-item/{action}/{item_id}` — extends the existing dispatcher's `_ITEM_ACTION_LABELS` with a `restart-setup` entry; no new route handler.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: `restart_setup_button(project_id, item_id)` macro in `dashboard/templates/components/action_button.html`.
- **Modified components**: `dashboard/templates/fragments/item_overview.html` (one new branch in the action-column conditional).
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00029/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00029_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00029_S01_Backend_prompt.md` | Prompt | StepDetail flag, endpoint, helper |
| `prompts/CR-00029_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00029_S03_Frontend_prompt.md` | Prompt | Macro + template branch |
| `prompts/CR-00029_S04_CodeReview_Frontend_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00029_S05_Tests_prompt.md` | Prompt | Tests |
| `prompts/CR-00029_S06_CodeReview_Tests_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00029_S07_CodeReview_Final_prompt.md` | Prompt | Cross-layer review |
| `prompts/CR-00029_S13_BrowserVerification_prompt.md` | Prompt | qv-browser |

QV gate steps S08–S12 run from declared `command` (no prompt file).

Reports created during execution under `ai-dev/active/CR-00029/reports/`.

## Acceptance Criteria

### AC1: `restartable` flag is true for setup-only failures

```
Given a BatchItem in status `setup_failed` (or `failed` with no WorkflowStep started)
When the item-overview page renders the synthetic S00 row
Then the StepDetail's restartable attribute is True
```

### AC2: `restartable` flag is false otherwise

```
Given a BatchItem in any status NOT in {setup_failed, failed} OR any WorkflowStep with status != pending
When the item-overview page renders the synthetic S00 row
Then the StepDetail's restartable attribute is False
```

### AC3: Button renders only when restartable

```
Given a synthetic S00 row in the item-overview page
When restartable is True
Then the row's action column contains a button with text "↻ Restart Setup"
And the button targets a confirm dialog via hx-get
```

### AC4: Confirm-dialog endpoint returns expected fragment

```
Given GET /project/{project_id}/api/confirm-item/restart-setup/{item_id}
When the BatchItem is restartable
Then the response is HTML containing the title "Restart setup {item_id}?"
And contains the description "This deletes the worktree and resets every step. The daemon will re-run setup from scratch."
And contains a confirm button POSTing to /project/{project_id}/api/item/{item_id}/restart-setup
```

### AC5: Restart-setup endpoint resets state correctly

```
Given a BatchItem in `setup_failed` with all WorkflowSteps `pending` and a worktree directory on disk
When POST /project/{project_id}/api/item/{item_id}/restart-setup is called
Then the worktree directory is removed
And all WorkflowStep records are reset (status=pending, started_at=None, completed_at=None, report_file=None)
And all StepRun records for the item are deleted (with log files unlinked)
And the WorkItem.status becomes `approved`
And the BatchItem.status becomes `pending` (notes cleared, started_at None)
And the parent Batch transitions from `completed_with_errors` to `approved` (if applicable)
And a `setup_restarted` daemon_event is emitted
```

### AC6: Restart-setup precondition rejects post-setup states

```
Given a BatchItem in `executing` (or `completed`, `merging`, `merge_failed`, etc.)
When POST /project/{project_id}/api/item/{item_id}/restart-setup is called
Then the response is HTTP 422
And no state changes occur
```

### AC7: End-to-end click flow works in the browser

```
Given an item with a failed S00 row visible on the item-overview page
When the operator clicks "Restart Setup" and confirms the dialog
Then the page updates to show the item back in `approved` state
And on the next daemon poll, S00 transitions to `setting_up`
```

## Rollback Plan

- **Database**: No schema changes. N/A.
- **Code**: `git revert` the merge commit. The new endpoint and button disappear; existing `full_restart_item` continues to work as before.
- **Data**: No data loss on rollback. Any item that was reset via `/restart-setup` is indistinguishable from one reset via `/full-restart` post-rollback (the only difference was the daemon_event type emitted).

## Dependencies

- **Depends on**: None
- **Blocks**: None (CR-00028 "Don't cascade merge failures" is independent)

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_synthetic_setup_step_restartable.py` — parametrized over BatchItem statuses + WorkflowStep states; assert `restartable` is true/false correctly.
  - `test_actions_restart_setup_endpoint.py` — precondition pass/fail, worktree deletion call, step reset, batch re-open, event emission. Use the existing dashboard test fixture pattern.
  - `test_actions_restart_setup_confirm_dialog.py` — GET returns HTML fragment with the expected text and POST target.
- **Integration tests** (`tests/integration/`):
  - `test_restart_setup_full_flow.py` — set up item in `setup_failed`, write a fake worktree dir, call the endpoint, assert filesystem cleanup + DB state.
- **Updated tests**:
  - Any existing test that asserts the action column for synthetic S00 row is empty must be updated to expect the button when restartable is True.

## Notes

- **Why a new endpoint instead of reusing `full_restart_item`?** The existing endpoint is permissive (`item.status in _FULL_RESTART_ALLOWED` accepts `failed`/`in_progress`/`paused`) and emits `item_full_restarted`. A setup-only restart should be precondition-gated to "setup hasn't progressed" so we don't accidentally tear down an item that was halfway through real work, and a distinct event makes log forensics cleaner. Both share an internal helper to avoid duplication.
- **Confirmed wording**: title "Restart setup {item_id}?" and description "This deletes the worktree and resets every step. The daemon will re-run setup from scratch." Reuses the generic `_ITEM_ACTION_LABELS` dispatcher (matches the `restart-merge` precedent — title becomes `f"{title.rstrip('?')} {item_id}?"`). Avoids a custom GET handler.
- **Why also accept `BatchItem.status = failed` with no step runs?** Cascade failures (where a sibling item's setup error fails the batch and a downstream item ends in `BatchItemStatus.failed` without ever running a step) are functionally setup failures from the operator's perspective. Without this branch, the new button wouldn't appear for those cases. Once CR-00028 lands, future cascade failures may appear as `merge_failed` on the predecessor instead, and this CR's logic naturally handles either path.
