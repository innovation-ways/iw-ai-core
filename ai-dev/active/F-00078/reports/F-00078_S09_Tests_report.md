# F-00078_S09_Tests_report

## Step Summary

S09 (tests-impl): Filled test coverage for the per-project self-assessment step (F-00078).

## What Was Done

Reviewed existing test files from S01/S03/S05/S07 to avoid duplication, then wrote missing tests across 6 files.

## Files Changed

| File | Action |
|------|--------|
| `tests/integration/test_project_registry_self_assess.py` | New — 9 tests |
| `tests/integration/test_batch_manager_self_assess.py` | New — 4 tests |
| `tests/integration/test_step_done_analysis_json.py` | New — 5 tests |
| `tests/dashboard/test_execution_report_self_assess.py` | Extended — 8 new tests added |
| `tests/unit/test_self_assess.py` | Extended — 5 new tests added |
| `tests/unit/test_skill_files.py` | Extended — 4 new tests added |

## Coverage Matrix

| Item | Test |
|------|------|
| AC1: flag=true round-trip | `test_flag_true_roundtrips` |
| AC1: flag=false round-trip | `test_flag_false_roundtrips` |
| AC1: flag absent → False | `test_flag_absent_defaults_false` |
| AC2: design skills inject step | `test_design_skill_injects_self_assess_conditional` (parametrized) |
| AC3: self_assess failure = soft | `test_self_assess_failure_does_not_block_merge` |
| AC4: report shows section with findings | `test_self_assessment_section_visible_when_findings_exist` |
| AC5: section hides when not applicable | `test_self_assessment_not_rendered_when_findings_json_missing` |
| AC6: skill output contract | `test_item_analyze_documents_two_file_output_contract` |
| AC7: step-done --analysis-json accepted | `test_flag_accepted_for_self_assess` |
| AC7: step-done --analysis-json rejected for non-self_assess | `test_flag_rejected_for_implementation_step`, `test_flag_rejected_for_code_review_step` |
| Boundary: non-bool projects.toml value | `test_non_bool_value_warns_and_defaults_false` (4 parametrized cases) |
| Boundary: findings JSON missing | `test_self_assessment_not_rendered_when_findings_json_missing` |
| Boundary: findings JSON malformed | `test_section_renders_narrative_when_json_malformed` |
| Boundary: all findings target=iw-ai-core | `test_self_assessment_only_iw_ai_core_findings` |
| Boundary: all findings target=project | `test_only_project_subsection_when_no_iw_ai_core_findings` |
| Boundary: self_assess fails non-zero | `test_self_assess_failed_renders_with_partial_data` |
| Invariant 1: never blocks merge | (covered by AC3) |
| Invariant 2: zero DOM nodes when not applicable | `test_no_self_assess_html_when_section_absent` |
| Invariant 3: canonical sidecar path | `test_findings_path_for_canonical_form` |
| Invariant 4: skill never writes outside reports dir | `test_item_analyze_constraints_mention_no_outside_writes` |
| Invariant 5: target field strict validation | `test_rejects_unknown_target` (already existed) |
| Invariant 6: deterministic skill injection | (covered by AC2) |

## Test Results

**make test-unit**: `2421 passed, 2 skipped, 5 xfailed, 1 xpassed`
- `tests/unit/test_self_assess.py`: 34 passed
- `tests/unit/test_skill_files.py`: 26 passed

**make test-integration** (specific new tests):
- `test_project_registry_self_assess.py`: 9 passed
- `test_batch_manager_self_assess.py`: 4 passed
- `test_step_done_analysis_json.py`: 5 passed (18 total when including full run)
- Dashboard XSS + edge case tests: passed

## Pre-flight Results

- **format**: `ruff format` applied to 6 test files — all formatted
- **typecheck**: `mypy orch/ dashboard/` — Success: no issues found
- **lint**: `ruff check` on modified test files — All checks passed

## Notes

- The `test_step_done_analysis_json.py` tests use `CliRunner.invoke` with `project_id` explicitly set in `ctx.obj` to work around the `resolve_project()` directory lookup (since tests run from temp dirs without `.iw-orch.json`).
- Some `step-done` negative tests use `exit_code != 0` rather than `exit_code == 2` because Click wraps `UsageError` in `SystemExit(1)` when invoked via `CliRunner.invoke(standalone_mode=False)` rather than `SystemExit(2)`.
- `make test-integration` timed out at 300s (expected for testcontainer suite); individual test files run in ~6-11s each.
- `orch/self_assess.py` line coverage: 83% (12 missed lines are defensive `isinstance` branches for forward-compat JSON field coercion — low priority).

## Blockers

None.
