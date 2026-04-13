# F-00039_S05_CodeReview_Final_prompt

**Work Item**: F-00039 — Section-Level Guide
**Step**: S05
**Agent**: CodeReview_Final
**Parallel With**: None — final review of all work

---

## Input Files

- `ai-dev/active/F-00039/F-00039_Feature_Design.md` — Design document
- `ai-dev/active/F-00039/reports/F-00039_S01_Database_report.md` — Migration report
- `ai-dev/active/F-00039/reports/F-00039_S02_Backend_report.md` — Backend report
- `ai-dev/active/F-00039/reports/F-00039_S03_CodeReview_Backend_report.md` — Backend review
- `ai-dev/active/F-00039/reports/F-00039_S04_Tests_report.md` — Tests report
- All changed files: migrations, `orch/db/models.py`, `orch/doc_service.py`, `orch/doc_sections.py`, test files

## Output Files

- `ai-dev/active/F-00039/reports/F-00039_S05_CodeReview_Final_report.md`

## Context

This is the global review of all F-00039 work. Evaluate completeness, consistency, and compliance.

## Review Checklist

### Completeness (all 5 ACs from design doc)
- [ ] AC1: `extract_sections` returns section names from H2 headings
- [ ] AC2: `extract_sections` returns `["Document"]` when no H2 headings
- [ ] AC3: Section guide upsert and retrieval round-trip tested
- [ ] AC4: Section guide snapshot captured at job creation
- [ ] AC5: No H2 headings — snapshot uses "Document" key

### Correctness
- [ ] `doc_section_guides` table created with correct DDL and unique constraint
- [ ] `section_guides_snapshot JSONB` column added to `doc_generation_jobs`
- [ ] `orch/doc_sections.py` is a pure-function module with no DB dependencies
- [ ] CRUD methods all use composite `project_id:doc_id` key

### Boundary Cases
- [ ] Empty content → `["Document"]` tested
- [ ] H3-only content → `["Document"]` tested
- [ ] Delete non-existent section guide → `False` returned (not raise)
- [ ] Job with no section guides → `section_guides_snapshot` is `None` (not `{}`)

### Migration Safety
- [ ] ON DELETE CASCADE on `doc_id` FK
- [ ] Unique constraint on `(doc_id, section_name)`
- [ ] Downgrade reverts both migrations cleanly

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW — same as per-agent review.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00039",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
