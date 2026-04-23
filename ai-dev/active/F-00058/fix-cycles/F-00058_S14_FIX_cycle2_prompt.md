# F-00058 S14 QV Fix Cycle 2/5

Quality gate S14 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Timeout after 600s (limit: 600s)

**Command output**:
```
...(truncated)...
D  [ 61%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[Based on the provided code,] PASSED [ 61%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[based on the context,] PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[According to the provided information,] PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[From the code snippets shown,] PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[Looking at these excerpts,] PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::test_variety_of_openers[Referring to the documentation above,] PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::TestNormalizeModulePathForFilter::test_dotted_path_converted_to_slashes PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::TestNormalizeModulePathForFilter::test_slash_path_left_alone PASSED [ 62%]
tests/unit/test_module_gen_prompt.py::TestNormalizeModulePathForFilter::test_single_segment_unchanged PASSED [ 62%]
tests/unit/test_module_parser.py::test_parse_returns_three_modules PASSED [ 62%]
tests/unit/test_module_parser.py::test_parse_module_fields PASSED        [ 62%]
tests/unit/test_module_parser.py::test_parse_empty_doc_returns_empty_list PASSED [ 62%]
tests/unit/test_module_parser.py::test_parse_no_components_section_returns_empty_list PASSED [ 62%]
tests/unit/test_module_parser.py::test_parse_slug_with_nested_path PASSED [ 62%]
tests/unit/test_module_parser.py::test_parse_never_raises PASSED         [ 63%]
tests/unit/test_module_parser.py::test_parse_with_bold_name_format PASSED [ 63%]
tests/unit/test_module_parser.py::test_parse_plain_format PASSED         [ 63%]
tests/unit/test_module_parser.py::test_parse_star_bullet_backtick_format PASSED [ 63%]
tests/unit/test_module_parser.py::test_parse_bold_with_path_inside_parens PASSED [ 63%]
tests/unit/test_module_parser.py::test_parse_skips_top_level_matching_header_with_empty_body PASSED [ 63%]
tests/unit/test_oss_config_writer.py::TestWriteProjectConfig::test_writes_config_when_absent PASSED [ 63%]
tests/unit/test_oss_config_writer.py::TestWriteProjectConfig::test_idempotent_when_identical_content PASSED [ 63%]
tests/unit/test_oss_config_writer.py::TestWriteProjectConfig::test_raises_when_file_differs_and_not_forced PASSED [ 63%]
tests/unit/test_oss_config_writer.py::TestWriteProjectConfig::test_overwrites_when_forced PASSED [ 63%]
tests/unit/test_oss_config_writer.py::TestWriteProjectConfig::test_creates_iw_directory PASSED [ 63%]
tests/unit/test_oss_dashboard_service.py::TestSseMessageFormatter::test_sse_status_event PASSED [ 63%]
tests/unit/test_oss_dashboard_service.py::TestSseMessageFormatter::test_sse_progress_line_format 

<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mecho "Exit code: $?"
Exit code: 0
[0m

```


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
