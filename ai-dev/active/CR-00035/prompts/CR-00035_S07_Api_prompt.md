# CR-00035_S07_Api_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S07
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step. No alembic commands.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. `## API Changes`, `## Acceptance Criteria` AC8).
- `ai-dev/active/CR-00035/reports/CR-00035_S05_Backend_report.md` (your dependency — reuses `orch/doc_report.read_log_tail`, `strip_ansi`).
- `dashboard/routers/docs.py` — current routes for the doc job lifecycle (start, stream, status, panel, cancel).
- `dashboard/routers/jobs_ui.py` — current job-detail route at line ~170.
- `dashboard/routers/sse.py` — established SSE pattern.
- `dashboard/routers/code_qa.py` — alternate SSE pattern (token-streaming) for reference.
- `dashboard/CLAUDE.md` — routing conventions, htmx rules, fragment-vs-page distinction.

## Output Files

- `dashboard/routers/docs.py` (or `jobs_ui.py`) — three new endpoints
- `ai-dev/active/CR-00035/reports/CR-00035_S05_Api_report.md`

## Context

Add three HTTP endpoints that read the on-disk doc-job log so the dashboard can render it. These are NEW routes — they coexist with the existing `/docs/{doc_id}/jobs/{job_id}/...` lifecycle endpoints. Mount them under the **job-detail** URL space:

```
GET /project/{project_id}/jobs/doc_generation/{job_id}/log/tail   → application/json
GET /project/{project_id}/jobs/doc_generation/{job_id}/log/stream → text/event-stream
GET /project/{project_id}/jobs/doc_generation/{job_id}/log/raw    → text/plain
```

Pick the router file: if you put them in `dashboard/routers/docs.py`, use the existing `router = APIRouter(...)` and mirror the prefix discipline; if `jobs_ui.py` is more natural (route is under `/project/{project_id}/jobs/...`), put them there. **Pick one and stick to it.** Document the choice in your report.

## Requirements

### 1. Path resolution helper

Write a private helper used by all three endpoints:

```python
def _resolve_doc_job_log_path(
    db: Session, project_id: str, job_id: str
) -> tuple[DocGenerationJob, pathlib.Path]:
    """Look up the job (must belong to project_id), resolve the log path,
    return (job, path). Raises HTTPException(404) on unknown job, missing
    project, missing repo_root."""
```

`job_id` may be either the public ID (`DOC-NNNNN`) or the internal UUID. Look up by either (mirror what `JobsAggregator.get_job` does — it accepts public_id-or-id).

The log path is `Project.repo_root / "ai-dev" / "logs" / f"doc_job_{job.id}.log"`. **Always** use `job.id` (the UUID), never `public_id`, in the filename — that's the convention from `doc_job_poller.py:152`.

Validate that the resolved path is inside `Project.repo_root` after `.resolve()` to defend against any future code that lets `job.id` contain unsafe characters (defence in depth — UUIDs are safe today, but cheap to guard).

### 2. `GET .../log/tail` — JSON

Response shape:

```json
{
  "lines": ["...", "..."],
  "truncated_from_bytes": null,
  "file_size_bytes": 4443,
  "line_count": 98
}
```

- Read the last `n` lines (default 200; `?n=` query parameter, hard-capped at 1000).
- ANSI escapes stripped server-side (use `orch.utils.log_capture.strip_ansi`).
- Each line capped at 8 KB (truncate longer lines with `…` suffix).
- File missing → 404 with body `{"detail": "log file not found", "path": "<relative>"}`.
- Empty file → 200 with `{"lines": [], "file_size_bytes": 0, ...}`.

### 3. `GET .../log/stream` — SSE

- Content-Type: `text/event-stream; charset=utf-8`
- Initial chunk: emit the last 50 lines (so a late-joiner sees recent context).
- Then `seek(0, os.SEEK_END)` and follow new bytes:
  - `os.read(fd, 4096)` (non-blocking via `os.set_blocking(fd, False)` OR a tight `time.sleep(0.25)` loop — pick one and document).
  - Split on `\n`; emit one `data:<line>\n\n` per line. Strip ANSI per line. Cap line length at 8 KB.
- Heartbeat: every 15 seconds when no new data, emit `event:ping\ndata:\n\n` so reverse proxies don't time out.
- Termination: every poll iteration, re-read job status (cheap — single SELECT). When the job is in a terminal state (`completed` or `failed`), emit `event:status\ndata:terminal\n\n` and close the generator.
- Client disconnect: `StreamingResponse` cancellation must terminate the generator; do not leak the file descriptor (use a `with open(...) as f:` pattern or explicit `try/finally`).
- **Do NOT hold a Session open across the generator's lifetime.** Open a fresh short-lived session per status re-check (every ~2 seconds) — see `routers/code_qa.py` for the established pattern.

### 4. `GET .../log/raw` — text/plain

- Stream the file as `text/plain; charset=utf-8`. ANSI is **NOT** stripped (operators want the original).
- `Content-Disposition: attachment; filename="doc_job_<job.id>.log"`.
- File missing → 404 with explanatory body.
- Use `FileResponse` if it integrates cleanly; otherwise stream chunks via `StreamingResponse`.

### 5. Wire into the dashboard

If you put the routes in `dashboard/routers/docs.py`, ensure the router is already mounted with the `/project/{project_id}/...` prefix (it likely is — confirm). If you put them in `jobs_ui.py`, the prefix is also already correct.

Make sure the route order doesn't shadow the existing `GET /jobs/{job_type}/{job_id}` detail route in `jobs_ui.py:170`. New routes must be registered BEFORE that catch-all (FastAPI matches in declaration order), OR placed in a different router with a more specific path (the `/log/...` suffix should naturally disambiguate).

### 6. Pass `log_file_exists` to the template (S09 dependency)

Modify the existing job-detail handler in `dashboard/routers/jobs_ui.py:170-200` to also resolve the log path (using `_resolve_doc_job_log_path` or a stripped-down equivalent that doesn't 404) and pass `log_file_exists: bool` into the template context. S09 uses this to conditionally render the "Download raw log" link.

## Project Conventions

Read `dashboard/CLAUDE.md` carefully. Critical rules:

- **Routers are thin.** Helper logic that's not pure routing belongs in `orch/`. `_resolve_doc_job_log_path` is fine inline (it's pure path/lookup glue); the log reader / ANSI strip is in `orch/`.
- **Fragments vs pages.** SSE endpoints return text/event-stream — NOT a fragment. The `/log/tail` JSON endpoint is also not a fragment. They don't go under `templates/fragments/`.
- **No JS files.** htmx + SSE handles the streaming on the page side.
- `dependencies.py:get_db()` — your DB sessions per request.

## TDD Requirement

S11 writes the integration tests, but you SHOULD write at least a smoke test for each endpoint (404, 200, content-type) before declaring `complete`. Don't reimplement S11's coverage; just ensure your routes don't 500 trivially.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

Clean for files you touched.

## Test Verification

```bash
make test-unit
make test-integration
```

Report PASS only with zero failures involving files you touched.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "api-impl",
  "work_item": "CR-00035",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/<chosen>.py",
    "dashboard/routers/jobs_ui.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Router file chosen: docs.py | jobs_ui.py — and rationale. SSE polling strategy used. log_file_exists wired into jobs_ui.py:job_detail."
}
```
