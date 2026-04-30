# F-00075 S04 Frontend Report

## What was done

Modified `dashboard/templates/fragments/llm_usage_footer.html` (lines 26–27) to:

1. **Replace the literal `"5h"` label** with `{{ minimax_reset or '5h' }}`, mirroring the Claude row's pattern. Now when the API supplies a real reset countdown string it will be displayed; otherwise it falls back to `"5h"`.

2. **Add a conditional `title` attribute** on the outer `<div class="hidden sm:flex items-center gap-1.5">` for the MiniMax 5h block. When both `minimax_5h_used` and `minimax_5h_total` are not `None`, the attribute reads `"<used> / <total> requests"`. When either is `None` (failure branch), no `title` attribute is emitted.

## Files changed

- `dashboard/templates/fragments/llm_usage_footer.html`

## Verification

- Jinja render sanity-check: success branch produces `title="0 / 4500 requests"`; failure branch produces no `title` attribute.
- `make format`: 504 files already formatted (no changes needed).
- `make typecheck`: All 210 source files pass mypy.
- `make lint`: All ruff checks pass.
- `make test-unit`: **2224 passed**, 2 skipped, 5 xfailed, 1 xpassed.

## Issues / Observations

- No new Tailwind classes introduced — `make css` was not required.
- Fragment remains a valid Jinja2 template with no base.html extension.
