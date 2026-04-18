# CR-00009_S10_CodeReview_Fix_Final_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Fix Cycle**: {cycle_number} of 5
**Final Review That Triggered Fix**: S09

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S09_CodeReview_Final_report.md`
- All files referenced in the findings

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S10_CodeReview_Fix_Final_report.md`

## Context

The final cross-agent review (S09) found issues that must be fixed. Address only the CRITICAL, HIGH, and MEDIUM (fixable) findings listed in the S09 report. Do not refactor beyond the scope of those findings.

## Findings to Fix

{For each mandatory finding from `CR-00009_S09_CodeReview_Final_report.md`, include:}

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
2. Preserve existing behavior. Do not break CR-00008's chat flow (SSE, markdown, Mermaid, citations, slash menu, image paste chip).
3. Cross-cutting fixes may span `orch/rag/qa.py`, `dashboard/routers/code_qa.py`, `dashboard/templates/chat/`, and `dashboard/static/chat/`. Keep naming consistent along the `module_name` chain.
4. Follow `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md`. No live DB in unit tests. No mocking the DB in integration tests.

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
  "step": "S10",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00009",
  "fix_cycle": {cycle_number},
  "review_step": "S09",
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
