# I-00081_S14_SelfAssess_prompt

**Work Item**: I-00081 -- Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step**: S14
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
- **Worktree logs** — `.worktrees/I-00081/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00081/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00081/reports/I-00081_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00081**. This step invokes the **`iw-item-analyze`** skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps, manifest issues) and surface process-improvement findings anchored in evidence. It is a **soft** step — failure does NOT block merge; produce the best report you can even if the analysis is partial. Do NOT re-implement the analysis inline — invoke the `iw-item-analyze` skill (in Claude Code via the `Skill` tool with `skill: "iw-item-analyze"`; in OpenCode reference it by name). The skill defines the output contract (the two files above). The skill NEVER reviews the generated code and NEVER edits any file other than its two report outputs.

Context the analysis might touch for this item: it spanned `backend-impl` (router helper) + `frontend-impl` (two Jinja2 fragments) + `tests-impl` because the bug touched the router→template render path; the design left two judgement calls to the implementer (two context vars vs one folded `arch_diagram_html`; exactly how to strip the leading H1 and the per-fenced-block `layout: elk` front-matter) — note whether either ambiguity caused thrash between S01/S03/S05 (e.g. the template not matching the router's context-var name). Also note whether the `make lint` template check (`scripts/check_templates.py`) or the new `tests/CLAUDE.md` → `skills/iw-ai-core-testing/SKILL.md` requirement caused any fix-cycle churn. If browser verification (S13) needed an `e2e_fixtures` file because the seeded DB lacked an iw-doc-generator-form `diagram-architecture` doc, flag that as an environment gap (the bug *was* reproduced from real prod data, so a missing seed would be a dump-staleness issue, not a code issue).

## Soft-Step Semantics

Failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00081/reports/I-00081_self_assess_report.md",
    "ai-dev/active/I-00081/reports/I-00081_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
