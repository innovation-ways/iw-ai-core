# F-00038_S05_CodeReview_Final_prompt

**Work Item**: F-00038 — Instance Guide Overlay — Per-Document Editorial Override
**Step**: S05
**Agent**: CodeReview_Final
**Parallel With**: None — final review of all work

---

## Input Files

- `ai-dev/active/F-00038/F-00038_Feature_Design.md` — Design document
- All reports: S01 through S04
- All changed files: migration, models, doc_service, test files

## Output Files

- `ai-dev/active/F-00038/reports/F-00038_S05_CodeReview_Final_report.md`

## Review Checklist

### Completeness
- [ ] All 4 acceptance criteria tested end-to-end
- [ ] `doc_instance_guides` table created with correct schema (PK, FK, NOT NULL, CASCADE)
- [ ] `DocInstanceGuide` model complete
- [ ] `_effective_guide` priority: instance > type > None
- [ ] `create_doc_job` uses merged effective guide (not just type guide)

### Consistency
- [ ] Composite key `{project_id}:{doc_id}` used consistently across model, service, and tests
- [ ] Model style matches `DocTypeGuide` (added by F-00037) and other models
- [ ] Service methods match pattern of adjacent methods

### Integration with F-00037
- [ ] F-00037's `guide_snapshot` column is correctly repurposed by F-00038 (no double-snapshot)
- [ ] `_effective_guide` correctly calls both `get_instance_guide` and `get_type_guide`

### Migration Safety
- [ ] FK constraint has ON DELETE CASCADE
- [ ] Downgrade drops the table cleanly

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00038",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
