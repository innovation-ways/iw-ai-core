# CR-00070_S04_CodeReview_FIX_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Fix Cycle**: {cycle_number} of 5
**Original Steps**: S01 (backend-impl), S02 (frontend-impl)
**Review That Triggered Fix**: S03

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

This CR introduces no migration and no schema change. Do not create an
Alembic revision.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- Design document (authoritative spec)
- `ai-dev/work/CR-00070/reports/CR-00070_S03_CodeReview_report.md` -- Review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S04_CodeReview_FIX_report.md` -- Fix report

## Context

The code review S03 for steps S01 + S02 found issues that must be fixed. You
must address **only** the CRITICAL, HIGH, and MEDIUM (fixable) findings from
the S03 review report. Do not refactor beyond the scope of those findings.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00070/CR-00070_CR_Design.md` is the authoritative spec.
**Read it before applying any fix.** Prior fix cycles across the project have
failed because the agent trusted a review's root-cause hypothesis and drifted
from the design spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Findings to Address

Read `ai-dev/work/CR-00070/reports/CR-00070_S03_CodeReview_report.md` and
address every finding with severity CRITICAL, HIGH, or MEDIUM_FIXABLE. Each
such finding names a `file`, `line`, `description`, and `suggestion`. Treat
the findings as one hypothesis — verify each against the design doc spec
before applying the fix; the spec wins on conflict.

## Pre-fix Procedure

1. **Read the design doc** — skim **Desired Behavior**, **Backend / Resolver
   Changes**, **Frontend Changes**, and **Acceptance Criteria** (AC1–AC6).
2. **Diff the target file(s) against the spec** — list deviations explicitly
   before editing.
3. **Apply the minimum patch** to align code with the spec; the findings
   should resolve as a side effect.
4. **If a finding disagrees with the spec, the spec wins** — note the
   disagreement in your output rather than silently following the finding.

## Constraints

1. **Only fix the flagged issues.** No unrelated refactors, no new features.
2. **Preserve existing behavior** — the `<select>` `value=""`/`name`/htmx
   attributes and the inherit/clear mechanism must keep working (AC4).
3. **Follow project conventions** — `CLAUDE.md`, `orch/CLAUDE.md`,
   `dashboard/CLAUDE.md`.
4. **Run targeted tests after every fix** to ensure no regressions.

## Escalation

This is fix cycle **{cycle_number} of 5**. Prefer honest escalation over a
Hail-Mary fix that drifts from the design spec. On cycle 5, report
unresolvable findings in `findings_skipped` with a clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes:

1. Run the targeted tests:
   `uv run pytest tests/dashboard/test_runtime_override_templates.py tests/integration/test_<resolver_test>.py -v`
2. Run `make format`, `make typecheck`, `make lint` on touched files.
3. Do **NOT** report `tests_passed: true` unless all targeted tests pass with
   zero failures. If a fix breaks other tests, fix those too.

## Fix Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_FIX",
  "work_item": "CR-00070",
  "fix_cycle": {cycle_number},
  "review_step": "S03",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": ["path/to/file"],
      "description": "What was done to fix it"
    }
  ],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `findings_skipped`: only acceptable on cycle 5 (escalation). On cycles 1–4
  all mandatory findings must be addressed.
