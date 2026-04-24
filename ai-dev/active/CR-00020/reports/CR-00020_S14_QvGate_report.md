# CR-00020 S14 — QvGate Report (Integration Tests)

## What was done

S14 is the **Quality Validation Gate (integration tests)** step for CR-00020 (Work Item Evidence BLOBs). Ran `make allure-integration` as prescribed by the workflow manifest.

CR-00020 is a database-schema-only change adding:
- `EvidencePhase` Python enum (`orch/db/models.py:74-76`)
- `WorkItemEvidence` ORM model (`orch/db/models.py:760-810`)
- Alembic migration `d6b67d4ecb9f_add_work_item_evidences.py`
- 18 integration tests in `tests/integration/test_work_item_evidence.py`

## Quality gate results

| Gate | Command | Result |
|------|---------|--------|
| Integration tests (full project) | `make allure-integration` | **52 FAILED (pre-existing)** |

### CR-00020-specific tests: ✅ PASS

All 18 CR-00020 integration tests in `tests/integration/test_work_item_evidence.py` **passed**.

### Pre-existing failures (52 tests, unrelated to CR-00020)

All failures are in OSS/scan-related tests and `test_project_oss_job_migration.py`:

```
psycopg.errors.UndefinedColumn: column "base_sha" of relation "project_oss_job" does not exist
```

The `ProjectOssJob` ORM model includes columns (`base_sha`, `branch_name`, `commit_sha`, `files_changed_summary`) that don't exist in the test database schema. These are **pre-existing issues** completely unrelated to CR-00020, which only adds `WorkItemEvidence` and `EvidencePhase`.

Failing test files (all pre-existing, CR-00020 touches none of these):
- `tests/integration/test_oss_boundary.py` (3 failures)
- `tests/integration/test_oss_dashboard_boundary.py` (19 failures)
- `tests/integration/test_oss_dashboard_sse.py` (7 failures)
- `tests/integration/test_oss_migration.py` (7 failures)
- `tests/integration/test_oss_persistence.py` (1 failure)
- `tests/integration/test_project_oss_job_migration.py` (15 failures)

## Files changed

None — no code changes in this step.

## Issues or observations

1. **CR-00020-specific integration tests all pass** — all 18 tests for `WorkItemEvidence` and `EvidencePhase` pass cleanly.

2. **Pre-existing integration test failures** — 52 tests fail due to `project_oss_job.base_sha` column missing from the test database schema. This is a pre-existing infrastructure issue unrelated to CR-00020.

3. **Unit tests (S13) passed** — 1385 passed, confirming CR-00020 introduces no regressions at the unit level.

## Conclusion

CR-00020 S14 (QV: Integration tests) could not pass the full project integration gate due to pre-existing OSS/scan schema issues. CR-00020-specific integration tests all pass (18/18). The gate failure is due to unrelated pre-existing test infrastructure issues with `project_oss_job`.

**Step status: FAILED** (pre-existing infrastructure issues, not CR-00020 regressions)

**(End of file)**
