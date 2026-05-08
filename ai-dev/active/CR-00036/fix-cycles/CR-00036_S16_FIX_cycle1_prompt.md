# CR-00036 S16 QV Fix Cycle 1/5

Quality gate S16 for work item CR-00036 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00036/ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                  192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                  58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                     94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                          360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33     20      8      1    34%   36-62
--------------------------------------------------------------------------------------
TOTAL                                      20874   7273   5820    848    61%

24 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 61.10%
=========================== short test summary info ============================
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_downgrade_drops_four_columns
FAILED tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade
FAILED tests/integration/test_alembic_guard_integration.py::TestGuardBehindHead::test_guard_fails_when_behind_one_revision
FAILED tests/integration/test_alembic_guard_integration.py::TestCheckDbAtHead::test_check_db_at_head_not_ok_when_behind
FAILED tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid
FAILED tests/integration/test_doc_index_jobs_migration.py::test_downgrade_and_upgrade_round_trip
FAILED tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
FAILED tests/integration/test_migration_roundtrip.py::test_migration_roundtrip[1713bc13]
FAILED tests/integration/test_migration_roundtrip.py::test_migration_roundtrip[7fcf3dda]
FAILED tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head
FAILED tests/integration/test_pending_migration_log_migration.py::test_downgrade_drops_table
FAILED tests/integration/test_pending_migration_log_migration.py::test_upgrade_recreates_table_empty
= 14 failed, 1972 passed, 32 skipped, 1 xfailed, 158 warnings in 499.62s (0:08:19) =
make: *** [Makefile:55: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
