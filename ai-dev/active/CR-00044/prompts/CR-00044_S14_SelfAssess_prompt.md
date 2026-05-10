# CR-00044_S14_SelfAssess_prompt

**Work Item**: CR-00044 -- Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Step**: S14
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`, `docker system prune`, …). The orchestration DB, daemon, and dashboard containers are outside your scope — touching them causes multi-hour outages (see the 2026-04-22 incident in `docs/IW_AI_Core_DB_Setup.md`). Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are analysing this item's execution, not modifying any database. Do not run `alembic upgrade|downgrade|stamp`. Read-only `alembic history|current|show` is fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/CR-00044/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00044/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/CR-00044/reports/CR-00044_self_assess_findings.json` — structured findings JSON.

## Context

Run the self-assessment for work item **CR-00044**. Invoke the **`iw-item-analyze`** skill (in Claude Code: the `Skill` tool with `skill: "iw-item-analyze"`) and follow its output contract exactly — it produces the two output files above. Do NOT re-implement the analysis inline. This step is **soft**: its failure does not block merge, but produce the best report you can even if the analysis is partial. If it can't complete, write a stub report explaining why plus a `findings: []` JSON.

This CR is small (one backend step, two reviews, one test step, QV gates, a browser step) — pay particular attention to whether any fix-cycle was triggered by the path-traversal guard or the `_SLUG_TO_DOC` anchor verification, since those are the easy-to-get-subtly-wrong parts; if so, surface a prompt-clarity finding.

## Soft-Step Semantics

Failure here does NOT block merge — still produce a usable report. If analysis can't complete, write a stub `_self_assess_report.md` explaining why and a `_self_assess_findings.json` with `"findings": []`.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00044",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00044/reports/CR-00044_self_assess_report.md",
    "ai-dev/active/CR-00044/reports/CR-00044_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
