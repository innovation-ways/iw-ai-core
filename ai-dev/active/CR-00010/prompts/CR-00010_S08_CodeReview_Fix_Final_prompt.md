# CR-00010_S08_CodeReview_Fix_Final_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Fix Cycle**: {cycle_number} of 5
**Final Review That Triggered Fix**: S07

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md`
- `ai-dev/active/CR-00010/reports/CR-00010_S07_CodeReview_Final_report.md`
- All files referenced in the S07 findings

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S08_CodeReview_Fix_Final_report.md`

## Context

The final cross-agent review (S07) flagged issues that must be fixed. Address only the CRITICAL, HIGH, and MEDIUM (fixable) findings listed in the S07 report. Do not refactor beyond the scope of those findings.

## Findings to Fix

{For each mandatory finding from `CR-00010_S07_CodeReview_Final_report.md`, include:}

### Finding {N}: {severity} — {category}

**File**: `{file_path}`, line {line}
**Cross-cutting**: {yes|no}
**Description**: {description}
**Suggestion**: {suggestion}

{Repeat for all mandatory findings.}

## Missing Requirements

{If the final review identified any missing AC implementations, list them here and implement them following the design document and TDD.}

## Constraints

1. Fix only the flagged issues. Do not add features or reorganize unrelated code.
2. Preserve existing behavior for non-research work items. Features, incidents, and other CRs must continue to transition `draft → approved → in_progress → completed` exactly as before.
3. Cross-cutting fixes may span `orch/daemon/state_machine.py`, `orch/cli/{item,doc,batch}_commands.py`, `dashboard/routers/{actions,project_pages}.py`, `dashboard/templates/**`, `skills/iw-research/SKILL.md`, and the test suite. Keep naming consistent along the chain (`item_type`, `WorkItemType.Research`, `Research` string).
4. Follow `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md`. No live DB in unit tests. No mocking the DB in integration tests. No `importlib.reload`.
5. Do NOT add `@pytest.mark.skip` / `@pytest.mark.xfail` to bypass failing tests.

## Escalation

This is fix cycle **{cycle_number} of 5**. If cycle 5 and you cannot resolve all findings, report them under `findings_skipped` with a clear reason. The orchestrator will escalate to a human reviewer.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. `uv run mypy orch/ dashboard/`

Do NOT report `tests_passed: true` unless all of the above pass.

## Fix Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00010",
  "fix_cycle": {cycle_number},
  "review_step": "S07",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": [],
      "description": ""
    }
  ],
  "findings_skipped": [],
  "missing_requirements_implemented": [],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "notes": ""
}
```
