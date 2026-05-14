# CR-00052_S12_SelfAssess_prompt

**Work Item**: CR-00052 -- Allure reporting recipes + curated smoke layer with SLA (P1-CR-E)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands except read-only or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database. This CR adds no migrations.

Allowed for agents:
  - alembic history / current / show (read-only)
  - Running migrations inside testcontainer fixtures (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor).
- **Worktree logs** — `.worktrees/CR-00052/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00052/reports/` — existing step reports (S01 Backend, S02 CodeReview, S03 CodeReview_Final, S04–S11 QvGate reports).
- **Pre-patch evidence** — `ai-dev/active/CR-00052/evidences/pre/cr-00052-smoke-baseline.txt`.

## Output Files

- `ai-dev/active/CR-00052/reports/CR-00052_self_assess_report.md` — Human-readable narrative.
- `ai-dev/active/CR-00052/reports/CR-00052_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00052** — the last Phase-1 grouping CR. This step invokes the `iw-item-analyze` skill. Soft step (failure does NOT block merge), but produce a usable report.

**Use the `iw-item-analyze` skill** to perform the analysis. Auto-discovered by Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`). Invoke via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline.

## Context-specific guidance for CR-00052

Three things make this CR's self-assess especially informative for future Phase-1+ work:

- **S09 was the first real run of `make test-integration` as a QV gate.** The canonical command was flipped from the no-op `make allure-integration` to the real `make test-integration` on 2026-05-14 (direct change, commit `a4e9ac8a`). Before this CR, the `integration-tests` gate had been a silent no-op since CR-00046's introduction. Did S09 pass cleanly on its first real outing? Did it surface any pre-existing integration-test failures the no-op gate had been hiding? If yes — flag as a HIGH process finding: the no-op gate had been masking real issues for months, and this CR's S09 is where the truth came out. Future agents/operators should know that the pre-2026-05-14 "passed S15" status is suspect.

- **The audit-table-as-deliverable is a new pattern.** Previous Phase-1 CRs (CR-00046 baseline, CR-00050 109-finding triage) used a similar "explicit per-row triage with rationale" pattern. Did S01's audit table for the 16 smoke tests follow the precedent set by CR-00050's gitleaks triage? Were the rationales substantive (each row names the path it covers, not just "smoke") or were they thin? This pattern is becoming the IW way of justifying curation decisions — surface findings about whether it scaled well to 16 rows vs. CR-00050's ~109.

- **Compare CR-00052 with CR-00050.** Both were CI/tooling/docs-only Phase-1 grouping CRs with no production code. Both required audit tables (16 smoke decorators / 109 gitleaks findings). Both touched documentation across 3+ locations. Did CR-00052 spend less / more time per file changed than CR-00050? Did it have fewer / more fix cycles? Process improvement findings here help calibrate sizing estimates for Phase-2 CRs.

- **Phase 1 is now (nearly) complete.** This is the last grouping CR. After CR-00052 merges, the remaining Phase-1 work is only: CR-00049 (lingering draft — re-enable `pytest-randomly`), the low-urgency assertion-baseline scrub follow-up, and the integration-tests-gate hardening if S09 surfaced issues. Surface any **Phase-2 readiness** findings: are there process improvements from Phase-1 the team should bake into Phase-2's mutation-testing / property-tests / flaky-workflow CRs before starting them?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

For S01 (the only behaviour-implementing step in this CR), verify the report contains `tdd_red_evidence`:

- The field records both the empty-allure-stub proof AND the 16-tests / no-SLA smoke baseline.
- The failure snippet is concrete: `make -n allure-unit` output (or equivalent) PLUS the 16-marker grep count + wall-clock measurement.
- If S01's `tdd_red_evidence` is `"n/a"` or one-half is missing, flag as a HIGH finding — this CR has two concrete RED anchors by design.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00052",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00052/reports/CR-00052_self_assess_report.md",
    "ai-dev/active/CR-00052/reports/CR-00052_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Includes: S09-first-real-run analysis; audit-table-pattern comparison with CR-00050; Phase-2 readiness findings."
}
```
