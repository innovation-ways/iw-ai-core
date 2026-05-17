# I-00090_S02_CodeReview_Backend_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step Being Reviewed**: S01 (backend-impl)
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

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps`, `docker inspect`, `docker logs`), and
invocations of `./ai-core.sh` or `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands against any
live DB from an agent context. This item does not generate or modify any
migration; if you see one in S01's diff, that is a CRITICAL finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00090 --json`
- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- Design document
- `ai-dev/active/I-00090/reports/I-00090_S01_Backend_report.md` -- S01 report
- All files listed in the S01 report's `files_changed` (expected: `dashboard/routers/running.py`)
- `orch/db/models.py` for the `WorkItemStatus` enum and `WorkItem.archived_at` definitions

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_S02_CodeReview_Backend_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by `backend-impl` for **I-00090**. The fix adds an active-item predicate to two SQL query helpers in `dashboard/routers/running.py` so that closed, cancelled, or archived work items no longer appear in the "Failed / Needs Attention" or "Recently Completed (last hour)" tables on `/system/running` and `/project/{id}/running`.

## Read the Design Document FIRST

Read `ai-dev/active/I-00090/I-00090_Issue_Design.md` BEFORE running gates and BEFORE opening any changed files. Specifically:

- Read the `## Acceptance Criteria` section in full — AC1, AC2, AC3, AC4, AC5 are mandatory checks for the final state. For S01, the relevant ones are AC1, AC2, AC3 (the read-side filter is now in place).
- Read the `## TDD Approach` section — note that the test file `tests/dashboard/test_running_router_active_filter.py` is owned by S03, NOT S01. If S01's `files_changed` includes any test file, raise a HIGH finding for scope violation; if it includes the production file plus the eventual test file as a side-edit, raise a MEDIUM_FIXABLE.
- Read the `## Notes` section — the running-now helpers (`_query_running_now`, `get_running_count`) are intentionally out of scope. If S01 modified them, raise a HIGH "scope violation" finding.

Note: this Backend step legitimately has no behavioural test attached (the test surface is the next step). The Tests step (S03) owns the RED-first proof. Do not flag absence of behavioural tests in S01 — but DO verify S01's `tdd_red_evidence` field is either an actual evidence snippet OR the explicit `"n/a — query-only filter; …"` form documented in the prompt template (a bare empty string or omission is a HIGH finding).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed` (expected: `dashboard/routers/running.py`):

```bash
make lint
make format-check
```

Any NEW violation (not present on `main` before this step) is a **CRITICAL** finding with `"category": "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Predicate Correctness (CRITICAL)

- Both `_query_failed_steps()` AND `_query_recent_completions()` MUST have the two new `.where(...)` clauses added.
- The clauses MUST be: `.where(WorkItem.archived_at.is_(None))` and `.where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))`.
- `WorkItemStatus` MUST be imported from `orch.db.models`.
- `is_(None)` (NOT `== None`) per SQLAlchemy 2.0 / project convention.
- The enum list MUST contain exactly `WorkItemStatus.completed` and `WorkItemStatus.cancelled`. Any deviation (extra status, missing one, including `failed`) is a CRITICAL finding — the design explicitly defines the active set.

### 2. Scope Adherence (HIGH)

- `_query_running_now()` MUST be unchanged.
- `get_running_count()` MUST be unchanged.
- `dashboard/templates/pages/system/running.html` MUST be unchanged.
- No new file is created in this step.
- No test file is touched in this step (that's S03's job).
- No alembic migration is created.

If any of the above is violated, raise a HIGH (or CRITICAL for the migration case) finding.

### 3. Architecture & Conventions

- The helper functions live in the dashboard router file — that's the existing pattern; do not flag it.
- The existing `WorkItem` join in both helpers is reused — no duplicate joins.
- Imports are organised per project convention (`from __future__`, stdlib, third-party, local).

### 4. Security & Performance

- The added predicates are simple equality / IN checks against indexed columns. No injection surface (enum values are literal Python objects, not strings from user input).
- Query plan is unchanged in shape — same joins, just two extra WHERE clauses on the already-joined `WorkItem` table. No new N+1 risk.

### 5. TDD RED Evidence (Backend step)

1. Confirm `tdd_red_evidence` is either an actual snippet OR the explicit `"n/a — query-only filter; behavioural tests added in S03 …"` form (or equivalent wording). A blank value or absence is a HIGH finding.
2. Reason about whether the eventual S03 test would actually fail against pre-S01 code. The proposed assertion `assert all(r.item_id != "CR-DEAD" for r in rows)` against a seeded `WorkItem(status=completed)` with a failed step DOES fail against pre-S01 code (because no filter exists) and passes after S01 (because the new predicate excludes it). State explicitly in your review report that this reasoning was performed and the conclusion.
3. (Optional) Stash-recheck — not required.

### 6. Documentation

- The change is small enough that a code comment is optional. If S01 added a comment like `# I-00090: limit to active items (archived_at IS NULL and status not in completed/cancelled)`, that's good. If not, do not raise it as a finding; the design doc captures the rationale.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` to verify no unit-test regressions.
2. Report results accurately in the result contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, wrong enum list, lint/format violation, migration generated |
| **HIGH** | Scope violation (touched running-now or template), missing `tdd_red_evidence`, AC1/AC2/AC3 unmet |
| **MEDIUM_FIXABLE** | Convention nit (e.g. `== None` instead of `is_(None)`) |
| **MEDIUM_SUGGESTION** | Code-comment suggestion, naming preference |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00090",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
