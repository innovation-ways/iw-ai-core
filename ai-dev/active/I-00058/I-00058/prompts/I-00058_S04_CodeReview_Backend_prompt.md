# I-00058_S04_CodeReview_Backend_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

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

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `ai-dev/active/I-00058/reports/I-00058_S03_Backend_report.md` — S03 implementation report
- All files listed in the S03 report's `files_changed` (`orch/db/models.py`, `orch/jobs/aggregator.py`)

## Output Files

- `ai-dev/active/I-00058/reports/I-00058_S04_CodeReview_Backend_report.md` — Review report

## Context

You are reviewing the backend changes from S03 for **I-00058**. The implementation must:
1. Add a `@event.listens_for(DocGenerationJob, "before_insert")` listener in `models.py` that allocates `DOC-NNNNN` from `id_sequences['DOC']`.
2. Update `_fetch_doc_generation` in `aggregator.py` to expose `public_id` as the `job_id`.
3. Update `_get_doc_generation` in `aggregator.py` to look up by `public_id` first, then UUID PK fallback.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Report new violations in changed files as CRITICAL findings.

## Review Checklist

### 1. Event listener correctness (`orch/db/models.py`)
- Is the listener decorated with `@event.listens_for(DocGenerationJob, "before_insert")`?
- Does it skip allocation if `target.public_id is not None` (idempotency guard)?
- Is the SQL `INSERT INTO id_sequences ... ON CONFLICT ... RETURNING next_number - 1` correct?
- Is the prefix `'DOC'`? Is the format `f"DOC-{int(n or 1):05d}"`?
- Is the listener placed immediately after the `DocGenerationJob` class definition?
- Are the type annotations (`Mapper[Any]`, `Connection`, `DocGenerationJob`) imported correctly?

### 2. Aggregator changes (`orch/jobs/aggregator.py`)
- Does `_fetch_doc_generation` set `job_id=job.public_id or job.id` in the `JobRow` constructor?
- Does `raw` include both `"id": job.id` and `"public_id": job.public_id`?
- Does `_get_doc_generation` attempt `public_id` lookup first, then fall back to PK lookup?
- Is the fallback `session.get(DocGenerationJob, job_id)` preserved for legacy UUID rows?
- Does `_get_doc_generation` return `job_id=job.public_id or job.id`?

### 3. Scope discipline
- Is `orch/doc_service.py` untouched? (UUID `id` PK should remain unchanged)
- Are any other models or files changed beyond `models.py` and `aggregator.py`?

### 4. Semantic correctness
- Does the `public_id` allocation follow the same arithmetic as `CodeIndexJob`? (`next_number - 1` → format as 1-indexed `DOC-00001`)
- Does the `or job.id` fallback in `job_id` ensure legacy rows don't break?

### 5. Architecture compliance
- SQLAlchemy 2.0 `select()` used in `_get_doc_generation`, not legacy `session.query()`?
- No cross-layer imports introduced?

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Listener never fires, wrong prefix, SQL atomicity broken, UUID rows break |
| HIGH | Missing fallback for legacy rows, wrong arithmetic in ID format |
| MEDIUM (fixable) | Missing `public_id` in `raw` dict, wrong placement of listener |
| MEDIUM (suggestion) | Alternative pattern |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00058",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
