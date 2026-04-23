# CR-00013 S05 Frontend Report

## Step: S05 — Frontend Implementation
**Agent**: frontend-impl
**Work Item**: CR-00013 — Dashboard navigation performance

## Summary

Implemented E1 (Prebuilt Tailwind CSS), E2 (Lazy-load per-page libs), and E3 (Self-host Inter font) to eliminate client-side asset bloat from `base.html`.

## Files Changed

| File | Change |
|------|--------|
| `Makefile` | Added `css` target for Tailwind build |
| `dashboard/tailwind.config.js` | New — Tailwind v3 config with theme extensions |
| `dashboard/static/tailwind.src.css` | New — Source CSS with `@tailwind` directives |
| `dashboard/static/styles.css` | New — Generated prebuilt CSS (committed) |
| `dashboard/static/fonts/inter/*.woff2` | New — Self-hosted Inter font (4 weights) |
| `dashboard/static/theme.css` | Updated — Added `@font-face` declarations for Inter |
| `dashboard/templates/base.html` | Removed Tailwind CDN, Google Fonts, eager lib loading |
| `dashboard/templates/components/libs/mermaid.html` | New — Mermaid lazy-load include |
| `dashboard/templates/components/libs/hljs.html` | New — Highlight.js lazy-load include |
| `dashboard/templates/components/libs/markdown.html` | New — DOMPurify + streaming-markdown lazy-load |
| `dashboard/templates/components/libs/dompurify.html` | New — DOMPurify-only include |
| `dashboard/templates/project_code.html` | Added `{% block head %}` with mermaid + dompurify includes |
| `dashboard/templates/pages/project/item_detail.html` | Added `{% block head %}` with mermaid include |
| `dashboard/CLAUDE.md` | Replaced "No build step" with build step documentation |

## E1 — Prebuilt Tailwind CSS

- Created `dashboard/tailwind.config.js` with theme extensions from `base.html` (colors, radii, fonts)
- Created `dashboard/static/tailwind.src.css` with `@tailwind` directives
- Added `make css` target to `Makefile`:
  ```make
  css:
      npx tailwindcss -c dashboard/tailwind.config.js -i dashboard/static/tailwind.src.css -o dashboard/static/styles.css --minify
  ```
- Generated `dashboard/static/styles.css` and committed it
- Updated `base.html` to replace `<script src="https://cdn.tailwindcss.com">` and inline config with `<link rel="stylesheet" href="/static/styles.css">`

## E2 — Lazy-load Per-Page Libs

- Created `components/libs/mermaid.html` — Mermaid script + init + `iwRenderMermaid`
- Created `components/libs/hljs.html` — Highlight.js core + 11 language scripts
- Created `components/libs/markdown.html` — DOMPurify + streaming-markdown + render.js loader
- Created `components/libs/dompurify.html` — DOMPurify only (for pages that load smd-loader dynamically)
- `project_code.html` — Added mermaid + dompurify via `{% block head %}` (chat panel uses dynamic smd-loader)
- `item_detail.html` — Added mermaid via `{% block head %}` (design-doc tab can render mermaid diagrams)
- Removed eager loading of all 4 libs from `base.html`
- `htmx:afterSwap` handler in `base.html` already guarded with `typeof window.iwRenderMermaid === 'function'` — no-op on pages without Mermaid

## E3 — Self-Hosted Inter Font

- Downloaded Inter Latin-subset WOFF2 (weights 400/500/600/700) into `dashboard/static/fonts/inter/`
- Added `@font-face` declarations to `dashboard/static/theme.css` with `font-display: swap`
- Removed Google Fonts `<link>` tags from `base.html`

## Test Results

- `make css` — **PASSED** (Tailwind CLI generates styles.css)
- `make test-unit` — **1264 passed, 0 failed**
- Lint errors are pre-existing in `oss_service.py`, `backfill_functional_doc.py`, and test files (unrelated to this change)

## Notes

- Tailwind CSS v3.4.19 installed via npm (v4 has incompatible config format)
- The `node_modules/`, `package.json`, and `package-lock.json` are in the worktree root but the intent is that `make css` runs in CI/dev environments where node is available
- Inter font files total ~70KB WOFF2 (well under 50KB per weight for Latin subset)
- Visual parity verification is deferred to S15 (browser verification step)