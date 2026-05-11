# I-00080_S16_SelfAssess_prompt

**Work Item**: I-00080 -- Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S16
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`, `docker system|container|image prune`).
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Your job is to ANALYZE the item's execution, not to modify the database. Read-only `alembic history|current|show` is allowed.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00080/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00080/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00080/reports/I-00080_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00080**. This step invokes the **`iw-item-analyze`** skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps, manifest issues) and surface process-improvement findings anchored in evidence. It is a **soft** step — failure does NOT block merge; produce the best report you can even if the analysis is partial. Do NOT re-implement the analysis inline — invoke the `iw-item-analyze` skill (via the `Skill` tool in Claude Code with `skill: "iw-item-analyze"`; in OpenCode reference it by name) — the skill defines the output contract (the two files above). The skill NEVER reviews the generated code and NEVER edits any file other than its two report outputs.

Relevant context for this item that the analysis might touch: it spanned three implementation agents (backend + frontend + api) because the bug genuinely lived in three layers; browser verification (S15) required dark-mode toggling and an e2e fixture; the dark-mode label-contrast root cause was empirically confirmed at design time (`color: rgb(255,255,255)`) but the exact CSS mechanism was left for the implementer to nail down — note whether that ambiguity caused any thrash.

## Soft-Step Semantics

Failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "self-assess-impl",
  "work_item": "I-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00080/reports/I-00080_self_assess_report.md",
    "ai-dev/active/I-00080/reports/I-00080_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
