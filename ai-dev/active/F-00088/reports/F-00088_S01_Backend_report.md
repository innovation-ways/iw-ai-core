# F-00088 S01 Backend Report

## Step: S01 — E2E Harness Foundation

**Agent**: backend-impl
**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Status**: `complete`

---

## What Was Done

Created the complete E2E browser-test harness infrastructure under `tests/e2e/`:

### Files Created

| File | Purpose |
|------|---------|
| `tests/e2e/__init__.py` | Empty package marker |
| `tests/e2e/.gitignore` | Ignores `_artifacts/` (screenshot output) |
| `tests/e2e/playwright_wrapper.py` | Thin subprocess wrapper around `~/.local/bin/playwright-cli` |
| `tests/e2e/conftest.py` | Fixtures: `base_url`, `pw`, `evidence_dir` |
| `tests/e2e/test_journey_home_navigation.py` | Journey 1 (marked `e2e` + `e2e_smoke`) |
| `tests/e2e/test_harness_selfcheck.py` | Unmarked harness unit tests |

### Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Registered `e2e` + `e2e_smoke` markers; extended `addopts` `-m` filter with `and not e2e` |
| `Makefile` | Added `test-e2e` and `test-e2e-smoke` targets + both names to `.PHONY` |

### Key Implementation Decisions

1. **`playwright_wrapper.py`**: All browser interactions are subprocess calls to `playwright-cli`. The binary is verified at import time (`RuntimeError` if absent). Exposes: `open_url`, `goto`, `snapshot`, `click`, `fill`, `eval_js`, `screenshot`, `read_console_errors`, `assert_no_console_errors`, `accessibility_check`, `assert_accessibility`.

2. **`conftest.py`**: `base_url` fixture reads `$IW_BROWSER_BASE_URL` and skips (fixture-scoped, not module-scoped) when unset — the harness self-check unit tests (no `base_url`/`pw` dependency) still run. The `pw` fixture runs `kill-all` at setup and teardown. The `evidence_dir` fixture reads `$IW_E2E_EVIDENCE_DIR` (defaults to `tests/e2e/_artifacts/`).

3. **`test_journey_home_navigation.py`**: Full home → project → cross-tab navigation journey with no auth step. Documents the in-scope fail-ability assertion: the `assert len(project_links) > 0` check at step 2 would fail if inverted to `== 0` (the test fails when seed data is present, proving it can detect regressions).

4. **`test_harness_selfcheck.py`**: 10 unmarked unit tests exercising the pure failure-detection logic with synthetic input — no browser, no E2E stack. All 10 pass consistently (verified 3× in a row). All pass the `make test-assertions` scanner.

5. **`pyproject.toml`**: `addopts` extended from `-m 'not browser and not quarantine and not contract_fuzz'` → `-m 'not browser and not quarantine and not contract_fuzz and not e2e'` (literal find-replace on the current `addopts` value, not a hardcoded assumption).

6. **Console error detection**: The `lstrip` pattern was tightened to `"([{ :"` (strip leading `(`, `[`, `{`, space, `:`) to correctly handle `[error]`, `(error)`, `{error}`, and `error:` prefixed lines. Verified with `make test-assertions` clean.

---

## Test Verification

### Default collection — no E2E journeys collected
```
uv run pytest tests/e2e/ --collect-only -q --no-cov
→ 10/11 tests collected (1 deselected)
→ Only test_harness_selfcheck.py tests are collected; test_journey_home_navigation is deselected by addopts -m filter
```

### Smoke selection — exactly the smoke test
```
uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q --no-cov
→ 1/11 tests collected (10 deselected)
→ test_journey_home_navigation collected
```

### Harness self-check — all 10 pass (3 consecutive runs)
```
uv run pytest tests/e2e/test_harness_selfcheck.py -v --no-cov
→ 10 passed in 0.17–0.19s (consistent across runs)
```

---

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make typecheck` | ✅ Success: no issues in 274 source files |
| `make format` | ✅ All files formatted |
| `make test-assertions` | ✅ No new violations (550 files scanned) |
| `make quality` | ✅ All pass (dep-check is warn-only per project policy) |

---

## TDD RED Evidence

Harness self-check tests written before the corresponding helper logic was committed. RED run captured:

```
tests/e2e/test_harness_selfcheck.py::TestReadConsoleErrors::test_flags_error_level_line FAILED
tests/e2e/test_harness_selfcheck.py::TestAssertNoConsoleErrors::test_raises_on_error_in_log FAILED

AssertionError: assert 0 == 1   # read_console_errors returned [] instead of ['[error] Something went wrong']
Failed: DID NOT RAISE <class 'AssertionError'>  # assert_no_console_errors() passed when it should have raised
```

GREEN after console-error detection logic was implemented and the `lstrip` pattern was corrected:
```
10 passed in 0.19s
```

**No production code was edited.** All changes are confined to `tests/e2e/`, `pyproject.toml`, and `Makefile` — exactly the scope defined by `scope.allowed_paths`.

---

## Git Scope Verification

```
git status --short
M Makefile
M pyproject.toml
A tests/e2e/.gitignore
A tests/e2e/__init__.py
A tests/e2e/conftest.py
A tests/e2e/playwright_wrapper.py
A tests/e2e/test_harness_selfcheck.py
A tests/e2e/test_journey_home_navigation.py
```

**Zero changes to `orch/`, `dashboard/`, `executor/`, or any production code.**

---

## Notes

- The `playwright-cli` binary was confirmed present at `~/.local/bin/playwright-cli`.
- `pytest-randomly` is on by default — all E2E journey tests are order-independent: each journey sets up its own browser state via `pw.kill_all()` + `_wipe_playwright_artifacts()`.
- The `test_harness_selfcheck.py` tests were originally written before the implementation (RED-first). The RED run showed `read_console_errors()` returning `[]` when a synthetic error log existed — confirming the detection logic was missing. After fixing the `lstrip` pattern the tests all passed.
- The E2E stack is not running in this environment — `test_journey_home_navigation.py` cannot be executed here (its `pw` fixture would skip with `E2E_STACK_MISSING`). The actual live-stack verification happens at S14 (qv-browser step).
- `scope.allowed_paths` is enforced at merge time — this step touches no production code.