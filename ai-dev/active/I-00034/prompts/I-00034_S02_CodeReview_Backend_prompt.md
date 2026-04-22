# I-00034_S02_CodeReview_Backend_prompt

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

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

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- Design document
- `ai-dev/active/I-00034/reports/I-00034_S01_Backend_report.md` -- S01 implementation report
- All files listed in the S01 report's `files_changed` (expected: `dashboard/routers/items.py`, possibly a new helper module)

## Output Files

- `ai-dev/active/I-00034/reports/I-00034_S02_CodeReview_Backend_report.md` -- Review report

## Context

You are reviewing the Backend fix for the Item view duration bug. S01 changed how `dashboard/routers/items.py` computes step duration — from reading `WorkflowStep.started_at` / `completed_at` directly (buggy because those are reset on retry) to aggregating `MIN(started_at)` / `MAX(completed_at)` across the append-only `step_runs` and `fix_cycles` tables.

Read the design document to understand the intent. Read the S01 report to understand the diff. Then review the actual code changes.

## Review Checklist

### 1. Correctness of the aggregation (CRITICAL — this is the core of the fix)

- Does the aggregation union `step_runs` AND `fix_cycles` (not just one)? Missing either table understates duration by the corresponding amount.
- Does it take `MIN(started_at)` and `MAX(completed_at)` — not `MIN(started_at)` and `step.completed_at`? The step-level `completed_at` is truncated the same way the step-level `started_at` is.
- Is `started_at = None` handled correctly for the "step never launched" case? (duration should remain `None`)
- Is `completed_at = None` handled correctly for the "step is still in-flight" case? (`duration_secs` should be `None` so the template renders `—` — the Item view's step table does NOT live-tick; `started_at` on the returned row should still be the aggregated earliest start, not the WorkflowStep's last-iteration start)
- Does the `StepDetail.started_at` / `completed_at` now surface the **aggregated** values, not `step.started_at` / `step.completed_at`?

### 2. No N+1 (HIGH — per `tests/CLAUDE.md`)

- Is the aggregation bulk-queried with `IN (...)` + `GROUP BY step_id`? Exactly **two** aggregation queries for the whole `_get_steps` call (one for `step_runs`, one for `fix_cycles`) — no per-step query inside a loop.
- Is the empty-list case handled (no workflow steps → skip the aggregation queries)?

### 3. `_get_metrics` also corrected

- Does `total_duration_secs` now include the full aggregated span? Since the correction is achieved by surfacing aggregated values on `StepDetail.started_at` / `completed_at`, confirm that `_get_metrics` reads from those (same dataclass field names) and therefore picks up the fix automatically.
- Synthetic setup/merge steps are still folded into the `min` / `max` correctly.

### 4. No out-of-scope changes (CRITICAL)

S01 must **not** have touched:

- `orch/daemon/fix_cycle.py` — the `step.started_at = None` resets MUST remain
- `orch/cli/step_commands.py` — the `step.started_at = datetime.now(UTC)` on each launch MUST remain
- `orch/db/models.py` — no new columns, no new indexes (existing `idx_step_runs_step` covers the `WHERE step_id IN (...)`)
- No Alembic migration
- `_synthetic_setup_step` and `_synthetic_merge_step` logic
- Unrelated router functions (`_get_batch_item`, `_read_report_file`, etc.)

If any of the above were modified, that's a CRITICAL finding — scope creep that widens the blast radius.

### 5. In-progress behaviour unchanged

- Confirm the templates `item_overview.html` / `item_header.html` are NOT modified (the Item view's step table renders `—` for in-progress and does not live-tick — this is a router-only fix).
- Confirm `StepDetail.started_at` for an in-progress step surfaces the aggregated earliest start (so the "Started" column shows the true first-launch time).

### 6. Comment anchor (MEDIUM suggestion)

- Is there a one-line comment at the aggregation call-site referencing I-00034 and explaining why we aggregate rather than reading `step.started_at`? This prevents a well-intentioned future refactor from reverting the fix.

### 7. Project conventions (MEDIUM)

- SQLAlchemy 2.0 idiom (`select(...)`, `db.execute(...).all()`)
- Type hints consistent with the existing module
- Imports organised correctly
- `func.min` / `func.max` imported from `sqlalchemy` correctly (or `func` from `sqlalchemy.sql`)
- No `# type: ignore` comments hiding real issues

### 8. Security / correctness general

- No raw SQL string interpolation (use `select(...).where(col.in_(...))`)
- Nullable columns in the DB handled (both `started_at` and `completed_at` are nullable on `StepRun` and `FixCycle`)
- UTC arithmetic preserved (`TIMESTAMPTZ` columns)

### 9. Tests

- Did S01 run the full test suite? (`make test-unit` AND `make test-integration`)
- Were any pre-existing tests that encoded the buggy behaviour updated with a comment, rather than silently deleted or weakened?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` -- zero failures
2. Run `make test-integration` -- zero failures
3. Run `make lint` -- zero errors
4. Run `uv run mypy orch/ dashboard/` -- zero errors on the touched files
5. Report results accurately in the contract

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Aggregation is wrong, N+1 introduced, scope creep into daemon/cli/models, tests fail | Must fix |
| **HIGH** | Missing one of the two tables (`step_runs` xor `fix_cycles`), in-progress live-tick broken, nullability bug | Must fix |
| **MEDIUM (fixable)** | Missing comment anchor, style violation, non-critical convention issue | Should fix |
| **MEDIUM (suggestion)** | Helper extraction choice debatable, naming preference | Optional |
| **LOW** | Nitpick, minor readability | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00034",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "dashboard/routers/items.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings. Otherwise `fail`.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM_FIXABLE findings.
