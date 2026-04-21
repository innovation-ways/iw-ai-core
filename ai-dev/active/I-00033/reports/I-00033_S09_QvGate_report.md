# QV Gate Report: unit-tests (S09)

**Work Item**: I-00033
**Gate**: unit-tests
**Command**: `make test-unit`
**Result**: FAIL

## Summary

Ran `make test-unit` to execute the unit test quality gate. Exit code was non-zero (1), indicating 7 test failures out of 1151 total tests (1144 passed, 7 failed).

## Failed Tests

| Test | Reason |
|------|--------|
| `test_missing_fix_summary_key_stores_none` | `cycle.fix_summary` not cleared to `None` when `fix_summary` key missing from JSON |
| `test_exit_code_0_on_success` | CLI test uses `--project` option which does not exist on `item-report` command |
| `test_exit_code_1_on_unknown_item` | Same `--project` option issue |
| `test_stdout_flag_prints_markdown` | Same `--project` option issue |
| `test_project_flag_respected` | Same `--project` option issue |
| `test_stdout_does_not_write_file` | Same `--project` option issue |
| `test_generate_level2_assembles_markdown` | `doc.doc_type` is `code_components` but test asserts `research` |

## Observations

- 5 of 7 failures (`test_item_report_cli.*`) appear to be stale tests that assume a `--project` flag exists on the `item-report` command, but the CLI no longer has that option.
- 1 failure (`test_missing_fix_summary_key_stores_none`) appears to be a logic bug where the fix summary cache is not being cleared when the key is absent.
- 1 failure (`test_generate_level2_assembles_markdown`) appears to be a mismatch between test expectations (asserting `DocType.research`) and actual behavior (returning `DocType.code_components`).
- All 7 failures are pre-existing in the codebase and unrelated to changes made in this work item.
