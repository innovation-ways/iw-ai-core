# F-00091_S20_SelfAssess_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S20
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`docker logs`/`docker inspect` are allowed for evidence gathering.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Read-only `alembic history/current/show` is allowed.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/F-00091/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/F-00091/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/F-00091/reports/F-00091_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **F-00091**.

This step invokes the `iw-item-analyze` skill to analyze the item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps, manifest issues) and surface concrete process improvements. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. Invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Areas of particular interest for this item

When the skill prompts you for areas to focus on, weight these:

- **Cross-step contract drift**: F-00091 has seven impl steps that share a payload contract between S06 (backend) and S07 (frontend). Did any fix-cycle reveal that the agents disagreed on a field name?
- **TDD RED quality**: Did S01, S02, S03, S04, S06, S07 all record plausible RED evidence, or did any of them record `n/a` for behaviour that warranted a test?
- **Migration sequencing**: S04 (database) precedes S06 (backend) precedes S07 (frontend), with S05 (`migration-check`) gated between. Did the gate catch anything? Did any agent run before its dependency's report was available?
- **Browser verification surface area**: S19 had to set up two project fixtures (V2/V3) and possibly a context-pct fixture (V5). Did the agent loop on fixture creation, or did the seed already cover it?
- **Scope creep**: Did any step's `files_changed` include a path NOT in `scope.allowed_paths`? Were there fix-cycle iterations triggered by the scope gate?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (S01 api-impl, S02/S03/S07 frontend-impl, S06 backend-impl, S04 database-impl):

- Confirm the report contains `tdd_red_evidence` with a plausible failure snippet (`AssertionError` / `NotImplementedError` / similar — NOT an import/collection error).
- If the step added no behavioural test (e.g., S04 might justifiably claim n/a for a data-only migration if the round-trip test counts as coverage), confirm the justification is one line and accurate.
- `tests-impl` step (S08) is EXEMPT from RED-first.
- Review steps (S09, S10) are EXEMPT.
- QV gates (S05, S11–S18) are EXEMPT.
- QV-browser (S19) is EXEMPT.

## Subagent Result Contract

```json
{
  "step": "S20",
  "agent": "self-assess-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00091/reports/F-00091_self_assess_report.md",
    "ai-dev/work/F-00091/reports/F-00091_self_assess_findings.json"
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
