# F-00082: Dashboard Cancel Buttons (Batch + Work Item)

**Type**: Feature
**Priority**: High
**Created**: 2026-05-14
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. No `docker` / `docker compose` invocations from dashboard
routes, tests, or fixtures. Testcontainer fixtures used by integration tests
are exempt. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Leaves migrations **unchanged**. No schema changes — this Feature is a pure
API + Frontend wrap of `orch/cancel.py` (already shipped before F-00082).

## Description

Wire the existing `orch.cancel.cancel_batch` / `orch.cancel.cancel_work_item`
service-layer primitives — and their `iw batch-cancel` / `iw item-cancel`
CLI counterparts — into the FastAPI dashboard so an operator can cancel a
runaway batch or work item directly in the UI, with full per-item teardown
(SIGTERM to running step PIDs, `worktree_compose down`, `git worktree
remove`) instead of the current shallow status-bit flip. The two existing
endpoints (`POST /project/{p}/api/item/{id}/cancel` and `POST
/project/{p}/api/batch/{id}/cancel` in `dashboard/routers/actions.py`)
predate the service layer; they are **rewritten**, not duplicated, so the
dashboard and CLI share one cancellation contract.

## Project Context

Read the project's `CLAUDE.md` (root, `dashboard/`, `orch/`) for
architecture, conventions, and hard rules. Key constraints for this
Feature:

- Dashboard pattern: FastAPI + Jinja2 + htmx + Tailwind (prebuilt via
  `make css`). Routers are **thin**: validate, delegate to `orch/`, render
  fragment.
- The existing `confirm_dialog` macro at
  `dashboard/templates/components/confirm_dialog.html` is the shared shell
  for destructive confirms; the cancel modals extend it.
- `dependencies.py:get_db()` yields the same sync ORM session daemon uses
  — no mocking allowed in integration tests (R3).
- Service-layer contract is locked in by F-00082's predecessor work
  (`orch/cancel.py`): cancel_batch raises `LookupError` (→ 404),
  `ValueError` (→ 422 / 409 depending on the message). The dashboard must
  surface both as toasts without crashing.

## Scope

### In Scope

- Rewrite `POST /project/{project_id}/api/item/{item_id}/cancel` to
  delegate to `orch.cancel.cancel_work_item`, accept optional `reason`
  and `to_draft` form fields, and surface `teardown_errors` in the
  toast.
- Rewrite `POST /project/{project_id}/api/batch/{batch_id}/cancel` to
  delegate to `orch.cancel.cancel_batch`, accept optional `reason` and
  `reset_items` form fields, and surface `teardown_errors` in the
  toast.
- Add an enriched confirm-dialog GET endpoint that returns a form-bearing
  modal for cancel actions (textarea for reason + checkbox for the
  reset/to-draft flag), using a new `confirm_action_form.html` fragment
  that reuses the existing `confirm_dialog` shell.
- Update `_ACTION_LABELS` for both `cancel` entries with destructive copy
  consistent with the service layer (mention worktree teardown).
- Expand cancel-button visibility in
  `dashboard/templates/fragments/batch_detail_header.html` to every
  cancellable batch status (`planning, approved, executing, paused,
  blocked, publish_failed`). Hide on terminal/published/archived.
- Add a cancel button to
  `dashboard/templates/pages/project/item_detail.html` (header area)
  visible only when the item is cancellable AND not in an active batch.
  When the item *is* in an active batch, render a disabled button with a
  hint "Belongs to active batch <BATCH-ID> — cancel the batch instead"
  that links to the batch detail page.
- Add a per-row "Cancel" icon-button to
  `dashboard/templates/pages/project/batches.html` for batches in
  cancellable statuses. Uses the browser's native `confirm()` dialog and
  POSTs with default reason (no `--reset-items`).
- Regenerate `dashboard/static/styles.css` via `make css` so any new
  Tailwind classes are JIT-purged correctly.
- Add new dashboard tests covering the rewritten endpoints, the new
  confirm-dialog form behaviour, and the disabled-with-hint state.
- Update `dashboard/CLAUDE.md` so the routers table reflects the
  rewritten endpoints (no new bullet — the existing entry already
  mentions "cancel"; only the description copy changes).

### Out of Scope

- **Operator capture**. `DaemonEvent.event_metadata` stays as-is; the
  service layer is the single source of truth. A follow-up CR adds an
  optional `operator` field (header / cookie) when dashboard auth lands.
  Filed as the design's first follow-up CR placeholder in §Notes.
- **Cancellation from the jobs/events page**. The cancel buttons are
  surfaced on batch and item pages only; the events feed continues to be
  read-only and merely shows the resulting `batch_cancelled` /
  `item_cancelled` events.
- **Backend logic changes**. `orch/cancel.py` already shipped and is
  frozen for this Feature; F-00082 only consumes it. Any service-layer
  bug surfaced during S01/S03 development is filed as a separate
  Incident, not patched in F-00082.
- **Removing the existing `cancel` button from `queue.html`**. Queue
  page's per-row cancel for draft/approved items is unchanged; the new
  service-layer call simply tolerates those statuses transparently.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | API (`api-impl`) | Rewrite the two cancel POST endpoints to call `orch.cancel.*`; add form parsing for `reason` / `to_draft` / `reset_items`; extend confirm-dialog GET to return form-bearing modal for cancel actions; update `_ACTION_LABELS`. | — |
| S02 | CodeReview (`code-review-impl`) | Review S01 endpoint contracts, form parsing, error mapping (LookupError→404, ValueError→422), service-layer call sites. | — |
| S03 | Frontend (`frontend-impl`) | Extend `components/confirm_dialog.html` to support an optional form slot; add `confirm_action_form.html` fragment for cancel with reason/reset fields; expand cancel button visibility in batch and item headers; add per-row quick-cancel in `batches.html`; run `make css`. | — |
| S04 | CodeReview (`code-review-impl`) | Review S03 templates: visibility rules match service-layer allowed sets; htmx targets correct; no dynamic Tailwind class construction. | — |
| S05 | Tests (`tests-impl`) | Add `tests/dashboard/test_actions_cancel_batch.py` and `tests/dashboard/test_actions_cancel_item.py` covering all ACs + Boundary Behavior rows. | — |
| S06 | CodeReviewFinal (`code-review-final-impl`) | Cross-cutting review: API ⇆ Frontend contract; service-layer integration; every AC/Invariant covered by tests. | — |
| S07 | QvGate | `make lint` | — |
| S08 | QvGate | `make format-check` | — |
| S09 | QvGate | `make type-check` | — |
| S10 | QvGate | `make arch-check` | — |
| S11 | QvGate | `make security-sast` | — |
| S12 | QvGate | `make test-unit` | — |
| S13 | QvGate | `make test-frontend` (dashboard tests via TestClient) | — |
| S14 | QvGate | `make allure-integration` (timeout 900s) | — |
| S15 | QvBrowser (`qv-browser`) | Drive cancel buttons end-to-end via `playwright-cli` against the worktree e2e stack. Verify the form-bearing modal, the disabled-with-hint state, and the resulting toast/audit event. | — |
| S16 | SelfAssess (`self-assess-impl`) | Standard `iw-item-analyze` self-assessment. | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no schema changes.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/api/confirm-item/cancel/{item_id}` — (already exists in route table; behaviour updated to return form-bearing modal for cancel action specifically. The GET URL is unchanged so existing `queue.html` links keep working.)
  - `GET /project/{project_id}/api/confirm-batch/cancel/{batch_id}` — (same: behaviour updated for cancel action.)
- **Modified endpoints**:
  - `POST /project/{project_id}/api/item/{item_id}/cancel` — now reads `reason` and `to_draft` form params, delegates to `orch.cancel.cancel_work_item`, returns toast with `teardown_errors` warnings.
  - `POST /project/{project_id}/api/batch/{batch_id}/cancel` — now reads `reason` and `reset_items` form params, delegates to `orch.cancel.cancel_batch`, returns toast with summary (cancelled items, reset list, killed PIDs, teardown errors).

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/confirm_action_form.html` — form-bearing variant of confirm dialog (textarea + optional checkbox).
- **Modified components**:
  - `dashboard/templates/components/confirm_dialog.html` — optional `form_html` parameter for embedding a `<form>` element with named fields.
  - `dashboard/templates/fragments/batch_detail_header.html` — cancel button visible on all cancellable batch statuses.
  - `dashboard/templates/pages/project/item_detail.html` — cancel button + disabled-with-hint state.
  - `dashboard/templates/pages/project/batches.html` — per-row quick-cancel icon-button.

## File Manifest

All files for this work item live under `ai-dev/active/F-00082/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00082_Feature_Design.md` | Design | This document |
| `F-00082_Functional.md` | Design | Human-facing summary (Why / What Changed / How / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00082_S01_API_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/F-00082_S02_CodeReview_prompt.md` | Prompt | S02 review checklist |
| `prompts/F-00082_S03_Frontend_prompt.md` | Prompt | S03 implementation instructions |
| `prompts/F-00082_S04_CodeReview_prompt.md` | Prompt | S04 review checklist |
| `prompts/F-00082_S05_Tests_prompt.md` | Prompt | S05 test plan |
| `prompts/F-00082_S06_CodeReview_Final_prompt.md` | Prompt | S06 global review |
| `prompts/F-00082_S15_BrowserVerification_prompt.md` | Prompt | S15 qv-browser script |
| `prompts/F-00082_S16_SelfAssess_prompt.md` | Prompt | S16 self-assessment |

Reports are created during execution in `ai-dev/active/F-00082/reports/`.

## Acceptance Criteria

### AC1: Cancel an executing batch from the detail page resets every step

```
Given a batch in 'executing' status with one BatchItem in 'executing'
  and a WorkItem with WorkflowSteps in mixed (in_progress, pending) states
When the operator opens the batch detail page, clicks "Cancel Batch",
  types "redesign" as the reason, ticks "Also reset items to draft",
  and confirms
Then the POST /api/batch/<id>/cancel endpoint is called with
       reason="redesign", reset_items=true
  and orch.cancel.cancel_batch is invoked
  and the batch status becomes 'cancelled'
  and the BatchItem status becomes 'skipped'
  and the WorkItem status becomes 'draft'
  and every WorkflowStep is reset to 'pending'
  and a 'batch_cancelled' DaemonEvent is recorded with the reason
  and the toast renders "Cancelled BATCH-<id> (redesign)" plus a "Reset to draft" line
```

### AC2: Cancel an in-progress work item not in an active batch

```
Given a WorkItem in 'in_progress' status with no row in any non-terminal Batch
When the operator opens the item detail page, clicks "Cancel Item",
  leaves the reason as the default, and confirms
Then the POST /api/item/<id>/cancel endpoint is called
  and orch.cancel.cancel_work_item is invoked
  and the WorkItem status becomes 'cancelled'
  and pending/in-progress WorkflowSteps are marked 'skipped'
  and a 'item_cancelled' DaemonEvent is recorded
  and the toast renders "Cancelled <id> (cancelled by operator)"
```

### AC3: Item-cancel refused when item is in an active batch (UI + API mirror)

```
Given a WorkItem in 'in_progress' status whose only Batch row is in 'executing'
When the operator opens the item detail page
Then the Cancel button is rendered DISABLED with a hint
  "Belongs to active batch BATCH-XXXXX — cancel the batch instead"
  linking to /project/<p>/batch/BATCH-XXXXX
And When the operator POSTs to /api/item/<id>/cancel directly (curl/bypass)
Then the endpoint returns 409 with detail containing "active batch" and the batch ID
  and the WorkItem state is unchanged
```

### AC4: Quick-cancel from the batches list uses default reason, no reset

```
Given a batches list page with one batch in 'paused' status
When the operator clicks the row's "Cancel" icon-button
  and accepts the native browser confirm()
Then the POST /api/batch/<id>/cancel endpoint is called
  with reason="cancelled from batches list" and reset_items=false
  and the row updates in place (htmx swap) to show status='cancelled'
```

### AC5: Cancel button hidden / endpoint refuses for terminal batches

```
Given a batch in 'completed' status (or completed_with_errors / publishing /
  published / archived / cancelled)
When the operator views the batch detail page
Then no Cancel Batch button is rendered
And When the operator POSTs to /api/batch/<id>/cancel directly
Then the endpoint returns 422 with detail containing "Cannot cancel batch"
  and the batch status is unchanged
```

### AC6: Teardown errors surface as warning toasts but do not block the cancel

```
Given a batch where worktree_compose.down raises a subprocess error
  (e.g., docker daemon down)
When the operator clicks "Cancel Batch" and confirms
Then orch.cancel.cancel_batch still completes the DB transition successfully
  and the response toast carries a separate warning line listing the
    teardown_errors values
  and the batch status is 'cancelled' (HTTP 200, not 500)
```

## Boundary Behavior

Every row is a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty reason field | Form submitted with `reason=""` | Service-layer default ("cancelled by operator") is used; reason captured in DaemonEvent metadata is the default string |
| Reason with leading/trailing whitespace | `reason="  redesign  "` | Service layer strips and persists `"redesign"` (`.strip()` already applied in `orch/cancel.py:359`) |
| Unknown batch ID | `POST /api/batch/BATCH-99999/cancel` | Returns 404, toast renders `"Batch BATCH-99999 not found"` |
| Unknown item ID | `POST /api/item/X-99999/cancel` | Returns 404, toast renders `"Work item X-99999 not found in project <p>"` |
| Cancel button on draft batch | Batch status `planning` | Button visible; POST allowed; batch transitions `planning → cancelled` |
| Cancel button on paused batch | Batch status `paused` | Button visible (the BATCH-00096 case); POST allowed |
| Cancel button on cancelled batch | Batch status `cancelled` | Button hidden in templates; direct POST returns 422 |
| Item in cancelled batch | WorkItem `in_progress`, Batch `cancelled` | Item-cancel button visible (active-batch gate clears on terminal batches); POST allowed |
| `to_draft=true` on draft item | WorkItem already `draft` | Service layer refuses with `"Cannot cancel work item: current status is 'draft'"` → 422; no DB write |
| Confirm modal closed without submitting | Operator clicks the modal backdrop | Modal closes; no POST issued; state unchanged |

## Invariants

Conditions that **must hold** after implementation. Each maps to a test.

1. **One contract.** The dashboard cancel endpoints call `orch.cancel.cancel_batch` / `orch.cancel.cancel_work_item` — they do NOT manipulate `BatchStatus` / `WorkItemStatus` directly. (Test: monkey-patch `orch.cancel.cancel_*`, verify it's called with the parsed form params.)
2. **Visibility ⇔ allowed-from set.** Every batch status in `orch.cancel.CANCELLABLE_BATCH_STATUSES` renders a cancel button; every status outside it does not. Same for work items vs. `CANCELLABLE_WORK_ITEM_STATUSES`. (Test: parametrised over the full enum.)
3. **In-active-batch gate mirrors the service layer.** The item detail template renders the disabled button + hint **iff** `orch.cancel._ACTIVE_BATCH_STATUSES` contains the parent batch's status. (Test: parametrised over batch status values; UI never shows a clickable button that the API would reject with exit 4 / HTTP 422.)
4. **Teardown errors never break the response.** `cancel_batch` raising no DB exception always yields HTTP 200; only `LookupError` / `ValueError` from the service layer map to non-2xx. (Test: monkey-patch the service to return a `CancelResult` with `teardown_errors=["compose down failed"]`; assert 200 + warning toast text.)
5. **No new orchestration logic.** The dashboard touches only `orch.cancel` and the existing `orch.db.models` enums; no `BatchStatus.X.value` literals or step-status flips. (Test: ruff/import scan in dashboard/routers/actions.py for the two endpoints.)
6. **Tailwind purge stays green.** Any new Tailwind class introduced in templates appears in `dashboard/static/styles.css` after `make css`. (Test: dashboard test_styles_present pattern — checks the generated CSS contains the new class names.)

## Dependencies

- **Depends on**: `orch/cancel.py` (already merged) — the service-layer module this Feature wraps. No new design dependency since the predecessor is on `main` at the time of this Feature's design.
- **Blocks**: None.

## Impacted Paths

- `dashboard/routers/actions.py`
- `dashboard/routers/items.py`
- `dashboard/templates/components/confirm_dialog.html`
- `dashboard/templates/fragments/confirm_action_form.html`
- `dashboard/templates/fragments/batch_detail_header.html`
- `dashboard/templates/pages/project/item_detail.html`
- `dashboard/templates/pages/project/batches.html`
- `dashboard/templates/pages/project/queue.html`
- `dashboard/static/styles.css`
- `dashboard/CLAUDE.md`
- `tests/dashboard/test_actions_cancel_batch.py`
- `tests/dashboard/test_actions_cancel_item.py`
- `tests/dashboard/test_cancel_confirm_dialog.py`
- `tests/dashboard/test_cancel_button_visibility.py`
- `tests/dashboard/test_confirm_dialog_form.py`
- `ai-dev/active/F-00082/**`
- `ai-dev/archive/F-00082/**`

## TDD Approach

- **Unit tests** (no DB): pure validators are already covered in `tests/unit/test_cancel_validators.py` (shipped with the predecessor). For F-00082 add **template helper unit tests** if any non-trivial logic lands in a Python helper (e.g., a `_format_teardown_toast` function); keep helpers small enough not to need them.
- **Dashboard tests** (`tests/dashboard/` — FastAPI TestClient + testcontainer-backed `db_session`):
  - Form-bearing confirm-dialog GET returns a `<form method="post">` with `name="reason"` textarea and the right checkbox name.
  - POST with form params calls `orch.cancel.cancel_batch` / `cancel_work_item` with the correct kwargs (monkey-patch + record call).
  - Each row of Boundary Behavior table → one TestClient test.
  - Each Invariant → one test (parametrised where appropriate over the enum).
  - Item detail rendering: in-active-batch state produces the disabled button + hint anchor; out-of-batch state produces an enabled htmx-triggering button.
  - Batches list rendering: per-row quick-cancel button rendered only for batches in `CANCELLABLE_BATCH_STATUSES`.
- **Edge cases**: empty reason, whitespace reason, unknown ID (404), teardown_errors propagation, terminal-batch refusal, in-active-batch refusal at both UI and API layers.
- **Browser verification (S15)**: confirms the htmx swap actually updates the DOM, the modal renders the form, the toast appears, and the daemon-events feed receives the new event.

## Notes

- **The BATCH-00096 / CR-00049 incident** (2026-05-13) motivated this Feature.
  An agent crashed mid-step on a paused batch; the existing dashboard cancel
  could not address it because it only allowed `planning → cancelled` and
  did nothing about the per-item worktree/compose state. The operator
  had to drop to the CLI to run `iw batch-cancel --reset-items`. After
  F-00082 the same scenario is one click on the batch detail page.

- **Follow-up CR placeholder — operator capture.** A future CR adds an
  optional `operator` field to `DaemonEvent.event_metadata`, sourced from
  a request header or cookie, defaulting to `"dashboard-user"`. Deferred
  until dashboard auth lands so the value is meaningful.

- **Follow-up CR placeholder — events-page surfacing.** A future CR can
  surface the new `batch_cancelled` / `item_cancelled` events as actionable
  rows in the events feed (e.g., a "View affected items" link). Not in
  scope for F-00082.

- **Risk: form-bearing modal regression for other actions.** The
  `confirm_dialog` component currently powers approve/pause/resume/kill
  flows too. The new `form_html` parameter MUST default to empty so
  existing call sites are byte-identical after the extension. S04 review
  step is explicit about this.

- **Risk: htmx swap of toast may race with htmx swap of row.** The two
  POST endpoints return a toast fragment, but the batches-list row also
  needs to refresh. Pattern: response carries an `HX-Trigger:
  refreshBatchRow` header so the row listener re-fetches. S03 + S04
  validate this.
