# CR-00022_S12_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S11 (frontend-impl — table + modal + SSE)
**Review Step**: S12
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S11 report
- `dashboard/templates/pages/project/oss.html`
- `dashboard/templates/fragments/oss_table.html`, `oss_finding_modal.html`
- `dashboard/routers/oss.py` (oss_page changes)
- `dashboard/static/styles.css` (regenerated)

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S12_CodeReview_report.md`

## Review Checklist

### 1. Layout matches design

- Page header + stale banner present?
- Action row has only `Scan` and `Apply all safe` (no Prepare/Publish)?
- Filter chips include MUST/SHOULD/INFO + status filter, with default = failing/human-required?
- Table columns: Group | Test | Type | Status | Details — in that order?
- Each row has `…` button in Details column?
- Domain headers collapse via Click; chevron rotates?
- Accepted group rendered separately at bottom?

### 2. Modal correctness

- Sections present in this order: What this test checks, How it tests, Risk if you ship anyway, Evidence (when present), How to fix, Preview (when applicable), References (when present)?
- Footer actions: Apply (only when `auto_apply_safe` AND status≠pass), Re-run check, Mark accepted, Close?
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` set?
- ESC closes; backdrop click closes?
- Focus trap implemented (Tab cycles within modal; Shift+Tab too)?
- First focusable element receives focus on open?
- No emoji?

### 3. SSE row-level updates

- `window.location.reload()` removed?
- `row-update` event listener added?
- Row patched in-place by `id="row-<check_id>"`?
- Header pill updated without reload?
- Falls back gracefully if SSE drops?

### 4. Tailwind / JS lint

- `make css` regenerated `styles.css`?
- No dynamic class construction (`'severity-' + sev` is OK as a string template; `'severity-' + dynamicVar` with no allowlist is NOT — verify the dynamic part is from a finite enum)?
- `make lint` passes (`node --check` on JS)?

### 5. Accessibility

- Severity color + text label (color-not-only)?
- Domain headers keyboard-operable?
- Filter chips have `aria-pressed`?
- Visible focus ring on all interactive elements?
- Modal traps focus correctly?

### 6. Catalog wiring

- `oss_page` route passes `catalog` and `accepted_findings` to template?
- Modal references `catalog[check_id].what_it_checks` etc., not hardcoded strings?
- If a check is missing from the catalog, the template fails loudly (not silently empty) — design intent: completeness test prevents this in CI, but template should still error rather than render blanks?

### 7. No regressions

- Existing scan flow still works (button → SSE → results)?
- Stale banner still renders?
- Verdict pill still renders?
- Stat tiles still render with the new "MUST failures present" / "Compliance gate clear" copy (no "Publish blocked" leftover)?

### 8. Conventions

- Fragments don't extend `base.html`?
- Routes still thin (no template logic in handlers)?
- No leftover references to `oss_domain_card.html` (S19 will delete; check for include statements in the new templates)?

### 9. Visual verification

Browse to `/project/iw-ai-core/oss` and confirm the screenshot in S11's report matches reality. Take your own screenshot for the review report.

## Output Report

Findings list, severity, file:line, verdict. End with `iw step-done` / `iw step-fail`.
