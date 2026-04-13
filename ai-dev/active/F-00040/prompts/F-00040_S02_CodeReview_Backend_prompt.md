# F-00040_S02_CodeReview_Backend_prompt

**Work Item**: F-00040 — Enhanced Document Diff
**Step**: S02
**Agent**: CodeReview_Backend
**Parallel With**: None — review of S01

---

## Input Files

- `ai-dev/active/F-00040/F-00040_Feature_Design.md` — Design document
- `ai-dev/active/F-00040/reports/F-00040_S01_Backend_report.md` — S01 implementation report
- `orch/doc_diff.py` — New diff module
- `dashboard/routers/docs.py` — Three new endpoints + preserved existing endpoint
- `orch/doc_service.py` — Must still have `diff_versions()` unchanged

## Output Files

- `ai-dev/active/F-00040/reports/F-00040_S02_CodeReview_Backend_report.md`

## Context

Review the implementation of F-00040 against the design document and project conventions.

## Review Checklist

### Correctness
- [ ] `orch/doc_diff.py` has NO database dependencies (no SQLAlchemy, no session)
- [ ] `DocDiff` and `SectionDiff` are dataclasses with correct fields
- [ ] `diff_document_versions` correctly classifies all four statuses: added, removed, changed, unchanged
- [ ] Documents with no H2 headings produce a single section named "Document"
- [ ] `DocService.diff_versions()` in `doc_service.py` is unchanged from pre-F-00040
- [ ] Existing `/api/docs/{doc_id}/diff` endpoint behavior is unchanged
- [ ] `/api/docs/{doc_id}/diff/ai-summary` returns HTTP 204 with `X-Stub: waiting-for-F-00025`
- [ ] `/api/docs/{doc_id}/diff/sections` returns JSON with `version_old`, `version_new`, `sections`
- [ ] `/api/docs/{doc_id}/diff/sections/{section_name}` returns HTML or 404 if section not in diff

### Conventions
- [ ] Module docstring on `orch/doc_diff.py`
- [ ] All public functions and dataclasses have docstrings
- [ ] Docstrings explain Args and Returns
- [ ] Imports follow project ordering
- [ ] `Literal["added", "removed", "changed", "unchanged"]` used for `status` field

### Architecture
- [ ] Routers are thin — all diff logic in `orch/doc_diff.py`, not in the router
- [ ] Router functions do not import from `orch.doc_diff` at module level (lazy imports acceptable)

### Backward Compatibility
- [ ] `DocService.diff_versions()` still present — this is MANDATORY
- [ ] Old diff endpoint still functions — verify no regression

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Backend",
  "work_item": "F-00040",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
