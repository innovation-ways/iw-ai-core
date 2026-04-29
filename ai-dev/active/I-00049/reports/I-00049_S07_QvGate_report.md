# I-00049 S07 QvGate Report

## Gate: format
**Command**: `make format-check` (ruff format --check)
**Result**: FAIL

## Output
```
Would reformat: ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py
Would reformat: ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py
Would reformat: tests/unit/rag/test_mapgen_mermaid.py
Would reformat: tests/unit/test_i00049_gate_command.py
4 files would be reformatted, 455 files already formatted
```

## Files with formatting issues
- `ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py`
- `ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py`
- `tests/unit/rag/test_mapgen_mermaid.py`
- `tests/unit/test_i00049_gate_command.py`

## Summary
Format check failed because 4 files would be reformatted by ruff. The gate is designed to fail when any files don't match the project's formatting standards.