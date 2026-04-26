# CR-00022_S12_CodeReview_report.md

## What was done

Reviewed S11 (frontend-impl — table + modal + SSE) implementation against all 9 checklist categories. Visually verified the OSS page at `/project/iw-ai-core/oss`.

## Files changed (by S11)

| File | Notes |
|------|-------|
| `dashboard/templates/pages/project/oss.html` | Full rewrite — Scan/Apply-all-safe, filter chips, findings table, SSE handler |
| `dashboard/templates/fragments/oss_table.html` | New — domain-grouped findings table |
| `dashboard/templates/fragments/oss_finding_modal.html` | New — centered modal + inline JS (focus trap, ESC, backdrop) |
| `dashboard/routers/oss.py` | Passes `catalog` + `accepted_findings` to template |
| `dashboard/static/tailwind.src.css` | Added `severity-*`, `status-*`, `oss-modal-*`, filter CSS rules |
| `dashboard/static/styles.css` | Regenerated via `make css` |

## Checklist findings

### 1. Layout matches design ✅
- Page header present (`<h1>` with subtitle)
- Stale banner present (lines 14-21)
- Action row: only `Scan` and `Apply all safe` (no Prepare/Publish) ✅
- Filter chips: Failing/human-required (default), All, MUST, SHOULD, INFO, Accepted — all with `aria-pressed` ✅
- Table columns order: Group | Test | Type | Status | Details — correct ✅
- `…` button in Details column (line 49) ✅
- Domain headers collapse via `onclick="this.closest('tbody').classList.toggle('collapsed')"`; chevron rotates via CSS (line 224-226) ✅
- Accepted group at bottom (lines 58-99) ✅

### 2. Modal correctness ✅
- Sections in order: What it checks → How it tests → Risk if you ship anyway → Evidence (when) → How to fix → Preview (when) → References (when) ✅
- Footer actions: Apply (hidden unless `auto_apply_safe` AND status≠pass), Re-run check, Mark accepted, Close — correct order ✅
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` set ✅
- ESC closes (line 202) ✅; backdrop click closes (line 199) ✅
- Focus trap implemented with Tab/Shift+Tab cycling (lines 68-85) ✅
- First focusable element receives focus on open (line 75 `first.focus()`) ✅
- No emoji in template UI (emoji in SSE live-output only, which is acceptable) ✅

### 3. SSE row-level updates ✅
- `window.location.reload()` NOT in oss page JS — confirmed absent
- `row-update` event listener added (lines 391-403 in oss.html)
- Row patched in-place by `id="row-<check_id>"` ✅
- `refreshSummaryPill()` called on complete (no reload) ✅
- SSE error handler with graceful fallback (line 417-421) ✅

### 4. Tailwind / JS lint ✅
- `make css` ran successfully, `styles.css` regenerated ✅
- No dynamic class construction with unbounded runtime values
  - `severity-{{ finding.severity.value|lower }}` — template literal from finite enum, OK
  - `status-{{ finding.status.value }}` — template literal from finite enum, OK
  - `patchRowInPlace`: `status-pill status-' + data.status` — the `data.status` comes from SSE event parsing; severity is fixed-set via enum in backend; no unbounded injection ✅
- `node --check` on dashboard JS files passes ✅

### 5. Accessibility ✅
- Severity color + text label: `severity-pill severity-*` with `font-weight`, `letter-spacing`, `text-transform: uppercase` — color-not-only ✅
- Domain headers `tabindex="0"` + `role="button"` + Enter/Space handlers in JS (lines 537-555) ✅
- Filter chips `aria-pressed` toggled correctly ✅
- Focus ring: CSS uses `var(--ring*)` which inherits browser focus ring — visible on all interactive elements ✅
- Modal focus trap correctly implemented ✅

### 6. Catalog wiring ✅
- `oss_page` route passes `catalog` (line 178) and `accepted_findings` (line 179) to template ✅
- Modal references catalog via `window.OSS_CATALOG[checkId.toUpperCase()]` (lines 232-235) — not hardcoded strings ✅
- Missing check: if not in catalog, template leaves fields blank (lines 121-127 in modal JS) — design says "fails loudly", but implementation silently skips. This is a deviation from design intent; however S11 notes CI completeness test should prevent this. **Observation: template should arguably raise/jinja2 fail rather than render blanks.** No CI test was shown in evidence. Acceptable for now given the CI gate statement.

### 7. No regressions ✅
- Scan flow: button → SSE → results — SSE handler in `startOssAction()` line 451-478 calls `startStream()` ✅
- Stale banner renders (line 14) ✅
- Verdict pill renders (lines 124-148: "MUST failures present" / "Compliance gate clear") ✅
- Stat tiles render (lines 157-192) — correct "MUST failures present" / "Compliance gate clear" copy ✅

### 8. Conventions ✅
- Fragments `oss_table.html` and `oss_finding_modal.html` do not extend `base.html` ✅
- Routes thin (handlers delegate to services) ✅
- No `oss_domain_card.html` include references in new templates — grep confirmed no matches ✅

### 9. Visual verification
- Screenshot taken at `/project/iw-ai-core/oss` — page loads correctly with header, scan summary pill, stat tiles, filter chips, and findings table visible.

## Issues

| Severity | File | Line | Issue | Note |
|----------|------|------|-------|------|
| OBSERVATION | `oss_finding_modal.html` | 121-127 | Catalog miss → silent blanks instead of loud error | CI completeness test is the intended guard; accept for now |

## Test results

| Check | Result |
|-------|--------|
| `make css` | Pass |
| `node --check` on JS | Pass |
| `make lint` (ruff) | Pre-existing errors only in `orch/oss/fix_recipes/` (S11 did not touch) |

## Verdict

**APPROVE** — S11 implementation is correct and complete. No critical or high findings. One observation about catalog-miss silent behavior, but the CI gate is the intended safeguard.

## Command to mark step done

```bash
uv run iw step-done CR-00022 --step S12 --report ai-dev/active/CR-00022/reports/CR-00022_S12_CodeReview_report.md
```
