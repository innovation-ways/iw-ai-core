# CR-00006 S05 — Frontend Implementation Report

## What was done

Implemented all UI components for the Jobs feature and sanitized markdown rendering in the Q&A panel.

## Files Changed

### Modified Files

- **`dashboard/templates/base.html`** — Added DOMPurify 3.1.7 CDN script immediately after marked.js (line 78).
- **`dashboard/templates/fragments/code_qa_panel.html`** — Added `qaRenderMarkdown()` helper using marked + DOMPurify, changed assistant bubble inner element from `<span>` to `<div class="qa-response-markdown ...">`, replaced `textContent += token` with `innerHTML = qaRenderMarkdown(fullResponse)` for per-token live rendering, added `<style>` block for markdown typography.
- **`dashboard/templates/fragments/code_job_report.html`** — Replaced green success banner with neutral single-line "Last run" summary (files · chunks · View → link to Jobs detail page).
- **`dashboard/templates/fragments/nav_projects.html`** — Added `('/project/' ~ project.id ~ '/jobs', 'Jobs')` tuple immediately after Queue link.

### New Files

- **`dashboard/templates/pages/project/jobs.html`** — Full page extending base.html: filter form (type/status checkboxes, date range), results count, includes `fragments/jobs_table.html`, pagination. Uses `fmt_duration` and `type_chip` macros.
- **`dashboard/templates/fragments/jobs_table.html`** — Sortable table (thead + tbody + pagination), used by htmx endpoint. Does NOT extend base.html. Includes `fmt_duration` and `type_chip` macros. Columns: ID (link), Type (chip), Title, Status (badge), Started (timeago), Finished (localdt), Duration.
- **`dashboard/templates/pages/project/job_detail.html`** — Full page: back link, header with status badge, summary card (type/status/triggered_by/started/finished/duration), type-specific parameters section with artifact links, error block for failed jobs.

## Test Results

```bash
uv run python -c "from dashboard.app import create_app; app = create_app(); print('app built ok')"
# Output: app built ok
```

## Issues or Observations

- The `jobs_table.html` uses `{% include "fragments/jobs_table.html" %}` from within `jobs.html` — since it's a fragment, the `{% from ... %}` imports work as expected.
- Artifact links in `job_detail.html` for `doc_generation` use `/project/{id}/docs/{doc_id}` (line 65 of docs.py), `batch_execution` uses `/project/{id}/batches/{batch_id}` (line 130+), `research` uses `/project/{id}/research/{doc_id}` (line 79 of research.py).
- The `code_qa_panel.html` Q&A streaming logic preserves all history truncation and error bubble behaviour; only the rendering path changed.
