# F-00057 S02 Code Review Report

## Summary

Reviewed S01 (database-impl) implementation: Alembic migration + ORM models for OSS compliance tables. All 35 OSS migration tests pass. One design-doc mismatch identified.

---

## Files Reviewed

| File | Status |
|------|--------|
| `orch/db/migrations/versions/824e6e6f34ee_add_oss_compliance_tables.py` | Reviewed |
| `orch/db/models.py` (OSS sections) | Reviewed |
| `tests/integration/test_oss_migration.py` | Reviewed |

---

## Findings

### Finding 1: `oss_finding.status` enum label mismatch (MEDIUM_FIXABLE)

**Severity**: MEDIUM_FIXABLE

**Location**: `models.py:227-231`, `models.py:269`, migration lines 41-43

**Description**: The design doc specifies `status ENUM('pass', 'fail', 'skip', 'human_required')` for `oss_finding.status`. However, the implementation uses `pass_status` as the enum label (Python member name `pass_status`, value `"pass"`).

**Root cause**: `pass` is a Python keyword and cannot be used as an enum member name, so the implementation uses `pass_status` as a workaround.

**Impact**: The PostgreSQL enum label is `pass_status` (not `pass`). The Python enum value is correctly `"pass"`, so database operations work correctly. The mismatch is cosmetic (design doc vs implementation naming).

**Recommendation**: Update the design doc to specify `pass_status` as the enum label to match the implementation, or use a different name like `passed` in both design and implementation.

**Verdict on this finding**: Implementation is functionally correct. Design doc should be updated for consistency.

---

## Checklist Summary

| Category | Result |
|----------|--------|
| Architecture Compliance | PASS (with 1 design-doc naming mismatch) |
| Code Quality | PASS |
| Project Conventions | PASS |
| Security | PASS |
| Testing | PASS (35/35 OSS tests pass) |

---

## Test Results

```
tests/integration/test_oss_migration.py - 35 passed
- TestOssMigrationApply: 10/10 passed
- TestOssEnumValues: 6/6 passed
- TestOssORMModels: 4/4 passed
- TestOssFKConstraints: 6/6 passed
- TestOssCascadeDeletes: 3/3 passed
- TestOssRelationships: 3/3 passed
- TestProjectOssEnabled: 2/2 passed
- TestOssMigrationDowngrade: 1/1 passed
```

**Lint**: `make lint` — All checks passed

---

## Architecture Compliance Details

- Migration creates exactly the tables and columns specified in the design doc
- `project.oss_enabled` added with `NOT NULL DEFAULT false` (correct)
- FK constraints with `ON DELETE CASCADE` correctly placed
- Indexes include `DESC` on `started_at` per design
- Downgrade reverses in correct order (tables → column → enums)
- JSONB used for `summary_json` and `evidence_json`
- `server_default` set for all new non-nullable columns
- Cascade relationships properly declared on Project→OssScan and OssScan→(OssFinding|OssToolRun)

---

## Notes

- The 12 failing tests in the full integration suite are pre-existing failures unrelated to OSS migration (test_module_gen_integration, test_code_qa_*, test_dashboard_pages, test_f00055_workflow_fixture).
- The `OssFindingStatus.pass_status` / `pass` enum value naming is a Python keyword workaround, not a bug. Implementation is correct; design doc should be updated.
- Test uses testcontainer Postgres (not live DB on port 5433) per CLAUDE.md.
- FTS triggers installed after `Base.metadata.create_all()` per tests/CLAUDE.md.

---

## Review Result

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00057",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "file": "models.py + design doc",
      "description": "oss_finding.status enum label is 'pass_status' in implementation but 'pass' in design doc (Python keyword workaround; functionally correct)"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "35 passed, 0 failed (OSS migration tests)",
  "notes": "All 35 OSS migration tests pass. One cosmetic design-doc mismatch (naming only). Implementation is functionally correct. 12 pre-existing failures in unrelated test files."
}
```
