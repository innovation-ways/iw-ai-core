# CR-00035 S10 — Code Review Report (Frontend Implementation)

## Work Item
**CR-00035** — Doc-generation job observability + execution report + dispatch fix

## Step Reviewed
**S09 — frontend-impl**

---

## Pre-Review Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✓ All checks passed |
| `make format-check` | ✓ 615 files already formatted |
| `make test-unit` | ✓ 2600 passed, 4 skipped, 5 xfailed, 1 xpassed |

---

## Files Reviewed

| File | Change |
|------|--------|
| `dashboard/templates/pages/project/job_detail.html` | Added Live Log card, Captured log `<details>`, Execution Report card for `doc_generation` jobs |
| `dashboard/routers/jobs_ui.py` | Added `_resolve_doc_job_log_path`, log endpoints (`/log/tail`, `/log/stream`, `/log/raw`), `log_file_exists` context |

---

## Review Findings

### Conditional Rendering Correctness ✓

- **Live Log card** (`{% if job.status == 'running' %}`) — correct, renders only when `status == 'running'`.
- **Captured log** (`{% if job.status != 'running' and raw.get('agent_output') %}`) — correct, shows only for terminal state with `agent_output`.
- **Execution Report card** (`{% if raw.get('report') %}`) — correct, renders whenever `report` is present.
- **Download raw log link** (`{% if log_file_exists %}`) — correct, uses the boolean passed from `job_detail` handler.
- **A queued job** shows none of Live Log / Captured log / Execution Report — confirmed.
- **Error block** (lines 348–355) unchanged and still renders for failed jobs — confirmed by comparing to pre-CR state.

### SSE Wiring ✓

- Inline script uses vanilla `EventSource` to `/project/{{ current_project.id }}/jobs/doc_generation/{{ raw.id }}/log/stream`.
- URL uses `raw.id` (UUID), NOT `raw.public_id` — confirmed.
- Closes connection on `event:status data:terminal` — confirmed in both frontend template (line 155–157) and backend `_doc_job_log_stream` (yields `event: status\ndata: terminal\n\n`).
- Also closes on `onerror` defensively.
- `htmx-sse` extension NOT used — consistent with existing SSE consumers in the project (`sse-client.js`, `code_ui.py`, `code_qa.py`).

### Accessibility ✓

- Log `<pre>` has `aria-live="polite"` and `aria-label="Live agent log"` — confirmed.
- Status pill uses `status_badge()` macro (semantic function), not an icon-only signal — confirmed.

### Tailwind ✓

- All classes are static string literals (`bg-card`, `border-border`, `font-mono text-xs`, etc.) — no `class="text-{{ color }}-500"` JIT-purge-breaking patterns.
- No new CSS classes needed; `make css` reports "Nothing to be done".

### Card Spacing & Visual Sanity ✓

- All cards use `bg-card border border-border rounded-lg p-4 mb-6` — identical to existing cards.
- Font sizes: `text-sm` headings, `text-xs` labels, `font-mono text-xs` for log text — consistent.
- Captured log uses `max-height: 32rem` with `overflow-auto` — matches Live Log.

### Inline Script ✓

- 14 lines (well under the 30-line limit).
- No new dependencies.
- Uses `new EventSource()` (vanilla) — consistent with project patterns.
- Closes on terminal event, error, and disconnect.

### Path Traversal Protection ✓

- `_resolve_doc_job_log_path` resolves `log_path` to absolute path and checks `is_relative_to(repo_root_resolved)` before returning — defence-in-depth path traversal protection confirmed.

### Error Block Regression ✓

- Error block at lines 348–355 unchanged from pre-CR state — confirmed identical by comparing to `aba08f8:dashboard/templates/pages/project/job_detail.html`.

### Aggregator `report` Field ✓

- `report: job.report` added to `_build_doc_generation_raw` (line 440 of `orch/jobs/aggregator.py`) — confirmed by `git diff aba08f8`.

### Uncommitted Test Files (Observed)

Two test files are **uncommitted but exist on disk**:
- `tests/unit/test_doc_report.py` (7751 bytes, created May 5 23:57)
- `tests/dashboard/test_doc_job_log_endpoints.py` (7869 bytes, created May 6 00:39)

These are S09 (Tests) deliverables but have not been committed. The frontend review does not depend on these files. They should be committed as part of S09 completion.

---

## Regression Check

No regressions found in existing template structure. The `doc_generation` Parameters card (lines 95–132) is unchanged. All `elif` branches for other job types (`batch_execution`, `oss_scan`, `research`) are intact.

---

## Mandatory Fix Count

**0**

No mandatory fixes required.

---

## Notes

1. The `log_file_exists` boolean is correctly computed in the `job_detail` handler by calling `_resolve_doc_job_log_path` (which validates project + job existence and path safety) and checking `_log_path.is_file()`. This is the correct pattern — it avoids raising exceptions for the template.

2. The inline SSE script closes on `event:status data:terminal`. The backend SSE endpoint emits `event: status\ndata: terminal\n\n`. The frontend listens for a `status` event with `e.data === 'terminal'`. This is consistent.

3. The `status_badge` macro is imported at the top of `job_detail.html` and handles arbitrary strings — it works for `outcome` values like `failed_process_exited` that are not enum members of `JobStatus`.

4. The dispatch fix (`/execute {job.id}` → `/doc-job {job.id}`) is confirmed in `orch/daemon/doc_job_poller.py` line 309 (git diff confirmed).

5. `commands/doc-job.md` exists (1435 bytes, created May 5 23:28) and routes to doc-generation skills based on editorial category.

---

## Verdict

**PASS** — S09 frontend implementation is correct and complete. All conditional rendering, SSE wiring, accessibility, Tailwind usage, card spacing, and regression checks pass.