# F-00078 S05 Frontend Report

**Step**: S05 — Frontend
**Agent**: frontend-impl
**Work Item**: F-00078 — Per-project self-assessment step with copy-paste fix prompts
**Date**: 2026-05-02

---

## What Was Done

Implemented the frontend extension for the `self_assess` step in the Execution Report tab:

### 1. `orch/daemon/execution_report.py` — Extended

- **New imports**: `SelfAssessmentData`, `SelfAssessFinding`, `SelfAssessParseError`, `findings_path_for`, `is_self_assess_step`, `parse_findings_json` from `orch.self_assess`; `json`, `suppress` from stdlib; `Sequence` from `collections.abc` (TYPE_CHECKING block)
- **`ExecutionReportData.self_assessment`**: new optional field of type `SelfAssessmentData | None`, added as last field with `field(default=None)`
- **`_load_self_assessment()`**: new private function that:
  - Finds the `self_assess` step type among all steps (using `is_self_assess_step`)
  - Fetches the latest `StepRun` for that step (by `step_id` DESC, `run_number` DESC, `LIMIT 1`)
  - Returns `None` if no runs, no `report_file`, or status is not `completed`/`failed` (terminal)
  - Reads the narrative from `report_file` (defensively, with `suppress(OSError)`)
  - Derives the findings JSON path via `findings_path_for(report_path)`
  - Returns `_build_self_assessment_data(narrative_md)` if JSON missing
  - Parses JSON with `parse_findings_json`, returns empty findings + narrative on parse error
- **`assemble_execution_report()`**: calls `_load_self_assessment` after building step rows; passes result to `ExecutionReportData` constructor
- **`render_execution_report_markdown()`**: new "## Self-Assessment" section when `data.self_assessment` is populated, with narrative, severity-sorted findings grouped by target, and paste prompts in fenced code blocks

### 2. `dashboard/templates/fragments/item_execution_report.html` — Extended

- Added Self-Assessment section AFTER the Retry Timeline block, wrapped in `{% if execution_report.self_assessment %}`
- **Header**: "Self-Assessment" title + "(self_assess failed)" badge when the step's final status is `failed` (determined by iterating `execution_report.steps` looking for `step_type == 'self_assess'`)
- **Bottom line**: italic callout with left-border if `sa.bottom_line` is present
- **Coverage notes**: small italic line if `sa.coverage_notes` is present
- **Findings grouped by target**: `core_findings` and `project_findings` lists built via `{% set _ = core_findings.append(f) %}` pattern; rendered in severity order (HIGH → MED → LOW) using three separate `{% for f in X %}{% if f.severity == 'Y' %}` loops per target to avoid Jinja2 lambda/map syntax errors
- **Severity badges**: color-coded inline spans (HIGH=red, MED=yellow, LOW=gray) using existing Tailwind pattern
- **"Copy paste prompt" buttons**: inline `onclick` using `navigator.clipboard.writeText(this.dataset.pastePrompt)` with 1.5s feedback
- **Empty findings**: italic "Self-assessment ran but no findings were captured."
- **Narrative**: collapsible `<details>/<summary>` block (closed by default)

### 3. `tests/unit/test_execution_report_self_assess.py` — New

12 unit tests in two classes:
- `TestLoadSelfAssessment`: 8 tests covering all `_load_self_assessment` code paths (no step, no runs, no report_file, pending status, valid findings, missing JSON, malformed JSON, missing report file with existing JSON)
- `TestAssembleExecutionReportWithSelfAssessment`: 4 tests covering `assemble_execution_report` integration with self_assessment (findings present, no self_assess step, skipped step, failed soft-step)

### 4. `tests/dashboard/test_execution_report_self_assess.py` — New

6 dashboard smoke tests using FastAPI `TestClient`:
- `test_self_assessment_section_visible_when_findings_exist`: asserts "Self-Assessment", finding titles, severity badges, clipboard buttons, bottom line, coverage notes
- `test_self_assessment_not_in_html_when_no_self_assess_step`: asserts "Self-Assessment" absent
- `test_self_assessment_not_rendered_when_step_is_pending`: asserts section absent when run status is `running`
- `test_self_assessment_not_rendered_when_findings_json_missing`: asserts "Self-Assessment" section present but "no findings were captured" italic line
- `test_self_assessment_only_iw_ai_core_findings`: asserts "Suggestions for iw-ai-core" present, "Suggestions for project-id" absent
- `test_self_assessment_section_absent_when_step_is_skipped`: asserts absent when step has no runs and `status=skipped`

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/execution_report.py` | Added `self_assessment` field + `_load_self_assessment()` + markdown renderer extension |
| `dashboard/templates/fragments/item_execution_report.html` | Appended Self-Assessment Jinja2 block (after Retry Timeline) |
| `tests/unit/test_execution_report_self_assess.py` | **New** — 12 unit tests |
| `tests/dashboard/test_execution_report_self_assess.py` | **New** — 6 dashboard smoke tests |

---

## Test Results

- **`make format`**: ok (ruff format applied to 3 files)
- **`make typecheck`**: ok (no issues in 214 source files)
- **`make lint`**: ok (all checks passed)
- **`make test-unit`**: 2387 passed, 2 skipped, 5 xfailed, 1 xpassed
- **`make test-integration`**: 1587 passed, 15 skipped, 1 xfailed (59.14% coverage, above 46% threshold)

---

## Notes

- **No new Tailwind classes**: only existing utility classes were used (e.g., `bg-destructive/20`, `text-warning`, `border-border`), so `make css` was NOT run and `dashboard/static/styles.css` was not modified
- **No new JS file**: clipboard functionality uses inline `onclick` attribute per existing fragment conventions
- **Jinja2 sorting limitation**: Jinja2's `sort` filter does not support `map=` with a lambda; severity ordering was implemented using three separate `{% for %}` loops per severity level per target section
- **StepRun FK**: `StepRun.step_id` is an integer FK to `WorkflowStep.id` (not `step_db_id`), so `_create_item_with_self_assess` uses `step.id` after `flush()` to get the correct integer
- **`_load_self_assessment` unused params**: `_project_id` and `_work_item_id` are prefixed with `_` to silence `ARG001` lint errors (present for API symmetry, not currently used)
- **Soft-step behavior**: when the self_assess step `failed`, the section still renders (soft-step means the item merges but the failure is recorded for reporting)

---

## Blockers

None.