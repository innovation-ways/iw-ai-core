# F-00071 S03 — Tests Report

## What Was Done

Created `tests/unit/test_security_targets.py` — a regression guard that locks the public surface of F-00071 (security scanning infrastructure) so future work cannot accidentally remove a security target or downgrade an action pin.

## Files Changed

- `tests/unit/test_security_targets.py` — new file (14 test cases)

## Test Results

```
tests/unit/test_security_targets.py::test_makefile_target_present[security-deps] PASSED
tests/unit/test_security_targets.py::test_makefile_target_present[security-iac] PASSED
tests/unit/test_security_targets.py::test_makefile_target_present[security-image-] PASSED
tests/unit/test_security_targets.py::test_makefile_target_present[security-all] PASSED
tests/unit/test_security_targets.py::test_makefile_target_present[security-report] PASSED
tests/unit/test_security_targets.py::test_workflow_file_exists PASSED
tests/unit/test_security_targets.py::test_workflow_required_jobs PASSED
tests/unit/test_security_targets.py::test_workflow_permissions_minimal PASSED
tests/unit/test_security_targets.py::test_workflow_actions_pinned_to_sha PASSED
tests/unit/test_security_targets.py::test_workflow_triggers_pr_push_schedule PASSED
tests/unit/test_security_targets.py::test_dev_dep_present[pip-audit] PASSED
tests/unit/test_security_targets.py::test_dev_dep_present[bandit] PASSED
tests/unit/test_security_targets.py::test_bandit_config_excludes_tests PASSED
tests/unit/test_security_targets.py::test_trivyignore_exists PASSED

14 passed, 0 failed
```

## TDD Verification

Temporarily removed `security-deps` target from Makefile and confirmed the parametrized test fails with a clear assertion message before restoring the target.

## Preflight

- **format**: new file auto-formatted by ruff
- **typecheck**: new file passes mypy (pre-existing errors in `orch/daemon/container_info.py` unrelated to this change)
- **lint**: new file passes ruff with `--fix`
- **test-unit**: 14 passed, 0 failed

## Blockers

None.