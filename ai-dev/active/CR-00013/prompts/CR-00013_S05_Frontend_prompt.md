# CR-00013_S05_Frontend_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step**: S05
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design document
- `dashboard/templates/base.html` — current CDN-based loading
- `dashboard/templates/pages/**/*.html` — pages that use Mermaid, Highlight.js, DOMPurify, or streaming-markdown (grep to find them)
- `dashboard/static/` — target dir for prebuilt CSS and self-hosted font
- `dashboard/CLAUDE.md` — must be updated to document the new build step
- `Makefile` — add `css` target
- `package.json` / lockfile — if creating one, use a minimal single-purpose setup for Tailwind CLI

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S05_Frontend_report.md` — step report

## Context

You are making the dashboard's first-paint fast and its per-page script load lean. The project currently violates its own "no build step" documented rule by loading Tailwind's runtime JIT from a CDN; this CR explicitly relaxes that rule. Mermaid, Highlight.js + 11 language scripts, DOMPurify, and streaming-markdown are also loaded on every page today — move them to the pages that actually need them.

Read the design (Section "Current Behavior" / AC6). Read `dashboard/CLAUDE.md` to see what the "no build step" rule said before; your update must replace it with a clear new rule.

## Requirements

### 1. E1 — Prebuilt Tailwind CSS + `make css` target — covers AC6 (part)

- Adopt the **Tailwind CLI** (`@tailwindcss/cli` or `tailwindcss` binary — pick the one the repo's Node ecosystem supports most cleanly).
- Create a Tailwind config file (`dashboard/tailwind.config.js`) that:
  - Points `content` at `dashboard/templates/**/*.html` and `dashboard/static/**/*.js` so JIT purges correctly.
  - Ports the theme extensions currently inlined in `base.html:32-70` (colors bound to CSS vars, radii, fonts) — visual output must match.
  - Sets `darkMode: 'class'` (already in base.html).
- Create an input CSS file (`dashboard/static/tailwind.src.css`) with `@tailwind base; @tailwind components; @tailwind utilities;` plus any `@layer` additions needed to keep parity.
- Add a `Makefile` target:
  ```
  css:
  	npx tailwindcss -c dashboard/tailwind.config.js -i dashboard/static/tailwind.src.css -o dashboard/static/styles.css --minify
  ```
- Hook it into existing flows where sensible (e.g., add to `make quality` **only if** it can run without network in CI; otherwise document in `dashboard/CLAUDE.md` as a dev-time step).
- In `dashboard/templates/base.html`:
  - Remove the `<script src="https://cdn.tailwindcss.com">` tag.
  - Remove the inline `tailwind.config = { ... }` block.
  - Add `<link rel="stylesheet" href="/static/styles.css">`.
- **Commit the generated `dashboard/static/styles.css`** to the repo so a fresh clone of the branch runs without requiring `make css` first. (The CR explicitly accepts the DX tradeoff.)

Verify visual parity: run the dashboard locally after the swap and confirm the layout, colors, dark mode, and spacing are identical to the pre-change screenshots at `ai-dev/active/CR-00013/evidences/pre/`.

### 2. E2 — Lazy-load per-page libs — covers AC6 (part)

Currently `base.html` eagerly loads:

- Highlight.js core + 11 language scripts (`base.html:77-89`)
- DOMPurify (`base.html:92`)
- Mermaid (`base.html:95`)
- streaming-markdown + render bridge (`base.html:128-142`)

Move each to only the pages that need it:

- **Mermaid**: pages showing diagrams (e.g., item design-doc viewers, architecture pages). Add via `{% block head %}` on those templates.
- **Highlight.js**: pages showing code blocks (e.g., code viewer, diffs). Same pattern.
- **DOMPurify + streaming-markdown**: pages with chat/markdown streaming (likely code-ui/chat pages). Same pattern.

Approach:

- Identify the pages by searching templates for `class="mermaid"`, `hljs`, `smd-loader`, `dompurify`, `class="markdown"` etc. (grep).
- Create small include snippets under `templates/components/` (e.g., `components/libs/mermaid.html`, `components/libs/hljs.html`) containing the `<script>` tags and associated init blocks.
- Each page that needs the lib does:
  ```jinja
  {% block head %}
    {{ super() }}
    {% include "components/libs/mermaid.html" %}
  {% endblock %}
  ```
- Remove the corresponding `<script>` blocks from `base.html`.
- The existing `document.body.addEventListener('htmx:afterSwap', ...)` block in `base.html:318-324` calls `window.iwRenderMermaid` — keep it, but guard with `typeof`. It becomes a no-op on pages without Mermaid.

### 3. E3 — Self-host Inter font — covers AC6 (part)

- Download Inter (weights 400/500/600/700, Latin subset is sufficient) into `dashboard/static/fonts/inter/`.
- Add a `@font-face` block to `dashboard/static/theme.css` (or a new `dashboard/static/fonts.css` imported from theme.css) for each weight, `font-display: swap`.
- Remove the `<link rel="preconnect" href="https://fonts.googleapis.com">`, `<link rel="preconnect" href="https://fonts.gstatic.com">`, and `<link href="https://fonts.googleapis.com/css2?..." rel="stylesheet">` from `base.html:12-14`.
- Commit the font files (WOFF2 only; keep repo size small — WOFF2 is well under 50 KB per weight for Latin subset).

### 4. Update `dashboard/CLAUDE.md`

- Remove the sentence that says "No build step — Tailwind loaded from CDN".
- Add a new "Build step" subsection describing:
  - `make css` regenerates `dashboard/static/styles.css` from templates.
  - Run it after editing templates that add new Tailwind classes.
  - The generated file is committed to the repo (intentional — keeps fresh clones runnable).

## Project Conventions

- Do not introduce a SPA framework or bundler beyond what Tailwind CLI requires.
- No dynamic Tailwind class construction in Python/Jinja — all classes must be literal in template source so the JIT can purge correctly.
- Keep `fragments/*.html` template rules intact (fragments do NOT extend `base.html`).

## TDD Requirement

Tests for this step are written in S07, not here. For S05, verify by:

1. Running the dashboard locally.
2. Visual diffing against `evidences/pre/` screenshots.
3. Opening the browser console — zero errors on every page you touch.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make css` succeeds.
2. `make test-unit` — clean.
3. `make test-integration` — clean.
4. `make quality` — clean.
5. Manual smoke: open `/`, `/system/status`, `/system/running`, a project dashboard, an item detail page in a browser. Confirm visual parity and zero console errors.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "Makefile",
    "dashboard/tailwind.config.js",
    "dashboard/static/tailwind.src.css",
    "dashboard/static/styles.css",
    "dashboard/static/fonts/inter/*.woff2",
    "dashboard/static/theme.css",
    "dashboard/templates/base.html",
    "dashboard/templates/components/libs/mermaid.html",
    "dashboard/templates/components/libs/hljs.html",
    "dashboard/templates/components/libs/markdown.html",
    "dashboard/templates/pages/**/*.html (pages updated with {% block head %})",
    "dashboard/CLAUDE.md"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
