# I-00114_S14_SelfAssess_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step ANALYZES, never applies. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00114/ai-dev/logs/` — run logs and fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00114/reports/` — all step reports through S13.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document.
- `ai-dev/active/I-00114/I-00114_Functional.md` — functional summary.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00114/reports/I-00114_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment for I-00114 — the Incident that itself was meant to prevent a class of silent step-crashes. There is a recursive flavour here: pay particular attention to whether the steps of I-00114 itself exhibited the very narration-exit pattern the fix is meant to address. If so, that's a notable data point for the analysis (and indirectly validates the fix's importance).

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code and OpenCode. In Claude Code, invoke it via the Skill tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline.

## Item-Specific Anchors for the Analysis

When the skill analyses this item, surface findings on:

1. **Narration-exit recurrence within I-00114 itself** — query the `daemon_events` for `entity_id='I-00114'` and check for any `step_crashed` events. Each one is a candidate "this Incident's own steps hit the very bug it fixes" data point — quote them.
2. **Builder pairing drift risk** — note whether the `_build_initial_command` / `_build_fix_inner_command` pair is still flagged with a "Keep in sync" comment after the fix; if not, propose adding/strengthening the comment.
3. **Test-determinism issues** — flag any flaky-test signals from S13's integration run (retries, timeouts on `test_pi_narration_guard.py`).
4. **Coverage of pi runtime evolution** — note whether the JSONL classifier has a TODO/comment about which pi schema version it targets and what happens on a future schema change.

## Soft-Step Semantics

This step's failure does NOT block merge. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00114",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00114/reports/I-00114_self_assess_report.md",
    "ai-dev/active/I-00114/reports/I-00114_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
