# F-00086_S05_CodeReviewFix_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Fix Cycle**: 1 of 5 (subsequent cycles auto-renumber)
**Original Step**: S03 (backend-impl)
**Review That Triggered Fix**: S04

---

## ⛔ Docker is off-limits

(Standard policy — see other prompts in this work item for the full text.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (authoritative spec)
- `ai-dev/active/F-00086/reports/F-00086_S04_CodeReview_report.md` — review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_S05_CodeReview_FIX_report.md` — fix report

## Context

The S04 code review for S03 (Backend) flagged CRITICAL / HIGH / MEDIUM(fixable) findings. Apply **only** those findings. Do not refactor beyond the flagged scope.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/F-00086/F-00086_Feature_Design.md` is authoritative. Read §Scope, §Invariants, and §Boundary Behavior before applying any fix.

**The design doc wins when findings disagree with it.** Past fix cycles have failed because the agent trusted the reviewer's root-cause hypothesis and drifted from the spec. Always re-anchor on the design.

## Diagnostic Hypothesis — Findings to Address

Read the findings from `F-00086_S04_CodeReview_report.md`. Each CRITICAL / HIGH / MEDIUM(fixable) finding is mandatory. The reviewer's `description` and `suggestion` are *one* hypothesis — verify against the spec before applying.

## Pre-fix Procedure

1. Read the design doc end-to-end (Scope, Invariants, Boundary Behavior, TDD Approach).
2. For each finding: diff the target file against the spec; list deviations before editing.
3. Apply the **minimum** patch that aligns code with the spec. Findings should resolve as a side effect.
4. If a finding disagrees with the spec, document the disagreement in `findings_skipped` and follow the spec.

## Constraints

1. **Only fix flagged issues.** No unrelated refactors.
2. **Preserve existing behaviour** (the OpenCode plumbing move must remain mechanical — no semantic drift).
3. Follow project conventions in `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`.
4. **Run tests after every fix** — targeted runs, not the full suite.

## Escalation

This is fix cycle 1 of 5. Prefer honest escalation over a Hail-Mary fix. If cycle 5 cannot resolve every finding while staying aligned with the spec, populate `findings_skipped` with a clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes:

```bash
uv run pytest tests/unit/chat/ -v
uv run pytest tests/dashboard/test_chat_router.py tests/dashboard/test_chat_endpoint_session_lifecycle.py -v
make lint
make typecheck
```

Do NOT report `tests_passed: true` unless all targeted tests pass with zero failures.

## Fix Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-fix-impl",
  "work_item": "F-00086",
  "fix_cycle": 1,
  "review_step": "S04",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": ["path/to/file.py"],
      "description": ""
    }
  ],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
