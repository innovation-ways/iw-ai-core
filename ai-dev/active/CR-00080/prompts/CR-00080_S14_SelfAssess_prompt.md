# CR-00080_S14_SelfAssess_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Analysis only — no infrastructure changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does not touch migrations or DB state.

Allowed read-only commands: `alembic history`, `alembic current`, `alembic show`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source; should equal `CR-00080`).
- **Worktree logs** — `.worktrees/CR-00080/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00080/reports/` — all step reports (secondary evidence only).
- **DB telemetry** — `uv run iw item-status CR-00080 --json` for the canonical step/fix-cycle record.
- **Spike evidence** — `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` — the data S02's surface decision depended on.

## Output Files

- `ai-dev/work/CR-00080/reports/CR-00080_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00080/reports/CR-00080_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00080**.

This step invokes the `iw-item-analyze` skill. The skill is auto-discovered by both Claude Code (`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

### CR-00080-specific focus areas

When the skill prompts for item-specific analysis, weight these questions:

1. **Did S01 hit its 3600s timeout?** The CR-00059 spike took 0:17:17 (1037s) on the narrow daemon-only scope, with 0 mutants actually executing (cov-fail-under killed each run immediately). The widened `orch/` scope with a working runner was expected to take materially longer. If S01 ran past 3600s and reported `partial`, did S02 still get usable M / K numbers? If S01 hit a hard timeout, did the design's "partial is acceptable + viability guard" cushion absorb the blast radius cleanly?

2. **Did the cov-fail-under fix actually solve the 0-mutants problem?** Read `evidences/pre/cr-00080-spike-measurements.txt`. Did mutants generated go from 0 (CR-00059) to a positive integer (CR-00080)? If still 0, the fix did not land — this is a process finding even if every gate passed.

3. **Did the AC3 viability guard fire correctly?** Read S02's report. If `M >= 20%` AND `K >= 30`, S02 should be `complete` with the workflow file created. If `M < 20%` OR `K < 30`, S02 should be `blocked` with NO workflow file. A mismatch is the most serious failure mode — record it as a finding.

4. **Did the threshold formula land in the correct band?** (Only applicable if S02 is `complete`.) Did S02 quote both M (measured score) and T (chosen threshold) and derive T from the band-based margin rule (5 for M>=70, 3 for 50<=M<70, 2 for 20<=M<50)? Or did the agent eyeball a value?

5. **Did the iw-ai-core-testing skill sync work first try?** S03 runs `iw sync-skills --force iw-ai-core-testing`. Did it need a fix-cycle to land the sync? CR-00049 had skill-sync gotchas; if CR-00080 hit the same one, recommend an iw-workflow improvement. Confirm `iw-workflow` skill was NOT synced (it should not have been touched).

6. **Was the step-granularity rule respected?** This CR has three implementation steps (S01 spike, S02 wiring, S03 docs). Did any of them creep into another's territory (e.g., S01 starting on docs, or S03 changing the threshold)?

7. **Did S04 catch any T-inconsistency across surfaces?** If S05 found drift in the T integer or "nightly GH workflow" phrasing across strategy doc / tracker / skill / workflow YAML that S04 missed, recommend improving the per-step review checklist.

8. **Canonical-chain audit**: did `skills/iw-workflow/SKILL.md` (and its project copy) stay UNCHANGED across this CR's diff? It must — mutmut lives on the nightly surface only. If either file was touched, that is a scope violation and a finding (the design deliberately removed these paths from `scope.allowed_paths`).

9. **Did the design correctly anticipate the cost?** Was S01's 3600s budget enough, or was the spike longer than that? Did the partial-data path + viability guard absorb the cost cleanly, or did the operator hit unexpected friction?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete (e.g., logs missing), write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (review-only)

For each behaviour-implementing step whose report claims new behavioural tests:
- S01: must have `tdd_red_evidence` with `AssertionError` (not import/collection error).
- S02 + S03: must use `"n/a — …"` (wiring / docs steps).

If S01's evidence is missing or implausible, record a finding.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00080/reports/CR-00080_self_assess_report.md",
    "ai-dev/work/CR-00080/reports/CR-00080_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
