# F-00041 S08 QVGate Report: Integration Tests

## What was done

Ran the full integration test suite (`tests/integration/`) via pytest to verify all database-backed routes, models, and invariants pass against a real PostgreSQL testcontainer.

## Files changed

None — no code changes, this was a verification gate only.

## Test results

```
.venv/bin/pytest tests/integration/ -x -q
=============================== warnings summary ===============================
tests/integration/test_models.py::test_duplicate_item_id_in_same_project_rejected
tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  SAWarning: transaction already deassociated from connection
tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  SAWarning: New instance <ProjectDoc ...> with identity key conflicts with persistent instance
-- Docs: https://docs.pytest.en/how-to/capture-warnings.html
408 passed, 3 warnings in 17.16s
```

**Result: PASS**

## Issues/observations

- All 408 tests passed in ~17 seconds
- 3 SAWarnings about transaction rollback and identity conflicts are pre-existing (not introduced by F-00041) — they appear in constraint tests and are expected behavior
- No test failures or errors
- The `--timeout=300` argument specified in the workflow manifest is not supported by the installed pytest plugins; tests completed well within any reasonable timeout threshold