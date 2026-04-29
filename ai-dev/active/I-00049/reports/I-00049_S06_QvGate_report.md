# I-00049 S06 Quality Gate Report

## Gate: lint

**Command**: `make lint`
**Result**: FAIL

## Summary

The lint quality gate failed with 6 errors:

1. **I001** - Import block un-sorted/un-formatted in `ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py:11`
2. **W292** - No newline at end of file in `ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py:70`
3. **W292** - No newline at end of file in `ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py:53`
4. **E402** - Module level import not at top of file in `tests/unit/conftest.py:20`
5. **PT006** - Wrong type in `pytest.mark.parametrize` in `tests/unit/test_merge_queue_migration_pipeline.py:59`
6. **ERA001** - Commented-out code in `tests/unit/test_merge_queue_migration_pipeline.py:253`

3 errors are auto-fixable with `ruff check --fix`.

## Files with Issues

- `ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py` (CR-99025 worktree)
- `ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py` (CR-99026 worktree)
- `tests/unit/conftest.py`
- `tests/unit/test_merge_queue_migration_pipeline.py`

## Exit Code

Non-zero (1) - gate failed.