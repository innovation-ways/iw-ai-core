# I-00118 S03 — Tests report

## What was done
- Extended `tests/unit/orch/daemon/test_qv_baseline.py` with:
  - `parse_assertion_scanner` subtraction tests for pre-existing suppression and new-failure surfacing.
  - garbage-line → `unparseable` fail-safe test.
  - `parse_generic_lines` normalization/subtraction tests.
  - `parser_for_gate` resolver tests (`assertions`, `lint`, `integration-tests`, unknown gate fallback callable).
- Extended `tests/integration/daemon/test_baseline_qv_pipeline.py` with assertions-gate regression coverage:
  - pre-existing assertions failure is suppressed.
  - added assertions failure surfaces while baseline failure stays suppressed.
- Updated AC3 baseline setup expectation to include `integration-tests` baseline row.

## Files changed
- `tests/unit/orch/daemon/test_qv_baseline.py`
- `tests/integration/daemon/test_baseline_qv_pipeline.py`

## Test results
- `uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v` → **33 passed, 0 failed**
- `uv run pytest tests/integration/daemon/test_baseline_qv_pipeline.py -v` → **13 passed, 0 failed**

## TDD RED evidence observed during implementation
- `tests/integration/daemon/test_baseline_qv_pipeline.py::TestAC1::test_ac1_assertions_pre_existing_failure_suppressed`
  - RED line before fixture/step metadata alignment:
  - `AssertionError: assert '**Log content** ...' == ''`

## Notes
- Required targeted tests are green.
- No docker/compose commands used (testcontainers-only pytest flow).
