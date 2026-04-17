# CR-00006 S09 — Final Cross-Agent Code Review

## Input Files (ALL changed by CR-00006)

Backend (S01):
- `dashboard/routers/code_qa.py`
- `orch/jobs/__init__.py`
- `orch/jobs/aggregator.py`
- `orch/rag/job.py` (or wherever the code-index completion path lives)

API (S03):
- `dashboard/routers/jobs_ui.py`
- `dashboard/routers/sse.py`
- `dashboard/app.py`

Frontend (S05):
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/code_qa_panel.html`
- `dashboard/templates/fragments/code_job_report.html`
- `dashboard/templates/fragments/nav_projects.html`
- `dashboard/templates/pages/project/jobs.html`
- `dashboard/templates/pages/project/job_detail.html`
- `dashboard/templates/fragments/jobs_table.html`

Tests (S07):
- `tests/unit/test_code_qa_streaming.py`
- `tests/unit/test_jobs_aggregator.py`
- `tests/integration/test_jobs_api.py`
- `tests/unit/test_qa_markdown_sanitize.py`

Reference:
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`

## Output Files

- `ai-dev/work/CR-00006/reports/S09_code_review_final.md`

## Context

**Work item**: CR-00006
**Step**: S09
**Agent**: code-review-final-impl

This is the final, cross-agent review. Per-agent reviews (S02, S04, S06, S08) have already accepted each layer in isolation. Your job is to verify the whole change hangs together: integration points, consistency, completeness, regressions.

## Review Focus — Integration Points

### 1. End-to-end Q&A streaming path

Trace a question from the browser to the screen:

- `code_qa_panel.html` opens a POST to `/api/projects/{id}/code/qa`.
- `dashboard/routers/code_qa.py` returns `StreamingResponse(_sse_generator(...))` with no-cache + `X-Accel-Buffering: no`.
- `_sse_generator` launches a worker thread that runs `QAEngine.answer_stream` and pushes tokens onto an `asyncio.Queue` via `call_soon_threadsafe`.
- Outer generator yields `data: {"token": "..."}\n\n` per token, then `data: {"event": "done", ...}\n\n`.
- Frontend `fetch()` reader parses `data:` lines; on each token frame, appends to `fullResponse` and calls `qaRenderMarkdown(fullResponse)` → `marked.parse` → `DOMPurify.sanitize` → `innerHTML`.

Verify:
- [ ] Wire format is consistent at both ends (same keys, same frame structure).
- [ ] The bridge does not buffer — confirm by reading the code, not by rerunning the test.
- [ ] Client disconnect signals the worker thread to stop.
- [ ] No resource leak: the thread is a daemon thread AND has a clear exit path.

### 2. End-to-end code-map-completion toast

- Code index job completes in `orch/rag/job.py`.
- `DaemonEvent(event_type="code_map_completed")` is inserted in the same commit as `status = "completed"`.
- `sse.py` `_event_generator` picks it up, sees it in `_TOAST_EVENTS`, maps `_TOAST_SEVERITY["code_map_completed"] == "success"`, yields `event: toast\ndata: {...}\n\n`.
- Browser `EventSource` on the Code page (or any page with toast binding) dispatches `toast` event, `showToast()` renders the toast with 10s auto-dismiss.
- The green banner at `fragments/code_job_report.html` is GONE; the file now renders the neutral Last-Run link instead.

Verify:
- [ ] Event type string matches exactly between `orch/rag/job.py` and `sse.py` (grep both).
- [ ] `event_metadata` attribute (not `metadata`) is used in the insert.
- [ ] The toast message is human-readable and references file/chunk counts.
- [ ] The old green-banner markup (`bg-green-50`, `"Code map generated successfully"` string) no longer appears anywhere in the templates directory.

### 3. Jobs view round-trip

- `/project/{id}/jobs` is registered in `dashboard/app.py`.
- `jobs_ui.py` calls `JobsAggregator.list_jobs` → queries 4 tables → returns `JobListResult`.
- Template `pages/project/jobs.html` renders the result table via `fragments/jobs_table.html`.
- Row link goes to `/project/{id}/jobs/{job_type}/{job_id}`, which calls `JobsAggregator.get_job` → renders `job_detail.html`.
- Sidebar has "Jobs" link between "History" and "Tests" in `fragments/nav_projects.html`.
- Neutral Last-Run link in `code_job_report.html` points to `/project/{id}/jobs/code_mapping/{job.id}`.

Verify:
- [ ] URL path consistency across route decorators, template hrefs, and sidebar nav.
- [ ] `job_type` values match across aggregator enum, route Literal type, template conditionals, and sidebar link targets.
- [ ] Sort/filter parameters round-trip through the URL without loss.

### 4. Consistency with project conventions

- [ ] No new globally-loaded JS libraries other than DOMPurify (pinned version).
- [ ] No new Python deps added (grep `pyproject.toml` diff — expected: untouched).
- [ ] All new files follow existing project naming: snake_case Python, kebab/underscore templates, per-dir CLAUDE.md conventions.
- [ ] Imports sorted by `ruff` conventions.
- [ ] No dynamic Tailwind class construction (per `dashboard/CLAUDE.md`).

### 5. Completeness vs acceptance criteria

Walk through each AC in the design doc:

- [ ] AC1 (streaming) — verifiable via existing test + manual browser check.
- [ ] AC2 (markdown + XSS) — verifiable via template-grep test + manual browser check.
- [ ] AC3 (Jobs list) — verifiable via integration test + manual browser check.
- [ ] AC4 (Job detail) — verifiable via integration test + manual browser check.
- [ ] AC5 (banner → toast + neutral link) — verifiable via grep (no `bg-green-50` success banner) + manual browser check.
- [ ] AC6 (sidebar Jobs link) — verifiable via grep in `nav_projects.html` + manual browser check.
- [ ] AC7 (no regressions) — verifiable via `make quality && make check`.

### 6. Regression risks

- [ ] Other pages that include `components/toast.html` or listen for `event: toast` continue to work (no event collision — `code_map_completed` is new and doesn't overlap existing types).
- [ ] Other routes in `code_ui.py` still work (`_trigger_job`, `code_page`, `code_status`, `code_index_stream`, cancel path).
- [ ] Existing `code_job_status.html` running-job template still renders correctly when a job is running.
- [ ] History page still renders (no accidental include changes).
- [ ] Search (`/api/search`) still works.
- [ ] Other SSE consumers on running/status/test/quality streams are unaffected.

## Commands

```bash
# Full quality pass
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/

# Tests
make test-unit
make test-integration

# Smoke-check for lingering green banner content
grep -rn "Code map generated successfully" dashboard/templates/ || echo "OK: success-banner text is gone"
grep -rn "bg-green-50" dashboard/templates/fragments/code_job_report.html || echo "OK: green styling gone from banner fragment"

# Event-type consistency
grep -rn "code_map_completed" orch/ dashboard/
# Expected: at least 3 matches — the insert site, _TOAST_EVENTS, _TOAST_SEVERITY

# JS libraries audit
grep -n "cdn.jsdelivr\|unpkg\|cdnjs" dashboard/templates/base.html
# Expected: existing scripts + DOMPurify pinned

# Imports audit
grep -n "jobs_ui" dashboard/app.py
```

## Findings report

Write all findings to `ai-dev/work/CR-00006/reports/S09_code_review_final.md` with severity and concrete fix suggestions. Use the severity scale: CRITICAL / HIGH / MEDIUM / LOW.

## Signal completion

If no CRITICAL or HIGH findings:

```bash
iw step-done CR-00006 S09 --summary "Final review passed: end-to-end streaming path correct, toast pipeline wired, Jobs view round-trip consistent, no regressions detected, acceptance criteria verifiable."
```

If CRITICAL/HIGH findings exist:

```bash
iw step-fail CR-00006 S09 --reason "<N CRITICAL + M HIGH findings — see report>"
```
