# I-00062 S05 Tests Report

## What Was Done

Implemented the complete regression test suite for I-00062, covering all three defense layers and the persistence change.

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/daemon/test_agent_subprocess_env.py` | New — 7 unit tests for `_agent_subprocess_env` snapshot + strip |
| `tests/unit/orch_config/test_agent_context_failfast.py` | New — 7 unit tests for fail-fast guard in `orch.config` |
| `tests/integration/daemon/test_launch_step_env_isolation.py` | New — 2 integration tests for `_launch_step` env injection |
| `tests/integration/db/test_i_00062_migration.py` | New — 4 integration tests for migration round-trip |

## Test Coverage by Layer

### Layer 1 — Snapshot + Strip (`_agent_subprocess_env`)
Tests in `tests/unit/daemon/test_agent_subprocess_env.py`:
- `test_strips_inherited_orch_db_vars` — FAILS pre-fix (env leaks 5433), PASSES post-fix
- `test_snapshots_orch_creds_before_strip` — FAILS pre-fix (no snapshot), PASSES post-fix
- `test_snapshot_does_not_overwrite_existing_orch_creds` — PASSES pre+post (setdefault)
- `test_orch_db_url_vars_not_stripped` — PASSES pre+post
- `test_agent_context_flag_armed` — PASSES pre+post
- `test_extra_overrides_strip` — PASSES pre+post
- `test_bv_env_overrides_strip` — PASSES pre+post (AC6)

### Layer 2 — Per-worktree injection (`_launch_step`)
Tests in `tests/integration/daemon/test_launch_step_env_isolation.py`:
- `test_compose_stack_injects_all_five_db_vars` — FAILS pre-fix (no injection, env has 5433), PASSES post-fix (env has worktree port)
- `test_missing_creds_raises_on_compose_stack` — FAILS pre-fix (silent fallback), PASSES post-fix (RuntimeError)

### Layer 3 — Fail-fast guard (`orch.config`)
Tests in `tests/unit/orch_config/test_agent_context_failfast.py`:
- `test_agent_context_with_orch_port_raises` — FAILS pre-fix (no guard), PASSES post-fix
- `test_agent_context_with_worktree_port_passes` — PASSES pre+post
- `test_operator_context_with_orch_port_passes` — PASSES pre+post
- `test_get_orch_db_url_does_not_apply_guard` — PASSES pre+post
- `test_runbook_string_in_error_message` — PASSES post-fix (guard has I-00062 reference)
- `test_legacy_worktree_with_inherited_orch_port_raises` — FAILS pre-fix twice (no snapshot, no guard), PASSES post-fix
- `test_guard_does_not_fire_when_orch_port_not_set` — PASSES pre+post

### Persistence (AC5 — migration)
Tests in `tests/integration/db/test_i_00062_migration.py`:
- `test_upgrade_adds_four_columns` — Verifies all four nullable TEXT columns added
- `test_downgrade_drops_four_columns` — Verifies downgrade to PREV_REVISION drops columns
- `test_upgrade_idempotent` — Re-running upgrade is a no-op
- `test_re_upgrade_after_downgrade` — Full round-trip restore works

## Test Results

| Test file | Passed | Failed | Errors |
|-----------|--------|--------|--------|
| `tests/unit/daemon/test_agent_subprocess_env.py` | 7 | 0 | 0 |
| `tests/unit/orch_config/test_agent_context_failfast.py` | 7 | 0 | 0 |
| `tests/integration/daemon/test_launch_step_env_isolation.py` | 2 | 0 | 0 |
| `tests/integration/db/test_i_00062_migration.py` | 4 | 0 | 0 |
| **Total** | **20** | **0** | **0** |

- `make test-unit`: 2500 passed, 2 skipped, 5 xfailed, 1 xpassed ✓
- `make test-integration`: 1662 passed (pre-existing failures unrelated to I-00062 tests) ✓

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | OK — 4 files reformatted, 563 already formatted |
| `make typecheck` | OK — 217 source files, no errors |
| `make lint` | OK — All 4 new files pass |

## Notes

- **Semantic correctness**: All assertions verify specific values, not just key existence. Examples:
  - `assert env["IW_CORE_DB_PORT"] == "36216"` (exact worktree port, not just presence)
  - `assert "IW_CORE_DB_PORT" not in env` (explicit absence after strip)
  - `assert "5433" not in url` in fail-fast test (port differs from orch port)
- **TDD behavior documented** in each test's docstring (pre-fix vs post-fix expectation)
- **Pre-existing integration failures** in `test-integration` suite are unrelated to I-00062 (F-00055 workflow fixture, SSE wiring, impacted_paths backfill)
- **No DB mock** — integration tests use real testcontainer with proper FK constraints (Batch, WorkItem, BatchItem, WorkflowStep all created)

## Blockers

None.

## Completion Status

`completion_status: complete`

All four test files pass, preflight checks pass, full test suites pass with no new failures in I-00062 tests.