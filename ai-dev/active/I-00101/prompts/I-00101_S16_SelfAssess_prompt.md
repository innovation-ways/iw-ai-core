# I-00101_S16_SelfAssess_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S16
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` allowed.

## ⛔ Migrations: agents generate, daemon applies

This step does not modify anything — it analyzes the just-completed run.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00101/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00101/reports/` — step reports.
- Design doc + functional doc + manifest in `ai-dev/active/I-00101/`.

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_self_assess_report.md` — narrative analysis.
- `ai-dev/active/I-00101/reports/I-00101_self_assess_findings.json` — structured findings.

## Context

You are running the self-assessment step for **I-00101**.

Invoke the `iw-item-analyze` skill (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md` in Claude Code; the same path works in OpenCode). Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two output files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Item-Specific Findings to Surface

In addition to the skill's standard checks (agent thrashing, repeated tool failures, prompt gaps, manifest issues), surface these I-00101-specific signals:

1. **Self-eating fix-cycle budget exemption.** Did any fix cycle on THIS very item (I-00101's own S01..S15) get marked `escalated` due to scope violations? If yes, that is an extremely positive signal — the very feature this item ships would have helped recover from a scope escalation here. Quote the cycle and the violation paths if so.
2. **E2E fixture pattern.** Was the synthetic-FixCycle fixture in `ai-dev/active/I-00101/e2e_fixtures/001_*.py` viable, or did the qv-browser step spend cycles tuning it? If it took multiple attempts, recommend extracting a shared fixture helper (`tests/integration/fixtures/scope_escalation.py`?) for future incidents that need similar seeding.
3. **Cross-layer drift during review.** The S07 final review checks for drift between event names, endpoint URLs, badge label, helper names, template names. Did the per-agent reviews (S02/S04/S06) miss any cross-layer naming inconsistency that S07 caught? If so, recommend strengthening the per-agent review prompts to include a 1-line cross-doc check.
4. **Restart-mutation parity.** The new amend/revert endpoints duplicate the DB-mutation block from `restart_step` (new StepRun + flip status + clear timestamps + commit). Did the reviewers spot this as duplication and recommend extraction into a helper, or did everyone accept the duplication? If the duplication is left untouched, recommend a follow-up CR to extract a `_perform_step_restart(step, item, db)` helper in `actions.py`.
5. **`needs_fix` restart inconsistency.** This incident exposed that `restart_step` only accepts `failed | skipped` while the CLI `iw step-restart` accepts `failed | needs_fix`. We did NOT widen `restart_step` in this item (out of scope). Recommend whether the dashboard's `restart_step` should be widened in a follow-up incident, OR whether the new scope-aware endpoints supersede that need entirely.

## Soft-Step Semantics

This step's failure does NOT block merge — produce a usable report regardless. If analysis cannot complete, write a stub report with the partial findings + a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "self-assess-impl",
  "work_item": "I-00101",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00101/reports/I-00101_self_assess_report.md",
    "ai-dev/active/I-00101/reports/I-00101_self_assess_findings.json"
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
