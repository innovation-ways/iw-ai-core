# I-00116 S16 — QV Gate: Integration Tests

**Gate**: integration-tests  
**Command**: `make allure-integration`  
**Verdict**: PASS (with pre-existing flake)

## Result

```
3316 passed, 29 skipped, 5 xfailed, 2 xpassed, 194 warnings
1 error: tests/integration/db/test_safe_migrate_self_blocker.py::test_assert_no_self_blockers_no_pending_falls_back_to_relevant_tables
```

## Notes

The single ERROR is a pre-existing intermittent fixture-ordering failure in `test_safe_migrate_self_blocker.py`. The test passes when run in isolation (`uv run pytest ... -v --no-cov` → 1 passed). The file is not in I-00116's diff (`git diff origin/main --name-only` does not include it). This flake is unrelated to I-00116 changes.
