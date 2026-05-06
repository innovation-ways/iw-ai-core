# I-00071 S04 Code Review Report

## Review Summary

Reviewed S03 (tests-impl) implementation against the design doc (`I-00071_Issue_Design.md`) and CLAUDE.md conventions. Pre-flight lint and format gates both pass. 39 I-00071 test cases added; 2 fail due to a logic bug in the production code (`scope_overlap.find_blocking_items` sibling check applies `_same_parent` to raw unfiltered paths, bypassing `_strip_test_globs`). The tests are correct and correctly expose the bug.

---

## Pre-Flight Quality Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | PASS | Zero violations in S03 files |
| `make format-check` | PASS | All 611 files already formatted |

---

## 1. Reproduction Test Validity

All S03 tests use exact equality assertions (`==` for paths, `is True`/`is False` for booleans) per the I003 lesson and design doc requirement.

**`tests/unit/test_design_doc_parser.py::TestImpactedPathsBacktickStripping`** (4 tests):

| Test | Assertion | Verdict |
|------|-----------|---------|
| `test_strips_surrounding_code_span_backticks_in_bullet_lines` | `result.paths == ["dashboard/CLAUDE.md", "dashboard/static/clipboard.js", "tests/dashboard/test_i00071.py"]` | **PASS** — exact equality, not substring |
| `test_strips_surrounding_code_span_backticks_in_fenced_code_block` | `result.paths == ["orch/foo.py", "orch/bar/**"]` | **PASS** — exact equality |
| `test_bare_paths_without_backticks_still_parse_unchanged` | `result.paths == ["orch/foo.py", "orch/bar/**"]` | **PASS** — regression |
| `test_mixed_wrapped_and_bare_paths` | `result.paths == ["orch/foo.py", "orch/bar/baz.py"]` | **PASS** — mixed case |

**`tests/unit/daemon/test_scope_overlap.py::TestIsTestPath`** (23 parametrized cases):

All cases use `assert is_test_path(path) is expected` — specific Boolean, not truthy. I-00071 cases confirmed:
- `("tests/dashboard/test_x.py", True)` ✓
- `("test/foo.py", True)` ✓
- `("__tests__/bar.py", True)` ✓
- `("tests/conftest.py", True)` ✓
- Plus wider regression coverage for nested paths, integration dirs, conftest variants ✓

**`tests/unit/test_batch_planner_dependencies.py`** (8 parametrized cases):

Parity test `test_batch_planner_is_test_path_matches_scope_overlap` asserts both helpers agree on every fixture using `is expected` — divergence guard in place ✓

---

## 2. Coverage Completeness (TDD Approach Cross-Check)

| Design Doc Bullet | Coverage | Test(s) |
|-------------------|----------|---------|
| Bullet-list backtick stripping | ✓ | `test_strips_surrounding_code_span_backticks_in_bullet_lines` |
| Fenced-code-block backtick stripping | ✓ | `test_strips_surrounding_code_span_backticks_in_fenced_code_block` |
| Bare paths (regression — no corruption) | ✓ | `test_bare_paths_without_backticks_still_parse_unchanged` |
| Mixed wrapped/bare paths | ✓ | `test_mixed_wrapped_and_bare_paths` |
| Relative `tests/`, `test/`, `__tests__/` recognition | ✓ | 9 `is_test_path` parametrized cases |
| Existing `is_test_path` cases still pass | ✓ | 14 pre-existing + new parametrize cases |
| BATCH-00078 scenario reproduction | ✓ | `TestI00071RegressionBatch00078::test_two_items_both_only_test_files_under_same_dir_do_not_block` (FAILS — exposes production bug) |
| Non-test sibling overlap still fires | ✓ | `test_non_test_sibling_still_blocks` — PASS |
| `batch_planner._is_test_path` parity test | ✓ | `test_batch_planner_is_test_path_matches_scope_overlap` — 8/8 PASS |

**Missing coverage**: None — all TDD bullets are covered.

---

## 3. Test Isolation & Determinism

- All tests are pure-helper unit tests — no DB, no I/O, no monkeypatching of stdlib.
- No filesystem dependencies.
- No test class or function imports `orch.config` at module level.
- Tests use only `pytest` fixtures; no testcontainer involvement.
- **Result**: Tests are fully isolated and run in any order ✓

---

## 4. Naming & Style

- All test names start with `test_` ✓
- All test names describe behaviour (e.g. `test_strips_surrounding_code_span_backticks_in_bullet_lines`) ✓
- Class names use CapWords: `TestImpactedPathsBacktickStripping`, `TestI00071RegressionBatch00078` ✓
- I-00071 tag present in docstrings: `"I-00071 RED: ..."` ✓

---

## 5. Production Code Untouched by S03

S03 added tests only. The uncommitted working-tree changes to `orch/design_doc_parser.py`, `orch/daemon/scope_overlap.py`, and `orch/batch_planner.py` are S01's fixes (backend-impl), NOT S03 modifications.

Confirmed via `git status`: S03 changed only:
- `tests/unit/test_design_doc_parser.py` (appended class)
- `tests/unit/daemon/test_scope_overlap.py` (appended class + parametrize extension)
- `tests/unit/test_batch_planner_dependencies.py` (appended test)

**No production code was modified by S03** ✓

---

## 6. CLAUDE.md Compliance

- Tests live under `tests/unit/` ✓
- No live-DB connections ✓
- No `importlib.reload(orch.config)` ✓
- No `dashboard.routers.*` or `dashboard.dependencies` imports at module level ✓

---

## 7. Test Verification

```
uv run pytest tests/unit/test_design_doc_parser.py::TestImpactedPathsBacktickStripping \
           tests/unit/daemon/test_scope_overlap.py::TestIsTestPath \
           tests/unit/daemon/test_scope_overlap.py::TestI00071RegressionBatch00078 \
           tests/unit/test_batch_planner_dependencies.py::test_batch_planner_is_test_path_matches_scope_overlap

Result: 39 I-00071 test cases
  - 37 PASSED
  - 2 FAILED (production bug, not test bug)
  - 0 xfailed, 0 skipped in the I-00071 set
```

### Failing Tests — Root Cause

**`TestI00071RegressionBatch00078::test_two_items_both_only_test_files_under_same_dir_do_not_block`** and **`test_mixed_test_and_prod_paths_test_only_candidate_still_not_blocked`** fail because `find_blocking_items` (scope_overlap.py:157-163) applies `_same_parent` to raw (unfiltered) `candidate_paths` and `in_flight_paths`, bypassing `_strip_test_globs`:

```python
# Lines 157-163 — sibling check uses RAW paths, not stripped
for cp in candidate_paths:        # cp = "tests/dashboard/test_...py" (raw)
    for ifp in in_flight_paths:  # ifp = "tests/dashboard/test_live_...py" (raw)
        if _same_parent(cp, ifp): # True — both under tests/dashboard/
            intersecting = [cp]   # ← incorrectly fires
```

The fix (which S01 did not apply) is to strip test paths before the sibling check:
```python
candidate_non_test = _strip_test_globs(candidate_paths)
in_flight_non_test = _strip_test_globs(in_flight_paths)
for cp in candidate_non_test:
    for ifp in in_flight_non_test:
        if _same_parent(cp, ifp):
            ...
```

**The tests are correct** — they expose a latent logic bug in the production code. The tests will pass once `find_blocking_items` is fixed to use filtered paths in the sibling check.

---

## Test Count Summary

| File | New I-00071 Tests | Status |
|------|-------------------|--------|
| `test_design_doc_parser.py` | 4 | 4 PASS |
| `test_scope_overlap.py::TestIsTestPath` | 9 new parametrize cases | 9 PASS |
| `test_scope_overlap.py::TestI00071RegressionBatch00078` | 3 | 1 PASS, 2 FAIL (production bug) |
| `test_batch_planner_dependencies.py` | 8 (parity) | 8 PASS |
| **Total** | **39** | **37 PASS, 2 FAIL** |

---

## Findings

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00071",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "orch/daemon/scope_overlap.py",
      "line": "157-163",
      "description": "Sibling-directory check in find_blocking_items applies _same_parent to raw (unfiltered) paths, bypassing _strip_test_globs. This causes two test files under the same directory to incorrectly block each other (test_two_items_both_only_test_files_under_same_dir_do_not_block and test_mixed_test_and_prod_paths_test_only_candidate_still_not_blocked fail). This is a production bug in S01, NOT a test bug in S03.",
      "suggestion": "Filter both lists before the sibling check: candidate_non_test = _strip_test_globs(candidate_paths); in_flight_non_test = _strip_test_globs(in_flight_paths); then iterate over the filtered lists. The tests are correct and will pass once this fix is applied."
    }
  ],
  "tests_passed": false,
  "test_summary": "37 passed, 2 failed — FAILING TESTS EXPOSE PRODUCTION BUG (not test bug)",
  "notes": "All 4 parser backtick-stripping tests pass (S01 fix works). All 23 is_test_path parametrized cases pass (S01 fix works). 8/8 parity tests pass (helpers stay in lock-step). The 2 failing regression tests in TestI00071RegressionBatch00078 are correctly written and correctly expose a latent logic bug in find_blocking_items that S01 did not fix. S03 tests are valid and require no changes."
}
```

---

## Verdict

**PASS** — S03 tests are correctly written, use exact semantic assertions, cover all TDD bullets, and correctly expose the sibling-check production bug. No mandatory fixes required in S03. The 2 failing tests are a production-code finding for S01 to address (or S05 final-review).