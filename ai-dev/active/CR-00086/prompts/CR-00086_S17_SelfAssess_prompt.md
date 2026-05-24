# CR-00086_S17_SelfAssess_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step**: S17
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job is to ANALYZE the item's execution, not to modify the database.

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00086/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00086/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00086/reports/CR-00086_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00086**.

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

### Item-specific focus

CR-00086 is a four-impl-step CR (Database / Backend service+CLI / Frontend panel+Jobs / CI+docs+skill+tracker) plus a `migration-check` QV gate, three CodeReviews, 8 standard QV gates, and a qv-browser. When analysing, pay particular attention to:

- (a) Did any QV gate burn a fix cycle? S09 lint, S10 format-check, S11 type-check, S12 unit-tests, S13 integration-tests, S14 diff-coverage, S15 security-secrets — flag any that retried and identify whether the failure was preventable at the implementation step (S03 / S05 / S07).
- (b) Did S05's empty-state handling cover all four metrics? The design specifically called out both per-metric placeholders AND a combined empty state — verify the panel test asserts both.
- (c) Did the mutation-JSON adapter (S03) correctly handle both CR-00080's widened-scope shape AND CR-00059's legacy shape, and did the qv-browser exercise a panel snapshot derived from a real CR-00080 JSON?
- (d) Did the CI workflow (S07) include `workflow_dispatch` for debugging? If only `push` + `schedule` triggers landed, that's a process improvement note for future CRs.
- (e) Compare against CR-00024's pattern (similar shape: schema → daemon emission → SSE registry → dashboard rendering) for any lessons not carried over (e.g., the SSE event-type registration trap from CR-00024 — N/A here but worth confirming).
- (f) Did the skill-mirror pair (`skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md`) land in S07's commit byte-identically? `iw sync-skills` is the operator note; if the diff is non-empty post-merge, flag it.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (notably S01 Database, S03 Backend, S05 Frontend) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` — the field records `run the new failing test` (the RED run) and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error).
- If the step added no behavioural test, the report says so with a one-line justification (e.g. `"n/a — workflow + docs + tracker + skill edits only, no production logic"` for S07).

**Dedicated coverage steps (`tests-impl`) are exempt** — none in this manifest, but the rule stands. Apply this checklist only when the reviewed step type is Backend or another behaviour-implementing agent.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "CR-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00086/reports/CR-00086_self_assess_report.md",
    "ai-dev/work/CR-00086/reports/CR-00086_self_assess_findings.json"
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
