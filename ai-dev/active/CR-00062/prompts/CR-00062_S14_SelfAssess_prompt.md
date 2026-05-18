# CR-00062_S14_SelfAssess_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S14
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Read-only `docker ps / inspect / logs` allowed. No state-changing commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database. Do NOT run any alembic command.

## Input Files

- All step reports under `ai-dev/active/CR-00062/reports/`
- Daemon logs and DB telemetry for CR-00062 (via `uv run iw item-status CR-00062 --json` and the DB queries the `iw-item-analyze` skill recommends)
- Workflow manifest: `ai-dev/active/CR-00062/workflow-manifest.json`
- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- Skill instructions: `skills/iw-item-analyze/SKILL.md` (and synced copy under `.claude/skills/iw-item-analyze/SKILL.md`)

## Output Files

- `ai-dev/active/CR-00062/reports/CR-00062_S14_SelfAssess_report.md`

## Context

You are running the `iw-item-analyze` skill against the just-completed CR-00062 execution. Your job is to surface **process issues**, not to review the code itself. Examples of what to flag:

- Agent thrashing (an agent retried >2 times for the same root cause).
- Repeated tool failures (e.g., a flaky test that caused multiple fix cycles).
- Redundant env/install steps that the orchestrator could amortize.
- Prompt gaps (a step's prompt didn't constrain enough, and the agent had to infer).
- Manifest issues (a step that should have been parallel was serial, or vice versa).
- Environment issues that wasted a fix-cycle slot (e.g., a missing tool on PATH that the prompt didn't pre-check).

## Requirements

Follow `skills/iw-item-analyze/SKILL.md` exactly. Do NOT review the generated code itself. Do NOT edit any file outside `ai-dev/active/CR-00062/reports/`.

Specifically look for CR-00062-relevant patterns:

- Did S03's eight-site dispatch require any fix-cycle? If so, was the prompt's site enumeration incomplete?
- Did S04's `agents/pi/` mirror operation hit any frontmatter-translation surprises that the prompt didn't anticipate?
- Did S05's stub-`pi` PATH mechanism work first-try, or did it require platform-specific tuning? If the latter, document for future runtime-add CRs.
- Did `make migration-check` (S02) catch anything that locally-run `make migration-check` (S01 preflight) missed? If yes, that's a useful signal about local-vs-CI environment drift.
- Did any review step (S06 / S08) raise a finding that, in hindsight, should have been caught by a more specific test in S05? File that as a prompt-improvement note for future tests-impl prompts.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S14_SelfAssess_report.md"
  ],
  "preflight": {
    "format": "n/a — analysis only",
    "typecheck": "n/a — analysis only",
    "lint": "n/a — analysis only"
  },
  "tests_passed": true,
  "test_summary": "analysis-only",
  "tdd_red_evidence": "n/a — self-assess step",
  "process_findings": [
    {"id": "P1", "category": "thrash|tool|prompt|manifest|env", "severity": "high|medium|low", "summary": "<one line>", "recommendation": "<one line>"}
  ],
  "blockers": [],
  "notes": ""
}
```
