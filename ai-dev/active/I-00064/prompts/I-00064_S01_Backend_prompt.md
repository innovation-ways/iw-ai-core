# I-00064_S01_Backend_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Step**: S01
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

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps`, `docker inspect`, `docker logs`), and
`./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT add or modify any Alembic migration. The fix is a pure
Python change inside `orch/jobs/aggregator.py`. If you find yourself
needing a migration, STOP and raise a blocker.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00064 --json` is the source of truth (CR-00023).
- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design document (read first).
- `ai-dev/active/I-00064/evidences/pre/` — pre-fix browser evidence.

## Output Files

- `orch/jobs/aggregator.py` — modified
- `ai-dev/active/I-00064/reports/I-00064_S01_Backend_report.md` — step report

## Context

You are fixing the bug captured in I-00064. Read
`I-00064_Issue_Design.md` end-to-end before touching code; the **Root
Cause Analysis** section pinpoints the exact lines.

In short: `DocGenerationJob.doc_id` is a foreign key to
`project_docs.id`, which is the **composite** PK
`"{project_id}:{doc_id}"`. The aggregator copies that composite into
`raw["doc_id"]`, but the `job_detail.html` template uses
`raw["doc_id"]` directly in a URL that the docs route then re-prefixes
— producing the double-prefixed lookup `iw-ai-core:iw-ai-core:code-index`
and a 404. The fix is to expose the **inner** identifier
(`ProjectDoc.doc_id`) in the row, matching the convention used by every
other place in the codebase that links to a doc detail page.

## Requirements

### 1. Update `_build_doc_generation_raw` to accept and use the inner doc_id

Currently in `orch/jobs/aggregator.py` (around line 397):

```python
def _build_doc_generation_raw(self, job: DocGenerationJob) -> dict[str, object]:
    return {
        ...
        "doc_id": job.doc_id,
        ...
    }
```

Change the signature to take an optional inner-id mapping:

```python
def _build_doc_generation_raw(
    self,
    job: DocGenerationJob,
    inner_doc_id: str | None = None,
) -> dict[str, object]:
    # raw["doc_id"] MUST be the inner ProjectDoc.doc_id (the user-defined
    # identifier within the project), NOT the composite FK. The job detail
    # template builds /project/{pid}/docs/{raw.doc_id}, and the docs route
    # re-prefixes that with project_id when looking up the row. Passing the
    # composite causes a double-prefix 404. See I-00064.
    return {
        ...
        "doc_id": inner_doc_id,
        ...
    }
```

The default `None` keeps the orphan case working: if the FK is set but
the doc has been deleted, the link should be hidden (template already
guards with `{% if raw.get('doc_id') %}`).

### 2. Update `_fetch_doc_generation` to pass the inner id

The list view at lines 341-395 already loads `ProjectDoc` rows for
titles in a single batch query (lines 362-366). Extend the same query
result so you can build a `doc_id_map: dict[str, str]` keyed by composite
id, with the inner `doc.doc_id` as the value:

```python
doc_titles: dict[str, str] = {}
doc_inner_ids: dict[str, str] = {}
if doc_ids:
    docs = self._session.scalars(select(ProjectDoc).where(ProjectDoc.id.in_(doc_ids))).all()
    doc_titles = {doc.id: doc.title for doc in docs}
    doc_inner_ids = {doc.id: doc.doc_id for doc in docs}
```

Then call:

```python
raw = self._build_doc_generation_raw(
    job,
    inner_doc_id=doc_inner_ids.get(job.doc_id) if job.doc_id else None,
)
```

Do NOT add a per-row DB query — reuse the batch query result.

### 3. Update `_get_doc_generation` to pass the inner id

The detail-page entry point at lines 606-631 already loads the
`ProjectDoc` for the title (lines 615-619). Reuse that lookup:

```python
doc_title = None
inner_doc_id: str | None = None
if job.doc_id:
    doc = self._session.get(ProjectDoc, job.doc_id)
    if doc:
        doc_title = doc.title
        inner_doc_id = doc.doc_id
title = doc_title or "Doc generation (orphan)"
return JobRow(
    ...
    raw=self._build_doc_generation_raw(job, inner_doc_id=inner_doc_id),
)
```

### 4. Add a convention comment to `_fetch_code_mapping`

In `_fetch_code_mapping` (around line 251-287), the `code_mapping` row also
copies the composite FK into `raw["doc_id"]`. The template uses it only
as a presence check (the link is `/project/{id}/code` — no doc id in the
URL), so this is not user-broken today, but the convention should be
documented to prevent the same regression in future code that consumes
the field.

Add a short comment above the `"doc_id": job.doc_id,` line:

```python
# NOTE: This is the composite FK to project_docs.id, used here as a
# presence flag only (the View link goes to /project/{id}/code, not
# /docs/{id}). Do NOT use this value to build a /docs/{id} URL — see
# I-00064 and _build_doc_generation_raw for the correct convention.
```

Do NOT change the value here — only the comment.

### 5. No other behaviour changes

- Do not modify `DocService.get_doc`, the docs router, or the
  `job_detail.html` template — the fix is contained to the aggregator.
- Do not modify `_fetch_research` (already correct, see line 495).
- Do not modify `DocGenerationJob` model or any migration.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:
- Sync SQLAlchemy 2.0 (`Mapped[]` style); use `select(...)` and
  `self._session.scalars(...).all()`.
- Use `psycopg` (NOT psycopg2).
- Type hints required (`from __future__ import annotations` is in scope).
- Run `make format` before reporting completion.

## TDD Requirement

S03 (Tests) is responsible for the failing-test phase. For S01 your job
is the **GREEN** step — confirm the existing test suite still passes,
and that the test S03 will write would pass after your change. You may
write a quick local sanity test in your head or scratchpad; do NOT commit
test code in this step (test files are owned by S03 per the scope).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in
order and fix any issues they report:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — must report zero errors involving the files you
   touched.
3. `make lint` — must report zero errors.

In your `preflight` object, record `"ok"`, `"fixed"`, or
`"skipped:<reason>"` per gate.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — must pass with zero failures.
2. Run `make test-integration` — must pass with zero failures.
3. Do NOT report `tests_passed: true` unless both pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00064",
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
