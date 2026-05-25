# CR-00084_S14_SelfAssess_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Step**: S14
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

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source). Should be `CR-00084`.
- **Worktree logs** — `.worktrees/CR-00084/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00084/reports/` — existing step reports (secondary evidence only).
- **Calibration evidence** — `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` (or its post-merge home under `ai-dev/archive/CR-00084/`).

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00084/reports/CR-00084_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00084** (LLM-as-judge spike). This step invokes the `iw-item-analyze` skill to surface process-improvement findings.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default and you can reference it by name. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Item-Specific Analysis Focus

Beyond the skill's standard checklist, look for these spike-specific signals:

1. **Did the calibration verdict in S01 propagate correctly?** Cross-check `calibration_verdict` in S01's report against the `hook_form` recorded by S02 and the `tracker_row_4_4_status` recorded by S03. If they disagree, S04 or S05 should have caught it — note whether the per-step or final review found it, and whether any fix cycle was burned on the inconsistency.

2. **Cost discipline observed?** Check S01's `calibration_cost_usd` against the < $2.00 budget. If S02 shipped the LIVE form, note whether the per-review cap (< $0.50) is explicitly stated in the agent-spec body or only implied. Cost overruns are a self-assess finding even if the calibration was technically successful.

3. **Did the spike's "calibrate first, advisory only" discipline hold under pressure?** Specifically: did the implementation at any point try to make the hook blocking (e.g., a finding category that quotes the judge score as fail-worthy, an early-draft sentence in the agent spec that lets a future agent treat low scores as fix triggers)? S04/S05 should catch this — note any near-misses surfaced by the per-step review's `advisory_contract_explicit` field.

4. **Did `tdd_red_evidence` for S01 record a real RED run?** S01 is a behaviour-implementing step (the judge script + validator + aggregator are production logic, even though they live in `scripts/`). The TDD evidence should be a real AssertionError/AttributeError from running the targeted tests *before* the script was implemented — not a placeholder. If the evidence looks like a placeholder, raise a finding.

5. **Compare against CR-00045's TDD-evidence patterns** (the canonical TDD-evidence CR) — was the format consistent? Was the failure mode plausible?

6. **Compare against CR-00059's spike patterns** (the mutmut/mutation-testing spike — closest precedent for a "spike with a calibration step that decides the disposition"). Did CR-00084 inherit any anti-patterns from CR-00059, or did it improve on them?

7. **Did any QV gate (S06–S13) burn a fix cycle?** If so, why? Common culprits on a tests-and-docs-and-script CR: lint on the new script, format-check on the labelled set (JSONL formatting is unusual), assertion-scanner picking up the new unit tests (the test names should not trip the scanner because they all assert real things — verify).

8. **Was the labelled set itself defensible?** Spot-check that S01 picked tests that the structural scanner already passes (i.e., not on `tests/assertion_free_baseline.txt`). If any labelled record overlaps with the baseline, the spike's premise (judge catches what the scanner cannot) is weakened — flag as a HIGH self-assess finding (but it does NOT block merge; soft-step semantics).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (S01 is the only one in this CR — S02 and S03 are doc/markdown only):

- The report contains `tdd_red_evidence` — the field records `run the new failing test` (the RED run) and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error).
- If the step added no behavioural test, the report says so with a one-line justification (e.g., `"n/a — agent-spec markdown edits only"`).

**Dedicated coverage steps (`tests-impl`) are exempt** — but S01 is `backend-impl`, not `tests-impl`, so it must show real RED evidence.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00084/reports/CR-00084_self_assess_report.md",
    "ai-dev/work/CR-00084/reports/CR-00084_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Spike-specific focus areas (calibration propagation, cost discipline, advisory-only safety, TDD evidence quality, labelled-set defensibility) all surveyed."
}
```
