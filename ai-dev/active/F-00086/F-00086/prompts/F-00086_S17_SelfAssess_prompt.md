# F-00086_S17_SelfAssess_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S17
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker command that changes container/volume/network state. Read-only introspection is allowed.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/F-00086/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/F-00086/reports/` — every step report from S01..S16, plus any fix-cycle reports.

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_self_assess_report.md` — human-readable narrative analysis
- `ai-dev/active/F-00086/reports/F-00086_self_assess_findings.json` — structured findings JSON

## Context

You are running the self-assessment step for F-00086 (Multi-tab AI Assistant on OpenCode). This step uses the `iw-item-analyze` skill to surface recurring process issues across the just-completed workflow — agent thrashing, repeated tool failures, prompt gaps, manifest issues, redundant env/install steps.

**You analyze the EXECUTION HISTORY, not the generated code.** Look at retry counts, fix cycles, gate failures, agent thrash patterns. Do NOT review the multi-tab feature itself for correctness — that's S04/S09's job.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, reference the skill by name. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Particular things to watch for in F-00086

The feature spans 5 implementation steps + 4 QV gates + 1 browser verification. Areas with elevated risk for thrash/retry:

- **S01 Database** — first item to add a UUID PK in this codebase since (check). If `gen_random_uuid()` vs `uuid.uuid4()` choice required multiple revisions of the migration, surface that.
- **S03 Backend mechanical move** — `git mv` discipline. If reviewers had to re-flag missed import path updates across multiple fix cycles, the prompt may need a stronger pre-flight grep instruction.
- **S07 Frontend** — Tailwind / `make css` health is intermittent in worktrees (I-00067). If S07 retried multiple times because of CSS toolchain issues, note that as a prompt-fix opportunity.
- **S08 Tests adaptation** — if many existing tests required deeper-than-mechanical changes (i.e., behavioural reshape), the design's "adapt, don't delete" rule may have been ambiguous; surface for prompt clarification.
- **S15 Integration tests** — if SSE/EventSource tests were flaky, document the flake pattern.
- **S16 Browser verification** — V2/V5 depend on a real OpenCode runtime responding in the test stack. If they failed with timeout-style errors, that's a stack-config issue (ENV_DATA_MISSING-class), not a code defect.

## TDD RED Evidence (cross-step check)

For each behaviour-implementing step (notably S03 Backend, S06 API), confirm the report contains plausible `tdd_red_evidence`:

- S03: expected to cite a `tab_service.py` test (e.g., `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten`) with an `AssertionError`/`AttributeError` / `ImportError` snippet from the RED run.
- S06: expected to cite a `test_chat_tabs_api.py` test (e.g., `test_post_tabs_rejects_unknown_runtime`) with `assert 404 == 400` or equivalent snippet.

If either step's `tdd_red_evidence` is missing, claims `n/a` without justification, or shows a non-plausible failure shape (e.g., a syntax error in the test itself), surface as a finding.

`tests-impl` (S08) is exempt — it's a dedicated coverage step.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/F-00086/reports/F-00086_self_assess_report.md",
    "ai-dev/active/F-00086/reports/F-00086_self_assess_findings.json"
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
