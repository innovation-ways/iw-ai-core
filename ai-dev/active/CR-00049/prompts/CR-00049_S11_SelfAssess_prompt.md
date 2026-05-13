# CR-00049_S11_SelfAssess_prompt

**Work Item**: CR-00049 -- Re-enable `pytest-randomly` by default (P1-CR-C-followup-randomly)
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.
This CR adds no migrations.

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00049/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00049/reports/` — existing step reports (S01 Backend, S02 CodeReview, S03 CodeReview_Final, S04–S10 QvGate reports).

## Output Files

- `ai-dev/active/CR-00049/reports/CR-00049_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00049/reports/CR-00049_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00049**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Context-specific guidance for CR-00049

This CR is the **direct follow-up to CR-00048** (merged `a789701`, 2026-05-13), which itself burned 5 fix cycles on S10 (`make diff-coverage`) trying to converge on order-dependent integration test failures. The eventual fix (manual fallback `-p no:randomly`) was applied by the operator, not the agent — the agent's fix cycles had timed out without finding the diagnosis.

When you analyse CR-00049's own execution, pay particular attention to comparing patterns between this item and CR-00048's saga:

- Did S01's bounded sweep this time include `make diff-coverage` (the invocation that exposed the leak), or did it again rely only on `make test-unit` + `make test-integration`? If the latter, that's a recurrence of CR-00048's gap.
- Did S01 actually identify a root-cause fixture leak, or did it lean entirely on quarantines? The design's pressure-relief valve allows quarantines, but if the quarantine count is high (e.g. >25 of the 50-ish offenders) and no fixture-level fix landed, that's a process finding worth surfacing — the orchestrator may want to file a sub-follow-up for deeper cleanup.
- Did any fix cycles run on S10 (`diff-coverage`)? Zero fix cycles is the success criterion — the operator's pre-emptive design (this CR exists to remove `-p no:randomly`) was supposed to make S10 trivial. If S10 still needed fix cycles, that's a HIGH process finding.
- Did the `iw-item-analyze` skill itself surface any process patterns specific to "follow-up CR right after a fallback" — e.g., did this CR re-do work CR-00048 already did, or did it cleanly pick up where CR-00048 left off?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

For S01 (the only behaviour-implementing step in this CR), verify the report contains `tdd_red_evidence`:

- The field records the failing seed-12345 reproduction run.
- The failure snippet shows a plausible `sqla…` collection-time error (NOT an `ImportError`, `SyntaxError`, or pytest internal error — those mean the test infra itself is broken, not RED).
- If S01's `tdd_red_evidence` is `"n/a"`, flag that as a HIGH finding — this CR has a real behavioural anchor (the failing reproduction).

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "CR-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00049/reports/CR-00049_self_assess_report.md",
    "ai-dev/active/CR-00049/reports/CR-00049_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Cross-item comparison with CR-00048 included (see notes in context section above)."
}
```
