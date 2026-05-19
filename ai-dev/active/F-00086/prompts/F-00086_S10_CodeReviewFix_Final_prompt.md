# F-00086_S10_CodeReviewFix_Final_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Fix Cycle**: 1 of 5 (subsequent cycles auto-renumber)
**Original Steps**: S01..S08
**Review That Triggered Fix**: S09 (Final Review)

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. If a finding requires schema changes, write a NEW Alembic revision — do NOT edit the existing F-00086 revision after it has been applied to any environment.)

## Input Files

- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (authoritative spec)
- `ai-dev/active/F-00086/reports/F-00086_S09_CodeReview_Final_report.md` — final review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_S10_CodeReview_FIX_Final_report.md`

## Context

The S09 final cross-agent review flagged CRITICAL / HIGH / MEDIUM(fixable) findings spanning multiple agents' work and/or missing requirements. Apply **only** those findings. Cross-cutting fixes may require coordinated changes across multiple modules — that is expected.

## Design Doc — Source of Truth (READ FIRST)

Read `ai-dev/active/F-00086/F-00086_Feature_Design.md` end-to-end. Final-review fixes often span sections (DB ↔ ORM ↔ API ↔ Frontend ↔ Tests). The design wins when findings disagree.

## Diagnostic Hypothesis — Findings to Address

Read `F-00086_S09_CodeReview_Final_report.md`. Each finding is one hypothesis from the reviewer — verify against the spec before applying.

## Missing Requirements

If the final review identified missing requirements, treat them as additional mandatory work. Each becomes a new test (TDD: RED first) followed by the minimal implementation to satisfy the design spec.

## Pre-fix Procedure

1. Read the design doc end-to-end.
2. For each finding (and missing requirement): diff the affected module against the spec; list deviations.
3. Apply the **minimum** patch that aligns code with the spec across all affected layers.
4. Cross-cutting fixes: ensure consistency between layers (e.g., a column type fix in S01 may require coordinated updates in S03's ORM, S06's response schema, and S08's test expectations).
5. If a finding disagrees with the spec, document in `findings_skipped` and follow the spec.

## Constraints

1. **Only fix flagged issues and implement missing requirements.** No unrelated refactors.
2. **Preserve existing behavior** that the design already specifies.
3. **Cross-cutting consistency** — when fixing one layer, propagate to dependent layers in the same fix cycle.
4. Follow project conventions in `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`.
5. **Run the full test suite after fixes** (both unit and integration).

## Escalation

This is fix cycle 1 of 5. Prefer honest escalation over a Hail-Mary fix. On cycle 5, document unresolvable findings in `findings_skipped` with clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes, run **targeted** tests over the F-00086 surface — the full-suite execution lives in S14 (`make test-unit`) and S15 (`make test-integration`), and re-running it here duplicates them and risks an I-00073-style timeout.

```bash
uv run pytest tests/unit/chat/ -v
uv run pytest tests/integration/test_chat_tabs_*.py -v
uv run pytest tests/dashboard/test_chat_*.py tests/integration/test_chat_endpoint_*.py -v
make lint
make typecheck
```

Do NOT report `tests_passed: true` unless every targeted test passes with zero failures. Broader regressions are caught by S14/S15 downstream.

## Fix Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00086",
  "fix_cycle": 1,
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
  "missing_requirements_implemented": [],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
