# I-00058_S03_Backend_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB (port 5433).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `ai-dev/active/I-00058/reports/I-00058_S01_Database_report.md` — S01 report (model changes)
- `ai-dev/active/I-00058/reports/I-00058_S02_CodeReview_Database_report.md` — S02 review
- `orch/db/models.py` — ORM models (read `CodeIndexJob` before-insert listener at lines ~1536–1553 and `ProjectOssJob` at ~1830–1852 for the exact pattern)
- `orch/jobs/aggregator.py` — Jobs aggregator (read `_fetch_doc_generation` ~line 341 and `_get_doc_generation` ~line 596)

## Output Files

- `orch/db/models.py` — add `before_insert` event listener for `DocGenerationJob`
- `orch/jobs/aggregator.py` — update to use `public_id` as display identifier
- `ai-dev/active/I-00058/reports/I-00058_S03_Backend_report.md` — Step report

## Context

You are implementing the business-logic layer of **I-00058**. S01 (Database) added the `public_id` column to `DocGenerationJob`. Your job is to:

1. Wire up the `before_insert` SQLAlchemy event listener that auto-allocates `DOC-NNNNN` from `id_sequences['DOC']`.
2. Update `orch/jobs/aggregator.py` so that `DocGenerationJob` rows surface their `public_id` as the display job ID (with UUID fallback for legacy rows).

Do NOT modify `orch/doc_service.py` — the UUID `id` primary key stays as-is. The `public_id` is the human-readable display identifier only.

## Requirements

### 1. Add `before_insert` event listener to `DocGenerationJob` in `orch/db/models.py`

Follow the **exact** pattern of `_code_index_job_allocate_public_id` (lines ~1536–1553):

```python
@event.listens_for(DocGenerationJob, "before_insert")
def _doc_generation_job_allocate_public_id(
    _mapper: Mapper[Any], connection: Connection, target: DocGenerationJob
) -> None:
    """Auto-allocate ``DOC-NNNNN`` public_id from id_sequences if not set."""
    if target.public_id is not None:
        return
    n = connection.execute(
        text(
            "INSERT INTO id_sequences (prefix, next_number) VALUES ('DOC', 2)"
            " ON CONFLICT (prefix) DO UPDATE"
            " SET next_number = id_sequences.next_number + 1"
            " RETURNING next_number - 1"
        )
    ).scalar()
    target.public_id = f"DOC-{int(n or 1):05d}"
```

Place the listener immediately after the `DocGenerationJob` class definition, consistent with how `CodeIndexJob`'s listener is placed after its class (line ~1536).

### 2. Update `orch/jobs/aggregator.py` — `_fetch_doc_generation`

In the `_fetch_doc_generation` method (around line 341), the `raw` dict and `JobRow` construction both use `job.id` (UUID). Change them to prefer `public_id`:

- In `raw` dict (line ~379): add `"public_id": job.public_id` alongside `"id": job.id`.
- In `JobRow` construction (line ~401): change `job_id=job.id` → `job_id=job.public_id or job.id`.

### 3. Update `orch/jobs/aggregator.py` — `_get_doc_generation`

The `_get_doc_generation(self, project_id, job_id)` method (line ~596) currently calls `self._session.get(DocGenerationJob, job_id)`, which looks up by primary key (UUID). After the fix, `job_id` coming from the list view will be a `public_id` like `DOC-00001`. Update the lookup to:

```python
def _get_doc_generation(self, project_id: str, job_id: str) -> JobRow | None:
    # Try lookup by public_id first (new rows), fall back to UUID PK (legacy rows)
    job = self._session.scalar(
        select(DocGenerationJob).where(DocGenerationJob.public_id == job_id)
    )
    if job is None:
        job = self._session.get(DocGenerationJob, job_id)
    if job is None or job.project_id != project_id:
        return None
    ...
    return JobRow(
        ...
        job_id=job.public_id or job.id,  # use public_id for display
        ...
        raw={"id": job.id, "public_id": job.public_id, "project_id": job.project_id, "status": job.status.value},
    )
```

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:
- SQLAlchemy 2.0 sync ORM — `Mapped[]` declarative style
- `select()` / `scalars()` / `scalar()` — not `session.query()` (legacy)
- The `Mapper` and `Connection` type annotations must be imported from `sqlalchemy` — check existing imports at the top of `models.py`

## TDD Requirement

1. **RED**: Write a failing test that proves the listener is absent (before your change). See the reproducing test in the design document.
2. **GREEN**: Add the listener and run the test.
3. **REFACTOR**: Ensure the test is clean and the implementation matches `CodeIndexJob`'s pattern exactly.

Run `make test-unit` after implementation to confirm no regressions.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix formatting drift
2. **`make typecheck`** — zero errors on touched files
3. **`make lint`** — zero errors

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "I-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
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
