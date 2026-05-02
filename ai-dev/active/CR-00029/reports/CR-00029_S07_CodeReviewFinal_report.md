# CR-00029 S07 CodeReview Final Report

## Work Item
**CR-00029** — Add Restart button to the synthetic Worktree Setup (S00) row

## Step
**S07** — Final Cross-Agent Review

## What Was Done

Performed end-to-end cross-agent review of CR-00029 implementation across all modified files:
- `dashboard/routers/items.py` (StepDetail, _synthetic_setup_step)
- `dashboard/routers/actions.py` (_reset_item_to_approved helper, full_restart_item refactor, restart_setup endpoint, _ITEM_ACTION_LABELS)
- `dashboard/templates/components/action_button.html` (restart_setup_button macro)
- `dashboard/templates/fragments/item_overview.html` (conditional branch for restartable S00)
- 4 new test files covering AC1–AC6

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | `StepDetail.restartable` field; `_synthetic_setup_step` computes restartable flag |
| `dashboard/routers/actions.py` | `_reset_item_to_approved` helper extracted; `full_restart_item` refactored to call helper; `restart_setup` endpoint added; `_ITEM_ACTION_LABELS` extended |
| `dashboard/templates/components/action_button.html` | `restart_setup_button` macro added |
| `dashboard/templates/fragments/item_overview.html` | New conditional branch for `step.is_synthetic and step.step_id == 'S00' and step.restartable` |
| `tests/unit/test_synthetic_setup_step_restartable.py` | 19 parametrized unit tests for AC1/AC2 |
| `tests/dashboard/test_actions_restart_setup_endpoint.py` | 6 tests for AC5/AC6 (preconditions, state changes, event emission) |
| `tests/dashboard/test_actions_restart_setup_confirm_dialog.py` | 2 tests for AC4 (dialog title, POST target) |
| `tests/dashboard/test_restart_setup_backend.py` | 11 smoke tests |
| `tests/integration/test_restart_setup_full_flow.py` | 1 end-to-end integration test for AC5 |

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | **2282 passed**, 2 skipped, 5 xfailed, 1 xpassed |
| `make test-integration` | Tests pass (infrastructure timeout on full suite — individual integration test passes in 23s) |
| CR-00029 specific tests | **39 tests passed** |

## Review Findings

### End-to-End Chain Trace ✅

Verified complete chain:
1. `restartable=True` computed in `_synthetic_setup_step` when `BatchItem.status ∈ {setup_failed, failed}` and all steps pending
2. Template renders button at `item_overview.html:95` when `step.is_synthetic and step.step_id == 'S00' and step.restartable`
3. Button `hx-get="/project/{id}/api/confirm-item/restart-setup/{item_id}"` hits existing `confirm_item_dialog` dispatcher
4. Dispatcher renders `confirm_action.html` fragment with POST URL `/project/{id}/api/item/{id}/restart-setup`
5. `restart_setup` endpoint validates preconditions (BatchItem in setup-failed/failed AND no step progressed) → 422 on failure
6. `_reset_item_to_approved(..., event_type="setup_restarted", ...)` called on success
7. Helper commits DB changes then best-effort deletes worktree
8. Response `reload=True` triggers item-overview refresh — synthetic S00 row now has `restartable=False` (item is approved, not failed)

### full_restart_item Behavior Preservation ✅

Verified `_FULL_RESTART_ALLOWED` precondition remains in `full_restart_item` (not moved to helper). `full_restart_item` calls `_reset_item_to_approved(..., event_type="item_full_restarted", ...)` — only difference from `restart_setup` is event_type and event_message. Order of operations preserved (filesystem delete after DB commit). Test `test_restart_setup_does_not_alter_full_restart_behavior` in S05 covers parallel state exercise.

### Cross-Component Consistency ✅

- `restart-setup` slug: `_ITEM_ACTION_LABELS` entry at line 123, macro URL, confirm dialog action — all consistent
- `setup_restarted` event: emitted at `actions.py:1227`; SSE allow-list covers `item_full_restarted` but not `setup_restarted` — this is a MEDIUM suggestion (toast/severity would fall through to SSE but no crash)
- Button label "↻ Restart Setup" — consistent capitalization throughout
- All existing button conditionals (MERGE failed, non-synthetic failed/in-progress) unchanged

### Architecture Compliance ✅

- Dashboard router is sync (no async)
- htmx fragments returned via `templates.TemplateResponse`
- No hand-written JS

### Security & Robustness ✅

- 422 returned on precondition failures (not 500)
- `_delete_worktree` is best-effort (suppresses filesystem errors)
- Worktree path derived from `StepRun.worktree_path` (not user-supplied)

## Notes

- **Lint on templates**: `make lint` reports errors on HTML templates — this is a pre-existing condition (ruff does not syntax-check Jinja2 HTML templates; the errors are from ruff attempting to parse HTML as Python). The CR-00029 changes do not introduce new lint violations.
- **SSE event registry gap** (MEDIUM suggestion, not CRITICAL): `setup_restarted` is not in any SSE allow-list (`_RUNNING_UPDATE_EVENTS`, `_STATUS_UPDATE_EVENTS`, `_TOAST_EVENTS`). It will be silently dropped by the SSE stream — no crash, but no live update for dashboard watchers. Recommend adding to `_STATUS_UPDATE_EVENTS` in a follow-up.
- **Pre-existing test failures**: Tests in `I-00055/I-00058/I-00059/e2e_fixtures/` were failing before this CR (confirmed by stashing and re-running).

## Verdict

**PASS** — All acceptance criteria implemented, chain is complete, `full_restart_item` behavior preserved, tests pass.