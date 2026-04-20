# F-00056_S11_CodeReview_Final_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S11
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document
- Every per-agent review report from S02, S04, S06, S08, S10
- Every implementation step report (S01, S03, S05, S07, S09)
- All files changed by any step

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S11_CodeReview_Final_report.md`

## Context

You are performing the global cross-agent review for F-00056. Per-agent reviews have already passed (any lingering findings are MEDIUM_SUGGESTION or LOW). Your job is to find integration issues that span layers — problems that no per-agent review could have caught.

## Focus Areas (cross-agent)

### 1. Contract alignment between backend and frontend

- `ExecutionReportData` shape in `orch/daemon/execution_report.py` matches the attribute accesses in `dashboard/templates/fragments/item_execution_report.html`. Flag any attribute the template references that the dataclass does not expose, or any field the backend provides that the template ignores without reason.

### 2. Contract alignment between backend and database

- Every column added or read by the backend exists on the SQLAlchemy model and in the DB schema (including `fix_cycles.fix_summary` post-migration).

### 3. Contract alignment between CLI, API, and the renderer

- CLI and API both call `write_execution_report` / `render_execution_report_markdown` via the same path. No duplicate assembly logic.

### 4. AC + Invariant coverage end-to-end

- Walk every AC (AC1..AC10) against the combined codebase (not just individual test files). For each, point to the code path that satisfies it.
- Walk every Invariant (1..12). Flag any that appear satisfied only by wishful thinking.

### 5. Backfill integrity

- The three backfilled markdown files exist, render non-empty, and contain the expected sections.
- The fix-cycle entries in those files render the "_no fix summary captured (pre-F-00056)_" placeholder gracefully for NULL cases.
- No spurious errors in the dashboard when viewing any of the three items.

### 6. No-regression

- Existing item-detail tabs (Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles) still render identically (Invariant 7).
- Existing CLI commands (`iw step-done`, `iw step-fail`, `iw item-status`, etc.) unaffected.
- Existing tests still pass.

### 7. Security and data hygiene

- No raw `fix_summary` content rendered without Jinja autoescape.
- No path-traversal possibility in `resolve_report_path`.
- No logging of sensitive content at INFO/DEBUG.

### 8. Fix prompt templates

- All three fix templates now require `fix_summary` in the result contract, with a realistic example and a short explanatory note.
- Older fix reports (pre-F-00056) are not affected — ingestion handles missing key gracefully.

## Review Methodology

For each focus area, produce a finding (or a "pass" note) in the review report. Cite specific `file:line` references.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check .`
4. `uv run mypy orch/ dashboard/`
5. Load `/project/iw-ai-core/item/F-00055/execution-report` in the dashboard (via curl or playwright-cli) and confirm HTTP 200 with non-empty body.

## Severity Levels

Standard 5-level scale. Cross-agent issues are typically HIGH or CRITICAL even when individual layers are fine.

## Review Result Contract

Standard CodeReview_Final JSON. `verdict=pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings across the global review.
