# I-00062 S06 Code Review — Tests (S05)

## What Was Reviewed

Reviewed the test suite produced by S05 (`tests-impl`) for semantic correctness,
AC coverage, pre/post-fix differentiation, and compliance with CLAUDE.md conventions.

## Files Reviewed

| File | Path |
|------|------|
| Unit tests for `_agent_subprocess_env` | `tests/unit/daemon/test_agent_subprocess_env.py` |
| Integration tests for `_launch_step` env injection | `tests/integration/daemon/test_launch_step_env_isolation.py` |
| Unit tests for fail-fast guard | `tests/unit/orch_config/test_agent_context_failfast.py` |
| Integration tests for migration round-trip | `tests/integration/db/test_i_00062_migration.py` |
| Updated pre-existing unit test (S03 fix verification) | `tests/unit/test_agent_subprocess_env.py` |

## Pre-Flight Checks

| Check | Result |
|-------|--------|
| `make format` | ❌ `test_launch_step_env_isolation.py` needed reformatting (fixed by reviewer) |
| `make lint` (new files only) | ✅ All 4 new test files pass ruff and format checks |
| `tests/unit/test_agent_subprocess_env.py` | ✅ Passes ruff and format after S03 fix update |

**Issue found (fixed during review):** `tests/integration/daemon/test_launch_step_env_isolation.py` had one formatting violation (line length). Fixed with `uv run ruff format`. After fix, all 4 new files pass both `format --check` and `ruff check`.

## Test Execution

| Test File | Result |
|-----------|--------|
| `tests/unit/daemon/test_agent_subprocess_env.py` | 7 passed |
| `tests/unit/orch_config/test_agent_context_failfast.py` | 7 passed |
| `tests/integration/daemon/test_launch_step_env_isolation.py` | 2 passed |
| `tests/integration/db/test_i_00062_migration.py` | 4 passed |
| `tests/unit/test_agent_subprocess_env.py` | 11 passed (updated by S03 to reflect I-00062 strip behavior) |
| **Total** | **30 passed, 0 failed** |

Coverage failure is pre-existing and unrelated to I-00062 tests (project-wide 4-5% on partial suite run).

## Semantic Correctness Review

All assertions in the 4 new test files were evaluated. None are shape-only primary assertions.

**Examples of semantic checks found (GOOD):**
- `assert env["IW_CORE_DB_PORT"] == "36216"` — exact worktree port value
- `assert "IW_CORE_DB_PORT" not in env` — explicit absence after strip
- `assert env["IW_CORE_ORCH_DB_PORT"] == "5433"` — exact snapshot value
- `assert captured_env.get("IW_CORE_DB_HOST") == "worktree-db-host"` — exact injected value
- `with pytest.raises(RuntimeError, match="I-00062")` — specific error type + runbook ref
- `assert cols["worktree_db_host"]["nullable"] is True` — exact nullable attribute

## AC Coverage Analysis

| AC | Description | Covered By | Assessment |
|----|-------------|------------|------------|
| AC1 | Compose path injects per-worktree DB vars | `test_launch_step_env_isolation.py::test_compose_stack_injects_all_five_db_vars` | ✅ Semantic: checks exact values (host="worktree-db-host", port="36216", etc.) and asserts IW_CORE_ORCH_DB_PORT="5433" is preserved |
| AC2 | Snapshot + strip before agent launch | `test_agent_subprocess_env.py::test_snapshots_orch_creds_before_strip` + `test_strips_inherited_orch_db_vars` + `test_snapshot_does_not_overwrite_existing_orch_creds` | ✅ All three semantic; `setdefault` behavior tested with exact value assertions |
| AC3 | Fail-fast in agent context with orch port | `test_agent_context_failfast.py::test_agent_context_with_orch_port_raises` + `test_legacy_worktree_with_inherited_orch_port_raises` + `test_runbook_string_in_error_message` + `test_get_orch_db_url_does_not_apply_guard` | ✅ Layer 3 tested thoroughly: raises with exact port match; URL passes when ports differ; get_orch_db_url bypasses guard; error message contains "I-00062" |
| AC4 | Reproduction tests exist & pass | All 4 files | ✅ |
| AC5 | Migration adds 4 nullable columns, reversible | `test_i_00062_migration.py::test_upgrade_adds_four_columns` + `test_downgrade_drops_four_columns` + `test_upgrade_idempotent` + `test_re_upgrade_after_downgrade` | ✅ All 4 columns checked individually; nullable asserted per-column; uses PREV_REVISION (not -1) per project rule |
| AC6 | Browser-verification env injection still wins | `test_agent_subprocess_env.py::TestBrowserVerificationEnvStillWins::test_bv_env_overrides_strip` | ✅ Semantic: asserts exact e2e port "39999" and e2e host, not just presence |

## Pre-Fix vs Post-Fix Behavior

The S05 report documents pre-fix vs post-fix expectations per test. Spot-check of key tests:

- **`test_strips_inherited_orch_db_vars`**: Pre-fix, `os.environ.copy()` leaks 5433 into env — test asserts `"IW_CORE_DB_PORT" not in env`, which FAILS pre-fix. Post-fix strip removes it — PASSES. ✅
- **`test_snapshots_orch_creds_before_strip`**: Pre-fix, no snapshot code exists — `IW_CORE_ORCH_DB_PORT` unset → assertion `== "5433"` FAILS. Post-fix snapshot runs first → PASSES. ✅
- **`test_compose_stack_injects_all_five_db_vars`**: Pre-fix, no injection block in `_launch_step`, env remains 5433 — assertion `== "36216"` FAILS. Post-fix injection sets it → PASSES. ✅
- **`test_agent_context_with_orch_port_raises`**: Pre-fix, no guard in `get_db_url()` — no exception raised. Post-fix guard fires → RuntimeError with "I-00062". ✅
- **`test_legacy_worktree_with_inherited_orch_port_raises`**: Pre-fix twice (no snapshot AND no guard) — no RuntimeError. Post-fix: snapshot sets `IW_CORE_ORCH_DB_PORT`, guard fires → RuntimeError. ✅

## Test Isolation Compliance

- ✅ No `importlib.reload(orch.config)` — all tests use `monkeypatch.setenv/delenv`
- ✅ No live DB connections (port 5433) — all use testcontainers
- ✅ `test_i_00062_migration.py` replaces `postgresql+psycopg2://` with `postgresql+psycopg://`
- ✅ Migration test uses `PREV_REVISION` ("4876b3246ff2"), not `-1`, per project rule
- ✅ Integration tests use `db_session` fixture (testcontainer-backed) — no direct engine creation outside fixture

## Edge Case Coverage

| Edge Case | Covered By |
|-----------|------------|
| Operator context (no `IW_CORE_AGENT_CONTEXT`) bypasses guard | `test_operator_context_with_orch_port_passes` — passes even with 5433 |
| `IW_CORE_ORCH_DB_PORT` unset → guard does nothing | `test_guard_does_not_fire_when_orch_port_not_set` — URL returned normally |
| `get_orch_db_url()` is NOT guarded | `test_get_orch_db_url_does_not_apply_guard` — returns 5433 in agent context |
| `extra` dict wins over strip | `test_extra_overrides_strip` + `test_bv_env_overrides_strip` — exact values checked |
| `setdefault` doesn't overwrite existing `IW_CORE_ORCH_DB_*` | `test_snapshot_does_not_overwrite_existing_orch_creds` — "preset-host" preserved |

## Test Naming & Organization

- ✅ File paths: `tests/unit/<area>/test_<topic>.py`, `tests/integration/<area>/test_<topic>.py`
- ✅ Class names describe behavior, not function: `TestAgentSubprocessEnvDoesNotLeakOrchDB`, `TestLaunchStepInjectsWorktreeDBEnv`, `TestAgentContextFailFast`
- ✅ Test methods start with `test_` and read as sentences
- ✅ Integration tests marked with `@pytest.mark.integration`

## Findings

No CRITICAL, HIGH, or MEDIUM (fixable) issues found.

### Observations (Non-Blocking)

1. **Migration revision hardcoded in test file**: `test_i_00062_migration.py` hardcodes `MIGRATION_REV = "4cc043748e92"` and `PREV_REVISION = "4876b3246ff2"`. If a rebase lands new migrations between PREV_REVISION and I-00062's revision before this merges, the test's `command.downgrade(alembic_cfg, PREV_REVISION)` would fail. However, this is standard project practice (see `test_migration_impacted_paths_backfill.py`) and the daemon's migration pipeline handles rebase ordering at merge time.

2. **Format fix applied during review**: `test_launch_step_env_isolation.py` required reformatting (line too long at line 162). Fixed with `uv run ruff format`. Post-fix, all 4 new test files pass format and lint checks. No re-formatting needed in the implementation code (orch/config.py, batch_manager.py etc. are S03's responsibility).

## Verdict

**PASS** — all tests are semantically correct, cover all 6 ACs, differentiate pre-fix from post-fix behavior correctly, and comply with project conventions.

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00062",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "30 passed, 0 failed (4 new test files + 1 updated pre-existing file)",
  "notes": "Format fix applied to test_launch_step_env_isolation.py (line length). After fix, all 4 new test files pass make format and make lint. All ACs covered with semantic assertions. Pre/post-fix differentiation correctly documented by S05."
}
```