# I-00061 S04 Code Review Report — Tests

## What Was Reviewed

The test suite written in S03 for I-00061 (auto-skip phantom QV gates at item approval).

**Files reviewed:**
- `tests/unit/test_qv_gate_validator.py` — 38 unit tests (new)
- `tests/integration/test_phantom_gate_auto_skip.py` — 5 integration tests (new)

**Supporting files cross-referenced:**
- `tests/integration/conftest.py` — testcontainer fixtures
- `tests/conftest.py` — shared fixtures
- `tests/CLAUDE.md` — testing conventions
- `orch/qv_gate_validator.py` — S01 implementation (already reviewed in S02)

---

## Pre-Review Lint & Format Gate

| Check | Result |
|-------|--------|
| `make lint` (ruff on all files) | 8 errors in `scripts/arch_check.py` — pre-existing, NOT in test files |
| `make format-check` | `565 files already formatted` |
| `uv run ruff check` on test files | **All checks passed** |
| `uv run ruff format --check` on test files | **3 files already formatted** |

**Verdict:** Tests are lint-clean and format-clean. The lint errors in `scripts/arch_check.py` are pre-existing and unrelated to S03.

---

## AC Coverage Map

| AC | Requirement | Test(s) | Coverage |
|----|-------------|---------|----------|
| AC1 | Phantom Makefile gate auto-skipped at `iw approve` | `test_iw_approve_auto_skips_phantom_makefile_gate` | ✅ Semantic: asserts `status == StepStatus.skipped`, `reason == "missing_makefile_target"`, `trigger == "approve"` |
| AC2 | Phantom `cd <dir>` gate auto-skipped at `iw approve` | `test_iw_approve_auto_skips_phantom_cd_gate` | ✅ Semantic: asserts `status == StepStatus.skipped`, `reason == "missing_directory"`, `trigger == "approve"` |
| AC3 | Real gates are NOT skipped | `test_iw_approve_does_not_skip_real_gates` | ✅ Semantic: asserts `auto_skipped_steps == []`, `DaemonEvent.count() == 0`, all steps stay `pending` |
| AC4 | Batch-approve safety net | `test_iw_batch_approve_runs_safety_net` | ✅ Semantic: simulates drift (Makefile target removed after approval), asserts step skipped with `trigger == "batch_approve"` and correct reason |
| AC5 | Regression test exists | Entire file existence + passing run | ✅ The file exists, runs, and passes |

---

## Semantic Correctness

All assertions verify **specific values**, not just shape. Key examples:

| Test | Assertion | Verdict |
|------|-----------|---------|
| AC1 | `assert s03_db.status == StepStatus.skipped` | ✅ Specific status |
| AC1 | `assert ev.event_metadata["reason"] == "missing_makefile_target"` | ✅ Specific reason string |
| AC1 | `assert ev.event_metadata["trigger"] == "approve"` | ✅ Specific trigger value |
| AC2 | `assert ev.event_metadata["reason"] == "missing_directory"` | ✅ Specific reason string |
| AC3 | `assert out.get("auto_skipped_steps", []) == []` | ✅ Specific empty list |
| AC4 | `assert ev.event_metadata["trigger"] == "batch_approve"` | ✅ Specific trigger value |

No shape-only assertions found. The I003 lesson is properly applied.

---

## Real-Fixture Honesty

**Unit tests (`test_qv_gate_validator.py`):**
- Use `tmp_path` (filesystem) for `repo_root` — no mocking of `validate_qv_gate`, `classify_qv_gate`, or `_makefile_has_target`
- Uses real `Path` operations and `shutil.which` — no `patch` of `shutil.which` (correct, as noted in the design doc: conservative approach means bare exec doesn't call `which`)
- No `Mock`, `MagicMock`, or `patch` found in the file

**Integration tests (`test_phantom_gate_auto_skip.py`):**
- Uses real PostgreSQL testcontainer via `db_session` fixture
- Uses real `CliRunner` invoking actual CLI commands (`iw approve`, `iw batch-approve`)
- Uses real `tmp_path` for `repo_root` with real `Makefile` filesystem operations
- No mocks found that replace `validate_qv_gate`, `classify_qv_gate`, `auto_skip_phantom_qv_gates`, or any DB function
- `cli_get_session` fixture injects the test DB session into CLI commands (never touches `orch.db.session`)

**FTS DDL:** Integration test fixture (`db_engine`) runs `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — ✅ confirmed.

---

## RED-GREEN Verification

S03 report documents RED-GREEN check with:
- **RED (pre-fix):** Test fails with `auto_skipped_steps == []` (phantom gate stays `pending`)
- **GREEN (post-fix):** Test passes — S03 is `skipped`, `DaemonEvent` audit row present
- Approach: temporarily removed `qv_gate_validator.py` from package, reverted CLI hooks to main-branch versions

The report quotes failing test output from the RED phase. ✅

---

## Test Isolation

- Each integration test uses isolated item IDs (`I-99001`, `I-99002`, `I-99003`, `I-99004`, `I-99101-I-99103`)
- Tests use the `db_session` transactional fixture (rollback after each test)
- `tmp_project_with_makefile` fixture updates `test_project.repo_root` in-place within the test transaction (avoids duplicate-key conflicts)
- No shared state between tests

---

## Edge Case Coverage

| Edge Case | Covered By |
|-----------|-----------|
| `make` with no Makefile at all (validator must not crash) | `test_makefile_file_missing_phantom` — `_makefile_has_target` returns `False`, `classify_qv_gate` returns `missing_makefile_file` |
| `cd <dir>` where `<dir>` is a regular file | `test_cd_dir_is_a_file_phantom` — creates a file, verifies `reason == "missing_directory"` |
| Bare-exec phantom (binary not on PATH) | `test_bare_exec_off_path_still_runnable` — confirms conservative default (still treated as runnable, as designed) |
| Unknown shell pipeline | `test_unknown_shape_returns_runnable` — `foo \| bar \| baz > out.txt` returns `runnable=True` (conservative) |
| `make` with no target | `test_make_with_no_target_returns_runnable` — returns `runnable=True` (conservative) |
| Command with env-var prefix | `test_command_with_envvars_returns_runnable` — `FOO=1 some-command` returns `runnable=True` (conservative) |
| Empty `quality_validation` list | Indirectly covered: `auto_skip_phantom_qv_gates` queries zero steps, returns `[]` |
| Item with mixed real and phantom gates | AC1 test: S02 `make lint` (real, stays pending), S03 `make arch-check` (phantom, skipped) |
| Batch with multiple items, mixed gates | `test_iw_batch_approve_handles_multiple_items` — 3 items, each with S01 lint (real) + S02 arch-check (phantom), all 3 phantoms skipped |

All identified edge cases are covered. ✅

---

## Project Conventions Compliance

| Convention | Status |
|------------|--------|
| psycopg2 URL replacement in testcontainer | ✅ `pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")` in `conftest.py` |
| FTS DDL after `Base.metadata.create_all()` | ✅ `FTS_FUNCTION_SQL`, `FTS_TRIGGER_SQL`, `PROJECT_DOCS_FTS_*`, `FUNCTIONAL_DOC_FTS_*` all executed |
| No `importlib.reload(orch.config)` | ✅ Not found in either test file |
| No `Mock`/`patch` of DB in integration tests | ✅ Confirmed by grep |
| No `Mock`/`patch` of validator functions in unit tests | ✅ Confirmed by grep |
| Session-scoped container, function-scoped transactions | ✅ `pg_container` session scope, `db_session` function scope |

---

## Test Verification

| Suite | Command | Result |
|-------|---------|--------|
| Unit | `uv run pytest tests/unit/test_qv_gate_validator.py -v` | **38 passed** ✅ |
| Integration | `uv run pytest tests/integration/test_phantom_gate_auto_skip.py -v` | **5 passed** ✅ |
| Full unit | `make test-unit` | **2524 passed, 2 skipped, 5 xfailed, 1 xpassed** ✅ (coverage: 52.80% > 46% threshold) |

**No flakes detected.** Tests pass cleanly across multiple runs.

---

## Migrations Check

`git diff HEAD -- orch/db/migrations/` returns empty — S03 made **no alembic changes**. ✅ Confirms the "migrations: agents generate, daemon applies" policy.

---

## Finding Summary

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM_FIXABLE | 0 | — |
| LOW | 0 | — |

Zero findings. The test suite is correct, complete, and compliant.

---

## Verdict

```
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00061",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "43 passed (38 unit + 5 integration), 0 failed",
  "notes": "RED-GREEN verified by S03 report. No mocks in real-fixture tests. All ACs semantically covered. All edge cases covered. Tests are lint-clean, format-clean, and isolation-safe."
}
```