# F-00082_S04_CodeReview_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step Being Reviewed**: S03 (Frontend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` allowed.

## ⛔ Migrations: agents generate, daemon applies

S03 must not have touched migrations.

## Input Files

- `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md`.
- `ai-dev/active/F-00082/reports/F-00082_S03_Frontend_report.md`.
- Every template / static / Python file listed in the S03 `files_changed`.
- Service-layer constants: `orch/cancel.CANCELLABLE_BATCH_STATUSES`, `CANCELLABLE_WORK_ITEM_STATUSES`, `_ACTIVE_BATCH_STATUSES`.

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S04_CodeReview_report.md`.

## Read the Design Document FIRST

Read §Acceptance Criteria, §Invariants, and §Boundary Behavior. Cross-check each row against the templates. The Visibility ⇔ Allowed-from set invariant (Invariant 2) is the dominant check here — get it right.

## Pre-Review Lint & Format Gate

Run:
- `make lint` — includes the Jinja2 `%`-style format gate.
- `make format-check`.
- `uv run python scripts/check_templates.py` (covered by `make lint` but call separately to surface a clear failure if it fires).
- `make css` from a clean state — if it regenerates `dashboard/static/styles.css` with non-zero diff, that means S03 forgot to run it. CRITICAL.

## Review Checklist

Score each: `pass | medium | high | critical`.

### Visibility rules
1. `batch_detail_header.html` renders a Cancel button **iff** `batch_status` is in `CANCELLABLE_BATCH_STATUSES`. Verify by inspecting the conditional and reading the enum from `orch/cancel.py`. (Invariant 2.)
2. `item_detail.html` renders a Cancel button **iff** `item.status` is in `CANCELLABLE_WORK_ITEM_STATUSES`. (Invariant 2.)
3. `item_detail.html` renders the **disabled with hint** state **iff** the item is in an active batch (parent batch status in `_ACTIVE_BATCH_STATUSES`). (Invariant 3.)
4. `batches.html` renders the per-row quick-cancel **iff** `batch.status` is cancellable.

### Form-bearing dialog
5. `components/confirm_dialog.html` accepts a `form_html` kwarg with default `""`. When empty, the rendered HTML for an existing approve/pause confirm is byte-identical to before. (Risk noted in design §Notes.)
6. `fragments/confirm_action_form.html` posts to the correct endpoint, with form fields named `reason` and (`to_draft` or `reset_items`).
7. Tailwind classes used in the new fragment exist in `dashboard/static/styles.css` after `make css`. (Invariant 6.)

### htmx wiring
8. Quick-cancel from list works without a full page reload — the click handler issues `htmx.ajax('POST', …)` with `values:{reason:'cancelled from batches list'}` and the server returns a fragment.
9. Modal swap target is `#confirm-dialog`; that element exists on every page that renders a cancel button.

### No layer violations
10. Templates do not import from `orch.daemon.*`.
11. No direct `BatchStatus.X.value` literals in templates — use string comparisons (e.g., `batch_status == 'executing'`). (This mirrors existing pattern; do not introduce ORM imports into Jinja.)

### Hygiene
12. No `navigator.clipboard` direct calls (rule in dashboard CLAUDE.md).
13. `%`-style format filters only (`"%dm%02ds"|format(m,s)`); no `"{}".format(...)` in Jinja.
14. `dashboard/CLAUDE.md` updated to reflect cancel = full teardown.

## Severities

Same scale as S02:

- CRITICAL: visibility wrong (UI shows button the API will reject, or hides button the API would accept) — directly violates Invariant 2 or 3.
- HIGH: bytes-identical regression of existing modal call sites; missing `make css`.
- MEDIUM: missing test, weak assertion.
- LOW: nit.

## Report

Same shape as S02: top summary table + `OVERALL: PASS | NEEDS_FIX` verdict.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00082",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/F-00082/reports/F-00082_S04_CodeReview_report.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — review step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "OVERALL: PASS | NEEDS_FIX (echo)"
}
```
