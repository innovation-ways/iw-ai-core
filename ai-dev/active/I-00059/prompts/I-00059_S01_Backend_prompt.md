# I-00059_S01_Backend_prompt

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
**Step**: S01
**Agent**: Backend

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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00059 --json`
- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — Design document

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S01_Backend_report.md` — Step report

## Context

You are fixing a bug in **I-00059: Doc Generation Job Detail Page Shows No Error Info or Parameters**.

The dashboard job detail page at `/project/{p}/jobs/doc_generation/{id}` renders a "Parameters" card and an "Error" block — both pulling data from `job.raw`. For `doc_generation` jobs the `raw` dict should contain fields like `error`, `skill_used`, `duration_seconds`, `doc_id`, `agent_output`, `lint_warnings`, etc.

The bug: `JobsAggregator._get_doc_generation` (the method used by the detail page route) builds a stub `raw` dict with only 3 keys (`id`, `project_id`, `status`), while `_fetch_doc_generation` (the list view method) correctly builds a 14-field dict. The template reads the missing keys, they're all `None`, so the page shows nothing useful.

Read the full design document before starting.

## Requirements

### 1. Fix `_get_doc_generation` in `orch/jobs/aggregator.py`

The method `_get_doc_generation` at lines 596–616 must return a `JobRow` with a `raw` dict that matches the field set built by `_fetch_doc_generation` at lines 378–396.

**Current stub (wrong):**
```python
raw={"id": job.id, "project_id": job.project_id, "status": job.status.value}
```

**Required fields** (match `_fetch_doc_generation` exactly):
```python
raw: dict[str, object] = {
    "id": job.id,
    "project_id": job.project_id,
    "doc_id": job.doc_id,
    "status": job.status.value,
    "requested_at": job.requested_at,
    "started_at": job.started_at,
    "completed_at": job.completed_at,
    "agent_output": job.agent_output,
    "error": job.error,
    "agent_pid": job.agent_pid,
    "skill_used": job.skill_used,
    "trigger_reason": job.trigger_reason,
    "lint_warnings": job.lint_warnings,
    "duration_seconds": job.duration_seconds,
    "section_guides_snapshot": job.section_guides_snapshot,
    "guide_snapshot": job.guide_snapshot,
    "created_at": job.created_at,
}
```

Also update the `JobRow` constructor call in `_get_doc_generation` to use `job.skill_used or job.trigger_reason` for `triggered_by`, matching the list view.

**Recommended refactor (optional but encouraged):** Extract a private `_build_doc_generation_raw` helper method that both `_fetch_doc_generation` and `_get_doc_generation` call, to prevent future drift. This is a small, safe refactor that stays entirely within `aggregator.py`.

### 2. No other changes

Do NOT modify the template, the route, or any other file. The fix is strictly limited to `orch/jobs/aggregator.py`. The template already handles all required fields correctly — the only gap is that `raw` never contained them.

## Project Conventions

Read the project's `CLAUDE.md` for:
- SQLAlchemy 2.0 ORM patterns
- Test organisation under `tests/`
- Build and run commands

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write a failing integration test first — create a `DocGenerationJob` with `error`, `skill_used`, `duration_seconds`, `doc_id` set, call `aggregator.get_job()`, assert those fields appear in `row.raw`. This test must FAIL against the current code.
2. **GREEN**: Apply the fix to `_get_doc_generation`. The test must now pass.
3. **REFACTOR**: If you extracted a helper method, ensure it's used consistently from both callers.

The reproduction test from the design document is a good starting point:

```python
def test_i00059_get_doc_generation_raw_contains_diagnostic_fields(db_session):
    from orch.jobs.aggregator import JobsAggregator, JobType
    from orch.db.models import DocGenerationJob, JobStatus
    import uuid

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-project",
        doc_id="test-project:some-doc",
        status=JobStatus.failed,
        error="generation timeout after 15 minutes",
        skill_used="iw-doc-generator",
        duration_seconds=900,
        trigger_reason="manual",
    )
    db_session.add(job)
    db_session.flush()

    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(
        project_id="test-project",
        job_type=JobType.doc_generation,
        job_id=job.id,
    )

    assert row is not None
    assert row.raw.get("error") == "generation timeout after 15 minutes"
    assert row.raw.get("skill_used") == "iw-doc-generator"
    assert row.raw.get("duration_seconds") == 900
    assert row.raw.get("doc_id") == "test-project:some-doc"
    assert row.raw.get("trigger_reason") == "manual"
```

Place this test in the appropriate integration test file (check `tests/integration/` for existing aggregator tests).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors in files you touched
3. `make lint` — must report zero errors

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` and `make test-integration`
2. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00059",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/jobs/aggregator.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
