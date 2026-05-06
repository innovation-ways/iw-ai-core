# I-00072_S13_SelfAssess_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Step**: S13
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

Allowed: testcontainers from pytest fixtures (read-only here); read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. Your job here is analysis-only — alembic is not in scope.

Allowed for agents: `alembic history|current|show` (read-only).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00072/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00072/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00072/reports/I-00072_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00072**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings — agent thrashing, repeated tool failures, redundant env/install steps, prompt gaps, manifest issues. **It does NOT review the generated code itself** (S05 already did that). It looks at the *process*, not the *output*.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which reads the same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning.

Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## What to look for, specific to this item

While the skill drives the analysis, here are I-00072-specific signals worth flagging if you spot them:

- **CR-00028 follow-on debt.** This item exists because CR-00028 added `merge_failed` without updating the CLI's filter. If the logs show similar drift (e.g., a comment in merge_queue.py referencing CR-00028 but no test pinning the new status's behaviour), surface it as a "test gap that allowed the regression" finding — it suggests a pattern that future enum-changing CRs should follow.
- **I-00042 forward-coverage.** This item adds `migration_rolled_back` to the constant despite no producer being wired. If the worktree logs show this point being challenged (S01 or S02 questioning whether to include it), the design's reasoning should be captured for future "should we forward-cover unwired enums?" decisions.
- **Test-location pattern.** S03 placed all new tests in `tests/unit/test_merge_queue_cli.py` (per I-00067). If any fix cycle flipped tests between `tests/unit/`, `tests/integration/`, and `tests/dashboard/`, that signals the I-00067 lesson didn't fully land — note the pattern so the prompt template's guidance can be tightened.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00072/reports/I-00072_self_assess_report.md",
    "ai-dev/active/I-00072/reports/I-00072_self_assess_findings.json"
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
