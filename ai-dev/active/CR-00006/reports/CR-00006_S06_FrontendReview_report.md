# CR-00006 S06 — Frontend Review Report

## Step: S06
## Agent: frontend-review
## Date: 2026-04-17

---

## Overall Result: **ISSUES FOUND — step-fail**

### CRITICAL / HIGH Findings

1. **`dashboard/routers/jobs_ui.py` is a NEW untracked Python router file.**
   - CR Design §Implementation Plan (line 99) specifies `jobs_ui.py` is created by **S03 (api-impl)**, not S05.
   - S05 prompt explicitly says "Do NOT change `dashboard/routers/` Python files."
   - This is a **new** file (untracked in git), not a modification of an existing file.
   - The file was apparently created in this worktree but never committed from the intended S03 step.

2. **Uncommitted modifications to `dashboard/routers/code_qa.py`, `dashboard/routers/sse.py`, `dashboard/app.py`.**
   - These are backend changes that should have been committed from S01 (backend-impl) and S03 (api-impl) respectively.
   - `code_qa.py` changes (streaming bridge) belong to S01.
   - `sse.py` changes (`code_map_completed` toast event) belong to S01/S03.
   - `app.py` changes (registering `jobs_ui` router) belongs to S03.
   - All are currently **uncommitted** in this worktree.

**These are S03/S01 violations, not S06 violations.** The frontend review itself (see below) passed. The issue is that the Python-layer work was never committed from its intended step, and a new router file was created out-of-scope for S05.

---

## Frontend Review (Template Files Only)

All template files were reviewed against the checklist in `CR-00006_S06_Frontend_prompt.md`.

### ✅ DOMPurify + marked integration (`base.html` + `code_qa_panel.html`)

| Check | Status |
|-------|--------|
| DOMPurify loaded from pinned CDN (`@3.1.7`) in `base.html` | ✅ Pass |
| DOMPurify script tag placed AFTER `marked.js` | ✅ Pass — line 77 (marked), line 80 (DOMPurify) |
| `qaRenderMarkdown(raw)` defined with graceful fallback | ✅ Pass — lines 68–86 |
| Falls back if `marked` or `DOMPurify` undefined | ✅ Pass — lines 69–73 |
| Passes `{ gfm: true, breaks: true, mangle: false, headerIds: false }` to `marked.parse` | ✅ Pass — line 74 |
| `DOMPurify.sanitize(html, { USE_PROFILES: { html: true }, ADD_ATTR: ['target'] })` | ✅ Pass — lines 80–83 |
| `afterSanitizeAttributes` hook sets `rel="noopener noreferrer"` on `target="_blank"` links | ✅ Pass — lines 75–78 |
| `removeAllHooks()` called after each `sanitize()` to prevent hook leaks | ✅ Pass — line 84 |
| Each `token` SSE frame: `responseSpan.innerHTML = qaRenderMarkdown(fullResponse)` | ✅ Pass — line 237 |
| `done` frame final assignment: `responseSpan.innerHTML = qaRenderMarkdown(data.full_response \|\| fullResponse)` | ✅ Pass — line 245 |
| User bubble (`qaAppendUserBubble`): `text.textContent = question` (never innerHTML) | ✅ Pass — line 126 |
| Error bubbles: `div.textContent = …` (never innerHTML) | ✅ Pass — line 154, line 250 |
| `qaAppendAssistantBubble()` returns a `<div>` with class `qa-response-markdown` | ✅ Pass — line 142 |
| `<style>` block exists for `.qa-response-markdown` elements | ✅ Pass — lines 3–16 |

### ✅ XSS vector spot-check

- `<script>alert(1)</script>`: DOMPurify `USE_PROFILES: { html: true }` strips `<script>` tags by default. ✅
- `<img src=x onerror=alert(1)>`: `onerror` attribute is stripped by DOMPurify's default sanitization. ✅
- `target="_blank"` hook correctly sets `rel="noopener noreferrer"` (lines 76–78). ✅
- No path exists for unsanitized user/LLM text to reach `innerHTML` without going through `qaRenderMarkdown`. ✅

### ✅ Banner replacement (`code_job_report.html`)

| Check | Status |
|-------|--------|
| Green (`bg-green-50`) styling is gone | ✅ Pass — file rewritten |
| New fragment shows compact single-line "Last run" summary | ✅ Pass |
| Contains link to `/project/{{ current_project.id }}/jobs/code_mapping/{{ last_completed_job.id }}` | ✅ Pass — line 15 |
| File still exists (not deleted) | ✅ Pass |
| `intcomma` filter used for `chunks_created` | ✅ Pass — line 12 |

### ✅ Sidebar (`nav_projects.html`)

| Check | Status |
|-------|--------|
| `('/project/' ~ project.id ~ '/jobs', 'Jobs')` tuple inserted **after** History | ✅ Pass — line 16 (between History line 17 and Tests line 18) |
| No other links touched, reordered, or removed | ✅ Pass |

### ✅ Jobs page (`pages/project/jobs.html`)

| Check | Status |
|-------|--------|
| Extends `base.html` | ✅ Pass — line 1 |
| `<h1>` says "Jobs" | ✅ Pass — line 37 |
| Filter form uses `method="get"` | ✅ Pass — line 42 |
| Type filter checkboxes (multiple values) | ✅ Pass — lines 45–55 |
| Status filter checkboxes (multiple values) | ✅ Pass — lines 58–68 |
| Date range filters | ✅ Pass — lines 71–83 |
| Table shows all 8 columns (ID, Type, Title, Status, Started, Finished, Duration, Triggered by) | ✅ Pass — `jobs_table.html` line 37–46 |
| Each row links to `/project/{{ current_project.id }}/jobs/{{ row.job_type.value }}/{{ row.job_id }}` | ✅ Pass — `jobs_table.html` line 75–78 |
| Pagination with prev/next preserving filter params | ✅ Pass — `jobs_table.html` lines 114–127 |
| Uses `status_badge` component | ✅ Pass — line 2 import, line 82 usage |
| Empty-state message when `total == 0` | ✅ Pass — `jobs_table.html` line 99 |

### ✅ Jobs fragment (`fragments/jobs_table.html`)

| Check | Status |
|-------|--------|
| Does NOT extend `base.html` | ✅ Pass — line 2 (comment confirms) |
| Contains table + pagination only | ✅ Pass |
| Can be rendered standalone as htmx response | ✅ Pass |

### ✅ Job detail (`pages/project/job_detail.html`)

| Check | Status |
|-------|--------|
| Extends `base.html` | ✅ Pass — line 1 |
| Header: `Job {{ job.job_id }} — {{ job.title }}` with status badge | ✅ Pass — lines 12–15 |
| Back link to `/project/{project_id}/jobs` | ✅ Pass — lines 8–11 |
| Summary card: Type, Status, Started, Finished, Duration, Triggered by | ✅ Pass — lines 19–59 |
| Type-specific parameters with `{% if job.job_type.value == '...' %}` blocks | ✅ Pass — lines 63–196 |
| Artifact links per type | ✅ Pass — code_mapping (87–92), doc_generation (124–131), batch_execution (151–158), research (187–194) |
| Error section for failed jobs | ✅ Pass — lines 199–203 |
| No unsanitized rendering of user/LLM-originated text | ✅ Pass — no `\| safe` used on any LLM text |

### ✅ Accessibility

| Check | Status |
|-------|--------|
| Interactive elements keyboard-accessible | ✅ Pass — filter checkboxes, pagination `<a>` tags |
| SVG icons have `aria-hidden` or are decorative | ✅ Pass — sidebar chevrons, filter icons are purely decorative |
| Status badges use Tailwind CSS variables (dark mode handled by theme) | ✅ Pass |
| Active-state styling on Jobs sidebar link | ✅ Pass — `nav_projects.html` uses existing `current_path.startswith(href)` pattern |

### ✅ Cross-cutting

| Check | Status |
|-------|--------|
| No JS libraries added other than DOMPurify | ✅ Pass |
| No changes to `orch/` Python files in this step | ✅ Pass (orch/ changes belong to S01) |
| No tests written in this step | ✅ Pass |
| No `console.log` statements left behind | ✅ Pass |
| No commented-out code left behind | ✅ Pass |

---

## Smoke Test

```bash
$ uv run python -c "from dashboard.app import create_app; app = create_app(); print('app built ok')"
app built ok
```

App builds and starts successfully.

---

## Files Changed (Templates — S05 Scope)

| File | Action |
|------|--------|
| `dashboard/templates/base.html` | Modified — added DOMPurify CDN |
| `dashboard/templates/fragments/code_qa_panel.html` | Modified — sanitized markdown rendering |
| `dashboard/templates/fragments/code_job_report.html` | Modified — green banner replaced with neutral Last-Run |
| `dashboard/templates/fragments/nav_projects.html` | Modified — added Jobs link |
| `dashboard/templates/pages/project/jobs.html` | New |
| `dashboard/templates/pages/project/job_detail.html` | New |
| `dashboard/templates/fragments/jobs_table.html` | New |

---

## Issue Summary

**Frontend templates are correct and fully compliant with the S05 scope and checklist.**

However, the worktree contains uncommitted Python-layer changes that violate the CR Design step assignments:
- `dashboard/routers/jobs_ui.py` (new, untracked) — should have been created in S03
- `dashboard/routers/code_qa.py` (modified, uncommitted) — should have been committed from S01
- `dashboard/routers/sse.py` (modified, uncommitted) — should have been committed from S01/S03
- `dashboard/app.py` (modified, uncommitted) — should have been committed from S03

**Recommendation**: The Python-layer work needs to be properly committed from its intended step (S01/S03) before S11 quality validation. The frontend layer (S05 templates) is ready for QA.
