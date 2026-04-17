# CR-00006 S05 — Frontend Implementation

## Input Files

- `CLAUDE.md` and `dashboard/CLAUDE.md` — Tailwind + htmx + Jinja2, no build step
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`
- `dashboard/templates/base.html` — loads `marked.js` at line 77; DOMPurify must be added here
- `dashboard/templates/fragments/code_qa_panel.html` — markdown rendering added here
- `dashboard/templates/fragments/code_job_report.html` — currently the green banner; replace with neutral Last-Run link
- `dashboard/templates/fragments/nav_projects.html` — sidebar; add Jobs link
- `dashboard/templates/pages/project/history.html` — reference pattern for filterable/sortable table
- `dashboard/templates/components/toast.html` — existing toast system (already integrated — nothing to change here)
- `dashboard/templates/fragments/code_job_status.html` — reference for running-job visuals if needed
- `orch/jobs/aggregator.py` — dataclasses you will reference in templates (`JobRow`, `JobListResult`)

## Output Files

- **New**: `dashboard/templates/pages/project/jobs.html`
- **New**: `dashboard/templates/pages/project/job_detail.html`
- **New**: `dashboard/templates/fragments/jobs_table.html`
- **Modified**: `dashboard/templates/base.html` (add DOMPurify CDN)
- **Modified**: `dashboard/templates/fragments/code_qa_panel.html` (sanitized markdown rendering)
- **Modified**: `dashboard/templates/fragments/code_job_report.html` (replace green banner with neutral Last-Run summary + Jobs link)
- **Modified**: `dashboard/templates/fragments/nav_projects.html` (add Jobs link)

## Context

**Work item**: CR-00006
**Step**: S05
**Agent**: frontend-impl

You are building the UI layer on top of the routes that S03 registered and the DOM-facing parts of the Q&A streaming + markdown work.

## Task 1: Add DOMPurify to `base.html`

Find the line:

```html
<!-- marked.js for markdown rendering in artifact viewer -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

(currently around line 77)

Add **immediately after** it:

```html
<!-- DOMPurify — sanitize LLM-rendered markdown output before injection -->
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.7/dist/purify.min.js"></script>
```

Pin the version (`@3.1.7` or equivalent known-good version — do not use a floating major tag).

## Task 2: Update `code_qa_panel.html` for sanitized markdown rendering

### What to change

The existing handler at lines 167-232 accumulates tokens into `fullResponse` and sets `responseSpan.textContent += data.token`. Replace that with per-token markdown rendering.

### Implementation

1. Add a helper at the top of the IIFE (after the `QA_MAX_HISTORY` constant):

   ```javascript
   function qaRenderMarkdown(raw) {
     if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
       // Graceful fallback: plain text with newlines preserved
       var pre = document.createElement('pre');
       pre.textContent = raw;
       return pre.outerHTML;
     }
     var html = marked.parse(raw, { gfm: true, breaks: true, mangle: false, headerIds: false });
     // Allow target on links; enforce safe rel
     DOMPurify.addHook('afterSanitizeAttributes', function (node) {
       if (node.tagName === 'A' && node.getAttribute('target') === '_blank') {
         node.setAttribute('rel', 'noopener noreferrer');
       }
     });
     var clean = DOMPurify.sanitize(html, {
       USE_PROFILES: { html: true },
       ADD_ATTR: ['target'],
     });
     DOMPurify.removeAllHooks();
     return clean;
   }
   ```

2. In `qaAppendAssistantBubble()`, change the inner element from a `<span>` to a `<div>` so block-level markdown (headings, lists, code blocks) renders correctly. Add a Tailwind class for typography spacing — e.g., `class="qa-response-markdown text-sm leading-relaxed space-y-2"`. Remove the `text` variable being a `span` — use a `div`. Return the `div`.

3. In `qaSubmit()`, replace:

   ```javascript
   if (data.token !== undefined) {
     fullResponse += data.token;
     responseSpan.textContent += data.token;
     qaScrollBottom();
   }
   ```

   with:

   ```javascript
   if (data.token !== undefined) {
     fullResponse += data.token;
     responseSpan.innerHTML = qaRenderMarkdown(fullResponse);
     qaScrollBottom();
   }
   ```

   On the `done` event, do one final `responseSpan.innerHTML = qaRenderMarkdown(data.full_response || fullResponse);`.

4. Add minimal `<style>` block at top of template for code-block appearance (below the `{# Q&A Panel … #}` comment, inside the file):

   ```html
   <style>
     .qa-response-markdown h1, .qa-response-markdown h2, .qa-response-markdown h3 { font-weight: 600; }
     .qa-response-markdown h1 { font-size: 1.05rem; }
     .qa-response-markdown h2 { font-size: 1rem; }
     .qa-response-markdown h3 { font-size: 0.95rem; }
     .qa-response-markdown pre { background: var(--muted); padding: 0.6rem; border-radius: 0.375rem; overflow-x: auto; font-family: var(--font-mono); font-size: 0.8rem; margin: 0.5rem 0; }
     .qa-response-markdown code { font-family: var(--font-mono); font-size: 0.85em; padding: 0.1rem 0.25rem; background: var(--muted); border-radius: 0.25rem; }
     .qa-response-markdown pre code { padding: 0; background: transparent; }
     .qa-response-markdown ul, .qa-response-markdown ol { padding-left: 1.25rem; }
     .qa-response-markdown ul { list-style: disc; }
     .qa-response-markdown ol { list-style: decimal; }
     .qa-response-markdown table { border-collapse: collapse; margin: 0.5rem 0; }
     .qa-response-markdown th, .qa-response-markdown td { border: 1px solid var(--border); padding: 0.25rem 0.5rem; }
     .qa-response-markdown a { color: var(--primary); text-decoration: underline; }
   </style>
   ```

5. User bubbles in `qaAppendUserBubble()` stay `textContent` (plain text, no markdown). Only the assistant bubble renders markdown.

### Do NOT

- Do NOT add syntax highlighting — out of scope.
- Do NOT render user input as markdown.
- Do NOT remove the error bubble logic or the history-truncation logic.

## Task 3: Replace the green banner in `code_job_report.html`

Current file content (the full green-banner block) must be replaced with a neutral, single-line "Last run" summary that links to the Jobs detail page. The include at `project_code.html:78` stays the same — only this fragment's body changes.

New content:

```html
{# Neutral "Last run" summary for the most recent completed code map job.
   Replaces the former persistent success banner; success toast is emitted
   via DaemonEvent(code_map_completed) and shown by components/toast.html. #}
<div class="flex items-center justify-between px-3 py-2 bg-muted/30 border border-border rounded-lg text-xs text-muted-foreground">
  <div class="flex items-center gap-2 min-w-0">
    <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
    </svg>
    <span class="truncate">
      Last run
      {% if last_completed_duration %}· {{ last_completed_duration }}{% endif %}
      · {{ last_completed_job.files_indexed }} files · {{ last_completed_job.chunks_created | intcomma }} chunks
    </span>
  </div>
  <a href="/project/{{ current_project.id }}/jobs/code_mapping/{{ last_completed_job.id }}"
     class="text-primary hover:underline flex-shrink-0 ml-2">
    View →
  </a>
</div>
```

Do NOT delete the file — it is still included by `project_code.html` when `last_completed_job and last_completed_recent`. The toast (emitted by the `DaemonEvent` inserted in S01) handles the "success notification" UX; this fragment is now the persistent compact summary.

## Task 4: Add Jobs link to `nav_projects.html`

File: `dashboard/templates/fragments/nav_projects.html`

Find the `links` list (around lines 12-23):

```jinja2
{% set links = [
  ('/project/' ~ project.id ~ '/', 'Dashboard'),
  ('/project/' ~ project.id ~ '/batches', 'Batches'),
  ('/project/' ~ project.id ~ '/queue', 'Queue'),
  ('/project/' ~ project.id ~ '/history', 'History'),
  ('/project/' ~ project.id ~ '/tests', 'Tests'),
  ...
] %}
```

Insert a new tuple **immediately after** `History`:

```jinja2
  ('/project/' ~ project.id ~ '/jobs', 'Jobs'),
```

The existing active-link highlight logic uses `current_path.startswith(href)`, so `/jobs/*` paths will highlight automatically.

## Task 5: Create `pages/project/jobs.html`

Full page, extends `base.html`. Structure: filters (form), results count, table (sortable column headers), pagination.

Use `history.html` as the visual template. Columns: ID, Type, Title, Status, Started at, Finished at, Duration, Triggered by.

Key requirements:
- Header: `<h1>Jobs</h1>` with subtitle "Background operations across this project".
- Filter form posts via `method="get"` (submit does a full page reload, not htmx, to keep URL shareable).
- Type filter is a `<select multiple>` with `size="4"` OR a set of checkboxes (prefer checkboxes for UX). Status filter the same shape.
- Date range: two `<input type="date">`.
- Results table uses `{% include "fragments/jobs_table.html" %}`.
- Pagination: prev/next at the bottom based on `total`, `page`, `page_size`.
- Type column: render a small colored chip per type (reuse `components/status_badge.html` pattern or inline).
- Status column: render using `{% from "components/status_badge.html" import status_badge %}` with the normalised lowercase status strings.
- Each row is clickable — wrap the first cell (ID) in `<a href="/project/{{ current_project.id }}/jobs/{{ row.job_type.value }}/{{ row.job_id }}">`.
- Timestamps use the existing `timeago` filter for "Started at" and show absolute ISO for "Finished at" (or use `timeago` consistently — pick one and document in a comment).
- Duration: compute in the template from `started_at` and `finished_at` OR add a `duration` property to `JobRow` — prefer a template macro `{% macro fmt_duration(start, end) %}...{% endmacro %}` at the top of the page.

## Task 6: Create `fragments/jobs_table.html`

Just the table markup (thead + tbody + pagination), used by the filter fragment endpoint. Does NOT extend `base.html`.

## Task 7: Create `pages/project/job_detail.html`

Full page. Layout:

- Header: "Job {{ job.job_id }} — {{ job.title }}" with status badge.
- Back link to `/project/{project_id}/jobs`.
- **Summary card**: Type, Status, Started, Finished, Duration, Triggered by.
- **Parameters section**: renders `raw` keys as a definition list. Use `{% if job.job_type.value == "code_mapping" %}` blocks to show type-specific fields:
  - `code_mapping`: `llm_model`, `embed_model`, `index_tier`, `files_discovered`, `files_indexed`, `chunks_created`, `languages_detected`, `provider`
  - `doc_generation`: `skill_used`, `trigger_reason`, `duration_seconds`, `lint_warnings` (rendered as a list if non-empty)
  - `batch_execution`: `max_parallel`, `cli_tool`, `auto_publish`
  - `research`: `audience`, `source_paths`, `version`
- **Artifact link**:
  - `code_mapping`: if `raw.doc_id`, link to `/project/{project_id}/code` (the architecture map page).
  - `doc_generation`: if `raw.doc_id`, link to `/project/{project_id}/docs/{doc_slug}` (or whatever the existing docs route is — grep for it in `docs.py`).
  - `batch_execution`: link to `/project/{project_id}/batches/{batch_id}`.
  - `research`: link to `/project/{project_id}/research/{doc_id}` (or existing research route — grep for it).
- **Error** (if `status == failed`): show `raw.error` or similar.

Keep the template under ~200 lines. Prefer simple inlined HTML over cleverness.

## Verification

```bash
uv run python -c "from dashboard.app import create_app; app = create_app(); print('app built ok')"
# Start the server manually to eyeball:
#   make dashboard-start
# then open http://localhost:9900/project/<any>/jobs
```

## Do NOT

- Do NOT write tests.
- Do NOT change `dashboard/routers/` Python files.
- Do NOT change `orch/rag/qa.py` or `orch/jobs/aggregator.py`.
- Do NOT add new JavaScript libraries other than DOMPurify.

## Signal completion

```bash
iw step-done CR-00006 S05 --summary "Added DOMPurify CDN; code_qa_panel now renders per-token sanitized markdown; replaced green banner with neutral Last-Run link in code_job_report.html; added Jobs link to sidebar; created pages/project/jobs.html, pages/project/job_detail.html, fragments/jobs_table.html"
```

If you hit a blocker (e.g., existing route path for research artifact is different):

```bash
iw step-fail CR-00006 S05 --reason "<what failed>"
```
