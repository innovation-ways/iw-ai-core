# CR-00010_S04_CodeReview_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md`
- `ai-dev/active/CR-00010/reports/CR-00010_S03_Frontend_report.md`
- All files listed in the S03 `files_changed`:
  - `dashboard/routers/actions.py`
  - `dashboard/routers/project_pages.py` (and/or sibling batch-queue router)
  - Every `dashboard/templates/**` file modified by S03 (read from the `audited_templates` list in the S03 report)

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S04_CodeReview_report.md`

## Context

Review S03's dashboard changes. Scope: hide approve/unapprove UI for research items, reject approve/unapprove routes for research, exclude research from batch-queue query and template.

Read the design doc first (especially AC8, AC9).

## Review Checklist

### 1. Template Audit Completeness (AC8)

- Cross-check the S03 `audited_templates` list against your own `grep -rn "approve\|unapprove" dashboard/templates/`. Any template the S03 agent missed is a HIGH finding.
- Every template that renders an approve or unapprove button/form for a work item must have the `{% if item.item_type.value != 'Research' %}` guard.
- The inline notice for research items uses the existing dashboard CSS utility classes (no new CSS). If new CSS was introduced, flag as MEDIUM.
- The guard predicate is exactly `item.item_type.value != 'Research'` (string comparison against `WorkItemType.Research.value`). A misspelling (`"research"` lowercase) is CRITICAL — `WorkItemType.Research.value == "Research"` per `orch/db/models.py`.

### 2. Route-Handler Rejection

- `dashboard/routers/actions.py`: both approve and unapprove handlers check `work_item.item_type == WorkItemType.Research` BEFORE any status-transition logic. Out of order → HIGH.
- Response style matches the existing invalid-transition branches in the same file (HTTPException, HTMLResponse with htmx header, or flash-message redirect — whichever the file already uses). Inconsistency is MEDIUM.
- The error message contains `"Research items"` and describes the reason (no approval workflow / auto-complete on doc creation). Missing substring is MEDIUM (the browser step will verify the text is visible).
- `WorkItemType` imported at module top, no duplicate imports.

### 3. Batch-Queue Backend Filter (AC9)

- The query that powers the batch-queue view adds `WorkItem.item_type != WorkItemType.Research` to its WHERE clause. Missing predicate is CRITICAL (AC9 is not satisfied).
- The filter is applied in the SQL (server-side), not in Python post-filtering. Post-filtering would still satisfy AC9 functionally but breaks the efficiency intent; flag as LOW if done in Python.
- If the query is in a service/helper, every call site uses the filtered version. No caller bypasses the guard.
- `WorkItemType` imported in the router/service.

### 4. Batch-Queue Template (Defense-in-Depth)

- The batch-queue list template wraps the row render in `{% if item.item_type.value != 'Research' %}` or an equivalent predicate. This is redundant with the backend filter but documents intent; absence is LOW (the backend filter is the authoritative gate).

### 5. Cross-Layer Consistency

- Jinja predicate (`item.item_type.value != 'Research'`) and Python predicate (`work_item.item_type == WorkItemType.Research`) agree on the same enum value. A mismatch (e.g., Jinja uses `.name` attribute instead of `.value`) is HIGH. Verify by tracing the enum definition.
- The Python model's `WorkItemType.Research` enum — the `.value` attribute is `"Research"` (capital R). Confirm via reading `orch/db/models.py:48-52`. Any deviation is CRITICAL.

### 6. Accessibility / UX

- The inline notice replacing the approve button:
  - Has a clear, complete sentence (starts with a capital letter, ends with a period).
  - Uses semantic HTML (likely `<p>` or `<section>` with an `aria-label` if purely decorative).
  - Does not hide from screen readers — no `aria-hidden="true"`.
- Flag LOW if the notice uses non-semantic `<div>` with no ARIA role.

### 7. Regression Surface

- **Non-research items unchanged**:
  - Approve/unapprove buttons still render for features, incidents, other CRs.
  - Batch-queue list still includes all approved non-research items.
  - Approve/unapprove HTTP handlers still work for non-research items.
- No new console errors introduced (the browser step will verify; for now, spot-check any new `<script>` blocks — there should be none).
- Existing htmx swap targets / hx-trigger patterns untouched.

### 8. Code Quality

- No `| safe` filter on user-controlled data.
- No new CSS (reuse existing utility classes).
- Comments explain WHY, not WHAT — an expected comment (if any) is on the `# research items excluded from batch queue — see CR-00010` marker.
- Type hints on any new Python parameters in router/service functions.

### 9. Project Conventions (`dashboard/CLAUDE.md`)

- Business logic stays in `orch/` — routers are thin. A new research-business-rule helper in `orch/` is acceptable; leaking research-specific logic into the router is MEDIUM.
- Jinja autoescape on — `| safe` on user data is CRITICAL.
- No new JS bundler / build step.

## Test Verification (NON-NEGOTIABLE)

1. `uv run ruff check dashboard/`
2. `uv run ruff format --check dashboard/`
3. `uv run mypy dashboard/`
4. `make test-unit` — no dashboard-test regressions.

Any failure is CRITICAL.

## Severity Levels

Standard. CRITICAL: (a) Jinja predicate mismatch with the enum value (e.g., `"research"` lowercase); (b) missing backend filter on the batch-queue query; (c) approve/unapprove route still mutates a research item's status.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00010",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
