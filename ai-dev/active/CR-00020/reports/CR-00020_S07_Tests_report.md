# CR-00020 S07 Tests Report

## What was done

S07 is the **Tests** step for CR-00020 (Work Item Evidence BLOBs). Wrote 18 integration tests for the new `WorkItemEvidence` model and `EvidencePhase` enum.

CR-00020 adds a database schema for storing evidence screenshots/snapshots as BLOBs:
- `EvidencePhase` Python enum with `pre` and `post` values
- `WorkItemEvidence` ORM model with FK to `work_items` (without cascade)
- Unique constraint on `(project_id, work_item_id, phase, filename)`
- Index on `(project_id, work_item_id, phase)`

## Files changed

- **Added**: `tests/integration/test_work_item_evidence.py` (382 lines, 18 tests)

## Test results

**18 passed** | 0 failed

| Test class | Tests | Status |
|------------|-------|--------|
| `TestEvidencePhaseEnum` | 3 | PASS |
| `TestWorkItemEvidenceInsert` | 8 | PASS |
| `TestWorkItemEvidenceUniqueConstraint` | 2 | PASS |
| `TestWorkItemEvidenceFKNoCascade` | 3 | PASS |
| `TestWorkItemEvidenceIndex` | 1 | PASS |
| `TestWorkItemEvidenceEnumConstraint` | 1 | PASS |

## Quality checks

- **Lint (ruff)**: All checks passed ✅
- **Typecheck (mypy)**: No issues ✅

## Coverage

Tests verify:
1. `EvidencePhase` enum has `pre` and `post` values
2. `WorkItemEvidence` can be inserted and queried back
3. BLOB content is stored and retrieved correctly (binary preserved)
4. Multiple evidences per (work_item, phase) with different filenames work
5. `step_id` is nullable, `captured_at` defaults to `now()`
6. Unique constraint `uq_evidence_per_file` rejects duplicates
7. Same filename in different phase is allowed
8. FK without cascade: work_item deletion blocked when evidence exists
9. Work_item deletable when no evidence exists
10. Work_item deletable after evidence is removed first
11. Index `ix_evidence_project_item_phase` enables efficient queries
12. Invalid `EvidencePhase` values rejected at DB level

## Issues or observations

1. **FK design vs. design doc discrepancy**: The design doc comment says "evidences survive work_item deletion", but the FK is defined without `ON DELETE` clause, which defaults to `RESTRICT` in PostgreSQL. This means work_item deletion is **blocked** when evidence exists (evidences do NOT survive). To allow deletion while preserving evidences, `ON DELETE SET NULL` would be needed. The S06 code review approved the current schema as correct, so the tests reflect actual behavior.

## Conclusion

S07 (Tests) is complete. 18 integration tests written and passing against PostgreSQL testcontainer.

**Step status: complete**

**(End of file)**