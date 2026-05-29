# I-00118 S01 Backend Report

## What was done
- Added `parse_assertion_scanner(raw_output)` to parse assertion scanner lines of the form:
  - `<file>:<line>: <category>: <test_name>: <message>`
  - Emits `FailureEntry(kind="assertion", key="<file>::<test_name>")`
  - Non-matching lines are captured in `unparseable`.
- Added `parse_generic_lines(raw_output)` as a conservative fallback parser:
  - Uses stripped non-empty lines as stable keys (`kind="line"`)
  - Docstring documents false-suppression risk for byte-identical lines.
- Added `parser_for_gate(gate_name)` that never returns `None`:
  - Uses precise parser from `GATE_PARSERS` if known
  - Falls back to `parse_generic_lines` for unknown gates.
- Extended parser mapping:
  - `assertions -> parse_assertion_scanner`
  - `integration-tests -> parse_pytest`
- Wired resolver usage into baseline compute and findings paths:
  - `orch/daemon/batch_manager.py::_compute_qv_baselines`
  - `orch/daemon/fix_cycle.py::_get_qv_findings`
  - Removed unknown-gate skip/no-subtraction behavior for parser selection.
- Updated affected unit assertions for gate-parser expectations.

## Files changed
- `orch/daemon/qv_baseline.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `tests/unit/orch/daemon/test_qv_baseline.py`

## Preflight
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Targeted tests
- `uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v`
- Result: **27 passed, 0 failed**

## Notes
- No migration added/applied.
- No Docker state-changing commands were executed.

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00118",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/qv_baseline.py",
    "orch/daemon/fix_cycle.py",
    "orch/daemon/batch_manager.py",
    "tests/unit/orch/daemon/test_qv_baseline.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "27 passed, 0 failed (targeted)",
  "tdd_red_evidence": "n/a — behavioral tests authored in S03 (Tests)",
  "blockers": [],
  "notes": ""
}
```