# {TYPE}{NNN}_S{NN}_QualityValidation_FIX_prompt

**Work Item**: {ID} -- {Title}
**Fix Cycle**: {cycle_number} of 5
**QV Step That Triggered Fix**: S{qv_step_NN}

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

## Input Files

- `ai-dev/work/{ID}/reports/{ID}_S{qv_step_NN}_QualityValidation_report.md` -- QV report with failing gates
- `CLAUDE.md` -- for project-specific conventions
- All source files related to the failing gates

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_QualityValidation_FIX_report.md` -- QV fix report

## Context

The Quality Validation for **{Work Item Title}** failed one or more gates. You must fix **only** the failing gates listed below. Do not refactor unrelated code or make changes beyond what is needed to pass the gates.

## Failing Gates

{For each failing gate from the QV report, include:}

### Gate: {gate_name}

**Command**: `{command}`
**Error Output**:

```
{paste the error output from the QV report}
```

{Repeat for all failing gates.}

## Constraints

1. **Only fix the failing gates.** Do not refactor unrelated code, add features, or reorganize files.
2. **Preserve existing behavior.** Fixes must not break functionality that was working before.
3. **Follow project conventions.** Read `CLAUDE.md` for project-specific patterns. Match existing code style.
4. **Re-run ALL gates after fixes, not just the failing ones.** A fix for one gate must not break another.

## Escalation

This is fix cycle **{cycle_number} of 5**. If this is cycle 5 and you cannot resolve all gate failures, report the unresolvable gates in `gates_skipped` with a clear explanation. The orchestrator will escalate to a human reviewer.

## Test Verification (NON-NEGOTIABLE)

After applying fixes:

1. Re-run every gate that was failing
2. Also re-run all other gates to ensure no regressions
3. Do **NOT** report a gate as fixed unless it passes with zero errors

## QV Fix Result Contract

```json
{
  "step": "S{NN}",
  "agent": "QualityValidation_FIX",
  "work_item": "{ID}",
  "fix_cycle": {cycle_number},
  "qv_step": "S{qv_step_NN}",
  "gates_fixed": [
    {
      "gate": "lint|format|typecheck|unit_tests|integration_tests|coverage|security",
      "status": "fixed",
      "files_changed": ["path/to/file.py"],
      "description": "What was done to fix it"
    }
  ],
  "gates_skipped": [
    {
      "gate": "typecheck",
      "reason": "Why it could not be fixed"
    }
  ],
  "verification": {
    "all_gates_rerun": true,
    "all_gates_pass": true,
    "failing_gates_remaining": []
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `gates_fixed`: Each gate you fixed. Include the files you changed and a brief description.
- `gates_skipped`: Any gates you could not fix. Only acceptable on cycle 5 (escalation). On cycles 1-4, all failing gates must be addressed.
- `verification.all_gates_rerun`: Must be `true`. You must re-run all gates, not just the ones you fixed.
- `verification.all_gates_pass`: `true` only if every gate passes after your fixes.
- `verification.failing_gates_remaining`: List of gates still failing after your fixes (should be empty on success).
