# CR-00073_S12_SelfAssess_prompt

**Work Item**: CR-00073 — iw CLI Contract Test Layer
**Step**: S12
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

Your job is to ANALYZE the item's execution, not to modify the database or any
migration. CR-00073 has no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00073/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00073/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00073/reports/CR-00073_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00073/reports/CR-00073_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00073**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT
re-implement the analysis procedure inline — the skill is the source of truth
for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

When analysing CR-00073 specifically, pay attention to:

- Did S01 fix spec drift directly in `docs/IW_AI_Core_CLI_Spec.md`, or did it
  lean heavily on the `KNOWN_SPEC_DRIFT` allowlist? A large allowlist means the
  spec is more out of date than expected — note it for follow-up.
- Did the `integration-tests` gate (S09) need fix cycles from latent CLI contract
  failures? The per-command tests exercise the full CLI contract for the first
  time — latent failures it surfaces burn S09 cycles.
- Were any `TODO(file-incident)` placeholders recorded for genuine CLI bugs
  discovered by the contract tests? If so, surface them as operator follow-up
  items — the operator files the Incident on `main` post-merge.
- Was the concurrency test for `next-id` stable under `pytest-randomly`? Did it
  require any special isolation to avoid flaking?
- Did the spec-conformance test find more drift than expected? Note the
  `KNOWN_SPEC_DRIFT` size as a health signal for the spec document.
- Note the `KNOWN_UNTESTED_COMMANDS` size — it is expected to be large on first
  merge (only 6 priority commands are tested). Record it as the baseline the
  follow-up coverage work must shrink.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00073 is a test-infrastructure CR. S01's `tdd_red_evidence` should record the
**monkeypatch demonstration** (a contract test failing when a `monkeypatch`
breaks the command's behaviour; the conformance test reporting injected drift
when a `monkeypatch` drops a command) rather than a classic RED run. Confirm the
S01 report contains that demonstration and that it was test-code-only — no
production file under `orch/` was edited at any point.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00073/reports/CR-00073_self_assess_report.md",
    "ai-dev/work/CR-00073/reports/CR-00073_self_assess_findings.json"
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
