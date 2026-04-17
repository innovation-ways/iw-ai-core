# CR-00006 S06 — Frontend Review Report

**Reviewer**: frontend-review
**Step**: S06
**Work Item**: CR-00006
**Date**: 2026-04-17

---

## Summary

The frontend implementation is generally well-executed with correct DOMPurify+marked integration, proper XSS protection, and functional Jobs pages. One HIGH issue was found: the "Triggered by" column is missing from the Jobs table.

---

## Files Reviewed

| File | Status |
|------|--------|
| `dashboard/templates/base.html` | ✅ PASS |
| `dashboard/templates/fragments/code_qa_panel.html` | ✅ PASS |
| `dashboard/templates/fragments/code_job_report.html` | ✅ PASS |
| `dashboard/templates/fragments/nav_projects.html` | ✅ PASS |
| `dashboard/templates/pages/project/jobs.html` | ✅ PASS |
| `dashboard/templates/pages/project/job_detail.html` | ✅ PASS |
| `dashboard/templates/fragments/jobs_table.html` | ⚠️ 1 HIGH issue |

---

## Detailed Findings

### ✅ DOMPurify + marked integration (`base.html` + `code_qa_panel.html`)

- **Pinned CDN URL**: `https://cdn.jsdelivr.net/npm/dompurify@3.1.7/dist/purify.min.js` — correctly pinned at `@3.1.7`
- **Script ordering**: `marked.js` at line 77, `DOMPurify` at line 80 — correct (DOMPurify is available when `qaRenderMarkdown` runs)
- **`qaRenderMarkdown(raw)`**: Correct fallback if either library is undefined (returns `<pre>` with textContent)
- **marked options**: `{ gfm: true, breaks: true, mangle: false, headerIds: false }` — correct
- **DOMPurify config**: `{ USE_PROFILES: { html: true }, ADD_ATTR: ['target'] }` — correct; `afterSanitizeAttributes` hook sets `rel="noopener noreferrer"` on `<a target="_blank">` and calls `removeAllHooks()` after each sanitize to prevent hook leaks
- **Token SSE handling**: On each `token` frame: `responseSpan.innerHTML = qaRenderMarkdown(fullResponse)` — correct (NOT `textContent`, NOT `insertAdjacentHTML`)
- **Done frame**: Final `innerHTML` assignment uses `data.full_response || fullResponse` — correct
- **User bubbles**: `qaAppendUserBubble` uses `textContent` (line 126: `text.textContent = question`) — user input is never treated as markdown
- **Error bubbles**: Use `textContent` (line 154: `div.textContent = '⚠ ' + message`) — correct
- **Assistant bubble**: `qaAppendAssistantBubble()` returns a `<div>` with class `qa-response-markdown` — correct for block-level markdown
- **Styles**: Complete `<style>` block exists for headings, code blocks, lists, tables, links inside `.qa-response-markdown`

### ✅ XSS vector spot-check

- **`<script>alert(1)</script>`**: Path `fullResponse → marked.parse → DOMPurify.sanitize(html, { USE_PROFILES: { html: true }) → innerHTML` — `<script>` tags are stripped by DOMPurify's `USE_PROFILES.html` profile
- **`<img src=x onerror=alert(1)>`**: `onerror` attribute is stripped by DOMPurify's default sanitization
- **`target="_blank"` hook**: `afterSanitizeAttributes` correctly sets `rel="noopener noreferrer"` on `<a target="_blank">` links and removes the hook after each call

### ✅ Banner replacement (`code_job_report.html`)

- Green (`bg-green-50`) styling is **gone** — replaced with `bg-muted/30` neutral styling
- Compact single-line "Last run" summary present
- Link to `/project/{{ current_project.id }}/jobs/code_mapping/{{ last_completed_job.id }}` present
- File still exists (not deleted)

### ✅ Sidebar (`nav_projects.html`)

- `('/project/' ~ project.id ~ '/jobs', 'Jobs')` is correctly inserted **after** `History` and **before** `Tests` (line 16)
- No other links were touched or reordered

### ✅ Jobs page (`pages/project/jobs.html`)

- Extends `base.html` (line 1)
- `<h1>Jobs</h1>` with subtitle (lines 37-39)
- Filter form uses `method="get"` (line 42) — shareable URL
- Type and Status filters use checkboxes with `name="type"` and `name="status"` (lines 48-64) — accepts multiple values
- Table via `{% include "fragments/jobs_table.html" %}` (line 105)
- Pagination uses `total`, `page`, `page_size` — not present in the page itself but correctly passed through to the fragment

### ✅ Jobs fragment (`fragments/jobs_table.html`)

- Does NOT extend `base.html` — correct
- Contains table + pagination only — correct
- Can be rendered standalone as htmx response

### ✅ Job detail (`pages/project/job_detail.html`)

- Extends `base.html` (line 1)
- Header: `Job {{ job.job_id }} — {{ job.title }}` with status badge (lines 12-15)
- Back link to `/project/{{ current_project.id }}/jobs` (lines 8-11)
- Summary card with Type, Status, Triggered by, Started, Finished, Duration (lines 18-60)
- Type-specific parameters using `{% if job.job_type.value == '...' %}` blocks (lines 63-196)
- Artifact links per type (code_mapping → `/code`, doc_generation → `/docs/{id}`, batch_execution → `/batches/{id}`, research → `/research/{id}`)
- Error section for failed jobs (lines 198-204)
- No unsanitized rendering of user/LLM-originated text

### ✅ Accessibility

- Filter checkboxes, pagination links, table row links are all keyboard-accessible via native `<a>` and `<input>` elements
- Status badges use existing `status_badge` component — Tailwind dark mode handled via CSS variables
- Sidebar Jobs link has appropriate active-state styling via the existing `current_path.startswith(href)` logic
- SVG icons have `aria-hidden` implicitly (decorative); no info loss

### ✅ Cross-cutting

- Only JS library added is DOMPurify — correct
- No changes to `orch/` or `dashboard/routers/` Python files
- No tests written in this step
- No `console.log` statements found
- No commented-out code left behind (pre-existing `//` comments in unrelated files are not from this CR)

---

## Issues Found

### HIGH: Missing "Triggered by" column in Jobs table

**File**: `dashboard/templates/fragments/jobs_table.html`

**Problem**: The Jobs table shows 7 columns (ID, Type, Title, Status, Started, Finished, Duration) but the spec requires 8 columns including "Triggered by".

**Evidence**: The `{% set cols = [...] %}` at lines 37-45 in `jobs_table.html` only defines 7 columns. The `job_detail.html` correctly shows `job.triggered_by` in its summary card (line 32), confirming the data is available from the aggregator.

**Required fix**: Add "Triggered by" as the 8th column to `jobs_table.html`:

1. Add `("triggered_by", "Triggered by")` to the `cols` list after `duration`
2. Add a corresponding `<td>` with `{{ row.triggered_by or '—' }}`

---

## Verdict

**Step PASSES with 1 HIGH fix required.**

The markdown pipeline is correctly implemented with proper sanitization and hook cleanup. All structural changes (banner replacement, sidebar link, Jobs pages) are correct. The missing "Triggered by" column must be added to `jobs_table.html` before this step can be marked complete.

---

## Signal

```bash
# FAIL — awaiting HIGH fix
# iw step-fail CR-00006 S06 --reason "Missing Triggered by column in jobs_table.html — spec requires 8 columns"
```
