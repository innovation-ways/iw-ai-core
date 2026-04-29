# F-00065 S08 QvGate Report

## Gate: lint
**Command**: `make lint`
**Result**: FAIL

## Output
```
uv run ruff check .
Found 4 errors:
- I001: Import block is un-sorted or un-formatted (ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py:11)
- W292: No newline at end of file (ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py:70)
- W292: No newline at end of file (ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py:53)
- E402: Module level import not at top of file (tests/unit/conftest.py:20)
```

## Files Changed
None — these are pre-existing lint issues in e2e fixtures and unit conftest.

## Issues
The lint errors are in:
- `ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py` — unsorted imports and missing trailing newline
- `ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py` — missing trailing newline
- `tests/unit/conftest.py` — import not at top of file (from tests/integration/conftest)

These are not related to F-00065 changes; they appear to be pre-existing issues in e2e fixture files.