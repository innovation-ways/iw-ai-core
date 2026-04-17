# CR-00006 S06 — Frontend Review

## Input Files

- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`
- `ai-dev/active/CR-00006/prompts/CR-00006_S05_Frontend_prompt.md`
- `dashboard/templates/base.html` (modified)
- `dashboard/templates/fragments/code_qa_panel.html` (modified)
- `dashboard/templates/fragments/code_job_report.html` (rewritten)
- `dashboard/templates/fragments/nav_projects.html` (modified)
- `dashboard/templates/pages/project/jobs.html` (new)
- `dashboard/templates/pages/project/job_detail.html` (new)
- `dashboard/templates/fragments/jobs_table.html` (new)

## Output Files

- `ai-dev/work/CR-00006/reports/S06_frontend_review.md`

## Context

**Work item**: CR-00006
**Step**: S06
**Agent**: frontend-review

Review the frontend implementation for correctness, accessibility, and security (XSS in the markdown pipeline).

## Review Checklist

### DOMPurify + marked integration (`base.html` + `code_qa_panel.html`)

- [ ] `base.html` loads DOMPurify from a **pinned version** CDN URL (not a floating major tag).
- [ ] DOMPurify script tag is placed AFTER `marked.js` so the global is available when `qaRenderMarkdown` runs.
- [ ] `code_qa_panel.html` defines a `qaRenderMarkdown(raw)` helper that:
  - Falls back gracefully if `marked` or `DOMPurify` is undefined.
  - Passes `{ gfm: true, breaks: true }` (or equivalent) to `marked.parse`.
  - Uses `DOMPurify.sanitize(html, { USE_PROFILES: { html: true }, ADD_ATTR: ['target'] })`.
  - Installs an `afterSanitizeAttributes` hook that sets `rel="noopener noreferrer"` on `<a target="_blank">` links, and removes the hook after `sanitize()` to avoid leaks across calls.
- [ ] On each `token` SSE frame, the handler sets `responseSpan.innerHTML = qaRenderMarkdown(fullResponse)` — NOT `textContent`, NOT `insertAdjacentHTML`.
- [ ] On the `done` frame, one final `innerHTML` assignment runs (using `data.full_response || fullResponse`).
- [ ] The user bubble (`qaAppendUserBubble`) uses `textContent` (not `innerHTML`) — user input is never treated as markdown.
- [ ] Error bubbles keep their existing `textContent` path.
- [ ] `qaAppendAssistantBubble()` returns a `<div>` (block-level) with class `qa-response-markdown` so headings/lists render correctly.
- [ ] A `<style>` block exists for code blocks, lists, tables, headings inside `.qa-response-markdown`.

### XSS vector spot-check

- [ ] Manually trace the flow for an assistant response containing `<script>alert(1)</script>` — the path `fullResponse → marked.parse → DOMPurify.sanitize → innerHTML`. Confirm DOMPurify strips `<script>` (it does by default under `USE_PROFILES.html`).
- [ ] Confirm `<img src=x onerror=alert(1)>` would have `onerror` stripped.
- [ ] Confirm the `target="_blank"` hook sets `rel="noopener noreferrer"` correctly by reading the hook code.

### Banner replacement (`code_job_report.html`)

- [ ] The green (`bg-green-50`) styling is gone.
- [ ] The new fragment shows a compact single-line "Last run" summary.
- [ ] The fragment contains a link to `/project/{{ current_project.id }}/jobs/code_mapping/{{ last_completed_job.id }}`.
- [ ] File still exists (not deleted) — the include at `project_code.html:78` keeps working.

### Sidebar (`nav_projects.html`)

- [ ] A new tuple `('/project/' ~ project.id ~ '/jobs', 'Jobs')` is inserted **after** `History` and **before** `Tests`.
- [ ] No other links were touched, reordered, or removed.

### Jobs page (`pages/project/jobs.html`)

- [ ] Extends `base.html`.
- [ ] `<h1>` says "Jobs".
- [ ] Filter form uses `method="get"` (not htmx) so the URL is shareable.
- [ ] Type and Status filters accept multiple values (checkboxes or `<select multiple>`).
- [ ] Table shows all 8 columns: ID, Type, Title, Status, Started at, Finished at, Duration, Triggered by.
- [ ] Each row is clickable and links to `/project/{{ current_project.id }}/jobs/{{ row.job_type.value }}/{{ row.job_id }}`.
- [ ] Pagination shows current page and total, with prev/next links preserving filter params.
- [ ] Uses `status_badge` component for status (consistent with History page).
- [ ] Empty-state message when `total == 0`.

### Jobs fragment (`fragments/jobs_table.html`)

- [ ] Does NOT extend `base.html`.
- [ ] Contains table + pagination only.
- [ ] Can be rendered standalone as an htmx response.

### Job detail (`pages/project/job_detail.html`)

- [ ] Extends `base.html`.
- [ ] Header shows `Job {{ job.job_id }} — {{ job.title }}` with status badge.
- [ ] Back link to `/project/{project_id}/jobs`.
- [ ] Summary card: Type, Status, Started, Finished, Duration, Triggered by.
- [ ] Type-specific parameters section using `{% if job.job_type.value == ... %}`.
- [ ] Artifact link per type, where applicable.
- [ ] Error section for failed jobs.
- [ ] No unsanitized rendering of any user/LLM-originated text (nothing passes through `| safe` unless it's been through `render_markdown` or is a known-safe string).

### Accessibility

- [ ] All interactive elements (filter buttons, pagination links, row links) are keyboard-accessible.
- [ ] Status badges have readable contrast in dark mode (Tailwind variables handle this — spot check).
- [ ] The Jobs sidebar link has appropriate active-state styling.
- [ ] SVG icons have `aria-hidden` or are decorative (no info loss without them).

### Cross-cutting

- [ ] No JS libraries added other than DOMPurify.
- [ ] No changes to `orch/` or `dashboard/routers/` Python files.
- [ ] No tests written in this step.
- [ ] No `console.log` statements left behind.
- [ ] No commented-out code left behind.

## Smoke test

Start the dashboard and manually verify:

```bash
make dashboard-start
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/<project_id>/jobs
playwright-cli snapshot
playwright-cli screenshot
```

Then navigate to a job detail page:

```bash
playwright-cli open http://localhost:9900/project/<project_id>/jobs/code_mapping/<job_id>
playwright-cli snapshot
```

Confirm the sidebar shows "Jobs" between History and Tests.

## Signal completion

If correct:

```bash
iw step-done CR-00006 S06 --summary "Frontend review passed: markdown pipeline is sanitized and hook-restricted, banner replaced with neutral Last-Run link, Jobs sidebar link added, Jobs list + fragment + detail templates render correctly, user input is never rendered as markdown"
```

If issues found:

```bash
iw step-fail CR-00006 S06 --reason "<CRITICAL/HIGH findings>"
```
