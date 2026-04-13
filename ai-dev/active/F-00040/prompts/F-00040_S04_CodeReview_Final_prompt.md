# F-00040_S04_CodeReview_Final_prompt

**Work Item**: F-00040 — Enhanced Document Diff
**Step**: S04
**Agent**: CodeReview_Final
**Parallel With**: None — final review of all work

---

## Input Files

- `ai-dev/active/F-00040/F-00040_Feature_Design.md` — Design document
- `ai-dev/active/F-00040/reports/F-00040_S01_Backend_report.md`
- `ai-dev/active/F-00040/reports/F-00040_S02_CodeReview_Backend_report.md`
- `ai-dev/active/F-00040/reports/F-00040_S03_Tests_report.md`
- `orch/doc_diff.py`
- `dashboard/routers/docs.py`
- `orch/doc_service.py`
- `tests/unit/test_doc_diff.py`
- `tests/integration/api/test_docs_diff_api.py`

## Output Files

- `ai-dev/active/F-00040/reports/F-00040_S04_CodeReview_Final_report.md`

## Context

Global review of all F-00040 work. Evaluate completeness and backward compatibility.

## Review Checklist

### Completeness (all 6 ACs from design doc)
- [ ] AC1: Section diff classifies added/removed/changed/unchanged correctly
- [ ] AC2: No H2 headings → single "Document" section
- [ ] AC3: `/diff/sections` returns section summary JSON
- [ ] AC4: `/diff/ai-summary` returns 204 with X-Stub header
- [ ] AC5: Existing `/diff` endpoint unchanged and `diff_versions()` still present
- [ ] AC6: `/diff/sections/{section_name}` returns HTML diff for known section; 404 for unknown section — and a dedicated integration test (`test_sections_single_section_endpoint`) covers this

### Backward Compatibility (CRITICAL)
- [ ] `DocService.diff_versions()` method still present in `orch/doc_service.py` — unchanged
- [ ] Existing `/api/docs/{doc_id}/diff` endpoint still works — test confirms this

### Correctness
- [ ] `orch/doc_diff.py` is truly pure — no DB or HTTP dependencies
- [ ] All four section statuses are tested
- [ ] 204 response has `X-Stub` header (not just empty response)
- [ ] 422 returned for v1 >= v2 on all three new endpoints

### Documentation
- [ ] `orch/doc_diff.py` module docstring present
- [ ] All public classes and functions documented
- [ ] AI-summary stub documents the F-00025 dependency in its docstring

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW

**CRITICAL finding**: `diff_versions()` removed or renamed.
**HIGH finding**: AI-summary returns 5xx instead of 204.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
  "work_item": "F-00040",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
