## I-00095 S08 — Code Review of S07 (tests-impl)

Reviewed inputs:
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S07_Tests_report.md`
- `tests/unit/test_auto_merge_aggregator.py`
- `tests/dashboard/test_auto_merge_routes.py`

Executed required gates/verification:
- `make lint` ✅
- `make format` ✅
- `uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v` ⚠️
  - All targeted tests passed: **83 passed, 0 failed**
  - Command exit status failed due repository coverage threshold (`fail_under=50`) on targeted subset.

### Scope checked against S08 checklist

1. **Placement**: tests are in the expected files ✅
2. **Design named tests exist**: required aggregator/dashboard tests are present by name/intent ✅
3. **Semantic correctness details**: partial pass (see findings)
4. **`message` column remains non-sortable**: missing explicit assertion ❌
5. **CSS class assertion style**: attribute-scoped style used where class assertions are present ✅
6. **Targeted-run discipline**: S07 report used `--no-cov` workaround; not exact required command output ❌

## Findings

### 1) MEDIUM — Sort tests assert SQL fragments instead of observable ordering behavior
- **File**: `tests/unit/test_auto_merge_aggregator.py`
- **Lines**: 135-176
- **Description**: `test_list_recent_events_sorts_by_event_type_desc`, `...entity_id_asc`, and `...verdict_nulls_last` validate generated SQL text (`"ORDER BY ..."`) instead of asserting sorted returned rows. This is weaker than the I003 requirement to assert semantic sort results via full-list comparison.
- **Suggested fix**: Seed deterministic rows and assert returned sequences directly (e.g., full `event_type`/`entity_id` lists and explicit NULLS-LAST verdict sequence), similar to `test_list_recent_events_sorts_by_event_type_asc`.

### 2) MEDIUM — Missing regression asserting `message` header is plain text (not sortable button)
- **File**: `tests/dashboard/test_auto_merge_routes.py`
- **Lines**: 1077-1149 (I-00095 block)
- **Description**: The dashboard regression block verifies sortable headers and bad params, but does not include an explicit assertion that the **message** column header is non-clickable/plain text.
- **Suggested fix**: Add a test that scopes to the message `<th>` and asserts no nested `<button>`/`hx-get` for that header.

### 3) LOW — S07 report test command deviates from required targeted verification command
- **File**: `ai-dev/active/I-00095/reports/I-00095_S07_Tests_report.md`
- **Lines**: 29-34
- **Description**: S07 reported targeted verification using `--no-cov` instead of the exact command listed for step verification. While practical for targeted subsets, this is a process mismatch.
- **Suggested fix**: Record both outputs: (a) exact required command (noting coverage-gate behavior), and (b) optional `--no-cov` informational run if needed.

## Verdict

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S07",
  "verdict": "fail",
  "findings": [
    {
      "severity": "MEDIUM",
      "file": "tests/unit/test_auto_merge_aggregator.py",
      "lines": "135-176",
      "description": "Sort tests rely on SQL ORDER BY string checks rather than full behavioral ordering assertions.",
      "suggested_fix": "Seed rows and assert returned ordered lists (including explicit NULLS LAST behavior)."
    },
    {
      "severity": "MEDIUM",
      "file": "tests/dashboard/test_auto_merge_routes.py",
      "lines": "1077-1149",
      "description": "No explicit test that message column remains plain/non-sortable.",
      "suggested_fix": "Add a scoped assertion that message header has no sort button/hx-get."
    },
    {
      "severity": "LOW",
      "file": "ai-dev/active/I-00095/reports/I-00095_S07_Tests_report.md",
      "lines": "29-34",
      "description": "Reported targeted run used --no-cov instead of exact required command.",
      "suggested_fix": "Include exact-command run outcome in step report; optionally add --no-cov run as supplemental context."
    }
  ],
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "make lint and make format passed; targeted pytest executed with 83 passed, 0 failed, but command exits non-zero due global coverage fail-under on subset.",
  "notes": "tdd_red_evidence = \"n/a — coverage step (tests-impl)\""
}
```
