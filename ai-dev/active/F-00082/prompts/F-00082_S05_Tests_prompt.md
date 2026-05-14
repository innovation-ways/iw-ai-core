# F-00082_S05_Tests_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step**: S05
**Agent**: Tests (`tests-impl`)

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures via pytest are allowed.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md` (read §Acceptance Criteria, §Boundary Behavior, §Invariants in full — every row / item maps to ≥1 test).
- S01–S04 reports.
- Implementation files from S01/S03 reports' `files_changed`.
- Existing test patterns: `tests/dashboard/test_*.py` (especially `tests/dashboard/test_batches_progress_parity.py`, `tests/dashboard/test_batch_detail_auto_merge_toggle.py`).
- `tests/CLAUDE.md` + `skills/iw-ai-core-testing/SKILL.md` — MUST read before writing tests.

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S05_Tests_report.md`.
- Tests under `tests/dashboard/`:
  - `tests/dashboard/test_actions_cancel_batch.py` (expand S01 anchors).
  - `tests/dashboard/test_actions_cancel_item.py` (expand S01 anchors).
  - `tests/dashboard/test_cancel_confirm_dialog.py` (new — covers the form-bearing modal + macro byte-equivalence).
  - `tests/dashboard/test_cancel_button_visibility.py` (new — parametrised over batch/item statuses).

## Context

You are expanding the test suite so every Acceptance Criterion, Invariant, and Boundary Behavior row of F-00082 is covered. Read `tests/CLAUDE.md` first — assertions must fail when the production code regresses (the mutation-test question). Use testcontainer-backed `db_session` for DB integration; monkey-patch `orch.cancel.cancel_*` only where the test is verifying the **router contract**, not the cancellation behaviour itself (the latter is already covered by `tests/integration/test_cli_cancel.py`).

## Requirements

### 1. Coverage matrix — every row in the design must have ≥1 test

For each AC (1–6) in the design doc, write one TestClient test that exercises the end-to-end path:

- AC1: `test_batch_cancel_executing_with_reset_items_resets_steps_and_returns_toast`. Use a real `db_session`, real `cancel_batch` (no mock). Set up a batch with mixed step states; POST with form data; assert DB state matches and response body contains the toast text the user will see.
- AC2: `test_item_cancel_standalone_in_progress_marks_steps_skipped`.
- AC3: `test_item_cancel_disabled_with_hint_when_in_active_batch` (template assertion) + `test_post_item_cancel_returns_409_when_in_active_batch` (direct POST bypass).
- AC4: `test_quick_cancel_from_batches_list_posts_default_reason` — render the list, find the button, POST with the values, assert.
- AC5: `test_cancel_button_hidden_for_terminal_batch` (template) + `test_post_cancel_batch_returns_422_for_completed_batch` (direct POST).
- AC6: `test_teardown_errors_surface_as_warnings_but_return_200` — monkey-patch `orch.cancel.cancel_batch` to return a `CancelResult` with `teardown_errors=["compose down failed"]`; assert status_code == 200 and the toast text contains the warning.

For each Boundary Behavior row, write one test. Some overlap with the ACs above — that's fine; do not duplicate but ensure each row is touched. The new rows (`empty reason`, `whitespace reason`, `unknown batch ID`, `unknown item ID`, `cancel button on paused batch`, `cancel button on cancelled batch`, `to_draft=true on draft item`, `modal closed without submitting`) each become a discrete test.

For each Invariant (1–6), write one assertion test:

- Invariant 1: `test_handler_calls_service_layer_with_exact_kwargs` (S01 already wrote this; re-check it covers both item and batch).
- Invariant 2: `test_cancel_button_visibility_parametrised_over_batch_status`, `test_cancel_button_visibility_parametrised_over_item_status` — `@pytest.mark.parametrize` over every enum value; assert button presence matches the service-layer constant.
- Invariant 3: `test_disabled_hint_visibility_parametrised_over_parent_batch_status`.
- Invariant 4: covered by AC6.
- Invariant 5: `test_handler_does_not_import_or_set_status_enums` — open `dashboard/routers/actions.py`, grep the two cancel handler bodies for `BatchStatus.` / `WorkItemStatus.` / `BatchItemStatus.` assignments. Zero matches.
- Invariant 6: `test_styles_css_contains_new_classes` — read `dashboard/static/styles.css`, assert it contains the Tailwind classes introduced for the new form (e.g., the textarea class set). (Skip-gracefully if the project is configured to skip Tailwind in CI; check existing tests for the same skip pattern.)

### 2. Form-bearing modal tests

In `test_cancel_confirm_dialog.py`:

- `test_confirm_dialog_get_for_cancel_action_renders_form` — GET `/api/confirm-batch/cancel/{batch_id}`; assert response HTML contains `<textarea name="reason">` and `<input type="checkbox" name="reset_items">`.
- `test_confirm_dialog_get_for_non_cancel_action_does_not_render_form` — GET `/api/confirm-batch/approve/{batch_id}`; assert NO `<textarea>` and the response equals the pre-F-00082 approve-confirm bytes (snapshot or substring assertion).
- `test_form_html_default_empty_preserves_existing_macro_output` — direct macro render via Jinja2 environment; compare with golden string.

### 3. Use the testcontainer DB pattern

Fixtures from `tests/integration/conftest.py` (`db_session`, `cli_get_session`, `test_project`) and `tests/conftest.py` (`pg_engine`, etc.). For TestClient tests against the dashboard:

```python
from fastapi.testclient import TestClient
from dashboard.app import create_app
from dashboard.dependencies import get_db

app = create_app()
app.dependency_overrides[get_db] = lambda: db_session
client = TestClient(app)
```

Match the pattern in `tests/dashboard/test_batches_progress_parity.py` (study it before writing).

### 4. Do NOT mock the DB

Per `tests/CLAUDE.md` Rule 3. Use real `db_session` for state-verification tests. Monkey-patch `orch.cancel.cancel_batch` / `cancel_work_item` only when verifying **what the router does** (kwarg names, exception mapping, teardown_error surfacing) — NOT what the service layer does. The service layer is already exhaustively tested in `tests/integration/test_cli_cancel.py`.

### 5. Assertions that mean something

For every assertion you write, ask: *would deleting the production line this covers fail this test?* If not, strengthen or remove.

For example, do NOT write:

```python
assert response.status_code == 200
```

alone. Add the *meaningful* assertion:

```python
assert response.status_code == 200
assert "cancelled" in response.text.lower()
assert "killed PIDs: 0" not in response.text  # not a feature
```

### 6. Document the coverage matrix in the report

Your S05 report must include a table mapping every AC, Boundary row, and Invariant to its test ID(s). The S06 reviewer uses this to verify coverage.

## TDD Requirement

For every test you add, write RED first, capture the failure line, then GREEN (implementation already exists from S01/S03, so most tests will go red-then-green on a single run as you add the right assertion). Capture one representative `tdd_red_evidence` line.

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck`.
3. `make lint`.

## Test Verification

Run **only** your new test files:

```bash
uv run pytest tests/dashboard/test_actions_cancel_batch.py tests/dashboard/test_actions_cancel_item.py tests/dashboard/test_cancel_confirm_dialog.py tests/dashboard/test_cancel_button_visibility.py -v
```

Do not run `make test-dashboard` or `make allure-integration` — those are S13 / S14 gates.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "F-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_actions_cancel_batch.py",
    "tests/dashboard/test_actions_cancel_item.py",
    "tests/dashboard/test_cancel_confirm_dialog.py",
    "tests/dashboard/test_cancel_button_visibility.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_cancel_confirm_dialog.py::test_confirm_dialog_get_for_cancel_action_renders_form — AssertionError: …",
  "blockers": [],
  "notes": "Coverage matrix in report maps every AC/Boundary row/Invariant to test IDs."
}
```
