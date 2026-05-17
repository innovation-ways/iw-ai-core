# I-00088 — S02 Code Review (S01 Backend)

## Scope reviewed

- Design: `ai-dev/active/I-00088/I-00088_Issue_Design.md`
- Implementation report: `ai-dev/active/I-00088/reports/I-00088_S01_Backend_report.md`
- Changed files reviewed:
  - `orch/daemon/auto_merge_health.py`
  - `tests/unit/test_auto_merge_health.py`

## Checks performed

- Ran `uv run iw item-status I-00088 --json` (runtime context)
- Ran `make lint` ✅
- Ran `make format` ✅ (`ruff format --check`)
- Ran required targeted test: `uv run pytest tests/unit/test_auto_merge_health.py -v`
  - Test functions: **9 passed**
  - Process exit: **failed** due repo coverage gate (`fail-under=50%`) when running one file in isolation

## Findings

### 1) MEDIUM_FIXABLE — S01 changed existing unit tests beyond intended step scope

- **Category**: test-plan compliance
- **File**: `tests/unit/test_auto_merge_health.py`
- **Line(s)**: 28-38, 65, 95, 109, 138, 154, 173
- **Description**: Per S02 instructions for reviewing S01, Backend step S01 should add one RED→GREEN argv-shape test and leave the broader test rewrites for S03. Instead, S01 diff updates multiple pre-existing tests to assert the new subprocess shape (via `_assert_probe_subprocess_shape(...)`) and modifies their setup patterns. This breaks the staged-plan expectation for S01 vs S03.
- **Suggested fix**: Re-scope S01 to only the minimal new test + backend fix, and move broad assertion rewrites to S03; or explicitly update the design/workflow to reflect that S01 intentionally included the broader test rewrite.

## Additional review notes

- `orch/daemon/auto_merge_health.py` implementation itself is aligned with the design redraft and canonical resolver pattern:
  - Uses `bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>`
  - Preserves timeout cap (`max(15, interval // 4)`), error handling, and success predicate (`returncode == 0 and "OK" in stdout`)
  - Preserves `event_metadata` contract keys/types (`runtime_reachable`, `cli_tool`, `model`, `probe_duration_ms`, `error`)
  - Uses `DaemonEvent(event_metadata=...)` (correct SQLAlchemy naming)
  - No `shell=True`; argv passed as list of strings
- `executor/step_executor.sh` and `executor/step_executor_lib.sh` were not modified.
- S01 report contains plausible RED evidence (`AssertionError: assert '/bin/bash' == 'bash'`) and is consistent with the pre-fix mismatch explanation.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00088",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "file": "tests/unit/test_auto_merge_health.py",
      "lines": "28-38, 65, 95, 109, 138, 154, 173",
      "category": "test-plan compliance",
      "description": "S01 modified multiple pre-existing tests, while S02 checklist requires broader rewrites to remain for S03.",
      "suggested_fix": "Restrict S01 to one new test + backend fix, or formally update the staged plan."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": false,
  "test_summary": "uv run pytest tests/unit/test_auto_merge_health.py -v: 9 passed, but command exits non-zero due coverage fail-under when running only this file.",
  "notes": "Backend code change is otherwise compliant with AC intent and metadata contract."
}
```
