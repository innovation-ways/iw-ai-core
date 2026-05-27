# I-00115 S01 Frontend Report

## What was done
- Fixed `dashboard/templates/components/scope_amend_modal.html` so all dismissal paths remove both `#scope-amend-modal` and `#scope-amend-overlay`.
- Added inline form hook per requirement:
  - `hx-on::after-request="..."` on the `<form>`.
  - Teardown runs only on successful htmx responses (`event.detail.successful`), preserving retry-on-error behavior.
- Replaced broken × close behavior with shared dismissal helper (`window.dismissScopeAmendModal()`).
- Re-pointed Cancel button to the same shared dismissal helper.
- Added ESC-to-dismiss and backdrop-click-to-dismiss in a small inline `<script>` block.
- Added listener cleanup to prevent leaks across modal reopens:
  - `document` keydown listener and overlay click listener are both detached on dismissal.

## Files changed
- `dashboard/templates/components/scope_amend_modal.html`

## Test results
- Baseline (before edit):
  - `uv run pytest tests/dashboard/ -k "scope_amend" -v` → `0 selected, 0 failed` (all deselected; no regressions present)
- After edit:
  - `uv run pytest tests/dashboard/ -k "scope_amend" -v` → `0 selected, 0 failed`
  - `uv run pytest tests/integration/test_scope_amend_endpoints.py -v` → `10 passed, 0 failed`
- Preflight gates:
  - `make format` → ok
  - `make type-check` → ok
  - `make lint` → ok

## Notes
- Chosen idiom:
  - Form success teardown uses required inline `hx-on::after-request` attribute.
  - Other dismissals use one shared helper in a small template-local `<script>` block for minimal, consistent wiring.
- Toast behavior is preserved (server 204 + `HX-Trigger: showToast`; no router changes).
