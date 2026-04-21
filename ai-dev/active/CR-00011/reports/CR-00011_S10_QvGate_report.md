# CR-00011 S10 Quality Validation Gate Report

## What Was Done

S10 executes the lint quality gate for CR-00011 (New Project Onboarding — Dashboard + New Project button). Same results as S08/S09.

## Quality Gate Result

| Gate | Command | Result | Notes |
|------|---------|--------|-------|
| Lint | `make lint` | **FAIL** | 8 errors (1 ARG002 pre-existing + 7 in CR-00011 test file) |

**Command**: `make lint` → `uv run ruff check .`

**Errors (8 total)**:

| File | Code | Description | Introduced By |
|------|------|-------------|---------------|
| `orch/rag/qa.py:77` | ARG002 | Unused method argument `symbol_hint` | **Pre-existing** (not in CR-00011 diff) |
| `tests/integration/test_project_onboarding_api.py:9` | TC003 | Move `pathlib.Path` to TYPE_CHECKING block | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:38` | S110 | try-except-pass detected | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:47` | S110 | try-except-pass detected | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:152` | S108 | Insecure `/tmp` usage | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:162` | S108 | Insecure `/tmp` usage | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:175` | S108 | Insecure `/tmp/nonexistent` usage | CR-00011 test file |
| `tests/integration/test_project_onboarding_api.py:184` | S108 | Insecure `/tmp` usage | CR-00011 test file |

**Note**: `pyproject.toml` per-file-ignores for `tests/**` does not include TC003, S110, or S108. These are common patterns in test code.

## QV Result Contract

```json
{
  "step": "S10",
  "agent": "qv-gate",
  "gate": "lint",
  "work_item": "CR-00011",
  "overall_status": "fail",
  "command": "make lint",
  "error_output": "8 errors: 1 ARG002 pre-existing in orch/rag/qa.py, 1 TC003 + 2 S110 + 4 S108 in CR-00011 test file",
  "summary": "8 errors found"
}
```

## Observations

1. **Pre-existing ARG002**: `orch/rag/qa.py:77` has an unused `symbol_hint` parameter — not introduced by CR-00011.
2. **Test file lint patterns**: S110 (try-except-pass) and S108 (insecure tmp) are common in test code; would need per-file-ignores added to `pyproject.toml`.
3. **TC003 in test file**: `pathlib.Path` import should be in TYPE_CHECKING block — style issue only.
4. **All CR-00011 tests pass**: 59 unit/template tests + 26 integration tests pass cleanly.

## Files Changed

None — read-only lint check only.

## Recommendation

CR-00011 implementation is correct. To pass the lint gate, either:
1. Add TC003, S110, S108 to per-file-ignores in `pyproject.toml` for `tests/**`, OR
2. Fix the test file issues (move Path to TYPE_CHECKING block, log exceptions, use pytest tmp_path fixture instead of `/tmp`)
