# {TYPE}{NNN}_S{NN}_CodeReview_FIX_prompt

**Work Item**: {ID} -- {Title}
**Fix Cycle**: {cycle_number} of 5
**Original Step**: S{impl_step_NN} ({Agent})
**Review That Triggered Fix**: S{review_step_NN}

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

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
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

- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- `ai-dev/work/{ID}/reports/{ID}_S{review_step_NN}_CodeReview_report.md` -- Review report with findings
- All files referenced in the findings below

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_CodeReview_FIX_report.md` -- Fix report

## Context

The code review for step S{impl_step_NN} found issues that must be fixed. You must address **only** the CRITICAL, HIGH, and MEDIUM (fixable) findings listed below. Do not refactor beyond the scope of these findings.

## Findings to Fix

{For each mandatory finding from the review report, include:}

### Finding {N}: {severity} -- {category}

**File**: `{file_path}`, line {line}
**Description**: {description}
**Suggestion**: {suggestion}

{Repeat for all mandatory findings.}

## Constraints

1. **Only fix the flagged issues.** Do not refactor unrelated code, add features, or reorganize files.
2. **Preserve existing behavior.** Your fixes must not break functionality that was working before.
3. **Follow project conventions.** Read `CLAUDE.md` for project-specific patterns. Match existing code style.
4. **Run tests after every fix.** Ensure no regressions are introduced.

## Escalation

This is fix cycle **{cycle_number} of 5**. If this is cycle 5 and you cannot resolve all findings, report the unresolvable findings in `findings_skipped` with a clear explanation. The orchestrator will escalate to a human reviewer.

## Test Verification (NON-NEGOTIABLE)

After applying fixes:

1. Run the project's unit test command
2. Run lint and type checking
3. Do **NOT** report `tests_passed: true` unless ALL tests pass with zero failures
4. If your fix breaks other tests, fix those too

## Fix Result Contract

```json
{
  "step": "S{NN}",
  "agent": "CodeReview_FIX",
  "work_item": "{ID}",
  "fix_cycle": {cycle_number},
  "review_step": "S{review_step_NN}",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE",
      "status": "fixed|partially_fixed",
      "files_changed": ["path/to/file.py"],
      "description": "What was done to fix it"
    }
  ],
  "findings_skipped": [
    {
      "finding_number": 2,
      "severity": "HIGH",
      "reason": "Why it could not be fixed"
    }
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `findings_addressed`: All findings you fixed. Use `partially_fixed` only if the fix is incomplete but improves the situation.
- `findings_skipped`: Any findings you could not fix. Only acceptable on cycle 5 (escalation). On cycles 1-4, all findings must be addressed.
