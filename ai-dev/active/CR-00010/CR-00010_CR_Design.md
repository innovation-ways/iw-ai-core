# CR-00010: Research items auto-complete without manual approval

**Type**: Change Request
**Priority**: Medium
**Reason**: Usability / correctness — research items currently follow the full `draft → approved → in_progress → completed` flow, which is meaningless for research (produced interactively by the `iw-research` skill with no daemon implementation phase). The approval gate creates confusion and leaves research items stuck in `draft` forever unless someone manually runs `iw approve`.
**Created**: 2026-04-18
**Status**: Draft

---

## Description

Make research work items (`WorkItemType.Research`) bypass the approval workflow entirely. They start as `draft` when registered and auto-transition to `completed` the first time `iw doc-update` runs for a `doc_type=research` document whose `doc_id` matches the work item's `id`. `iw approve` and `iw unapprove` error out when invoked on a research item. Research items are rejected from `iw batch-create` and are not rendered in the dashboard batch-queue list. Dashboard pages hide the approve / unapprove action controls for research items.

## Project Context

Read `CLAUDE.md` at the repo root for architecture, conventions, and hard rules. Orchestration package conventions live in `orch/CLAUDE.md`. Dashboard conventions (FastAPI + Jinja2 + htmx, no build step) live in `dashboard/CLAUDE.md`. Test conventions (testcontainers, FTS trigger rule, no `importlib.reload`) live in `tests/CLAUDE.md`.

## Current Behavior

- `orch/daemon/state_machine.py::_WORK_ITEM_STATUS` (lines 28–37) is a single shared transition table: `draft → {approved}`, `approved → {draft, in_progress}`, `in_progress → {completed, failed, paused}`. All work item types (Feature, Issue, ChangeRequest, Research) share it. `draft → completed` is NOT a valid transition today.
- `orch/cli/item_commands.py::validate_approve_transition` (lines 33–37) and `validate_unapprove_transition` (lines 40–49) gate approve/unapprove. The `approve` command (lines ~309–337) and `unapprove` (lines ~340–389) accept any work item type; nothing rejects research.
- `orch/cli/batch_commands.py::batch_create` (lines 244–258) requires every item to be in `WorkItemStatus.approved`. Since research items never reach `approved` in the new flow, they would be silently blocked — but the error message says "not approved" instead of "research items are not eligible for batches", which is misleading.
- `orch/cli/doc_commands.py::doc_update` (lines 107–229) upserts the `ProjectDoc` row via `DocService.upsert_doc`. It does NOT touch the associated `WorkItem`. There is no implicit link between the doc and the work item beyond the shared string ID (`doc_id == work_item.id`, e.g., `R-00001`).
- `skills/iw-research/SKILL.md` Step 6 (lines 172–199) registers the item with `iw register ... --type research` (leaves it in `draft`), then runs `iw doc-update ... --status draft`. The skill never calls `iw approve`; the item remains stuck at `draft` forever unless a human intervenes.
- Dashboard: `dashboard/routers/actions.py` and the approve/unapprove action endpoints render buttons for every work item regardless of type. The batch-queue list at `dashboard/routers/project_pages.py` / corresponding template enumerates every `approved` work item — research items never appear there today (by accident of state), but the filter is status-based, not type-based, so if a research item were ever manually approved it would leak into the queue.

## Desired Behavior

1. **State machine — research-specific transitions**:
   - Add a type-aware transition function: `validate_work_item_status(from_s, to_s, item_type)` where `item_type: WorkItemType | None = None`.
   - When `item_type == WorkItemType.Research`, allowed transitions are: `draft → completed` (terminal). No `approved`, no `in_progress`, no `paused`, no `failed` (the skill either finishes or the user retries from scratch).
   - When `item_type` is any other value (or `None` for backward compatibility), transitions match the existing table.
   - Keep the old no-arg signature callable (default `item_type=None`) so pre-existing call sites in the daemon, CLI, and tests continue to compile without change.
2. **`iw approve` / `iw unapprove` reject research**:
   - `validate_approve_transition(current_status, item_type=None)`: if `item_type == WorkItemType.Research`, return `"Cannot approve research items — they auto-complete when the research document is created via 'iw doc-update'"`.
   - `validate_unapprove_transition(current_status, active_batch_id, item_type=None)`: if `item_type == WorkItemType.Research`, return `"Cannot unapprove research items — they do not use the approval workflow"`.
   - The `approve` and `unapprove` Click commands load the work item, call the type-aware validator, and `output_error` on the message. Exit code 2 (same as existing invalid-transition errors).
3. **`iw doc-update` auto-completes research work items**:
   - After `svc.upsert_doc(...)` succeeds AND the resolved `DocType` is `research`, look up `WorkItem` with the same `project_id` and `id == doc_id`. If it exists and is `WorkItemType.Research` and its status is `draft`, transition it to `WorkItemStatus.completed`, set `phase = WorkItemPhase.done`, and set `completed_at = datetime.now(UTC)`.
   - Idempotent: if the work item is already `completed`, skip silently. If the work item is not of type `Research`, skip silently (some non-research doc may coincidentally share an ID with a non-research work item — do not touch it).
   - If no work item with that ID exists, skip silently (the user may use `iw doc-update` for ad-hoc research docs without registering a work item).
   - Emit the auto-complete in the JSON output: add `"work_item_auto_completed": true|false` alongside the existing `doc_id`, `project_id`, `version`, `status`, `snapshot_created` fields.
4. **`iw batch-create` rejects research items**:
   - Before the `status != approved` check, add a type check: if `item.item_type == WorkItemType.Research`, call `output_error(ctx, f"Work item {iid} is a research item and cannot be added to a batch — research items auto-complete via 'iw doc-update'", 1)`.
5. **Dashboard — hide approve/unapprove**:
   - On the work-item detail page, hide the approve and unapprove buttons/forms when `item.item_type == WorkItemType.Research`. Replace with an inline notice: `"Research items auto-complete when the research document is created."`.
   - Wherever the dashboard lists work items with bulk or inline approve actions, exclude research items from those actions (or disable the action with the same notice).
6. **Dashboard — batch-queue exclusion**:
   - The batch-queue list (approved work items available to be added to a new batch) filters by both `status == approved` AND `item_type != Research`. This is defense-in-depth — research should never reach `approved`, but the filter makes the intent explicit and prevents leaks.
   - The backend query that feeds the batch-queue template must add the `WorkItem.item_type != WorkItemType.Research` predicate.
7. **Skill update — `skills/iw-research/SKILL.md` Step 6**:
   - Update the `iw doc-update` example to reflect the new behavior: drop `--status draft` (the doc still defaults to `planned`; if the skill wants a non-default value, keep it, but the *work item* transition is automatic).
   - Add a note: "The work item transitions from `draft` to `completed` automatically when `iw doc-update` runs for a `research` doc. Do NOT call `iw approve`."

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/daemon/state_machine.py::validate_work_item_status` | `(from_s, to_s) -> None` | `(from_s, to_s, item_type: WorkItemType \| None = None) -> None` — branches to research table when `item_type == Research` |
| `orch/daemon/state_machine.py::can_transition_work_item_status` | `(from_s, to_s) -> bool` | `(from_s, to_s, item_type: WorkItemType \| None = None) -> bool` |
| `orch/daemon/state_machine.py` (new) | — | `_RESEARCH_WORK_ITEM_STATUS` table: `{draft: {completed}, completed: {}}` |
| `orch/cli/item_commands.py::validate_approve_transition` | `(current_status) -> str \| None` | `(current_status, item_type: WorkItemType \| None = None) -> str \| None` |
| `orch/cli/item_commands.py::validate_unapprove_transition` | `(current_status, active_batch_id) -> str \| None` | `(current_status, active_batch_id, item_type: WorkItemType \| None = None) -> str \| None` |
| `orch/cli/item_commands.py::approve` / `unapprove` | Type-agnostic | Load item, pass `item.item_type` to validator, error on research |
| `orch/cli/doc_commands.py::doc_update` | Only upserts doc | After upsert, if `doc_type==research` AND matching research work item in `draft`, transition work item to `completed` |
| `orch/cli/batch_commands.py::batch_create` | Rejects on `status != approved` | Rejects on `item_type == Research` first, then on `status != approved` |
| `dashboard/routers/actions.py` (approve/unapprove endpoints) | Accept any item type | Return 400 / htmx error when `item.item_type == Research` |
| `dashboard/routers/project_pages.py` / batch queue endpoint | Lists all `approved` items | Excludes `WorkItemType.Research` from the batch-queue query |
| `dashboard/templates/**` (item detail + batch queue) | Always render approve/unapprove UI; batch queue lists all approved items | Hide approve/unapprove for research; batch queue excludes research |
| `skills/iw-research/SKILL.md` Step 6 | Tells user to register then doc-update with `--status draft`; no mention of auto-complete | Documents that `iw doc-update` auto-completes the work item; no `iw approve` step |

### Breaking Changes

- **`iw approve <R-ID>` and `iw unapprove <R-ID>` now error.** No existing research items in the DB (verified via `iw item-status R-00001/R-00002` — both "not found"), so no running workflow is impacted.
- **`iw doc-update` output JSON gains a `work_item_auto_completed` field.** Additive — callers that parse specific fields still work. Callers that strictly validate the full shape may need an update (there are none in-repo — grep confirms no automated JSON-shape assertions on `doc-update` output).
- **`validate_approve_transition` / `validate_unapprove_transition` / `validate_work_item_status` / `can_transition_work_item_status` gain an optional `item_type` parameter.** The default is `None` which preserves exact previous behavior; all existing call sites continue to compile. No hard break.

### Data Migration

- **None required.** There are no existing research items in the database. If one is introduced mid-flight (race between this CR's deployment and a new research item registered on the old code), it would simply be stuck in `draft` until `iw doc-update` runs — exactly the new desired flow. No manual backfill needed.
- **Reversibility**: Revert commit. The state-machine table is a code change, not a schema change. No migration to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `orch/daemon/state_machine.py`: research transition table + type-aware validators. `orch/cli/item_commands.py`: reject approve/unapprove for research, wire `item_type` into validators. `orch/cli/doc_commands.py`: auto-complete research work item after `doc-update`. `orch/cli/batch_commands.py`: reject research items. `skills/iw-research/SKILL.md`: Step 6 update. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | `dashboard/routers/actions.py`: reject approve/unapprove on research. `dashboard/routers/project_pages.py` (and sibling routers feeding the batch-queue view): exclude research from batch-queue query. `dashboard/templates/**`: hide approve/unapprove UI for research items on item detail pages; add explanatory notice. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | Update all existing tests that assert research goes through the approved state. Add unit tests: state-machine research transitions, validator rejection for research, `doc-update` auto-complete, `batch-create` rejection. Add integration tests: end-to-end research flow (register → doc-update → completed), approve/unapprove CLI rejection, batch-create CLI rejection. | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Cross-agent final review | — |
| S08 | code-review-fix-final-impl | Apply final-review findings | — |
| S09 | qv-gate (lint) | `uv run ruff check .` | — |
| S10 | qv-gate (format) | `uv run ruff format --check .` | — |
| S11 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S12 | qv-gate (unit-tests) | `make test-unit` | — |
| S13 | qv-gate (integration-tests) | `make test-integration` | — |
| S14 | qv-browser | Browser verification: research item detail page hides approve/unapprove; research item does not appear in batch-queue list; `iw doc-update` via CLI auto-completes an item (visible on the dashboard). | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None (pure code change in state-machine table + CLI validators + templates)

### API Changes

- **New endpoints**: None
- **Modified endpoints**:
  - Dashboard approve/unapprove action endpoints (under `dashboard/routers/actions.py`): now return a 4xx (or htmx error response consistent with existing invalid-transition handling) when invoked on a research item.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**:
  - `dashboard/templates/**` — item detail page template (whichever template renders the approve/unapprove forms) gains `{% if item.item_type.value != 'Research' %}` guards, plus an inline notice for research items.
  - Batch-queue list template — reflects the backend filter change (research excluded).
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00010/`.

| File | Type | Purpose |
|------|------|---------|
| `CR-00010_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00010_S01_Backend_prompt.md` | Prompt | S01 — backend-impl (state machine + CLI + skill) |
| `prompts/CR-00010_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/CR-00010_S03_Frontend_prompt.md` | Prompt | S03 — frontend-impl (dashboard) |
| `prompts/CR-00010_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/CR-00010_S05_Tests_prompt.md` | Prompt | S05 — tests-impl |
| `prompts/CR-00010_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/CR-00010_S07_CodeReview_Final_prompt.md` | Prompt | S07 — final cross-agent review |
| `prompts/CR-00010_S08_CodeReview_Fix_Final_prompt.md` | Prompt | S08 — apply final-review fixes |
| `prompts/CR-00010_S14_BrowserVerification_prompt.md` | Prompt | S14 — qv-browser |

### Files to Modify (source tree)

- `orch/daemon/state_machine.py`
- `orch/cli/item_commands.py`
- `orch/cli/doc_commands.py`
- `orch/cli/batch_commands.py`
- `dashboard/routers/actions.py`
- `dashboard/routers/project_pages.py` (and/or sibling routers feeding batch-queue view)
- `dashboard/templates/**` (item detail + batch queue templates — S03 identifies exact paths)
- `skills/iw-research/SKILL.md`
- `tests/unit/test_state_machine.py`
- `tests/unit/test_cli_core.py`
- `tests/unit/test_cli_batches.py` (if exists, otherwise add research case to existing unit coverage)
- `tests/integration/test_cli_core.py`
- `tests/integration/test_cli_batches.py`
- `tests/integration/test_doc_commands.py` (or extend existing doc-command integration test)

Reports are created during execution in `ai-dev/active/CR-00010/reports/`.

## Acceptance Criteria

### AC1: `iw approve` rejects research items

```
Given a research work item R-00001 is registered with status "draft"
When  a user runs `iw approve R-00001`
Then  the command exits non-zero
And   stderr contains "Cannot approve research items"
And   R-00001's status remains "draft"
```

### AC2: `iw unapprove` rejects research items

```
Given a research work item R-00001 exists (regardless of status)
When  a user runs `iw unapprove R-00001`
Then  the command exits non-zero
And   stderr contains "Cannot unapprove research items"
```

### AC3: `iw doc-update` auto-completes research work items

```
Given a research work item R-00001 is registered with status "draft"
When  the user runs `iw doc-update R-00001 --doc-type research --title "..." --content "..."`
Then  the command exits 0
And   the stdout JSON includes "work_item_auto_completed": true
And   R-00001's status is "completed"
And   R-00001's phase is "done"
And   R-00001's completed_at is set to a recent timestamp
```

### AC4: `iw doc-update` is idempotent on already-completed research items

```
Given a research work item R-00001 is in status "completed"
When  the user runs `iw doc-update R-00001 --doc-type research --content "..."` again
Then  the command exits 0
And   the stdout JSON includes "work_item_auto_completed": false
And   R-00001's status stays "completed"
And   no InvalidTransition exception is raised
```

### AC5: `iw doc-update` does not touch non-research work items

```
Given a feature F-00001 in status "draft" AND a doc with doc_id "F-00001" exists for the same project
When  the user runs `iw doc-update F-00001 --doc-type tech --content "..."`
Then  the command exits 0
And   the stdout JSON includes "work_item_auto_completed": false
And   F-00001's status remains "draft"
```

### AC6: `iw batch-create` rejects research items

```
Given a research work item R-00001 exists (in any status)
When  the user runs `iw batch-create R-00001 F-00002`
Then  the command exits non-zero
And   stderr contains "research item" AND "cannot be added to a batch"
And   no Batch row is created
```

### AC7: State machine allows `draft → completed` for research only

```
Given the state machine validators
When  can_transition_work_item_status(draft, completed, item_type=Research) is called
Then  it returns True
When  can_transition_work_item_status(draft, completed, item_type=Feature) is called
Then  it returns False
When  can_transition_work_item_status(draft, approved, item_type=Research) is called
Then  it returns False
When  can_transition_work_item_status(draft, approved, item_type=None) is called
Then  it returns True (backward compatibility)
```

### AC8: Dashboard hides approve/unapprove for research items

```
Given a research work item R-00001 appears on the work-item detail dashboard page
When  the page is rendered
Then  no "Approve" or "Unapprove" buttons/forms are present
And   an inline notice reads "Research items auto-complete when the research document is created"
```

### AC9: Dashboard batch-queue excludes research items

```
Given a research work item R-00001 and a feature F-00001 both exist in status "approved" (forced via DB for test purposes only; in normal operation research never reaches approved)
When  the user views the batch-queue list on the dashboard
Then  F-00001 appears in the list
And   R-00001 does NOT appear in the list
```

### AC10: Skill documents the new flow

```
Given skills/iw-research/SKILL.md Step 6
When  a reader reads the instructions
Then  Step 6 does NOT instruct the user to run "iw approve"
And   Step 6 states that "iw doc-update" auto-transitions the work item to "completed"
```

## Rollback Plan

- **Database**: Not applicable. No schema changes.
- **Code**: Revert the merge commit. The change is isolated to `orch/daemon/state_machine.py`, `orch/cli/{item,doc,batch}_commands.py`, `dashboard/routers/{actions,project_pages}.py`, `dashboard/templates/**`, `skills/iw-research/SKILL.md`, and their tests. Reverting restores the old single-table state machine and unguarded CLI commands.
- **Data**: No data loss on rollback. Any research items completed via the new auto-flow will remain in `completed` state after rollback — the old state machine has `completed → {}` (terminal), so no legacy transition is broken. Users would, post-rollback, need to manually `iw approve` new research items again — inconvenient but non-destructive.

## Dependencies

- **Depends on**: None (CR is self-contained — research type was introduced by earlier work; this CR refines its lifecycle)
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_state_machine.py`: parameterized tests for `can_transition_work_item_status` covering (a) research: `draft → completed` pass, (b) research: `draft → approved`, `draft → in_progress` fail, (c) non-research: current table unchanged, (d) `item_type=None`: current table unchanged (backward compat).
  - `test_cli_core.py`: `validate_approve_transition(draft, Research)` returns the rejection message; `validate_approve_transition(draft, Feature)` returns `None`; same pattern for `validate_unapprove_transition`.
  - `test_cli_batches.py` (new or extended): pure-function test for the research-exclusion guard if one is factored out; otherwise covered only in integration.
- **Integration tests** (`tests/integration/`):
  - `test_cli_core.py` (or a new `test_research_flow.py`): register a research item → `iw approve` errors → `iw doc-update` succeeds → work item is `completed`. Cover AC1, AC3, AC4 in sequence.
  - `test_cli_core.py`: `iw unapprove` on a research item errors (AC2).
  - `test_doc_commands.py`: verify `iw doc-update` for a non-research work item with matching ID does NOT auto-complete (AC5).
  - `test_cli_batches.py`: `iw batch-create` rejects a research item with the correct error message and exit code (AC6).
  - Dashboard template / route test (under `tests/integration/` if dashboard integration tests exist, otherwise a unit test on the query helper): confirm research items are excluded from the batch-queue query (AC9).
- **Updated tests**: any test in `tests/unit/test_state_machine.py` or `tests/unit/test_cli_core.py` that currently asserts research items must go through the `approved` state needs its fixture/parameter updated to expect the new behavior. The tests-impl agent is responsible for finding and updating them.

## Notes

- **Why type-aware validators instead of a new "auto-complete" status**: the cleanest fix is to let the state machine express "research has its own lifecycle" rather than shoehorning research into the generic table. Adding a new `WorkItemStatus` value (e.g., `auto_completed`) would bloat the enum and require a DB migration for no semantic gain — `completed` already means "work is done"; research just takes a shortcut.
- **Why auto-complete triggers on `doc-update` (not on a dedicated `iw research-done` command)**: the trigger should match the *user's* mental model. Users don't think "I'm done researching"; they think "I wrote the document." `doc-update` IS the document-creation moment. Dedicated commands add ceremony without benefit.
- **Why idempotent on already-complete**: the `iw-research` skill may re-run `doc-update` to refine content; the work item transition should fire exactly once and subsequent calls should be silent no-ops.
- **Why exclude research from batches via backend filter AND frontend check AND CLI guard**: defense in depth. The CLI guard is the contract. The backend query filter prevents the dashboard from even offering research items as batch candidates. The frontend filter would be redundant once the backend filter lands; the frontend responsibility is the approve/unapprove button hiding, not the batch-queue list (that's backend).
- **Risk — `doc_id` collision across types**: if a user registers a non-research work item (e.g., `F-00001`) AND a non-research doc with the same `doc_id == F-00001`, the new `doc-update` logic must NOT touch the work item because the doc's `doc_type` is not `research`. The guard is: `doc.doc_type == DocType.research AND work_item.item_type == WorkItemType.Research`. Both checks are required.
- **Risk — dashboard template divergence**: the approve/unapprove UI may appear in multiple templates (item detail, list views, context menus). S03 must `grep` for every approve action form and audit each.
- **Risk — existing tests asserting the old flow**: the research type was introduced recently. S05 MUST run the full suite and fix every test that expects research items to go through `approved`. Do not skip tests; update them.
- **Out of scope**: changing the flow for features, incidents, or other change requests. Changes to `iw-research-quick` (it doesn't create work items). Dashboard visual redesign.
