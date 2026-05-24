# I00108_S14_SelfAssess_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` should be exit 2 usage error, not exit 3 TypeError
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. You are analyzing logs and reports, not modifying infra. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are NOT modifying the database. No alembic commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00108/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00108/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00108/reports/I-00108_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **I-00108**. This is the **last** step in the manifest (after all QV gates), so the execution history is complete: any retries triggered by `lint` / `assertions` / `format-check` / `type-check` / `unit-tests` / `integration-tests` / `diff-coverage` / `security-secrets` are now visible to you.

Use the `iw-item-analyze` skill to perform the analysis. The skill is auto-discovered by both Claude Code (`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## What to look for in this item specifically

I-00108 is a small, narrowly-scoped CLI usability fix surfaced by the CR-00073 contract test layer. The fix is a single conditional in one CLI callback plus two regression tests. Self-assessment is mostly a baseline run for the workflow analytics. Things worth flagging if they occurred:

- **xfail-marker handoff between S01 and S03.** S01 is expected to record `XPASS(strict)` on `test_doc_update_new_doc_without_tier_is_clean_usage_error` (the desired contract test now passes); S03 removes the `@pytest.mark.xfail(strict=True)` marker so the test records as a normal `passed`. If S02 review missed the `XPASS(strict)` and treated it as a regression, or if S03 failed to remove the marker (or removed assertions instead), note the cycle. The XPASS-strict-to-marker-removed handoff is a non-obvious workflow step that future incidents could trip on.
- **Update path regression.** The S01 pre-check must fire **only** when no existing doc is found. If a fix cycle was needed because the pre-check fired on the update path (breaking `test_doc_update_existing_doc_update_without_tier_succeeds`), note this as a prompt-clarity issue — S01 and S02 prompts both explicitly call out the update-path-stays-optional requirement.
- **Scope creep on `orch/doc_service.py`.** The design doc and S02 review both explicitly say `DocService.create_doc()`'s required-args signature is intentional and out of scope. If an S01 retry tried to make those args optional in the service layer instead of guarding at the CLI layer, note it as a strong signal that the design's intent needs more emphasis in the S01 prompt.
- **Assertion-scanner trip on the new regression tests.** S03's two regression tests use specific-value assertions (doc id equals, title equals, exit code equals). If `make test-assertions` flagged either as shape-only or tautology, note the cycle — the S03 and S04 prompts both warn about this.
- **`make test-integration` runtime.** The integration-tests QV gate (S11, 1800 s budget) runs the full integration suite including the CR-00073 contract layer. If this step needed multiple fix cycles for unrelated reasons (other items' tests), note the cycle and any latent test instability surfaced.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step whose report claims new behavioural tests:

- **S01 (backend-impl)** is expected to cite the `XPASS(strict)` line from the pre-existing reproduction test as its `tdd_red_evidence` — that is the RED→GREEN signal for this fix. An empty `tdd_red_evidence` or a generic "n/a" is a documentation-clarity issue (LOW); flag it only if the fix coverage is actually missing.
- **S03 (tests-impl)** is exempt from the RED-run requirement (it adds tests after the fix lands). The two new tests pin **preserved** behaviour (update path, new-doc happy path) — there is no bug to RED on. S03's `tdd_red_evidence` is expected to be `"n/a — regression-guard tests pin preserved behaviour"` plus a pytest GREEN line for the xfail-flipped reproduction test.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00108",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00108/reports/I-00108_self_assess_report.md",
    "ai-dev/active/I-00108/reports/I-00108_self_assess_findings.json"
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
