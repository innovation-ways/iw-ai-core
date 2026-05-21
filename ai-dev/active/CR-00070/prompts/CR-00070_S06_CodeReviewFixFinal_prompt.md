# CR-00070_S06_CodeReview_FIX_Final_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Fix Cycle**: {cycle_number} of 5
**Final Review That Triggered Fix**: S05

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
- `ai-dev/work/CR-00070/reports/CR-00070_S05_CodeReview_Final_report.md` -- Final review report with findings
- All files referenced in the findings

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S06_CodeReview_FIX_Final_report.md` -- Fix report

## Context

The **final cross-agent review** S05 found issues that must be fixed. These
may be cross-cutting integration problems (e.g. a `inherited_runtime_label`
context-variable name mismatch between routers and template, a render path
that was missed, a missing test). You must address **only** the CRITICAL,
HIGH, and MEDIUM (fixable) findings listed in the S05 report.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00070/CR-00070_CR_Design.md` is the authoritative spec.
**Read it end-to-end before applying any fix** — final-review fixes often
span multiple sections. **The design doc wins when a finding disagrees.**

## Diagnostic Hypothesis — Findings to Address

Read `ai-dev/work/CR-00070/reports/CR-00070_S05_CodeReview_Final_report.md`
and address every finding with severity CRITICAL, HIGH, or MEDIUM_FIXABLE,
plus any `missing_requirements` it lists. Verify each against the design doc
spec before applying the fix; the spec wins on conflict.

For any `missing_requirements`: implement them following the design document,
using TDD.

## Pre-fix Procedure

1. **Read the design doc** end-to-end.
2. **Diff each affected module against the spec** — list deviations
   explicitly. Cross-cutting findings must be reconciled with the doc, not
   patched in isolation.
3. **Apply the minimum patch** to align code with the spec.
4. **If a finding disagrees with the spec, the spec wins** — note it in your
   output.

## Constraints

1. **Only fix the flagged issues and implement missing requirements.** No
   unrelated refactors.
2. **Preserve existing behavior** — the inherit/clear mechanism (AC4) must
   keep working.
3. **Follow project conventions** — `CLAUDE.md`, `orch/CLAUDE.md`,
   `dashboard/CLAUDE.md`.
4. **Cross-cutting fixes may span multiple modules** (resolver, routers,
   template) — keep all changes consistent.
5. **Run the full test suite after fixes.**

## Escalation

This is fix cycle **{cycle_number} of 5**. Prefer honest escalation over a
Hail-Mary fix that drifts from the design spec. On cycle 5, report
unresolvable findings in `findings_skipped` with a clear explanation.

## Test Verification (NON-NEGOTIABLE)

After applying fixes:

1. Run the **targeted** tests:
   `uv run pytest <CR-00070 resolver integration test> tests/dashboard/test_runtime_override_templates.py -v`
   (use the resolver integration test file named in S01's report). Do **NOT**
   run `make test-integration` here — the full suite is the S07 QV gate's job;
   re-running it in a fix step duplicates that gate and risks the I-00073
   timeout pattern.
2. Run `make format`, `make typecheck`, `make lint`.
3. Do **NOT** report `tests_passed: true` unless ALL targeted tests pass with
   zero failures. If a fix breaks other tests, fix those too.

## Fix Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_FIX_Final",
  "work_item": "CR-00070",
  "fix_cycle": {cycle_number},
  "review_step": "S05",
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
  "missing_requirements_implemented": [],
  "tests_passed": true,
  "test_summary": "X targeted tests passed, 0 failed",
  "notes": ""
}
```

- `findings_skipped`: only acceptable on cycle 5 (escalation).
- `missing_requirements_implemented`: each must include tests (TDD).
