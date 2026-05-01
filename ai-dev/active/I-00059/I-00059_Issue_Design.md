# I-00059: Doc Generation Job Detail Page Shows No Error Info or Parameters

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-01
**Reported By**: Operator (investigation of live failed job 2fb5a9a9)
**Status**: Draft

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

---

## Description

When navigating to a doc generation job's detail page (`/project/{p}/jobs/doc_generation/{id}`), the Parameters section shows no values and a failed job shows no error text. All diagnostic information stored in the DB — the error message, skill used, duration, doc ID, and agent output — is invisible to the operator. This makes it impossible to diagnose why a doc generation job failed from the dashboard.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key areas: `orch/jobs/aggregator.py` (jobs read layer), `dashboard/routers/jobs_ui.py` (detail route), `dashboard/templates/pages/project/job_detail.html` (rendering).

## Browser Evidence

Pre-fix screenshot showing the empty Parameters card and missing Error block:
- `ai-dev/active/I-00059/evidences/pre/I-00059-bug-evidence.png`

## Steps to Reproduce

1. Trigger or locate a `DocGenerationJob` row in the database (any status, failed is most revealing).
2. Navigate to `/project/{project_id}/jobs/doc_generation/{job_id}` in the dashboard.
3. Observe the "Parameters" card — all fields (`skill_used`, `trigger_reason`, `duration_seconds`) are blank.
4. For a failed job, observe the Error block at the bottom — it does not appear at all.

**Expected**: Parameters card shows `skill_used`, `duration_seconds`, `trigger_reason`, lint warnings (if any), and a "→ View document" link. A failed job shows a red Error block with the failure reason.

**Actual**: Parameters card renders with no visible fields. No error block appears even for a failed job.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open http://iw-dev-01:9900/project/iw-ai-core/jobs/doc_generation/2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435
playwright-cli screenshot
# Observe: Parameters card empty, no error block
```

## Root Cause Analysis

`JobsAggregator` exposes two paths to retrieve a `DocGenerationJob`:

1. **List path** — `_fetch_doc_generation` (`orch/jobs/aggregator.py:341-413`): builds a rich `raw` dict at line 378 with 14 fields including `error`, `agent_output`, `skill_used`, `trigger_reason`, `lint_warnings`, `duration_seconds`, `doc_id`, timestamps, etc.

2. **Detail path** — `_get_doc_generation` (`orch/jobs/aggregator.py:596-616`): called by `get_job()` when the detail route requests a single job. Returns a `JobRow` where `raw` is a stub dict with **only 3 keys**: `{"id": job.id, "project_id": job.project_id, "status": job.status.value}`.

The template (`dashboard/templates/pages/project/job_detail.html:244`) reads:
```jinja
{% set error_text = raw.get('error') or raw.get('error_message') %}
{% if job.status == 'failed' and error_text %}
```

Because `raw` never contains `'error'`, the error block never renders. Similarly the Parameters card reads `raw.get('skill_used')`, `raw.get('duration_seconds')`, `raw.get('doc_id')`, etc. — all `None` from the stub dict.

The fix is to align `_get_doc_generation`'s `raw` dict with the full set of fields that `_fetch_doc_generation` builds. No template changes are required.

Note: the same stub pattern also affects `_get_batch_execution` (`aggregator.py:618-632`) which similarly only puts `id`, `project_id`, `status` in `raw`, but that is out of scope for this incident.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Jobs aggregator (detail path) | `orch/jobs/aggregator.py:596-616` | `_get_doc_generation` returns stub `raw` dict — root cause |
| Dashboard job detail template | `dashboard/templates/pages/project/job_detail.html:99-131,244-250` | Reads `raw` fields that are always `None` — symptom |
| Dashboard job detail route | `dashboard/routers/jobs_ui.py:170-200` | Passes `job.raw` to template — uninvolved, correct |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Align `_get_doc_generation` raw dict with `_fetch_doc_generation` in `orch/jobs/aggregator.py` | — |
| S02 | CodeReview_Backend | Review S01 output | — |
| S03 | Tests | Reproduction test + regression tests for `_get_doc_generation` | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06 | QV lint | `make lint` | — |
| S07 | QV format | `make format-check` | — |
| S08 | QV typecheck | `make typecheck` | — |
| S09 | QV unit-tests | `make test-unit` | — |
| S10 | QV integration-tests | `make test-integration` | — |
| S11 | QV Browser | Verify error block and parameters visible on job detail page | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `orch/jobs/aggregator.py` (single method `_get_doc_generation`, lines 596-616)
- **Nature of change**: Replace 3-field stub `raw` dict with the same 14-field dict built in `_fetch_doc_generation`

## File Manifest

All files for this work item live under `ai-dev/active/I-00059/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00059_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00059_S01_Backend_prompt.md` | Prompt | S01 — fix aggregator |
| `prompts/I-00059_S02_CodeReview_Backend_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00059_S03_Tests_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00059_S04_CodeReview_Tests_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00059_S05_CodeReview_Final_prompt.md` | Prompt | S05 — global review |
| `prompts/I-00059_S11_BrowserVerification_prompt.md` | Prompt | S11 — browser QV |

Reports are created during execution in `ai-dev/active/I-00059/reports/`.

## Test to Reproduce

```python
def test_i00059_get_doc_generation_raw_contains_diagnostic_fields(db_session):
    """_get_doc_generation must return the same rich raw dict as _fetch_doc_generation.

    This test FAILS before the fix (raw only has 3 keys) and PASSES after.
    """
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
    row = aggregator.get_job(project_id="test-project", job_type=JobType.doc_generation, job_id=job.id)

    assert row is not None
    # These assertions FAIL before the fix because raw only has id/project_id/status
    assert row.raw.get("error") == "generation timeout after 15 minutes"
    assert row.raw.get("skill_used") == "iw-doc-generator"
    assert row.raw.get("duration_seconds") == 900
    assert row.raw.get("doc_id") == "test-project:some-doc"
    assert row.raw.get("trigger_reason") == "manual"
```

## Acceptance Criteria

### AC1: Error block visible for failed jobs

```
Given a DocGenerationJob with status=failed and error="generation timeout after 15 minutes"
When the operator navigates to /project/{p}/jobs/doc_generation/{id}
Then a red Error block is visible containing the text "generation timeout after 15 minutes"
```

### AC2: Parameters card shows diagnostic fields

```
Given a DocGenerationJob with skill_used="iw-doc-generator" and duration_seconds=900
When the operator navigates to the job detail page
Then the Parameters card shows skill_used="iw-doc-generator" and duration_seconds=900
```

### AC3: View document link appears when doc_id is set

```
Given a DocGenerationJob with doc_id="iw-ai-core:some-doc"
When the operator navigates to the job detail page
Then the Parameters card contains a "→ View document" link to /project/{p}/docs/iw-ai-core:some-doc
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproduction test passes with specific semantic assertions on raw field values
```

## Regression Prevention

The `_get_doc_generation` method is the only hand-rolled single-record fetch that diverges from the richer list-view path. Adding a typed `_build_doc_generation_raw(job: DocGenerationJob) -> dict[str, object]` helper and calling it from both `_fetch_doc_generation` and `_get_doc_generation` would make future field additions automatically flow to both paths. The `Tests` step should add a cross-check assertion ensuring `get_job` and `fetch` (via list with a matching ID) produce identical `raw` dicts.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: Integration test that creates a `DocGenerationJob` with `error`, `skill_used`, `duration_seconds`, `doc_id` set, calls `aggregator.get_job()`, and asserts all fields are present in `raw` with the exact stored values.
- **Unit tests**: None needed — the aggregator logic is DB-coupled and integration tests are the right level.
- **Integration tests**: Reproduction test above; additional test covering a job with `lint_warnings` (list field) and `agent_output` set.

## Notes

The operator discovered this bug while investigating live failed job `2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435` which timed out at 10 minutes (now raised to 15 minutes in `orch/daemon/doc_job_poller.py:57`). The timeout change is already committed to `main` and is NOT part of this incident's scope.

The same stub pattern exists in `_get_batch_execution` but that code path renders a different template block that does not read `error` or `skill_used` from `raw`, so it has no visible user impact and is out of scope.
