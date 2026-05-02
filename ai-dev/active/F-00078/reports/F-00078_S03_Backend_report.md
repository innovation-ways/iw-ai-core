# F-00078 S03 Backend Report

**Step**: S03 — Backend
**Agent**: backend-impl
**Work Item**: F-00078 — Per-project self-assessment step with copy-paste fix prompts
**Date**: 2026-05-02

---

## What Was Done

Implemented the backend layer for the `self_assess` step type:

1. **`ProjectConfig.self_assess_enabled`** — added to `orch/daemon/project_registry.py` with strict bool coercion (non-bool values log a warning and default to False per the Boundary Behavior table).

2. **`orch/self_assess.py`** (new module) — dataclasses `SelfAssessFinding` / `SelfAssessmentData`, `parse_findings_json` (tolerant parser with validation), `is_self_assess_step`, `findings_path_for`, `is_soft_step_failure`.

3. **Soft-step semantics** — added to `orch/daemon/batch_manager.py`: when a `self_assess` step fails, the item proceeds to the next step or merge without fix cycle or retry. The StepRun row preserves the actual `failed` status for reporting.

4. **`fix_cycle.py` guard** — `should_attempt_fix` returns `False` for `self_assess` steps, preventing any fix cycle creation.

5. **`iw step-done --analysis-json`** and **`iw step-fail --analysis-json`** — new optional flags on both commands with validation: step must be `self_assess`, JSON must share parent dir with report, report must be provided.

6. **`executor/step_executor_lib.sh`** — `get_step_type()` returns `"implementation"` for `self-assess-impl`; `get_agent_label()` returns `"SelfAssess"`.

7. **`item_commands.py`** — added `("self-assess", StepType.self_assess)` to `_AGENT_STEP_TYPE_PATTERNS` for defense-in-depth register-time slug inference.

8. **`IW_ITEM_ID` export** — added to `batch_manager.py` at line ~1061: `agent_env["IW_ITEM_ID"] = step.work_item_id`. Previously the comment referenced it but the variable wasn't exported.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/project_registry.py` | Added `self_assess_enabled` field + strict bool coercion in `_build_project_config` |
| `orch/self_assess.py` | **New** — dataclasses, parser, helpers |
| `orch/daemon/batch_manager.py` | Soft-step logic in `_check_executing_item` + `IW_ITEM_ID` env var export |
| `orch/daemon/fix_cycle.py` | Guard in `should_attempt_fix` returning False for `self_assess` |
| `orch/cli/step_commands.py` | `--analysis-json` flag on `step-done` and `step-fail` with validation |
| `orch/cli/item_commands.py` | Added `("self-assess", StepType.self_assess)` to `_AGENT_STEP_TYPE_PATTERNS` |
| `executor/step_executor_lib.sh` | `self-assess-impl` slug in `get_step_type()` → `"implementation"` and `get_agent_label()` → `"SelfAssess"` |
| `tests/unit/test_self_assess.py` | **New** — 30 unit tests for all `orch/self_assess.py` public functions |
| `tests/integration/test_batch_manager.py` | Added `test_self_assess_failure_does_not_block_item_completion` |

---

## Test Results

- **Unit tests (self_assess module)**: 30 passed
- **Integration tests (batch_manager soft-step)**: 1 passed
- **Existing batch_manager tests**: 9 passed (no regressions)
- **`make lint`**: All checks passed
- **`make typecheck`**: Success (no issues in 214 source files)

---

## Notes

- **`IW_ITEM_ID` export location**: `batch_manager.py` line ~1061 — was referenced in a comment but not actually exported. Added alongside `IW_STEP_ID`.
- **Soft-step branching location**: The soft-step short-circuit lives in `_check_executing_item` (batch_manager.py) before calling `fix_cycle.should_attempt_fix`. This preserves truth in the StepRun row while letting the item proceed to merge.
- **`is_soft_step_failure` enum handling**: Uses `.value` attribute when available (StepStatus enum) to extract `"failed"` rather than `"StepStatus.failed"`.
- **No DB schema changes** — findings are discovered via `findings_path_for(report_path)` convention, not a new column.
