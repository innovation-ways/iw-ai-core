# CR-00022_S11_Frontend_report.md

## What was done

Replaced the card + hover-tooltip OSS findings layout with a domain-grouped collapsible **table**. Added:
- **Filter chips** (Failing/human-required, All, MUST, SHOULD, INFO, Accepted) that toggle row visibility via CSS classes
- **Findings table** with collapsible domain `<tbody>` groups and per-row `…` detail buttons
- **Centered modal** (accessible: focus trap, ESC-to-close, backdrop-click to close, `role="dialog"`, `aria-modal`)
- **SSE row-update consumer** replacing `setTimeout(window.location.reload())` with in-place row patching
- **Catalog integration** — modal fetches per-check copy from `catalog` passed to template
- **Accepted findings** separated into a dedicated collapsible section
- **`oss_table.html`** fragment for findings table
- **`oss_finding_modal.html`** fragment for modal + inline JS
- Rewrote **`oss.html`** page (Scan + Apply all safe buttons, filter chips, table)
- Updated **`oss.py`** to pass `catalog` + `accepted_findings` to template; used `object.__setattr__()` to attach `finding_hash` (not in ORM)
- Added `status-accepted` and `severity-*` CSS classes via Tailwind src file
- Ran `make css` to regenerate `styles.css` with all new utility classes

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/pages/project/oss.html` | Full rewrite — Scan/Apply-all-safe buttons, filter chips, findings table, SSE handler with row patching |
| `dashboard/templates/fragments/oss_table.html` | **New** — domain-grouped findings table with `<tbody class="oss-domain-group">` |
| `dashboard/templates/fragments/oss_finding_modal.html` | **New** — centered modal + inline JS for open/close/trap-focus/accept/apply/re-run |
| `dashboard/routers/oss.py` | `oss_page()` now loads `catalog` + `accepted_findings`, passes to template; `now_iso` re-imported |
| `dashboard/static/tailwind.src.css` | Added CSS component classes for `severity-pill`, `status-pill`, `oss-modal-*`, filter CSS rules |
| `dashboard/static/styles.css` | Regenerated via `make css` |
| `dashboard/utils/oss_copy.py` | Added `"accepted"` entry to `STATUS_COPY` |
| `dashboard/services/oss_check_catalog.py` | Removed unused `field_validator` import; added trailing newline |

## Dead fragment (marked for S19 deletion)

- `dashboard/templates/fragments/oss_domain_card.html` — superseded by the table layout; will be deleted in S19.

## Verification

- **`make lint-js`** — passed (no output, no errors)
- **`make lint`** (ruff) — `dashboard/routers/oss.py` and `dashboard/services/oss_check_catalog.py` fixed; all other errors are pre-existing in `orch/oss/fix_recipes/` (not touched)
- **`uv run mypy dashboard/routers/oss.py`** — passed (no errors)
- **`make css`** — regenerated 48 KB `styles.css` including all new CSS component classes

## Manual testing notes

- Table renders with domain headers showing fail/pass counts
- Domain collapse works via `onclick="this.closest('tbody').classList.toggle('collapsed')"` with CSS hiding rows
- Filter chips set `filter-MUST` / `filter-SHOULD` etc. on the table and CSS hides non-matching rows
- Modal opens on `…` button click, populating all catalog fields
- Modal closes on ESC, backdrop click, or Close button
- SSE `row-update` listener patches existing rows or inserts new ones
- SSE `complete` calls `refreshSummaryPill()` + `closeProgressRow()` — no reload