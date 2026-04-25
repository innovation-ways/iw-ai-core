# CR-00022_S14_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S13 (frontend-impl — Phase E UI)
**Review Step**: S14
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S13 report
- `dashboard/templates/pages/project/oss.html`
- `dashboard/templates/fragments/oss_table.html`, `oss_finding_modal.html`, `oss_apply_all_safe_modal.html`, `oss_accept_modal.html`
- `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S14_CodeReview_report.md`

## Review Checklist

### 1. Per-row Re-run icon

- Icon present on every row?
- Click triggers `/oss/recheck/{check_id}`?
- Visual feedback (spinner on icon while running)?
- Row patches in place after SSE row-update or sync response?
- Keyboard accessible?

### 2. Mark-accepted form

- Reason input requires ≥ 5 chars (HTML `minlength` attribute)?
- Confirm POSTs to `/oss/accept/{check_id}` with `{finding_hash, reason}`?
- On success: row moves to Accepted group, modal closes, toast shows?
- On failure: error displayed, modal stays open?
- finding_hash is read from the `data-finding-hash` attribute on the row, not recomputed client-side?

### 3. Apply-all-safe preview modal

- POST `/oss/apply-all-safe/preview` triggered on button click?
- Modal lists every recipe with target files?
- Recipe-level checkbox controls inclusion?
- Per-file checkboxes documented as informational (per S13's decision)?
- "Writes to your working tree only. No branch is created." copy visible?
- Confirm POST sends `{check_ids: [...]}` with only checked recipes?
- After apply, table refreshes via SSE row updates (no full reload)?

### 4. Modal accessibility

- Both new modals: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`?
- Focus trap on each?
- ESC closes?
- Backdrop click closes?
- Visible focus ring?

### 5. Tailwind / JS lint

- `make css` produced an updated `styles.css`?
- `make lint` passes?
- No dynamic class construction that breaks JIT?

### 6. UX consistency

- Toasts use the existing dashboard pattern (HX-Trigger or vanilla)?
- Button styles match the rest of the dashboard (primary / secondary)?
- Spacing follows the existing scale?

### 7. Server-side defensiveness re-check

S09 was supposed to validate that every check_id in the apply-all-safe body has `auto_apply_safe=True`. Confirm the UI cannot bypass this (e.g., DOM tampering submits arbitrary IDs). Server should still 422 / 403 in that case.

## Output Report

Findings list, severity, file:line, verdict. End with `iw step-done` / `iw step-fail`.
