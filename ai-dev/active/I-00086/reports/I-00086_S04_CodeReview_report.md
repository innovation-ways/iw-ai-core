# I-00086 — S04 Code Review (S03 Frontend)

## Scope reviewed

- Step reviewed: **S03 (frontend-impl)**
- Design reference: `ai-dev/active/I-00086/I-00086_Issue_Design.md` (AC1, AC2, AC3 + Notes)
- Implementation report: `ai-dev/active/I-00086/reports/I-00086_S03_Frontend_report.md`
- Files reviewed:
  - `dashboard/templates/fragments/item_overview.html`
  - `dashboard/templates/fragments/item_steps_table.html` (new)

## What I validated

1. **Template extraction correctness**
   - New fragment `fragments/item_steps_table.html` exists and does **not** extend `base.html`.
   - It contains the full steps table + bulk footer.
   - Root wrapper is `id="item-steps-table"`.
   - All required macros are imported and used (`status_badge`, `approve_merge_button`, `restart_button`, `skip_button`, `kill_button`, `restart_merge_button`, `abandon_merge_button`, `restart_setup_button`).
   - Conditional branches from the original inline block are preserved (synthetic/non-synthetic, statuses, MERGE/S00 actions, empty state).
   - Lazy-loaded run container remains present for `run_count > 1`: `id="step-runs-{{ step.step_id }}" class="step-runs-container"`.
   - Bulk selector `id="bulk-runtime-option"` remains **inside** the swapped fragment.

2. **htmx wiring**
   - Per-step `<select>` now has:
     - `hx-target="#item-steps-table"`
     - `hx-swap="outerHTML"`
     - preserved `hx-disabled-elt="this"` (critical requirement met)
   - Bulk Apply button now has:
     - `hx-target="#item-steps-table"`
     - `hx-swap="outerHTML"`
   - `hx-patch` paths unchanged.
   - No `onchange="this.disabled=true"` introduced.
   - `hx-target` id matches rendered fragment root id.

3. **Toast integration**
   - `dashboard/templates/pages/project/item_detail.html` has no diff in this step.
   - Existing page-level `HX-Trigger.showToast` handler remains unchanged.
   - No duplicate toast handler added in the new fragment.

4. **Conventions**
   - Tailwind classes are existing/static utility usage style; no dynamic class construction introduced.
   - No clipboard code introduced.
   - Jinja `format` filter usage in changed template remains `%`-style (`"%dm%02ds"|format(m, s)`).

5. **S03 testing/report sanity**
   - S03 report includes dashboard test run evidence and a plausible template-level TDD RED narrative.
   - Design doc explicitly names the fragment assertion (`id="item-steps-table"`) in TDD section.

## Quality gates run in S04

- `make lint` ✅
- `make format-check` ✅
- `uv run pytest tests/dashboard/ -v` ⚠️
  - Execution summary: **848 passed, 0 failed, 15 skipped, 1 xfailed**
  - Command exit is non-zero due repository-wide coverage fail-under gate (`29.40% < 50%`), not due test failures in this change.

## Findings

No S03 frontend defects found against this review checklist.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00086",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": false,
  "test_summary": "848 passed, 0 failed, 15 skipped, 1 xfailed (pytest exit non-zero only due global coverage fail-under 50%)",
  "notes": "S03 template extraction and htmx rewiring satisfy AC-related frontend requirements, including preserved hx-disabled-elt and in-fragment bulk selector placement."
}
```
