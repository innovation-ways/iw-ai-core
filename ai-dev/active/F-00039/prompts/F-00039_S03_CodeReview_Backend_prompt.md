# F-00039_S03_CodeReview_Backend_prompt

**Work Item**: F-00039 — Section-Level Guide
**Step**: S03
**Agent**: CodeReview_Backend
**Parallel With**: None — review of S02

---

## Input Files

- `ai-dev/active/F-00039/F-00039_Feature_Design.md` — Design document
- `ai-dev/active/F-00039/reports/F-00039_S02_Backend_report.md` — S02 implementation report
- `orch/db/models.py` — DocSectionGuide model + section_guides_snapshot column
- `orch/doc_service.py` — CRUD methods + snapshot update
- `orch/doc_sections.py` — extract_sections / split_by_sections
- `tests/unit/test_doc_sections.py` — Unit tests

## Output Files

- `ai-dev/active/F-00039/reports/F-00039_S03_CodeReview_Backend_report.md`

## Context

Review the backend implementation of F-00039 against the design document and project conventions.

## Review Checklist

### Correctness
- [ ] `DocSectionGuide` model: `id BIGINT PK`, `doc_id TEXT NOT NULL FK`, `section_name TEXT NOT NULL`, `guide_md TEXT NOT NULL`, `updated_at TIMESTAMPTZ`
- [ ] `UniqueConstraint("doc_id", "section_name")` present on the model
- [ ] `section_guides_snapshot JSONB` column added to `DocGenerationJob`
- [ ] `extract_sections` returns `["Document"]` for content with no H2 headings
- [ ] `extract_sections` correctly strips whitespace from section names
- [ ] `split_by_sections` returns `{"Document": content}` for no-H2 content
- [ ] CRUD methods use composite `project_id:doc_id` key
- [ ] `delete_section_guide` returns `False` (not raises) when row not found
- [ ] `create_doc_job` snapshot captures all section guides at creation time

### Conventions
- [ ] Module docstring on `orch/doc_sections.py`
- [ ] All functions in `doc_sections.py` have docstrings with Args and Returns
- [ ] Column `comment=` on every `mapped_column`
- [ ] Model class has a docstring
- [ ] Imports follow project ordering

### Tests
- [ ] `test_extract_sections_no_h2_returns_document` present and meaningful
- [ ] `test_extract_sections_empty_content` present
- [ ] `test_split_by_sections_no_h2_returns_document_key` present
- [ ] Tests follow project test patterns

### Architecture
- [ ] `orch/doc_sections.py` has NO database dependencies — pure functions only
- [ ] Service methods use `self._session` consistently
- [ ] No business logic outside the service layer

## Severity Classification

- **CRITICAL**: Security or data loss
- **HIGH**: Broken functionality or convention violation
- **MEDIUM (fixable)**: Concrete code quality issue with specific fix
- **MEDIUM (suggestion)**: General improvement without specific fix
- **LOW**: Style suggestion

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Backend",
  "work_item": "F-00039",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```

Set `review_passed: false` and populate `mandatory_fixes` if any CRITICAL, HIGH, or MEDIUM (fixable) findings exist.
