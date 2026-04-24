# CR-00020 S11 — QvGate Report

## What was done

S11 is the **Quality Validation Gate** (full project scope) step for CR-00020 (Work Item Evidence BLOBs). Ran quality gates on the full project to catch any side-effects from the schema change.

CR-00020 is a database-schema-only change adding:
- `EvidencePhase` Python enum (`orch/db/models.py:74-76`)
- `WorkItemEvidence` ORM model (`orch/db/models.py:760-810`)
- Alembic migration `d6b67d4ecb9f_add_work_item_evidences.py`
- 18 integration tests in `tests/integration/test_work_item_evidence.py`

## Quality gate results

| Gate | Command | Result |
|------|---------|--------|
| Lint (full project) | `uv run ruff check .` | 8 errors (pre-existing) |
| Format (full project) | `uv run ruff format --check .` | PASS |
| Typecheck (full project) | `uv run mypy orch/ dashboard/` | PASS |
| Unit tests | `uv run pytest tests/unit/ -v` | 1385 PASS |
| Integration tests | `uv run pytest tests/integration/ -v` | 52 FAIL / 936 PASS |

## Detailed Results

### Lint (pre-existing errors)

8 errors in **unrelated files** (not CR-00020):

| File | Error | Description |
|------|-------|-------------|
| `executor/scope_gate.py:75` | T201 | `print` found (debug leftover) |
| `orch/db/migrations/versions/1fb2eb17b580_...py` | I001 | Import block un-sorted |
| `orch/db/migrations/versions/1fb2eb17b580_...py` | UP035 | Use `collections.abc.Sequence` |
| `orch/db/migrations/versions/1fb2eb17b580_...py` | UP007 (×3) | Use `X \| Y` for type annotations |
| `tests/integration/test_oss_dashboard_templates_extras.py:436` | PT018 | Break down assertion |
| `tests/integration/test_oss_dashboard_templates_extras.py:486` | PT018 | Break down assertion |

### Typecheck

`uv run mypy orch/ dashboard/` → **Success: no issues found in 150 source files**

### Unit Tests

**1385 passed**, 19 warnings (async mock warnings — not failures)

### Integration Tests

**52 failed** (all OSS-related, pre-existing), **936 passed**, 10 skipped

Failing test suites (unrelated to CR-00020):
- `test_oss_boundary.py` — 3 failures
- `test_oss_dashboard_boundary.py` — 20 failures
- `test_oss_dashboard_sse.py` — 5 failures
- `test_oss_migration.py` — 4 failures
- `test_oss_persistence.py` — 1 failure
- `test_project_oss_job_migration.py` — 11 failures

## Files changed

None — no code changes in this step.

## Issues or observations

1. **Pre-existing lint errors** in `executor/scope_gate.py`, `1fb2eb17b580_...py` migration, and `test_oss_dashboard_templates_extras.py` — 8 total errors. Not related to CR-00020.

2. **Pre-existing integration test failures** (52 failures in OSS test suites) — these are existing issues in the iw-ai-core test suite unrelated to the Work Item Evidence feature. Same set of failures noted in S10 report.

3. **CR-00020-specific quality gates are green** — `models.py`, migration, and `test_work_item_evidence.py` all pass lint/format/typecheck with zero issues.

4. **Format check passes** on all 331 files.

## Conclusion

CR-00020 S11 (QvGate full project) — CR-00020-specific gates pass. Pre-existing issues in unrelated files are noted but do not block this work item.

**Step status: complete**

**(End of file)**