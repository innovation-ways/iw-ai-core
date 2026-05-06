# I-00071 S01 Backend Report

## What Was Done

Fixed two latent bugs in the F-00076 cross-batch scope-overlap gate:

### Bug 1 — Markdown code-span backticks persisted into `impacted_paths` (`orch/design_doc_parser.py`)

Added `_strip_code_span(s: str) -> str` helper that removes surrounding single-backtick fences (`` `foo/bar.py` `` → `foo/bar.py`) and double-backtick fences (`` `` `foo` `` `` → `` `foo` ``) before validation/storage. Applied it in both:
- The **bullet-line branch** (line 89): `_strip_code_span(raw_line[indent + 2 :].strip())` before `_validate_glob`
- The **fenced-code-block branch** (line 76): `_strip_code_span(stripped)` before `_validate_glob`

### Bug 2 — `is_test_path` missed relative test paths (`orch/daemon/scope_overlap.py` + `orch/batch_planner.py`)

Added a prefix check at the start of `is_test_path` in `scope_overlap.py` and `_is_test_path` in `batch_planner.py`:

```python
if glob.startswith(("tests/", "test/", "__tests__/")):
    return True
```

This ensures relative test paths (`tests/foo.py`, `test/foo.py`, `__tests__/foo.py`) are recognized as test paths, fixing the sibling-directory false positive in `find_blocking_items`.

## Files Changed

| File | Change |
|------|--------|
| `orch/design_doc_parser.py` | Added `_strip_code_span` helper; applied in bullet and fenced-code-block branches |
| `orch/daemon/scope_overlap.py` | Extended `is_test_path` to check prefix `startswith(("tests/", "test/", "__tests__/"))` |
| `orch/batch_planner.py` | Mirrored the same fix in `_is_test_path` for parity |

## Test Results

- **Targeted tests** (`tests/unit/test_design_doc_parser.py` + `tests/unit/daemon/test_scope_overlap.py`): **79 passed, 0 failed**
- **Full unit suite** (`make test-unit`): 2579 passed, 2 failed — both failures are pre-existing `test_safe_migrate.py` tests that fail due to DNS resolution in the test environment (unrelated to this change)

## Quality Gates

- **`make format`**: ruff auto-fixed 1 file (`orch/design_doc_parser.py`)
- **`make typecheck`**: Zero errors
- **`make lint`**: Zero errors

## Acceptance Criteria

- ✅ AC1: Backtick-wrapped bullet paths are stored bare (`dashboard/CLAUDE.md` not `` `dashboard/CLAUDE.md` ``)
- ✅ AC2: Relative test paths (`tests/dashboard/test_x.py`) are stripped before sibling-directory check
- ✅ AC3: Both existing and new test cases pass; `is_test_path` parity between `scope_overlap` and `batch_planner` preserved

## Notes

- The 2 failing tests in `test_safe_migrate.py` (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) fail due to `psycopg.OperationalError: failed to resolve host 'unused': [Errno -3] Temporary failure in name resolution` — a pre-existing environment issue, not caused by this change.
- No regressions in any parser or scope_overlap tests.