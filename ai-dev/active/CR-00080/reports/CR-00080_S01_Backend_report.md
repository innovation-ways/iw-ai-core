# CR-00080 S01 Backend Report

## What was done
- Applied **Option A** for mutmut runner coverage interaction:
  - Added `--cov-fail-under=0` in `[tool.mutmut].runner` (`pyproject.toml`)
  - Added `--cov-fail-under=0` in `Makefile` `mutation-check` and `mutation-audit` runner strings.
- Widened mutmut scope from `orch/daemon/` to `orch/` in `[tool.mutmut].paths_to_mutate`.
- Updated `Makefile` `mutation-audit` loop to iterate `orch/**/*.py` and exclude `__init__.py`, `__pycache__`, and `*/migrations/*`.
- Extended RED-first guard test in `tests/unit/test_mutmut_setup.py` to assert `paths_to_mutate == "orch/"`.
- Ran the second spike via `make mutation-audit` with a 3600s budget.
- Wrote partial spike evidence to:
  - `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt`
- Updated mutmut comment block in `pyproject.toml` with CR-00080 partial spike note.

## TDD evidence
- RED run captured:
  - `AssertionError: assert 'orch/daemon/' == 'orch/'`
  - test: `tests/unit/test_mutmut_setup.py::test_pyproject_tool_mutmut_block_pins_orch_target`

## Spike result
- `make mutation-check MODULE=orch/daemon/main.py` showed non-zero mutants (mutants executed; no immediate cov-fail-under abort).
- `make mutation-audit` timed out at 3600s (partial).
- Partial measured data captured in evidence file:
  - processed module: `orch/active_files.py`
  - generated=55, killed=0, survived=55, score=0%
  - timeout while processing `orch/agent_runtime/audit.py`

## Files changed
- `pyproject.toml`
- `Makefile`
- `tests/unit/test_mutmut_setup.py`
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt`

## Verification / gates
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/unit/test_mutmut_setup.py -v`
  - tests: 2 passed
  - process exits non-zero due global coverage floor in addopts (`FAIL Required test coverage of 50.0% not reached`), not due assertion failures.

## Notes
- Completion status should be treated as **partial** due spike timeout at 3600s.
