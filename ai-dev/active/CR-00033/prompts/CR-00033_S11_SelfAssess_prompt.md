# CR-00033_S11_SelfAssess_prompt

**Work Item**: CR-00033 -- Document Tailwind CLI Fallback Strategy in Tech Stack Docs
**Step**: S11
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, and
`./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orchestration DB.
Your job is to ANALYZE the item's execution, not to modify the database.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00033/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00033/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/CR-00033/reports/CR-00033_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00033/reports/CR-00033_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00033**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's
execution history and surface process improvement findings. This step is **soft** —
failure does NOT block the item from merging. Produce the best report you can even
if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered
by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which
reads the same path). In Claude Code, invoke it via the `Skill` tool with
`skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent
and you can reference it by name in your reasoning. Do NOT re-implement the analysis
procedure inline — the skill is the source of truth for the output contract (two files:
`_self_assess_report.md` + `_self_assess_findings.json`).

## Item-Specific Notes

- This is a **documentation-only** CR. The expected execution profile is short:
  one impl step (S01), two reviews (S02, S03), and seven QV gates (S04–S10).
- A clean run should show no fix-cycles. Any fix-cycle on S01–S03 is worth
  surfacing — it likely indicates the AC list was unclear or the prompt under-specified.
- QV-gate failures on a docs-only CR (lint, format, typecheck, unit-tests,
  integration-tests, arch-check, security-sast) would indicate the implementer
  touched a non-doc file. Treat any such failure as a HIGH-severity process
  signal even if a fix-cycle resolved it.
- Compare the actual diff (`git diff main..HEAD`) against the file manifest in
  the design doc. Any drift is worth a finding.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "CR-00033",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00033/reports/CR-00033_self_assess_report.md",
    "ai-dev/active/CR-00033/reports/CR-00033_self_assess_findings.json"
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
