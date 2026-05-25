# I-00112_S19_SelfAssess_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S19
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. You are analysing the item's execution history, not modifying infrastructure.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Read-only inspection of the S01 revision is fine; `alembic upgrade/downgrade/stamp` is forbidden.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00112/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00112/reports/` — all step reports.
- **Design document** — `ai-dev/active/I-00112/I-00112_Issue_Design.md`.
- **Functional document** — `ai-dev/active/I-00112/I-00112_Functional.md`.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00112/reports/I-00112_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for I-00112.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings (agent thrash, repeated tool failures, prompt gaps, manifest issues, redundant env steps). The skill NEVER reviews the generated code itself and NEVER edits any file — it reports only.

**Use the `iw-item-analyze` skill.** In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. The skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`). Do NOT re-implement the analysis procedure inline.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## Areas To Pay Special Attention To

I-00112 has four interesting characteristics worth surfacing in the analysis:

1. **Contract-level test boundary move.** The fix deliberately moves the test mock from `fire_claude` (wrapper) to `subprocess.run` (real decision point). If S07 mocked at the wrong boundary in any fix cycle, that's a recurrence of the bug class — surface it.
2. **Three-step coupling (S01 schema → S03 logic → S05 UI).** S03 broke S05's data shape (added new ORM fields) and S05 broke S03's tests (new fragment column count breaks tests asserting on three-column shape). If multiple fix cycles bounced between S03 and S07 chasing this, that's a manifest design issue worth flagging.
3. **Magic-number discipline.** `_MIN_SUCCESS_ELAPSED_MS = 500` lives in `keep_alive_poller.py` (per S03's prompt). If S03 inlined `500` anywhere else, S04 should have caught it. If S04 missed it, that's a prompt gap — the per-agent code-review prompt may need stronger "named constant" guidance.
4. **OAuth credential timing coincidence.** The pre-fix bug surfaced when an OAuth token refresh ran adjacent to a poll firing. If any agent during execution flagged the auth flow as the cause, that's misdiagnosis — surface it so the prompt's "Root Cause Analysis" section in future incidents calls out the credential refresh red herring more explicitly.

These are hints, not a checklist. The skill's standard procedure is authoritative; these are just notable surfaces.

## TDD RED Evidence

For each behaviour-implementing step (S03 only — S01/S05 are RED-exempt by template policy, S07 is a dedicated coverage step):

- S03's report must contain `tdd_red_evidence` referencing the existing tests broken by the `FireResult` signature change. If the evidence is missing, or quotes an `ImportError` / `SyntaxError` instead of an `AttributeError` / `AssertionError`, flag it.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "self-assess-impl",
  "work_item": "I-00112",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00112/reports/I-00112_self_assess_report.md",
    "ai-dev/active/I-00112/reports/I-00112_self_assess_findings.json"
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

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S19
# work — invoke iw-item-analyze skill
uv run iw step-done I-00112 --step S19 --report ai-dev/active/I-00112/reports/I-00112_self_assess_report.md
```
