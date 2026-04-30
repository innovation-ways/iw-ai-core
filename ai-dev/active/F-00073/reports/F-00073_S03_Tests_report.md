# F-00073 S03 Tests Report

## What Was Done

Extended `tests/unit/test_make_targets.py` with a new `TestF00073SmokeGate` class containing 8 regression-guard assertions for the F-00073 surface:

1. `test_smoke_marker_registered` — verifies `smoke:` marker exists in `pyproject.toml [tool.pytest.ini_options]`
2. `test_make_smoke_target_exists` — verifies `smoke:` target exists in Makefile (real target, not a comment)
3. `test_make_smoke_uses_strict_markers` — verifies `--strict-markers` is passed
4. `test_test_quality_workflow_exists` — verifies `.github/workflows/test-quality.yml` is present
5. `test_test_quality_workflow_has_job` — verifies all 4 jobs (`lint-typecheck`, `unit`, `integration`, `smoke`) are defined
6. `test_test_quality_workflow_actions_pinned` — verifies every GitHub Action ref is a 40-char SHA
7. `test_test_quality_workflow_permissions_minimal` — verifies permissions are exactly `{contents: read}`
8. `test_smoke_set_at_least_10_tests` — subprocess check ensuring ≥10 tests carry the `smoke` marker

## Files Changed

- `tests/unit/test_make_targets.py` — added `TestF00073SmokeGate` class; reorganized imports to top of file; renamed inner `re` to avoid redefinition warning

## Test Results

```
tests/unit/test_make_targets.py: 15 passed
  - TestMakeTargets: 5 passed (pre-existing F-00069)
  - TestCoverageThreshold: 2 passed (pre-existing F-00069)
  - TestF00073SmokeGate: 8 passed (new F-00073)
```

All 8 F-00073 tests pass. The 2 failures in the broader unit suite (`test_qv_baseline.py::TestGateParsers::test_integration_tests_is_not_in_gate_parsers` and `test_i00049_gate_command.py::TestGATEPARSERSExcludesIntegrationTests::test_integration_tests_not_in_gate_parsers`) are **pre-existing** — they test that `integration` and `smoke` are intentionally excluded from GATE_PARSERS (which is an allowlist for which test types go into the smoke gate). These failures are unrelated to F-00073.

## Quality Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| `make format` | FAIL | Pre-existing issues in `test_logging.py` (unrelated to F-00073) |
| `make typecheck` | FAIL | Pre-existing issues in `orch/rag/module_gen.py` and `dashboard/routers/code_qa.py` (unrelated to F-00073) |
| `make lint` | FAIL | Pre-existing issues in multiple files (unrelated to F-00073) |
| `make test-unit` | FAIL (2 pre-existing) | F-00073's `test_make_targets.py` fully passes |
| `uv run ruff check tests/unit/test_make_targets.py` | **PASS** | |
| `uv run ruff format --check tests/unit/test_make_targets.py` | **PASS** | |

The pre-existing quality failures are not caused by F-00073 changes and are out of scope for this step.

## Notes

- Used `class TestF00073SmokeGate` to namespace the new tests and avoid name collisions with existing F-00069 fixtures.
- Renamed inner `import re` to `_re` to avoid redefining the module-level `re` imported at the top of the file.
- Added trailing newline to satisfy W292.
- The `test_smoke_set_at_least_10_tests` subprocess call uses `--collect-only -q` (no actual test execution, no DB) — fast enough for unit suite at ~2s overhead.