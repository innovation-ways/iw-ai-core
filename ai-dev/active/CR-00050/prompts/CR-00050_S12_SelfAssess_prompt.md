# CR-00050_S12_SelfAssess_prompt

**Work Item**: CR-00050 -- Security gates — gitleaks (blocking) + Semgrep (nightly-first) (P1-CR-D)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands allowed except read-only introspection or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database. This CR adds no migrations.

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor).
- **Worktree logs** — `.worktrees/CR-00050/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00050/reports/` — existing step reports (S01 Backend, S02 CodeReview, S03 CodeReview_Final, S04–S11 QvGate reports).
- **Pre-patch evidence** — `ai-dev/active/CR-00050/evidences/pre/cr-00050-gitleaks-pre.json` and `cr-00050-gitleaks-summary.md`.

## Output Files

- `ai-dev/active/CR-00050/reports/CR-00050_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00050/reports/CR-00050_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00050**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings. This step is **soft** — failure does NOT block the item from merging.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Context-specific guidance for CR-00050

This CR introduces a brand new daemon QV gate (`security-secrets`, the 8th canonical gate) AND runs it on itself (S11). When you analyse this item's execution, pay attention to:

- **Did S11 (security-secrets) need a fix cycle?** Zero fix cycles on S11 is the success criterion — it would mean S01's triage was complete and the gate works on its own author. Any fix cycle on S11 is a HIGH process finding: it would mean the gate works *too well* on this CR's own changes, or that S01's deliverable 0 triage missed something. Compare with the historical pattern of newly-introduced gates (CR-00046's `assertions` gate, CR-00047's `diff-coverage` gate, CR-00048's `pytest-randomly` whose gate then needed CR-00049 to fix).
- **Did Semgrep findings burn fix cycles on S04 or S08?** Semgrep is GH-only in this CR (not a daemon gate yet), so it shouldn't have direct effect — but if S01 added inline `# nosemgrep:` comments without thinking, those might have triggered lint/format violations that DID burn cycles. Surface as a process finding.
- **Did the 109-finding triage produce REAL_OR_SUSPICIOUS escalations?** If S01 escalated >0 real-looking secrets via `blockers`, the CR couldn't merge until the operator rotated them. Note this in the report — it's a significant process step that delays merging and the platform should surface it more visibly than via the blockers field alone.
- **Did the `# why` rationales in `.gitleaks.toml` get reviewed at S02 / S03 for quality?** The review prompts explicitly check this. Surface any findings from S02/S03 about weak rationales — they're a pattern worth flagging for future security-config CRs.
- **Compare CR-00050 to CR-00046 (the assertion-scanner CR)** — both introduced a brand new daemon QV gate, both had a triage / baseline workflow (621 entries in CR-00046's case, ~109 here). Are there process lessons CR-00050 could have learned from CR-00046's self-assess that weren't applied? If yes, that's a high-value process finding for the next CR that introduces a baseline-driven gate.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

For S01 (the only behaviour-implementing step in this CR), verify the report contains `tdd_red_evidence`:

- The field records the 109-finding (or whatever current count is) pre-patch gitleaks scan.
- The failure snippet shows the `WRN leaks found: <N>` line + the top RuleIDs.
- If S01's `tdd_red_evidence` is `"n/a"`, flag as a HIGH finding — this CR has a concrete RED anchor.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00050",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00050/reports/CR-00050_self_assess_report.md",
    "ai-dev/active/CR-00050/reports/CR-00050_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Pattern comparison with CR-00046 (the prior baseline-driven gate-introducing CR) included."
}
```
