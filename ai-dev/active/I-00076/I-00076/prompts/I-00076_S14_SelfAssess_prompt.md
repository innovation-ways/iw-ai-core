# I-00076_S14_SelfAssess_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). Testcontainers spun up by pytest fixtures are the
allowed exception. Read-only `docker ps|inspect|logs` and `./ai-core.sh` / `make` targets are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run any alembic command. Your job is to ANALYZE the item's execution, not to
modify the database. (`alembic history|current|show` read-only is fine; testcontainer fixtures
run migrations themselves.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00076/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00076/reports/` — existing step reports (secondary evidence).
- **Item DB telemetry** — `uv run iw item-status I-00076 --json` and the `daemon_events` for this item.

## Output Files

- `ai-dev/active/I-00076/reports/I-00076_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00076/reports/I-00076_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00076**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution
history (retries, fix cycles, agent thrash, repeated tool failures, prompt/manifest gaps) and
surface process-improvement findings. **This step is soft** — failure does NOT block the item
from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the
`Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the
agent — reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline;
the skill is the source of truth for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`). The skill NEVER reviews the generated code itself and NEVER edits
any file — it reports only.

## Soft-Step Semantics

Failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete,
write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00076/reports/I-00076_self_assess_report.md",
    "ai-dev/active/I-00076/reports/I-00076_self_assess_findings.json"
  ],
  "preflight": {"format": "ok|skipped:no-code-changes", "typecheck": "ok|skipped:no-code-changes", "lint": "ok|skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
