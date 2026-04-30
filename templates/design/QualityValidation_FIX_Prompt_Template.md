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

## Scope Classification (REQUIRED — do this FIRST)

**BEFORE touching a single line**, classify every reported error.

1. Open `ai-dev/active/{ID}/workflow-manifest.json` and read `scope.allowed_paths`. Treat `ai-dev/active/{ID}/**` and `ai-dev/archive/{ID}/**` as implicitly allowed. Together these are the **in-scope set**.
2. For each failing test, lint error, or type error, identify the file it points to. If the failure is on a file NOT in the in-scope set, it is **PRE_EXISTING** — the file was already broken on the branch's base commit and is not yours to fix.
3. Choose your action:
   - **Every** reported error is PRE_EXISTING → STOP. Do not modify anything. Call:
     ```bash
     uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
       --reason "PRE_EXISTING: {gate}: {one-line summary of failures + files}" \
       --report ai-dev/active/{ID}/reports/{ID}_S{NN}_QualityValidation_FIX_report.md
     ```
     A human operator will triage — you are done.
   - Some IN_SCOPE, some PRE_EXISTING → fix only the IN_SCOPE ones. Leave PRE_EXISTING errors in place; the gate will still fail, and that is the correct outcome. The operator files a separate incident.
   - Every error is IN_SCOPE → proceed to the constraints below.

**Why this matters**: the executor's `worktree_commit.sh` runs a mechanical scope gate at merge time that rejects any branch whose modified files fall outside `scope.allowed_paths`. Drive-by "fixes" in unrelated files will be caught there — at best wasting a fix cycle, at worst blocking the whole batch merge. Don't do it.

The 2026-04-22 I-00034 retrospective is the precedent: S06 and S10 fix-cycles expanded scope by 30 files while "fixing" lint/test failures that were all pre-existing. The gate now blocks that class of merge; this classification step is what keeps the gate from firing.

## Constraints

1. **Only fix the failing gates, and only within scope.** Do not refactor unrelated code, do not touch files outside `scope.allowed_paths`, do not add features, do not reorganize files.
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
