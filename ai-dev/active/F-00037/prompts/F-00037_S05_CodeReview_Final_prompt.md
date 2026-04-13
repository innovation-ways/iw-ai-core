# F-00037_S05_CodeReview_Final_prompt

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines
**Step**: S05
**Agent**: CodeReview_Final
**Parallel With**: None — final review of all work

---

## Input Files

- `ai-dev/active/F-00037/F-00037_Feature_Design.md` — Design document
- `ai-dev/active/F-00037/reports/F-00037_S01_Database_report.md` — Migration report
- `ai-dev/active/F-00037/reports/F-00037_S02_Backend_report.md` — Backend report
- `ai-dev/active/F-00037/reports/F-00037_S03_CodeReview_Backend_report.md` — Backend review
- `ai-dev/active/F-00037/reports/F-00037_S04_Tests_report.md` — Tests report
- All changed files: migrations, `orch/db/models.py`, `orch/doc_service.py`, test files

## Output Files

- `ai-dev/active/F-00037/reports/F-00037_S05_CodeReview_Final_report.md`

## Context

This is the global review of all F-00037 work. Evaluate completeness, consistency, and
compliance with the design document and project conventions.

## Review Checklist

### Completeness
- [ ] All 4 acceptance criteria from the design document are met
- [ ] Migration creates `doc_type_guides` table with correct DDL
- [ ] Migration adds `guide_snapshot` to `doc_generation_jobs`
- [ ] Seed data exists for `_default` and `marketing` guides
- [ ] `DocTypeGuide` model is correctly defined
- [ ] `DocService.get_type_guide` and `save_type_guide` are implemented
- [ ] `DocService.create_doc_job` snapshots the guide

### Consistency
- [ ] Model style matches other models in `orch/db/models.py`
- [ ] Service methods match style of other `DocService` methods
- [ ] Test patterns match existing integration tests

### Boundary Cases
- [ ] Unknown doc_type returns None (not exception)
- [ ] `guide_snapshot` is None when no guide configured — tested
- [ ] Upsert tested: save same type twice results in one row

### Migration Safety
- [ ] Downgrade reverts both changes cleanly
- [ ] Migration chain is linear (single head after both migrations)
- [ ] No raw file I/O at migration runtime

## Severity Classification

Same as S03 (CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00037",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```

Set `review_passed: false` and populate `mandatory_fixes` if any mandatory-fix findings exist.
