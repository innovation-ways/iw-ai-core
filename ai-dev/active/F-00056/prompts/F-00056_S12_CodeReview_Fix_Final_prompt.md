# F-00056_S12_CodeReview_Fix_Final_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Fix Cycle**: (final)
**Original Step**: (cross-agent — all impl steps S01/S03/S05/S07/S09)
**Review That Triggered Fix**: S11

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document
- `ai-dev/active/F-00056/reports/F-00056_S11_CodeReview_Final_report.md` -- Final review with findings
- All files referenced in the findings below

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S12_CodeReview_FIX_Final_report.md` -- Fix report

## Context

The global cross-agent review in S11 flagged CRITICAL and HIGH findings that must be addressed. Apply the minimum changes needed to resolve each mandatory finding. Do NOT refactor beyond the flagged findings.

## Findings to Fix

{For each mandatory finding from S11, include:}

### Finding {N}: {severity} -- {category}

**File**: `{file_path}`, line {line}
**Description**: {description from S11}
**Suggestion**: {suggestion from S11}

{Copy each mandatory finding verbatim from the S11 report.}

## Constraints

1. Only fix the flagged issues.
2. Preserve existing behavior.
3. Follow project conventions per `CLAUDE.md`.
4. Run tests after every fix; do not proceed to the next fix until the current suite is green.
5. Fixes that cross layers (e.g., contract alignment between backend and frontend) require updates to both sides; do not fix one side only.

## Escalation

This is the final fix cycle before QV gates. If a finding genuinely cannot be resolved, report it in `findings_skipped` with a clear explanation. The orchestrator will escalate.

## Test Verification (NON-NEGOTIABLE)

After all fixes:

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check .`
4. `uv run mypy orch/ dashboard/`
5. Re-verify the dashboard `/project/iw-ai-core/item/F-00055/execution-report` loads cleanly.

## Fix Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00056",
  "fix_cycle": 1,
  "review_step": "S11",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed",
      "files_changed": ["..."],
      "description": "What was done to fix it"
    }
  ],
  "findings_skipped": [],
  "fix_summary": "- bullet 1 (what changed and why)\n- bullet 2\n- bullet 3",
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

The `fix_summary` field is mandatory per the F-00056 agent contract. Keep it under 2000 characters. It will be persisted to `FixCycle.fix_summary` and surfaced in the execution report.
