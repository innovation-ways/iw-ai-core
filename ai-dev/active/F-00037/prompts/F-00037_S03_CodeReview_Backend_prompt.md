# F-00037_S03_CodeReview_Backend_prompt

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines
**Step**: S03
**Agent**: CodeReview_Backend
**Parallel With**: None — review of S02

---

## Input Files

- `ai-dev/active/F-00037/F-00037_Feature_Design.md` — Design document
- `ai-dev/active/F-00037/reports/F-00037_S02_Backend_report.md` — S02 implementation report
- `orch/db/models.py` — DocTypeGuide model + guide_snapshot column
- `orch/doc_service.py` — get_type_guide, save_type_guide, updated create_doc_job
- `tests/unit/test_doc_type_guide_service.py` — Unit tests

## Output Files

- `ai-dev/active/F-00037/reports/F-00037_S03_CodeReview_Backend_report.md`

## Context

Review the backend implementation of F-00037 against the design document and project conventions.

## Review Checklist

### Correctness
- [ ] `DocTypeGuide` model matches the design: `doc_type TEXT PK`, `guide_md TEXT NOT NULL`, `updated_at TIMESTAMPTZ`
- [ ] `guide_snapshot` column added to `DocGenerationJob` as nullable TEXT
- [ ] `get_type_guide` returns `None` (not raises) when no row exists
- [ ] `save_type_guide` uses upsert pattern (INSERT or UPDATE, not blind INSERT)
- [ ] `create_doc_job` correctly snapshots the guide at creation time
- [ ] Guide snapshot is `None` when no guide configured — acceptable, not an error

### Conventions
- [ ] Model docstring present and meaningful
- [ ] Column `comment=` parameter on every mapped_column
- [ ] Service methods have docstrings explaining return values
- [ ] Imports follow project ordering (stdlib → third-party → local)
- [ ] `onupdate=func.now()` used for `updated_at` (not manual update in service)

### Tests
- [ ] Tests cover: missing guide returns None, present guide returns content, insert new, update existing
- [ ] Tests follow project test patterns (see `tests/CLAUDE.md` or existing test files)
- [ ] No mocking of the database in integration tests (rule from CLAUDE.md)

### Architecture
- [ ] No business logic in the model — only data definition
- [ ] Service methods use `self._session` consistently
- [ ] No direct DB access from outside the service layer

## Severity Classification

Classify each finding:
- **CRITICAL**: Security vulnerability or data loss risk
- **HIGH**: Broken functionality or convention violation
- **MEDIUM (fixable)**: Concrete code quality issue with a specific fix
- **MEDIUM (suggestion)**: General improvement without a specific fix
- **LOW**: Style suggestion

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Backend",
  "work_item": "F-00037",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```

Set `review_passed: false` and populate `mandatory_fixes` if any CRITICAL, HIGH, or MEDIUM (fixable) findings exist.
