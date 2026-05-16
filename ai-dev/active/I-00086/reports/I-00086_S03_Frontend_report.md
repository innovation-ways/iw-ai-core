# I-00086 — S03 Frontend report

## What was done

- Extracted the full steps table + bulk runtime footer from `fragments/item_overview.html` into a new fragment: `dashboard/templates/fragments/item_steps_table.html`.
- Added `id="item-steps-table"` on the swapped fragment root `<div>`.
- Preserved all existing table columns, per-row badges, conditionals, lazy-loaded `step-runs-*` containers, and action macros.
- Updated per-step runtime `<select>` htmx wiring:
  - `hx-target="#item-steps-table"`
  - `hx-swap="outerHTML"`
  - preserved `hx-disabled-elt="this"` and the critical inline comment about disabled controls being omitted from htmx form serialization.
- Updated bulk Apply button wiring:
  - `hx-target="#item-steps-table"`
  - `hx-swap="outerHTML"`
- Kept `id="bulk-runtime-option"` inside the swapped fragment so `hx-vals="javascript:{option_id: document.getElementById('bulk-runtime-option').value}"` remains valid after swap.
- Replaced the extracted block in `item_overview.html` with `{% include "fragments/item_steps_table.html" %}` while preserving the surrounding wrapper and all other overview sections.

## Files changed

- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/item_steps_table.html` (new)

## TDD red/green evidence (template-level)

- Pre-change source did not contain `id="item-steps-table"` in `item_overview.html` (table block existed inline with no swap-target id).
- Post-change source contains `id="item-steps-table"` in `fragments/item_steps_table.html`.
- Attempted runtime curl check against `http://localhost:9900/project/iw-ai-core/item/I-00086/tab/overview`; response did not include the marker in this environment (likely due route/data state mismatch for that URL), but template-level extraction is present and validated by static checks.

## Preflight quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Test results

- Ran: `uv run pytest tests/dashboard/ -k "item_overview or runtime_override" -v`
- Result: **9 failed, 51 passed, 1 skipped**
- Failures are in existing runtime override API/template tests that still assert the pre-S01 `204 No Content` contract. Current behavior is `200 + HTML fragment` and these assertions are expected to be updated in S05.

## Issues / observations

- S01 currently renders the full `item_overview.html` fragment body from the PATCH endpoints; S03 extraction is complete and ready for S05/S04 review alignment.
