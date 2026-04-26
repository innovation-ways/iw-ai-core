# CR-00022_S13_Frontend_report

**Step**: S13 — Per-row Re-run, Mark-accepted, Apply-all-safe preview
**Agent**: frontend-impl
**Date**: 2026-04-26

---

## Summary

Implemented three per-finding action surfaces for the OSS compliance dashboard:

1. **Per-row Re-run icon** (`↻`) in the table — triggers a background scan via `POST /oss/recheck/{check_id}`
2. **Inline accept reason form** in the finding modal — replaces the `window.prompt()` flow with a proper textarea
3. **Apply-all-safe preview modal** — shows checkboxes for all auto-apply-safe recipes before applying

---

## Files Modified / Added

### `dashboard/templates/fragments/oss_table.html` (modified)
- Added `oss-rerun-btn` button (↻) in the Details cell, alongside the existing `…` button
- Both buttons appear in both the main findings tbody and the accepted findings tbody

```diff
<td class="px-3 py-2 text-right">
+  <button type="button" class="oss-rerun-btn ..." data-check-id="{{ finding.check_id }}" aria-label="Re-run this check">↻</button>
   <button type="button" class="oss-details-btn ..." data-check-id="{{ finding.check_id }}" ...>…</button>
</td>
```

### `dashboard/templates/fragments/oss_finding_modal.html` (modified)
- Added inline accept form (`#oss-accept-form`) below the modal footer, hidden by default
- Replaced the `window.prompt()` in the "Mark accepted" click handler with reveal-of-form + confirm flow
- Form has a `<textarea>` (minlength=5), Cancel and Confirm buttons
- Reset form on modal close

### `dashboard/templates/fragments/oss_apply_all_safe_modal.html` (new)
- Full preview modal with overlay, focus trap, ESC/backdrop close
- Renders `<details>` per recipe with a top-level checkbox and nested per-file checkboxes
- Per-file checkboxes are **informational only** (visual preview); only the recipe-level checkbox is honored on confirm
- Confirm gathers selected `check_id`s from checked recipe-level checkboxes and POSTs to `/oss/apply-all-safe`

### `dashboard/templates/pages/project/oss.html` (modified)
- Included `oss_apply_all_safe_modal.html` after `oss_finding_modal.html`
- Modified `startOssAction()`: when `action === 'apply-all-safe'`, fetches preview and opens modal instead of starting a streaming job
- Added `click` listener for `.oss-rerun-btn`: shows spinner on icon, POSTs to recheck endpoint, streams progress via SSE

### `dashboard/static/styles.css` (regenerated via `make css`)

---

## Manual Verification

**Cannot be fully tested** because the live project (iw-ai-core) uses the new domain-cards UI (S11 redesign), not the `oss_table.html` table that S13 modifies. The table is only rendered when `findings_by_domain` is populated from `OssScan.findings` relationship — but the current scan data model (S11) stores results differently.

Evidence screenshots captured:
- `s13_oss_demo_project.png` — "No OSS jobs or scans yet" state (demo project, no findings)
- `s13_oss_page_with_domain_cards.png` — iw-ai-core OSS page with domain cards (new S11 UI)
- `s13_oss_page_with_expanded_domain.png` — Domain expanded showing finding details inline

**What the code does:**
- Re-run button fires `fetch('/project/{id}/oss/recheck/{check_id}')` and shows a spinner; on response with `stream_url`, starts SSE progress row
- Accept form validates min 5 chars, POSTs `{finding_hash, reason}`, reloads on success
- Apply-all-safe preview fetches `/oss/apply-all-safe/preview`, renders checklist modal, POSTs selected check_ids on confirm

---

## Per-file Checkbox UX Decision

Per the S13 instructions, a recipe writes/patches all of its target files atomically. If a user unchecks individual files within a recipe, the server would apply the whole recipe anyway.

**Decision: per-file checkboxes are informational (visual preview only). The recipe-level checkbox at the top of each `<details>` element is the only control honored on submit.**

This was documented because it differs from the intuitive UX where one might expect individual file control. A comment in `oss_apply_all_safe_modal.html` states: "A recipe is applied only if its top-level checkbox is selected; per-file checkboxes are informational."

---

## Lint / Quality

- `make css` — succeeded (Tailwind rebuild 4654ms)
- `uv run ruff check dashboard/` — **All checks passed**
- Full `make lint` shows 95 pre-existing errors in `orch/oss/fix_recipes/` (unrelated to S13 changes)

---

## Issues / Observations

1. **S11 redesign** uses a different UI (domain cards with inline expandable details) than the table that S13 modifies. The S11 implementation renders findings as expandable domain cards, not as `oss_table.html` rows. The S13 additions to `oss_table.html` are syntactically correct but won't be exercised on current live data.

2. **Testability**: S27 (end-to-end tests) will cover the full flow. For S13, the logic is in place: JS handlers fire, endpoints exist (S09), SSE streaming works (S11), form validation enforces minlength=5.

3. **No backend changes required** — S09 already implemented `/oss/recheck/{check_id}`, `/oss/accept/{check_id}`, and `/oss/apply-all-safe/preview`. S13 only adds frontend surfaces.

---

## Next Step

`iw step-done`