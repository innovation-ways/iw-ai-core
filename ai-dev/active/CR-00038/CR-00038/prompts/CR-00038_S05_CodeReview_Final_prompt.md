# CR-00038 S05 — Final Cross-Agent Code Review

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Objective

Global review of all changes in CR-00038 (S01 + S03). Verify correctness, consistency, and completeness across layers.

## Input Files

- `ai-dev/active/CR-00038/CR-00038_CR_Design.md`
- `dashboard/templates/docs_library.html`
- `dashboard/templates/fragments/docs_running_jobs.html`
- `dashboard/templates/fragments/docs_card.html`
- `dashboard/routers/docs.py`
- `dashboard/static/styles.css`
- `tests/dashboard/test_docs.py`
- S02 report: `ai-dev/active/CR-00038/reports/CR-00038_S02_CodeReview_Frontend_Report.md`
- S04 report: `ai-dev/active/CR-00038/reports/CR-00038_S04_CodeReview_Tests_Report.md`

## Review Checklist

### Cross-layer consistency
- [ ] The `id` values referenced in templates match what the JS and htmx attributes target (no dangling refs)
- [ ] `HX-Trigger` event names used in Python responses match those listened for in templates (`runningJobsReload`, `docJobCreated`, `docJobCompleted`, `docJobFailed`)
- [ ] The `docs_generate_running.html` file is confirmed deleted and no Python or template code still imports/references it
- [ ] The new `GET /api/docs/running-jobs` endpoint is registered in the router (reachable from the template's `hx-get` URL)

### Completeness vs design
- [ ] AC1: Single-line filter bar (no pill buttons remain)
- [ ] AC2: All three filters combined in `hx-include="#docs-filter-form"`
- [ ] AC3: Generate click disables button + strip shows running row
- [ ] AC4: Completion removes strip row + card refreshes
- [ ] AC5: Multiple concurrent jobs each get a strip row
- [ ] AC6: Failed job shows red row briefly before disappearing

### Regression risk
- [ ] The `#docs-grid` htmx target still exists and is not affected by the filter bar changes
- [ ] The `#stale-summary` and `#docs-config-overlay` elements are still in `docs_library.html` and unaffected
- [ ] The floating action bar (export) and select mode toggle are unaffected
- [ ] Existing `docJobCompleted` handler in `docs_card.html` still fires `htmx.ajax` to refresh the card
- [ ] Research docs are not exposed in the running-jobs strip (endpoint filters non-research by project prefix only — verify query is correct)

### Security
- [ ] The `docs_running_jobs` endpoint filters strictly by `project_id` prefix — no cross-project data leakage
- [ ] No unsanitised user data interpolated into the EventSource URL or job row HTML

## Output

Write `ai-dev/active/CR-00038/reports/CR-00038_S05_CodeReview_Final_Report.md`.

Then call:
```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00038/reports/CR-00038_S05_CodeReview_Final_Report.md
```
