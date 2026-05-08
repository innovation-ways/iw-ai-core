# CR-00038 S02 — Code Review: Frontend (S01)

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy. No docker commands. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Objective

Review all changes introduced in S01 of CR-00038. Produce a findings report and, for any CRITICAL or HIGH finding, implement the fix directly in the same step.

## Input Files

- `ai-dev/active/CR-00038/CR-00038_CR_Design.md` — design reference
- `dashboard/templates/docs_library.html` — filter bar redesign + running-jobs container
- `dashboard/templates/fragments/docs_running_jobs.html` — new running-jobs strip fragment
- `dashboard/routers/docs.py` — new `docs_running_jobs` endpoint + changed `docs_generate` response
- `dashboard/static/styles.css` — any new CSS rules
- Verify `dashboard/templates/fragments/docs_generate_running.html` is deleted

## Review Checklist

### Template / htmx correctness
- [ ] `#docs-filter-form` wraps all three filter controls; each control uses `hx-include="#docs-filter-form"` so all values travel together
- [ ] `<select>` and `<input>` have appropriate `hx-trigger` values (`change` for selects, `input changed delay:300ms` for text input)
- [ ] `hx-target="#docs-grid"` and `hx-swap="innerHTML"` on all filter controls
- [ ] `#docs-running-jobs` uses `hx-trigger="load, runningJobsReload from:body"`
- [ ] Fragment `docs_running_jobs.html` does NOT extend `base.html`
- [ ] No dangling `hx-target`, `hx-include`, `aria-controls`, `aria-labelledby`, or `for` references pointing at non-existent IDs

### JavaScript correctness
- [ ] `window._docJobSources` deduplication pattern is implemented — existing EventSource for a job is closed before a new one is opened
- [ ] `clearInterval` is called on the elapsed timer when the job row is cleaned up
- [ ] `EventSource.close()` is called on completion, failure, and timeout
- [ ] `docJobCompleted` and `docJobFailed` events are dispatched on `document.body` with correct `detail` payload (`{job_id, doc_id}`)
- [ ] `runningJobsReload` event is dispatched on `document.body` to trigger strip reload
- [ ] `onerror` handler on EventSource triggers a delayed `runningJobsReload` (avoids infinite reconnect loop)
- [ ] No `navigator.clipboard` direct usage

### Backend correctness
- [ ] `docs_running_jobs` endpoint filters by `project_id` prefix to avoid cross-project leakage
- [ ] Query orders by `requested_at ASC` (oldest first)
- [ ] `docs_generate` response: `HX-Trigger` header is valid JSON with both `docJobCreated` and `runningJobsReload` keys
- [ ] Disabled button HTML is valid (no unclosed tags)
- [ ] `import json` used correctly — no import conflict with existing imports in `docs.py`
- [ ] `docs_generate_running.html` is confirmed deleted (no remaining references in Python or templates)

### Accessibility / UX
- [ ] `<select>` elements have `<label>` elements or `aria-label`
- [ ] Disabled button has `aria-label="Generation queued"` or similar
- [ ] Cancel button in job row has `aria-label`

### CSS
- [ ] If `.docs-filter-select` CSS was added to `styles.css`, it is valid CSS and appended at the end of the file (no duplicate rules)

## Output

Write `ai-dev/active/CR-00038/reports/CR-00038_S02_CodeReview_Frontend_Report.md` with:
- Findings table (severity: CRITICAL / HIGH / MEDIUM / LOW / INFO)
- For CRITICAL and HIGH: describe the fix applied

Then call:
```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00038/reports/CR-00038_S02_CodeReview_Frontend_Report.md
```
