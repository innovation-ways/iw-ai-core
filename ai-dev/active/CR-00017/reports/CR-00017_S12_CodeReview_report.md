# CR-00017 S12 — Code Review Report

## What Was Reviewed

S11 (tests-impl) implementation for the daemon-only migration application (CR-00017).

## Files Changed by S11

- `tests/unit/test_safe_migrate_guards.py` — extended with guard permutation tests
- `tests/unit/test_safe_migrate.py` — smoke tests for safe_migrate
- `tests/unit/test_migrations_cli.py` — CLI exit code tests
- `tests/unit/test_merge_queue_cli.py` — merge-queue CLI tests
- `tests/unit/test_migration_pipeline.py` — pipeline unit tests
- `tests/integration/test_migration_pipeline.py` — 3-phase pipeline integration tests
- `tests/integration/test_migration_pipeline_frozen.py` — frozen-state integration tests
- `tests/integration/test_agent_migrate_guard.py` — agent-context guard integration tests
- `tests/integration/test_agent_constraints_coverage.py` — extended with R2 marker

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| `test_safe_migrate_guards.py` | 15 | PASS |
| `test_safe_migrate.py` | 8 | PASS |
| `test_migrations_cli.py` | 10 | PASS |
| `test_merge_queue_cli.py` | 7 | PASS |
| `test_migration_pipeline.py` (unit) | 10 | PASS |
| `test_migration_pipeline.py` (integration) | 6 | PASS |
| `test_migration_pipeline_frozen.py` | 2 | PASS |
| `test_agent_migrate_guard.py` | 2 | PASS |
| `test_agent_constraints_coverage.py` | 31 | PASS |
| **Total** | **91** | **All pass** |

## Checklist Findings

### 1. No live-DB leaks ✅
- All 5433 references in S11 test files are synthetic test values or pre-existing config fixtures
- `test_safe_migrate_guards.py:73` uses `localhost:5433` as a mocked URL value (no real connection)
- `test_migration_pipeline.py` uses `DUMMY_DB_URL` and mocks `safe_dry_run`/`safe_apply` — no real DB connections
- psycopg v3 URL replacement pattern present in all testcontainers fixtures

### 2. Coverage matrix ✅

| AC | Requirement | Test(s) | Status |
|----|-------------|---------|--------|
| AC1 | Agent-context guard blocks application | `test_safe_migrate_guards.py::TestAgentContextGuardSemantics` (9 parametrized cases); `test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context`; `test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context`; `test_agent_migrate_guard.py::test_agent_cannot_apply_migration` (CLI exit 2) | ✅ |
| AC2 | Phase 1 dry-run rejects broken migration | `test_migration_pipeline.py::test_dry_run_rejects_broken_migration` | ✅ |
| AC3 | Happy path through apply | `test_migration_pipeline.py::test_pipeline_happy_path` | ✅ |
| AC4a | Apply fails → rollback succeeds | `test_migration_pipeline.py::test_apply_fails_rollback_succeeds` | ✅ |
| AC4b | Apply fails → rollback fails → frozen | `test_migration_pipeline.py::test_apply_fails_rollback_fails_freezes_queue` | ✅ |
| AC5a | Frozen blocks merges | `test_migration_pipeline.py::test_frozen_queue_blocks_merges` | ✅ |
| AC5b | Operator unfreeze resumes | `test_migration_pipeline_frozen.py::test_unfreeze_logs_ack_reason` | ✅ |
| AC5c | Agent cannot unfreeze | `test_migration_pipeline_frozen.py::test_unfreeze_refuses_in_agent_context` | ✅ |
| AC6 | Multi-head rejected | `test_migration_pipeline.py::test_multi_head_state_rejected`; `test_safe_migrate.py::TestListPendingRevisions::test_multiple_heads_raises` | ✅ |
| AC7 | CLI exit codes | `test_migrations_cli.py::TestApplyRefusesWithoutOperatorFlag`; `test_migrations_cli.py::TestDryRun::test_dry_run_failure_exit_code`; `test_merge_queue_cli.py` | ✅ |
| AC8 | R2 marker coverage | `test_agent_constraints_coverage.py::test_prompt_template_contains_migrations_rule` (12 templates parametrized); `test_claude_md_references_migrations_policy` | ✅ |
| AC9 | Observability | Manual verification (smoke) | N/A |
| AC10 | No regression | `make check` | N/A |

### 3. Guard permutation test ✅
`TestAgentContextGuardSemantics` in `test_safe_migrate_guards.py` covers:
- Negative: `"TRUE"`, `"True"`, `"1"`, `"yes"`, `"YES"`, `"true\n"`, `" true"`, `""`, `None`
- Positive: `"true"` only

Module-level docstring in `test_safe_migrate_guards.py:26-31` documents the exact-string semantic rationale.

### 4. Frozen-queue tests ✅
- `test_unfreeze_refuses_in_agent_context` — subprocess with env=true → exit 2
- `test_unfreeze_logs_ack_reason` — writes `DaemonEvent`, verifies `acknowledged_by` + `active=False`
- `test_frozen_queue_blocks_merges` — mocked `is_merge_queue_frozen` → `process_merge_queue` skips
- `test_apply_fails_rollback_fails_freezes_queue` — both fail → `frozen=True`

### 5. Coverage test extension ✅
- `MARKER_R2 = "⛔ Migrations: agents generate, daemon applies"` added
- `test_prompt_template_contains_migrations_rule` parametrized over all 12 templates
- Original R1 check (`test_prompt_template_contains_docker_rule`) still present
- `test_policy_doc_exists_and_includes_rule` asserts both R1 and R2 markers present

### 6. Mutation verification ⚠️ MEDIUM
S11 report does not document a mutation test (remove R2 marker → coverage test fails with file name). This verification step should be performed and documented.

### 7. Subprocess env test ⚠️ MEDIUM
`test_agent_env_propagates_to_subprocess` calls `_build_agent_env()` directly and asserts on the returned dict — it does NOT spawn an actual subprocess stub. However, `test_agent_cannot_apply_migration` does use `subprocess.run()` to verify CLI exit 2, which partially covers the intent. Strictly, the checklist requirement is not met by the named test alone.

### 8. Test speed ✅
- Unit tests: 50 passed in 0.39s
- Integration tests: 41 passed in 20.71s (includes testcontainer startup/teardown)
- All within acceptable limits

### 9. No destructive live-DB operations ✅
- No test stops/starts/removes the production `postgres` container
- No test writes to `/opt/postgres/data`
- `testcontainers` used correctly with self-destruct (Ryuk)

## Issues Found

### MEDIUM — Mutation verification not documented
The S11 report does not describe removing the R2 marker from a template file and verifying that `test_prompt_template_contains_migrations_rule` fails with the specific file name. This verification should be performed and added to the report.

### MEDIUM — Subprocess env test doesn't actually spawn subprocess
`test_agent_env_propagates_to_subprocess` (line 79-95 of `test_agent_migrate_guard.py`) calls `_build_agent_env()` directly and asserts on the returned dictionary. It does not use `subprocess.run()` or similar to actually spawn a subprocess and verify the env is present. The functional requirement is partially covered by `test_agent_cannot_apply_migration`, which does use `subprocess.run()` and verifies exit 2.

## Severity Assessment

- **CRITICAL**: None
- **HIGH**: None — all ACs have corresponding tests
- **MEDIUM**: 2 (mutation verification not documented; subprocess test doesn't spawn subprocess)
- **LOW**: 2 (SIM117 warnings in new test file; unregistered `@pytest.mark.slow` mark)

## Overall Assessment

S11 tests are well-structured and comprehensive. All 10 ACs have corresponding test coverage. Test isolation is correct — no live DB connections. The two MEDIUM issues are documentation/completeness gaps rather than functional defects. Recommend: fix the subprocess test to actually spawn a subprocess stub, and add mutation verification documentation to the report.

## Recommendation

**APPROVE with fixes required** — Address the two MEDIUM items before S13 (final review).
