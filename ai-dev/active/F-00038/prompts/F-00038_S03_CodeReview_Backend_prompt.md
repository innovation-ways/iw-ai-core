# F-00038_S03_CodeReview_Backend_prompt

**Work Item**: F-00038 — Instance Guide Overlay — Per-Document Editorial Override
**Step**: S03
**Agent**: CodeReview_Backend
**Parallel With**: None — review of S02

---

## Input Files

- `ai-dev/active/F-00038/F-00038_Feature_Design.md` — Design document
- `ai-dev/active/F-00038/reports/F-00038_S02_Backend_report.md` — S02 implementation report
- `orch/db/models.py` — DocInstanceGuide model
- `orch/doc_service.py` — instance guide methods + _effective_guide + updated create_doc_job
- `tests/unit/test_instance_guide_service.py` — Unit tests

## Output Files

- `ai-dev/active/F-00038/reports/F-00038_S03_CodeReview_Backend_report.md`

## Review Checklist

### Correctness
- [ ] `DocInstanceGuide` model: `doc_id TEXT PK` with FK to `project_docs.id` ON DELETE CASCADE
- [ ] `get_instance_guide` uses composite key `project_id:doc_id` consistently
- [ ] `save_instance_guide` upserts correctly (INSERT or UPDATE)
- [ ] `delete_instance_guide` returns True/False correctly
- [ ] `_effective_guide` priority: instance first, then type, then None
- [ ] `create_doc_job` uses `_effective_guide` (not `get_type_guide` — that was the F-00037 interim version)
- [ ] `doc.doc_id` (short ID) is used for `_effective_guide`, not `doc.id` (composite)

### Conventions
- [ ] Model docstrings and `comment=` on all columns
- [ ] Service method docstrings, especially return value and priority explanation in `_effective_guide`
- [ ] Consistent use of `self._session` pattern
- [ ] `onupdate=func.now()` on `updated_at`

### Tests
- [ ] All 8 unit tests listed in the prompt are present and meaningful
- [ ] Tests are isolated (no shared state)
- [ ] Priority: instance-wins, type-fallback, none-fallback all tested

### Architecture
- [ ] `_effective_guide` is a private method (underscore prefix) — not exposed in API
- [ ] Composite key format `{project_id}:{doc_id}` matches `ProjectDoc.id` pattern (verified in `ProjectDoc.__tablename__`)

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Backend",
  "work_item": "F-00038",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
