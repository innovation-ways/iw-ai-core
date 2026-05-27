# I-00115 S03 Tests Report

## What was done
- Added new dashboard test module `tests/dashboard/test_scope_amend_modal_i00115.py`.
- Implemented 5 required tests (2 repro + 3 regression) against `GET /project/{id}/api/item/{item_id}/scope/amend-modal/{step_id}` rendered HTML.
- Reused TestClient + DB seed pattern from `tests/integration/test_scope_amend_endpoints.py` (project/work-item/step + StepRun + escalated FixCycle with `scope_violations`).
- Collected RED-phase evidence by inspecting template history/diff (no checkout/stash rollback).

## Files changed
- `tests/dashboard/test_scope_amend_modal_i00115.py`
- `ai-dev/active/I-00115/reports/I-00115_S03_Tests_report.md`

## Test results
- `uv run pytest tests/dashboard/test_scope_amend_modal_i00115.py -v` → **5 passed, 0 failed**

## Preflight
- `make format` → fixed (ran `uv run ruff format tests/dashboard/test_scope_amend_modal_i00115.py` then `make format` passed)
- `make type-check` → ok
- `make lint` → ok

## RED evidence (pre-S01 reasoning)
- `test_i00115_modal_submit_form_wires_cleanup_hook`: pre-S01 `<form ... hx-post=".../scope/amend-and-restart/...">` had no teardown hook and no references to `scope-amend-modal` / `scope-amend-overlay` in the open tag (diff hunk at form lines ~38-41) → assertion would fail.
- `test_i00115_modal_close_button_uses_getelementbyid_for_overlay`: pre-S01 close button contained literal `this.closest('#scope-amend-overlay')` (diff line replacing old onclick at ~19-23) → `not in html` assertion would fail.
- `test_i00115_modal_esc_key_dismisses`: pre-S01 had no Escape handler and no keydown listener script block (script block is entirely added in diff tail) → assertion would fail.
- `test_i00115_modal_backdrop_click_dismisses`: pre-S01 overlay had no click handler and no overlay listener guard (`event.target === overlay`) (added in new script block) → assertion would fail.
- `test_i00115_cancel_button_still_works`: pre-S01 cancel used direct `document.getElementById(...)` removals for both modal and overlay (already correct); this remains a regression guard.

## Notes
- S01 chose mixed idiom: form cleanup uses `hx-on::after-request`; other dismissal paths use a shared `<script>` helper (`window.dismissScopeAmendModal`).
- Assertions are written to tolerate this approach while still requiring both modal + overlay teardown semantics.
