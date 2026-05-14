# F-00082_S06_CodeReview_Final_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` allowed.

## ⛔ Migrations: agents generate, daemon applies

S01–S05 must not have touched migrations. If any did, that's a CRITICAL finding.

## Input Files

- `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md`.
- All step reports: `ai-dev/active/F-00082/reports/F-00082_S0[1-5]_*_report.md`.
- All per-step review reports: `…_S02_CodeReview_report.md`, `…_S04_CodeReview_report.md`.
- Every file in the union of `files_changed` across S01, S03, S05.
- Service-layer contract: `orch/cancel.py`.

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S06_CodeReview_Final_report.md`.

## Context

This is the cross-agent review. Per-step reviews (S02, S04) already validated their own work; you catch the seams.

## Read the Design Document FIRST

Read §Acceptance Criteria, §Invariants, §Boundary Behavior, §TDD Approach in full. Write down every test file the design names (`tests/dashboard/test_actions_cancel_batch.py`, `…_item.py`, plus the new `test_cancel_confirm_dialog.py` and `test_cancel_button_visibility.py`). Cross-check the union of `files_changed` across S01+S03+S05 — any named test file missing is CRITICAL.

## Pre-Review Lint & Format Gate

```bash
make lint
make format-check
```

NEW violations in F-00082's `files_changed` = CRITICAL.

## Review Checklist

### 1. Completeness vs design

- Every AC1–AC6 mapped to ≥1 test in S05? (Read the S05 report's coverage matrix.)
- Every Boundary Behavior row mapped to a test?
- Every Invariant 1–6 mapped to a test?
- Every file in the design's Impacted Paths actually touched (or explicitly skipped with reason in S03's notes — e.g., `queue.html` audit-only)?

### 2. Cross-step seams

- S01's confirm-dialog GET handler renders the template name S03 created. Both sides agree on `default_reason`, `reset_field_name`, `reset_field_label` (S01 sets, S03 reads).
- S03's form posts to the URL S01's handler accepts. Form field names (`reason`, `to_draft`, `reset_items`) match on both sides.
- S05's TestClient setup uses `app.dependency_overrides[get_db]` with the testcontainer session — does not import or invoke the live DB.

### 3. Integration with the service layer (most important)

- The two POST handlers call `orch.cancel.cancel_batch` / `cancel_work_item` and nothing else for state mutation. (Invariant 1, Invariant 5.) Grep both handler bodies — they should be ~30 lines each.
- No new module under `orch/` was added. F-00082 is wrap-only.

### 4. Architecture compliance

- `dashboard/CLAUDE.md` — routers thin, fragments don't extend base.html, no `navigator.clipboard` direct calls.
- `tests/CLAUDE.md` — testcontainer, no DB mocks, no `importlib.reload(orch.config)`.

### 5. Test coverage (holistic)

- Happy path + error path covered for both endpoints?
- Browser-side concerns (modal swap, htmx target, button visibility) covered in `test_cancel_button_visibility.py`?
- The `confirm_dialog` macro byte-equivalence test exists?

### 6. Security

- No hardcoded reasons that look like secrets.
- Form inputs are not interpolated into raw SQL anywhere (they go to `orch.cancel.*` which uses ORM).
- The reason text is HTML-escaped when rendered into the toast (Jinja2 autoescapes by default; verify the toast template doesn't `| safe` it).

## Test Verification (NON-NEGOTIABLE)

Run:

```bash
make test-unit
make test-frontend     # dashboard tests
```

(Skip `make allure-integration` — S14 owns it.) If anything fails, CRITICAL.

## Severities

- CRITICAL: AC unmet, Invariant violated, layer breach, security issue, test suite red.
- HIGH: missing test for a Boundary row, missing macro byte-equivalence test, cross-step contract drift.
- MEDIUM: copy weakness, missing report-side coverage matrix, hygiene.
- LOW: nit.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReviewFinal",
  "work_item": "F-00082",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/F-00082/reports/F-00082_S06_CodeReview_Final_report.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make test-unit + make test-frontend — X passed, 0 failed",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "OVERALL: PASS | NEEDS_FIX (echo)"
}
```
