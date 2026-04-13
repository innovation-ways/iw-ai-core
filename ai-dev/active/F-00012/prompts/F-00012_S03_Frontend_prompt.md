# F-00012_S03_Frontend_prompt

**Work Item**: F-00012 — Project-Level Documentation System — AI Generation (Phase 2)
**Step**: S03
**Agent**: Frontend

---

## Input Files

- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — Design document
- `ai-dev/work/F-00012/reports/F-00012_S01_Backend_report.md` — S01 report
- `ai-dev/work/F-00012/reports/F-00012_S02_API_report.md` — S02 report
- `dashboard/templates/fragments/docs_card.html` — Existing doc card (from F-00011)
- `dashboard/templates/docs_detail.html` — Existing detail page (from F-00011)
- `dashboard/CLAUDE.md` — Dashboard conventions

## Output Files

- `dashboard/templates/fragments/docs_card.html` — Modified: add Generate button
- `dashboard/templates/docs_detail.html` — Modified: add Regenerate button + SSE progress + job history panel
- `dashboard/templates/fragments/docs_job_status.html` — New: SSE-driven progress indicator
- `dashboard/templates/fragments/docs_job_history.html` — New: job history list

## Context

You are implementing the frontend for **F-00012: AI Documentation Generation**. This step adds the Generate/Regenerate controls and live progress feedback to the existing Phase 1 UI. Every component must integrate seamlessly with the existing Tailwind + htmx patterns established in F-00011.

## Requirements

### 1. Doc Card — Generate Button

Modify `docs_card.html` to add a "Generate" button in the card actions area:

- Appears only when `doc.status == "planned"` or `doc.content is None` (no content yet)
- For docs that already have content: show "Regenerate" (smaller, secondary style)
- Button: `hx-post="/api/project/{project_id}/docs/{doc.slug}/generate"`, `hx-target="#doc-card-{doc.slug}"`, `hx-swap="outerHTML"`
- While job is running (detected via htmx event `docJobCreated`): replace button with animated spinner + "Generating..." text
- On `completed` event (from SSE): trigger a card refresh (`hx-get` the card fragment again to show updated status badge and "Regenerate" button)
- Generating state: animate with pulsing ring (`animate-pulse`, border ring)

**Last generation failed indicator:** If `doc` has a recent failed job, show an orange warning badge: "Last run failed" with a tooltip showing the error message (truncated to 80 chars).

### 2. Document Detail Page — Regenerate Button + Progress

Modify `docs_detail.html`:

**Regenerate button** (in the right sidebar action area):
- `hx-post="/api/project/{project_id}/docs/{doc_id}/generate"`, `hx-target="#generation-progress"`, `hx-swap="innerHTML"`
- Disabled while a job is already running (check `doc` context for running job)

**Generation progress section** (`id="generation-progress"`):
- Initially empty; populated by htmx after "Generate"/"Regenerate" is clicked
- `docs_job_status.html` is swapped in with the job_id
- Uses SSE: `hx-ext="sse"`, `sse-connect="/api/project/{id}/docs/jobs/{job_id}/stream"`, `sse-swap="message"` targeting the progress content area
- Shows: spinner icon + "Generating documentation..." + elapsed time counter (JavaScript `setInterval` updating every second)
- On completion event: replace with success banner "Documentation updated — refreshing..." then `htmx.trigger` a reload of the main doc content area
- On failure event: replace with error banner showing the error message

### 3. Job Status Fragment (`docs_job_status.html`)

The SSE-connected progress indicator:

```
┌─────────────────────────────────────────────┐
│  ⟳ Generating documentation...              │
│  Skill: iw-doc-generator  ·  0:42 elapsed   │
│  [━━━━━━░░░░░░░░░░] indeterminate progress   │
└─────────────────────────────────────────────┘
```

- Indeterminate progress bar (animated CSS gradient sweep)
- Elapsed time counter (JavaScript, counts up from 0)
- Skill name shown when available (from SSE status event payload)
- Cancel button: `DELETE /api/project/{id}/docs/jobs/{job_id}` (if supported — optional for Phase 2)

### 4. Job History Panel (`docs_job_history.html`)

Loaded via htmx into the detail page sidebar when user clicks "View History" button. Shows last 10 jobs:

```
Job History
┌──────────────────────────────────────────────┐
│ ● completed   iw-doc-generator   2m 14s      │
│   Apr 13, 2026 at 14:32                      │
├──────────────────────────────────────────────┤
│ ✗ failed      iw-doc-generator   0m 8s       │
│   "Source file not found: docs/auth.md"      │
│   Apr 12, 2026 at 09:15                      │
├──────────────────────────────────────────────┤
│ ● completed   iw-doc-system      4m 01s      │
│   Apr 10, 2026 at 11:47                      │
└──────────────────────────────────────────────┘
```

Status dot colors:
- `completed`: green dot
- `failed`: red ✗
- `running`: animated blue spinner
- `queued`: gray clock icon

Error message: shown in red italic, truncated with `line-clamp-2` (expandable on click).

### 5. Library Page Card Refresh on Completion

When a `DocGenerationJob` completes (detected via the htmx `docJobCreated` custom event and subsequent SSE `completed` event):
- Refresh the specific card by polling `GET /api/project/{id}/docs/{doc_id}/card` (add this route in docs.py returning a single card fragment)
- The refreshed card should show: updated status badge, updated "last generated" time, version number
- Use `htmx.ajax('GET', url, {target: '#doc-card-{slug}', swap: 'outerHTML'})` triggered from JavaScript on SSE completion event

## Project Conventions

- Read `dashboard/CLAUDE.md` before modifying any template
- Use the same Tailwind classes and patterns as existing templates — no new CSS
- SSE pattern: follow `dashboard/templates/` existing htmx-sse usage exactly
- All interactive elements must have `aria-label` or `title` attributes for accessibility
- Animate with Tailwind only (`animate-spin`, `animate-pulse`, `transition-all`) — no custom keyframes

## Test Verification (NON-NEGOTIABLE)

1. `make quality` — ruff + mypy pass
2. Describe in report: manually verified that clicking "Generate" shows spinner, SSE stream updates progress, completion refreshes the card

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "F-00012",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/docs_card.html",
    "dashboard/templates/docs_detail.html",
    "dashboard/templates/fragments/docs_job_status.html",
    "dashboard/templates/fragments/docs_job_history.html"
  ],
  "tests_passed": true,
  "test_summary": "quality checks passed",
  "blockers": [],
  "notes": ""
}
```
