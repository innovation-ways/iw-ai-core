# I-00077_S03_frontend-impl_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document (read first; especially Root Cause #3 and AC3)
- `dashboard/routers/docs.py` — `docs_running_jobs` (the strip fragment endpoint), `docs_job_stream` / `_job_status_stream` (SSE), `docs_job_cancel` — context
- `dashboard/templates/docs_library.html` — the `/project/<id>/docs` catalogue page
- `dashboard/templates/fragments/docs_running_jobs.html` — the running-jobs strip fragment
- For reference: `dashboard/templates/docs_detail.html` (its `docJobFailed` handler — line ~311 — shows what the catalogue page is missing), `dashboard/templates/components/toast.html` (the reusable `showToast({type,message})` helper)

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_S03_frontend-impl_report.md` — step report
- Modified: `dashboard/routers/docs.py`, `dashboard/templates/docs_library.html`, `dashboard/templates/fragments/docs_running_jobs.html`

## Context

You are implementing the dashboard half of I-00077 — making doc-generation job failures visible on the **Docs catalogue page** (`/project/<id>/docs`, rendered by `docs_library.html`). Read the design doc in full, especially **Root Cause Analysis** cause #3 and **AC3**. Read `dashboard/CLAUDE.md` and `CLAUDE.md`. **Do not touch `orch/doc_service.py` or the skills** — that's S01's scope.

## Requirements

### 1. `docs_running_jobs` also returns recently-failed jobs

In `dashboard/routers/docs.py`, `docs_running_jobs(...)` currently filters `DocGenerationJob.status == JobStatus.running`. Widen it so the query also returns jobs whose `status == JobStatus.failed` **and** `completed_at` is within roughly the last 10 minutes (use `datetime.now(UTC) - timedelta(minutes=10)`; the module already imports `datetime`/`UTC` — add `timedelta` if needed). Keep the existing `ProjectDoc.doc_type != DocType.research` exclusion and the `doc_id.startswith(f"{project_id}:")` scoping. Order so running jobs come first, then failed jobs (e.g. order by a computed status priority then `requested_at`, or just `requested_at` — running jobs will naturally have no `completed_at`; pick something deterministic and explained in a comment).

Extend the per-job dict the handler builds (and passes to the template as `running_jobs`) with at least: `status` (the `JobStatus` value as a string, e.g. `"running"` / `"failed"`) and `error` (the job's `error` string, or `""`/`None`). Keep `job_id`, `doc_id`, `doc_title`.

> Note: there is no `JobStatus.cancelled` — a user-cancelled job is recorded as `failed` with `error="Cancelled by user"` by `docs_job_cancel`, which does **not** set `completed_at` (it stays `NULL`). So a cancelled job will *not* match the `completed_at` ≥ cutoff window and won't appear in the strip — that's fine and intended (the user who clicked Cancel doesn't need a failure notice). Don't widen the filter to also catch `completed_at IS NULL` failed rows (that would resurface every old cancelled job forever), and don't add a `completed_at` write to `docs_job_cancel` — both are out of scope. The agent-driven failure path (`iw doc-job-done --error`, which is the actual bug case — DOC-00055) *does* set `completed_at`, so genuine generation failures land in the window correctly.

### 2. `fragments/docs_running_jobs.html` renders failed jobs as a dismissible red row

Today every row in this fragment renders a spinner, an elapsed timer, a Cancel button, and an inline `<script>` that opens an `EventSource` to the job's SSE stream. Split the loop body so that:

- **`status == "running"`** rows render exactly as today (spinner, elapsed timer, Cancel button, the EventSource `<script>`). Do not change that path's behaviour.
- **`status == "failed"`** rows render a **static** red row: a distinct CSS state (e.g. `border-l-4 border-l-[var(--destructive)]` or a clearly-named class like `docs-rjob-failed` — see `dashboard/static/theme.css` / `styles.css` for the destructive colour token), an error icon, the `doc_title`, the `error` text (HTML-escaped by Jinja2 autoescaping — do not mark it safe), and a **Dismiss** button. The Dismiss button removes the row client-side: `onclick="this.closest('[id^=docs-rjob-]').remove()"` (a client-side dismiss is sufficient — the row will reappear on the next strip reload only if still within the 10-min window; do **not** add a new server endpoint or relax `docs_job_cancel`'s 409 guard). A failed row must **NOT** open an `EventSource`, must **NOT** start an elapsed timer, and must **NOT** render a Cancel button.

Keep the outer wrapper `id="docs-rjob-{{ item.job_id }}"` convention so the existing `hx-target` / dedup logic and the new Dismiss `onclick` both work.

**Jinja2 hard rule:** if you use the `format` filter anywhere, keep it `%`-style (`"%dm%02ds"|format(m, s)`), never `str.format`-style. (`make lint` → `scripts/check_templates.py` enforces this.)

### 3. `docs_library.html` surfaces failures with a persistent toast

The catalogue page currently has no `docJobFailed` listener (only `docs_detail.html` does). Add to `docs_library.html`:

- `{% include "components/toast.html" %}` (this defines the reusable `showToast({type, message})` helper and is not currently loaded on this page — verify it isn't already included before adding).
- A `document.body.addEventListener('docJobFailed', ...)` handler that calls `showToast({type: 'error', message: 'Documentation generation failed' + (detail.doc_id ? ' — ' + detail.doc_id : '') + (detail.error ? ': ' + detail.error : '')})`. Truncate an overly long error (say >160 chars) before showing it.
- (Recommended, low-risk) A `document.body.addEventListener('docJobCreated', ...)` handler that dispatches `runningJobsReload` immediately and again after ~3 s and ~8 s, so a quick `queued → running` transition shows up in the strip without a manual refresh. Keep it tiny — a couple of `setTimeout`s. This is the only behaviour beyond AC3 that you should add; do not redesign the strip's refresh model otherwise.

The `docJobFailed` / `docJobCompleted` / `docJobCreated` CustomEvents are already dispatched on `document.body` by `fragments/docs_running_jobs.html`'s per-job SSE script (the `failed` branch) and by the `HX-Trigger` on `docs_create_job`. You are adding *listeners*, not changing the dispatchers.

## Project Conventions

Read `dashboard/CLAUDE.md` and `CLAUDE.md`: htmx fragment patterns, where plain CSS goes (`dashboard/static/styles.css` if `make css` is a no-op — but prefer existing Tailwind utility classes / CSS vars and avoid needing new CSS at all), Jinja2 `format`-filter rule, JS conventions (`node --check` runs on dashboard JS via `make lint`).

## TDD Requirement

Follow Red-Green-Refactor where it applies. The behavioural surface here is: (a) `docs_running_jobs` returns failed jobs — testable via the `client` fixture under `tests/dashboard/`; (b) the rendered fragment marks failed rows distinctly with a Dismiss control and no Cancel button — testable on the rendered HTML; (c) `docs_library.html` includes a `docJobFailed` handler — testable on the rendered page HTML. Write at least a minimal failing `tests/dashboard/test_docs_running_jobs.py` assertion for (a) before you change the query, then make it pass. S05 will round out the full test set, but do not ship the query change without a RED→GREEN test for it.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in files you touched:

1. `make format`
2. `make typecheck`
3. `make lint` — **includes `scripts/check_templates.py`** (Jinja2) and `node --check` on dashboard JS; both must pass.

Record results in the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests for what you changed — not the full suite:

```bash
uv run pytest tests/dashboard/test_docs_running_jobs.py -v
```

Do not report `tests_passed: true` unless that passes. Do not run `make test-integration` — that's a downstream QV gate.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/docs.py", "dashboard/templates/docs_library.html", "dashboard/templates/fragments/docs_running_jobs.html", "tests/dashboard/test_docs_running_jobs.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
