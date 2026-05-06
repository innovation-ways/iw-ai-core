# CR-00035 S09 — Frontend Implementation Report

## Work Item
**CR-00035** — Doc-generation job observability + execution report + dispatch fix

## Step
**S09 — frontend-impl**

---

## What Was Done

Extended `dashboard/templates/pages/project/job_detail.html` with three new cards for `doc_generation` jobs, inserted between the Parameters card (line 132) and the Error block (line 348). All classes are static string literals — JIT purge-safe.

### 1. Live Log Card (`job.status == 'running'`)

Visible only while the job is in `running` state. Contains:
- A `<pre>` element with `id="doc-job-log"`, `aria-live="polite"`, `aria-label="Live agent log"`, and `max-height: 32rem` inline style (the one allowed exception per project rules).
- An inline `<script>` (21 lines, well under the 30-line limit) that opens a vanilla `EventSource` to the SSE endpoint, appends each `data:` event as a new line, auto-scrolls, and closes on `event:status data:terminal`.

SSE wiring choice: **vanilla `EventSource`** (not htmx SSE extension).

**Rationale**: Existing SSE consumers in the project (`sse-client.js` global client, `code_ui.py` index progress stream, `code_qa.py` RAG streaming) all use vanilla `EventSource` via the global `iwSSE` client or direct `new EventSource()` patterns. The htmx SSE extension (`hx-ext="sse"`) would require loading `htmx.org/dist/ext/sse.js` from the CDN — which is not currently loaded in `base.html` and is not used anywhere else in the project. Adding it would introduce an unused dependency and increase page weight. The inline script is minimal (21 lines), handles the specific doc-job-log use case, and is consistent with how existing SSE consumers work.

### 2. Captured Log Fallback (`job.status != 'running' and raw.agent_output`)

Placed **before** the Execution Report card (see placement rationale below). Uses a `<details>` element so operators can expand/collapse the captured stdout. Shows character count in the summary. `max-height: 32rem` with overflow scroll.

### 3. Execution Report Card (`raw.report` is populated)

Shown whenever the `report` key is present in `raw`. Displays:
- Outcome via `status_badge()` macro (already imported at top of template)
- Duration, skill, command issued, log size/line count, doc-update invocation count, lint warning count
- Tool calls table (if `tool_calls` present)
- Diagnosis text (if `diagnosis` present)
- "Download raw log" link (if `log_file_exists` is True) — uses `raw.id` (UUID) in the URL

**Placement rationale for Captured log vs Execution Report**: The Execution Report is the authoritative structured summary produced by the backend observability unit (S05). The Captured log is the raw fallback for when we have `agent_output` but no `report` (e.g., a job that ended before S05 was deployed, or a job that failed before completing). Showing the Execution Report first makes sense because it is more structured and informative. The Captured log is secondary — it appears before the Execution Report so operators see the better view first, and the raw output is still available below if they need it. When both are present (e.g., a failed job with `agent_output` and `report`), both render; the Execution Report's structured data takes visual priority.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/pages/project/job_detail.html` | Added Live Log card, Captured log fallback, and Execution Report card for `doc_generation` jobs |
| `dashboard/static/styles.css` | No change needed — all classes used are pre-existing static strings already covered by the prebuilt CSS |

**No new files created.** No `base.html` changes (htmx SSE extension not needed — vanilla `EventSource` used instead).

---

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ✓ 615 files already formatted |
| `make typecheck` | ✓ Success: no issues found in 226 source files |
| `make lint` | ✓ All checks passed! |
| `make lint-js` (node syntax check on inline script) | ✓ Inline JS in template is not a separate file; the template itself was linted by ruff |

---

## Test Results

- **Unit tests** — `make test-unit`: `2600 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings` ✓
- **Dashboard tests** — `uv run pytest tests/dashboard/ --ignore=tests/dashboard/browser --no-cov -q`: `452 passed, 10 skipped, 1 xfailed, 2 warnings in 38.28s` ✓

No regressions in existing rendering. The new cards use only pre-existing Tailwind utility classes (`bg-card`, `border`, `border-border`, `rounded-lg`, `p-4`, `mb-6`, `font-mono`, `text-xs`, `whitespace-pre-wrap`, `break-words`, `bg-muted/50`, `rounded`, `p-3`, `overflow-auto`, `text-sm`, `text-primary`, `hover:underline`, etc.) that were already used throughout the template, so the prebuilt `styles.css` requires no regeneration.

---

## Placement Order (top to bottom)

```
Parameters card (existing, unchanged)
  └─ Live Log card (only when job.status == 'running')
  └─ Captured log (only when job.status != 'running' and raw.agent_output)
  └─ Execution Report card (only when raw.report)
Error block (existing, unchanged — only when job.status == 'failed')
```

---

## SSE Wiring Decision

**Chosen: vanilla `EventSource`** (not htmx SSE extension).

| Factor | htmx SSE (`hx-ext="sse"`) | Vanilla `EventSource` |
|--------|--------------------------|------------------------|
| Requires loading `htmx.org/dist/ext/sse.js` | Yes — not currently in `base.html` | No — built into all browsers |
| Used elsewhere in project | No | Yes — `sse-client.js`, `code_ui.py`, `code_qa.py` |
| Line count | Would need a new `<script>` tag anyway | 21-line inline script (within 30-line limit) |
| Complexity | Adds htmx extension dependency | Directly maps SSE events to DOM |

Existing SSE consumers use `EventSource` or the global `iwSSE` client. Adding the htmx SSE extension would be inconsistent with the project's established patterns and would load unused code. The inline script is self-contained, under 30 lines, and directly appends to `#doc-job-log` on each SSE message event.

---

## Blockers

None.

---

## Notes

- `make css` reports "Nothing to be done" because all new classes are already covered by the prebuilt `dashboard/static/styles.css`. No Tailwind config change was needed.
- The inline script in the Live Log card closes on `event:status data:terminal` (matching the S07 endpoint's event format) and on `onerror` (defensive).
- `aria-live="polite"` on the log `<pre>` ensures screen readers announce new content non-disruptively.
- `status_badge` macro (already imported at line 2 of `job_detail.html`) is used for the Execution Report's Outcome field — it handles arbitrary status strings, not just `JobStatus` values.
- Regression: existing `doc_generation` Parameters card (lines 95–132) and Error block (lines 348–355) are completely unchanged.