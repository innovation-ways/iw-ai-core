# I-00071 S02 Code Review Report

## Step Reviewed: S01 (backend-impl)

## What Was Done

Reviewed the implementation of two bug fixes in:
- `orch/design_doc_parser.py` — added `_strip_code_span` to strip surrounding markdown code-span backticks in both bullet and fenced-code-block branches
- `orch/daemon/scope_overlap.py` — added prefix check for relative test paths (`tests/`, `test/`, `__tests__/`)
- `orch/batch_planner.py` — mirrored the same prefix check in `_is_test_path` for parity

## Files Changed (S01 implementation)

| File | Change |
|------|--------|
| `orch/design_doc_parser.py` | Added `_strip_code_span` helper; applied to both bullet-line and fenced-code-block branches |
| `orch/daemon/scope_overlap.py` | Extended `is_test_path` with `startswith(("tests/", "test/", "__tests__/"))` prefix check |
| `orch/batch_planner.py` | Mirrored same prefix check in `_is_test_path` |

## Pre-Review Gates

- **`make lint`**: ✅ All checks passed
- **`make format-check`**: ✅ All 611 files already formatted

## Architecture Compliance

✅ `orch/design_doc_parser.py` and `orch/daemon/scope_overlap.py` remain pure modules — no DB, no I/O imports added.

✅ `parse_impacted_paths` and `is_test_path` are side-effect-free pure functions.

## Code Quality

### Bug 1 — Backtick stripping (`design_doc_parser.py:97-117`)

The `_strip_code_span` function correctly:
- Strips **only** surrounding backticks (not mid-string backticks)
- Handles single-backtick fences: `` `foo/bar.py` `` → `foo/bar.py`
- Handles double-backtick outer fences: `` `` `foo` `` `` → `` `foo` `` (via recursion)
- Requires inner content to have no whitespace or backticks before accepting the strip
- Applied to **both** bullet-line branch (line 86-88) and fenced-code-block branch (line 74)

No regression: bare paths without backticks pass through unchanged.

### Bug 2 — `is_test_path` broadening (`scope_overlap.py:33-34`, `batch_planner.py:113-114`)

Both functions correctly add the leading-segment prefix check:

```python
if glob.startswith(("tests/", "test/", "__tests__/")):
    return True
```

This correctly handles:
- `tests/dashboard/test_x.py` → True (was False before)
- `test/foo.py` → True (was False before)
- `__tests__/bar.py` → True (was False before)
- `src/tests/foo.py` → True (still True, via `/tests/` marker)
- `conftest.py` → True (still True)
- `foo.test.ts` → True (still True)
- `testscript.sh` → False (correct — no `/tests/`, `conftest`, `.test.`, `.spec.`)
- `test_data.json` → False (correct)
- `src/test_utils.py` → False (correct — `test_utils` is not a test marker)

### Parity check

✅ `scope_overlap.is_test_path` and `batch_planner._is_test_path` are in lock-step. Both now use identical logic: prefix check first, then `any(marker in glob)` as fallback.

## Project Conventions

✅ No emojis in code or docs.

✅ Comment `# strip markdown code-span — I-00071` on line 88 is appropriate — it explains the WHY of the normalization without restating the code.

✅ Naming, formatting, import order all match existing module style.

✅ No scope creep — only the targeted fixes were applied; `_TEST_PATH_MARKERS` constant not renamed, `globs_intersect` unchanged.

## Security

✅ No hardcoded secrets, credentials, or API keys introduced.

✅ No user-input boundary code touched — pure helpers operating on already-validated strings.

## Testing

✅ S01 did NOT modify `tests/unit/test_design_doc_parser.py` or `tests/unit/daemon/test_scope_overlap.py` — those files are owned by S03.

✅ **Full unit test suite**: `make test-unit` — **2581 passed**, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings. Zero failures.

## Test Summary

```
= 2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 60.26s =
```

The 5 xfailed and 1 xpassed are pre-existing and unrelated to this change.

## Verdict

**PASS** — zero CRITICAL findings, zero HIGH findings, zero MEDIUM_FIXABLE findings.

## JSON Result

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00071",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings",
  "notes": "Both bugs correctly fixed. _strip_code_span handles single and double-backtick fences. is_test_path broadened for relative paths. Parity maintained between scope_overlap and batch_planner. No regressions. No scope creep."
}
```