# I00103_S17_SelfAssess_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step**: S17
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. You are analyzing logs and reports, not modifying infra. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

You are NOT modifying the database. No alembic commands. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00103/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00103/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00103/reports/I-00103_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **I-00103**. This is the **last** step in the manifest (after all QV gates and the browser verification), so the execution history is complete: any retries triggered by `lint` / `format-check` / `type-check` / `arch-check` / `security-sast` / unit / frontend / integration / browser steps are now visible to you.

Use the `iw-item-analyze` skill to perform the analysis. The skill is auto-discovered by both Claude Code (`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (the two output files above).

## What to look for in this item specifically

Because I-00103 is a small observability fix with deterministic acceptance criteria, this self-assessment is mostly a baseline run for the workflow analytics. Things worth flagging if they occurred:

- **Field-name drift across S01 / S03 / S05.** If S01 named the field one thing, S03 read another, and S05 had to be re-run to catch up, that's a workflow defect — the GO/NO-GO checklist for I-00103 explicitly called out cross-agent contract consistency as a HIGH risk. Note any fix-cycle iterations on this axis.
- **Browser-step environment gaps.** S16 may have called `iw step-fail` with `ENV_DATA_MISSING:` if the fixture file was required but not seeded. Note whether the fixture file (`e2e_fixtures/001_seed_failed_event_with_per_file_errors.py`) had to be added late.
- **Test placement errors.** If S05 placed a dashboard test under `tests/unit/` (no `client` fixture there per I-00067), it would have failed with `fixture 'client' not found` — note this as a prompt-clarity issue if it occurred.
- **CSS-assertion false positives.** If S05's dashboard test used bare-substring class assertions and passed for the wrong reasons (a CSS source map containing `per-file-error`), the S06 / S07 reviews should have caught it. Note any HIGH finding on this axis.
- **`make test-frontend` vs `make test-dashboard`.** The manifest uses `make test-frontend` (= alias). If the gate failed because the alias was wrong, that's a workflow defect.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (notably S01 backend) whose report claims new behavioural tests were added:

- The report should contain `tdd_red_evidence`. For I-00103, S01 is expected to use `"n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach"` because the design doc explicitly delegates tests to S05.
- S05 (`tests-impl`) is exempt from the RED-run requirement (it adds tests after the code exists). Its `tdd_red_evidence` is expected to cite the design-time RED proof (the pre-fix evidence screenshot at `evidences/pre/`).
- S03 (`frontend-impl`) is template-only and is expected to use `"n/a — template/markdown edits only, no production logic; behavioural tests delegated to S05 per design doc TDD Approach"`.

If S01 / S03 / S05 use different forms than the above, note as a documentation-clarity finding (LOW); only flag as HIGH if the test coverage is actually missing.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "I-00103",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00103/reports/I-00103_self_assess_report.md",
    "ai-dev/active/I-00103/reports/I-00103_self_assess_findings.json"
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
