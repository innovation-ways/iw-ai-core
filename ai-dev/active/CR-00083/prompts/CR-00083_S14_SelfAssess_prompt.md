# CR-00083_S14_SelfAssess_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Step**: S14
**Agent**: SelfAssess (self-assess-impl)

---

## ⛔ Docker is off-limits

Standard policy. This step ANALYZES; it does not modify infrastructure.

## ⛔ Migrations: agents generate, daemon applies

Read-only step.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/CR-00083/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00083/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_self_assess_report.md` — narrative analysis.
- `ai-dev/work/CR-00083/reports/CR-00083_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **CR-00083** (Performance-budget test layer — Phase 4 first item).

This step invokes the **`iw-item-analyze`** skill to analyse the just-completed item's execution history and surface process improvement findings.

This step is **soft** — failure does NOT block merge. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## What to look for (CR-00083-specific)

Beyond the skill's standard checks, weight these CR-00083-specific signals:

1. **Budget revision mid-step.** Did S01 or S02 have to revise a BUDGET constant after the initial 10-run sample because of an outlier? If yes, the 10-run baseline methodology may need more rounds — record a finding pointing the strategy doc at a higher round count for the budget-set phase.
2. **`perf` marker wiring**. Did S10 (`make test-unit`) or S11 (`make allure-integration`) burn a fix cycle because a perf test was accidentally collected? This is the most likely failure mode for this CR (the `not perf` `addopts` append is fragile). If it happened, recommend a CONTAINS guard test (`tests/unit/test_perf_marker_isolation.py` or similar) for a follow-up CR.
3. **Cross-surface consistency**. Did S04/S05 catch a date or CR-ID mismatch across the strategy doc / skill / mirror / tracker quadruple? This is a recurring failure mode (CR-00072/73/74/75/76 each had >0 fix cycles around it). Record the count vs. those historical CRs.
4. **RAG embedding stub coupling**. Did S02's deterministic-stub patch raise any unexpected coupling concerns (e.g., the stub had to patch a function that production code calls in a way that the patch can leak between tests)? If yes, the stub may need to be a fixture-scoped monkeypatch rather than a module-level patch.
5. **Workflow YAML lint**. Did the `make lint` gate (S06) trip on the new `.github/workflows/perf-budgets.yml`? If yes, the project's lint pipeline may need a YAML linter integration follow-up.
6. **Phase 4 comparison**. Compare against Phase 1/2/3 CR setup-cost patterns (CR-00059 mutmut spike, CR-00060 Hypothesis property tests, CR-00061 quarantine workflow, CR-00072 contract sweep, CR-00075 security tests). Look for: dep-installation cycles, marker-registration cycles, doc-sync cycles. Is CR-00083's cycle count higher or lower than the average? If higher, what specifically caused the excess?

## Soft-Step Semantics

Failure does NOT block merge — produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

S01 and S02 are behaviour-implementing (Backend) and added new behavioural tests (the perf modules themselves). Verify their reports' `tdd_red_evidence` fields record the initial-measurement → budget-set → final-green narrative — NOT `"n/a"` or a generic "tests pass". S03 (docs/CI/skill) should use `"n/a — docs/CI/skill/tracker only"`. Flag deviations.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00083/reports/CR-00083_self_assess_report.md",
    "ai-dev/work/CR-00083/reports/CR-00083_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. CR-00083-specific signals reviewed (budget revision, perf marker wiring, cross-surface consistency, RAG stub coupling, workflow YAML lint, Phase 4 cycle-count comparison)."
}
```
