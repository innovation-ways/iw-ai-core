# F-00037_S03_CodeReview_Backend_report

## Step: S03 — CodeReview_Backend

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines  
**Agent**: CodeReview_Backend  
**Completion Status**: complete

## Review Summary

Reviewed S02 backend implementation against the design document and project conventions.

## Files Reviewed

- `orch/db/models.py` — `DocTypeGuide` model (lines 971–986), `guide_snapshot` column (lines 952–956)
- `orch/doc_service.py` — `get_type_guide()` (lines 808–810), `save_type_guide()` (lines 812–820), `create_doc_job()` (lines 453–480)
- `tests/unit/test_doc_type_guide_service.py` — 4 unit tests

## Correctness: All Passed

| Check | Result |
|-------|--------|
| `DocTypeGuide` model: `doc_type TEXT PK`, `guide_md TEXT NOT NULL`, `updated_at TIMESTAMPTZ` | ✅ Pass |
| `guide_snapshot` on `DocGenerationJob` as nullable TEXT | ✅ Pass |
| `get_type_guide` returns `None` (not raises) when no row | ✅ Pass |
| `save_type_guide` uses upsert pattern | ✅ Pass |
| `create_doc_job` snapshots guide at creation time | ✅ Pass |
| Guide snapshot is `None` when no guide — acceptable | ✅ Pass |

## Conventions: 2 Issues Found

### MEDIUM (fixable)

1. **`guide_md` column missing `comment=` parameter** (`models.py:981`)
   - `doc_type` and `updated_at` both have `comment=` but `guide_md` does not
   - Fix: Add `comment="Editorial guideline markdown content."` to the `guide_md` mapped_column

2. **`get_type_guide` and `save_type_guide` lack docstrings** (`doc_service.py:808–820`)
   - All other service methods have docstrings; these two don't
   - Fix: Add docstrings explaining return values per project convention

## Test Results

```
tests/unit/test_doc_type_guide_service.py: 4 passed
- test_get_type_guide_returns_none_when_missing ✓
- test_get_type_guide_returns_content_when_present ✓
- test_save_type_guide_inserts_new_row ✓
- test_save_type_guide_updates_existing_row ✓
```

## Architecture: Pass

- No business logic in model — data definition only ✅
- Service methods use `self._session` consistently ✅
- No direct DB access outside service layer ✅

## Subagent Result

```json
{
  "step": "S03",
  "agent": "CodeReview_Backend",
  "work_item": "F-00037",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [
    {
      "severity": "MEDIUM (fixable)",
      "file": "orch/db/models.py",
      "line": 981,
      "issue": "guide_md column missing comment= parameter",
      "fix": "Add comment='Editorial guideline markdown content.' to mapped_column"
    },
    {
      "severity": "MEDIUM (fixable)",
      "file": "orch/doc_service.py",
      "lines": "808–820",
      "issue": "get_type_guide and save_type_guide lack docstrings",
      "fix": "Add docstrings explaining return values"
    }
  ],
  "mandatory_fixes": [],
  "notes": "All CRITICAL, HIGH, and MEDIUM (fixable) correctness issues pass. Two convention issues identified but do not block review_passed. All 4 unit tests pass. No database mocking in tests (correct)."
}
```
