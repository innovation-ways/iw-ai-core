# I-00118 — S05 Global Cross-Step Review

## Result
PASS (no CRITICAL/HIGH findings)

## Mechanical AC verification
- **AC1**: Covered by integration test `TestAssertionsGateBaseline::test_pre_existing_assertions_failure_is_suppressed` (pre-existing assertions failure yields empty findings).
- **AC2**: Covered by integration test `TestAssertionsGateBaseline::test_new_assertions_failure_surfaces` (new failure appears in findings delta).
- **AC3**: Verified in code:
  - `orch/daemon/batch_manager.py::_compute_qv_baselines` uses `parser_for_gate(gate)`.
  - `orch/daemon/fix_cycle.py::_get_qv_findings` uses `parser_for_gate(gate_name)`.
  - Grep confirms no remaining `GATE_PARSERS.get(...)` + `if parser is None` skip path in these functions.
- **AC4**: Parser/resolver/integration tests present with semantic assertions in:
  - `tests/unit/orch/daemon/test_qv_baseline.py`
  - `tests/integration/daemon/test_baseline_qv_pipeline.py`

## Cross-step checks
1. Existing precise parsers unchanged for `lint`, `typecheck`, `unit-tests`, `frontend-tests`; `integration-tests` explicitly resolves to `parse_pytest`.
2. Legacy no-subtraction path remains only for genuine fallback cases (disabled feature, missing command/gate/base SHA/baseline/latest run/output/recompute failure), not for unknown gates.
3. Diff scope clean: only
   - `orch/daemon/qv_baseline.py`
   - `orch/daemon/fix_cycle.py`
   - `orch/daemon/batch_manager.py`
   - `tests/unit/orch/daemon/test_qv_baseline.py`
   - `tests/integration/daemon/test_baseline_qv_pipeline.py`
4. Required tests executed:
   - `make test-unit` ✅
   - `uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v` ✅

## Notes
- No blocking issues found.
