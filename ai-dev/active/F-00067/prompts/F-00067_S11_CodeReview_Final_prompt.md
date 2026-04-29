# F-00067_S11_CodeReview_Final_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Review Step**: S11 (Final Review)
**Implementation Steps Reviewed**: S01–S09

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md`
- All reports: `F-00067_S01_*` through `F-00067_S10_*`
- All files changed across S01–S09 (read each report's `files_changed` list)

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S11_CodeReview_Final_report.md`

---

## Context

Perform a global cross-layer review of all implementation work for F-00067. The goal is to detect cross-layer inconsistencies, missing integration points, and any issue that individual per-step reviews may have missed.

---

## Final Review Checklist

### 1. Color palette consistency (CRITICAL cross-layer check)
- Verify the `classDef` hex values in `orch/rag/mapgen.py` and `orch/rag/module_gen.py` are **identical**.
- Verify the CSS colors in `docs_detail.html` callout classes match the canonical palette in the design doc.
- Verify the hex values in `skills/iw-doc-generator/references/diagram-guidelines.md` match both of the above.
- Any mismatch across these three layers is CRITICAL — it means diagrams and docs will have different visual languages.

### 2. "Why" paragraph round-trip
- Trace the full path: LLM prompt → `purpose` block extraction → `<!-- purpose: -->` storage → Python router extraction → Jinja2 template rendering.
- Verify no step in this chain can fail silently (None-safe, exception-safe).

### 3. Callout rendering completeness
- Verify all 5 callout types (note, tip, warning, danger, important) are handled in the **server-side** Python post-processor (`render_markdown_with_callouts()` in `dashboard/utils/markdown.py`) — this is the primary path.
- Verify matching CSS classes exist for all 5 types.
- Verify the `[!NOTE]` callout used in the generated index page and doc templates will actually render in the dashboard — confirm by checking that `render_markdown_with_callouts()` is used in `dashboard/routers/docs.py`.

### 4. Index page integration
- Verify `index_gen.py` is correctly imported and called in `job.py`.
- Verify the try/except wrapper is in place.
- Verify `code-index` doc can be viewed via the existing docs route (no new route needed — confirm the existing `/project/{id}/docs/{doc_id}` route serves it).

### 5. Skills sync
- Verify S03 ran `iw skills sync` and the report confirms it.

### 6. No regressions introduced
- Scan all modified files for: import cycles, broken Jinja2 syntax, Python type errors, JS syntax errors.
- Verify `make typecheck` passes on the full codebase.

### 7. AC coverage
- Verify every Acceptance Criterion (AC1–AC6) in the design doc is addressed by the implementation.

## Test Verification

Run `make test-unit` and `make test-integration`. Report results.

## Final Review Result Contract

```json
{
  "step": "S11",
  "agent": "CodeReview_Final",
  "work_item": "F-00067",
  "steps_reviewed": ["S01", "S02", "S03", "S07", "S09"],
  "verdict": "pass|fail",
  "cross_layer_findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
