# I-00058: DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-01
**Reported By**: sergio
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

`DocGenerationJob` records are assigned a raw UUID (e.g. `2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435`) as their identifier, making them impossible to reference meaningfully in the dashboard Jobs table. Every other job type in the platform (`CodeIndexJob` → `CM-NNNNN`, work items → `I/F/CR-NNNNN`, `ProjectOssJob` → `O-NNNNN`) uses the `id_sequences` table with a before-insert event listener to auto-allocate a sequential human-readable `public_id`. `DocGenerationJob` is missing this pattern entirely — the model has no `public_id` column and no `@event.listens_for` handler, and `doc_service.py` assigns `id=str(uuid.uuid4())` directly.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Pay special attention to:
- The `id_sequences` table and the `before_insert` event listener pattern (see `CodeIndexJob` in `orch/db/models.py:1451–1553`)
- The migration constraint: agents write the migration file only; the daemon applies it
- The `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` requirement after `Base.metadata.create_all()` in tests

## Browser Evidence

Deferred — dev environment was not running at design time. The bug is visible in the Jobs table on the dashboard (`/jobs` route), where doc generation job rows display a UUID string instead of a short readable ID.

## Steps to Reproduce

1. Open the dashboard Jobs page for any registered project.
2. Trigger a documentation generation (Docs page → Regenerate, or wait for the daemon to enqueue one).
3. Observe the **Job ID** column in the Jobs table for the new `doc_generation` row.

**Expected**: Job ID reads `DOC-00001` (or next sequential number).

**Actual**: Job ID reads a UUID string such as `2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435`.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
# Log in, navigate to /jobs for a project, trigger a doc generation, verify the ID column
```

## Root Cause Analysis

Three places are broken in concert:

1. **`orch/db/models.py:1327–1331`** — `DocGenerationJob.id` is a plain `Text` primary key with a `"UUID primary key"` comment. There is no `public_id` column and no `@event.listens_for(DocGenerationJob, "before_insert")` handler, unlike `CodeIndexJob` (lines 1536–1553) and `ProjectOssJob` (lines 1830–1852) which both auto-allocate from `id_sequences`.

2. **`orch/doc_service.py:467`** — `DocService.create_doc_job()` calls `DocGenerationJob(id=str(uuid.uuid4()), ...)`, explicitly assigning a UUID. With the `public_id` fix in place the UUID `id` column can remain (it's the PK), but the UUID must no longer be surfaced as the display identifier.

3. **`orch/jobs/aggregator.py:379,401,608`** — `_fetch_doc_generation` sets `job_id=job.id` (UUID) and `raw["id"]=job.id`. `_get_doc_generation` also returns `job_id=job.id`. Both must be updated to prefer `job.public_id`.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| ORM model | `orch/db/models.py:1322–1378` | Missing `public_id` column and before-insert listener |
| Database schema | `orch/db/migrations/versions/` | No migration exists for `public_id` |
| Doc creation service | `orch/doc_service.py:467` | Assigns UUID directly; must stay as UUID PK but not as display ID |
| Jobs aggregator | `orch/jobs/aggregator.py:379,401,608` | Exposes UUID as `job_id`; must prefer `public_id` |
| Dashboard Jobs UI | `dashboard/` | Displays whatever `job_id` the aggregator provides |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Add `public_id` column to `DocGenerationJob`; generate Alembic migration | — |
| S02 | CodeReview_Database | Review S01 migration and model change | — |
| S03 | Backend | Add `before_insert` event listener in `models.py`; update `aggregator.py` to expose `public_id` | — |
| S04 | CodeReview_Backend | Review S03 changes | — |
| S05 | Tests | Write reproduction test (fails before fix, passes after) + regression tests | — |
| S06 | CodeReview_Tests | Review test coverage | — |
| S07 | CodeReview_Final | Global cross-layer review | — |
| S08 | QV: lint | `make lint` | — |
| S09 | QV: format | `make format-check` | — |
| S10 | QV: typecheck | `make type-check` | — |
| S11 | QV: unit-tests | `make test-unit` | — |
| S12 | QV: integration-tests | `make allure-integration` | — |
| S13 | QV Browser | Verify DOC-NNNNN IDs appear in Jobs table | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `doc_generation_jobs` — add `public_id TEXT UNIQUE` column (nullable, default NULL; populated by before-insert trigger for new rows)
- **Migration notes**: Existing UUID rows retain their UUID `id`; `public_id` starts NULL for pre-existing rows (acceptable — forward-only fix). The migration must not backfill existing rows.

### Code Changes

- **`orch/db/models.py`**: Add `public_id: Mapped[str | None]` column to `DocGenerationJob` + unique index. Add `@event.listens_for(DocGenerationJob, "before_insert")` that allocates `DOC-NNNNN` from `id_sequences['DOC']` using the same INSERT … ON CONFLICT pattern as `CodeIndexJob` (lines 1541–1553).
- **`orch/jobs/aggregator.py`**: In `_fetch_doc_generation`, change `"id": job.id` in `raw` to include both UUID and `public_id`; change `job_id=job.id` → `job_id=job.public_id or job.id`. In `_get_doc_generation`, change `job_id=job.id` → `job_id=job.public_id or job.id`; update `raw` to include `public_id`. Also update `_get_doc_generation` lookup: since `job_id` is now the `public_id`, query by `public_id` first (scalar select with filter) and fall back to PK lookup.

## File Manifest

All files for this work item live under `ai-dev/active/I-00058/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00058_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00058_S01_Database_prompt.md` | Prompt | Add public_id column + migration |
| `prompts/I-00058_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/I-00058_S03_Backend_prompt.md` | Prompt | Add event listener + fix aggregator |
| `prompts/I-00058_S04_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/I-00058_S05_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00058_S06_CodeReview_Tests_prompt.md` | Prompt | Review S05 |
| `prompts/I-00058_S07_CodeReview_Final_prompt.md` | Prompt | Global cross-layer review |
| `prompts/I-00058_S13_BrowserVerification_prompt.md` | Prompt | Playwright verification |

## Test to Reproduce

```python
def test_i00058_doc_generation_job_gets_sequential_public_id(db_session):
    """This test should FAIL before the fix and PASS after.

    Before fix: DocGenerationJob has no public_id column.
    After fix: public_id is auto-allocated as DOC-00001 (or next number).
    """
    import uuid
    from orch.db.models import DocGenerationJob

    # Arrange — create a project first (or use an existing fixture project)
    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="iw-ai-core",  # adjust to a seeded project_id in testcontainer
        status="queued",
    )
    db_session.add(job)
    db_session.flush()  # triggers before_insert listener

    # Assert — public_id must be a DOC-NNNNN string, not None, not a UUID
    assert job.public_id is not None, "public_id must be allocated on insert"
    assert job.public_id.startswith("DOC-"), (
        f"public_id must start with 'DOC-', got: {job.public_id!r}"
    )
    assert len(job.public_id) == 9, (
        f"public_id must be exactly 9 chars (DOC-NNNNN), got: {job.public_id!r}"
    )
```

## Acceptance Criteria

### AC1: New doc generation jobs receive a sequential DOC-NNNNN public_id

```
Given a DocGenerationJob is inserted into the database
When the before_insert SQLAlchemy event fires
Then job.public_id is set to DOC-NNNNN (e.g. DOC-00001, DOC-00002, ...)
And successive jobs receive strictly incrementing numbers
```

### AC2: The Jobs aggregator surfaces public_id as the display job_id

```
Given a DocGenerationJob with public_id = "DOC-00001"
When the jobs aggregator fetches and serialises it
Then JobRow.job_id == "DOC-00001"
And the dashboard Jobs table displays "DOC-00001", not a UUID
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then test_i00058_doc_generation_job_gets_sequential_public_id passes
```

## Regression Prevention

- The `public_id` column has a `UNIQUE` constraint in the DB — duplicate IDs are impossible.
- The `before_insert` listener is the single allocation path; `doc_service.py` never sets `public_id` directly.
- Integration tests that create `DocGenerationJob` rows will exercise the listener on every run via the testcontainer.
- A future code review checklist item: any new job model must have a `public_id` + before-insert listener matching the `CodeIndexJob` pattern.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test** (`tests/integration/`): `test_i00058_doc_generation_job_gets_sequential_public_id` — fails before the `public_id` column and listener exist, passes after.
- **Unit tests**: Test that `_fetch_doc_generation` and `_get_doc_generation` in `aggregator.py` return `public_id` as `job_id` when it's set.
- **Integration tests**: End-to-end test that creates a job via `DocService.create_doc_job()` and asserts the returned job has a `DOC-NNNNN` `public_id`; test that sequential IDs increment correctly across multiple inserts.

## Notes

- Existing rows in production have NULL `public_id` after migration; the aggregator's `job.public_id or job.id` fallback ensures they still render (as UUID) rather than breaking.
- The `_get_doc_generation(project_id, job_id)` lookup must handle both `public_id` (new) and UUID `id` (legacy/existing rows). Implement as: try `scalar(select(DocGenerationJob).where(DocGenerationJob.public_id == job_id))` first; if None, fall back to `session.get(DocGenerationJob, job_id)`.
- Do NOT backfill existing UUID rows — the risk of a backfill migration touching large tables outweighs the benefit for legacy records.
