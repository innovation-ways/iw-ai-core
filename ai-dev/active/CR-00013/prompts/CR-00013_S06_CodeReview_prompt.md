# CR-00013_S06_CodeReview_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design
- `ai-dev/active/CR-00013/reports/CR-00013_S05_Frontend_report.md` — S05 report
- All files in S05's `files_changed`

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S06_CodeReview_report.md` — review report

## Context

Review S05: prebuilt Tailwind CSS + per-page lazy-load of heavy libs + self-hosted Inter font + CLAUDE.md rule update.

## Review Checklist

### 1. Tailwind Build (E1)

- `dashboard/tailwind.config.js` has `content` globs that cover every template file that might contain Tailwind classes — including `fragments/`, `components/`, and `pages/`.
- **Critical**: No dynamic Tailwind class construction in any template or Python file. Grep for string concatenation like `f"text-{color}"` or `" ".join(["bg-", status])` — these break the JIT's static-analysis purge. Findings here are CRITICAL.
- Theme extensions from `base.html` (colors bound to CSS vars, radii, fonts) ported into `tailwind.config.js`. Visual output identical to pre-change.
- `make css` target runs cleanly with whatever tooling is present (npm + npx, bunx, or a vendored binary). Document clearly in `dashboard/CLAUDE.md` if any prereqs exist.
- `dashboard/static/styles.css` is committed (intentional; do not flag as "generated file in repo").
- No remaining CDN tag for Tailwind in `base.html`.

### 2. Per-page Lazy Loading (E2)

- Every page that uses Mermaid has `{% include "components/libs/mermaid.html" %}` in its `{% block head %}`. Grep templates for `class="mermaid"` and cross-check.
- Same for Highlight.js (`class="hljs"` or `class="language-*"`), DOMPurify, streaming-markdown.
- The fragment templates (`templates/fragments/`) that return Mermaid/hljs content after htmx swaps still work: the parent page that hosts the swap target must include the lib in its `{% block head %}`.
- The `document.body.addEventListener('htmx:afterSwap', ...)` block in `base.html` guards `window.iwRenderMermaid` with `typeof` so it's a no-op on pages without Mermaid.
- `base.html` no longer loads Mermaid, DOMPurify, Highlight.js, streaming-markdown, or the 11 language scripts unconditionally.

### 3. Self-hosted Font (E3)

- No `fonts.googleapis.com` or `fonts.gstatic.com` references anywhere in templates.
- `@font-face` declarations present for each Inter weight used; `font-display: swap`; `src: url('/static/fonts/inter/...woff2') format('woff2')`.
- WOFF2 files present in `dashboard/static/fonts/inter/`.
- Latin subset (or whichever scope the project needs) — not full 15 MB unicode range.

### 4. CLAUDE.md Update

- `dashboard/CLAUDE.md` no longer says "No build step — Tailwind loaded from CDN".
- New "Build step" subsection explains `make css`, when to run it, and why the generated file is committed.
- No other CLAUDE.md files mention the removed rule (cross-check `/CLAUDE.md`).

### 5. Visual Parity

- Compare against `ai-dev/active/CR-00013/evidences/pre/` screenshots visually. Layout, colors, dark mode, and spacing must match.

### 6. Project Conventions

- Fragments do NOT extend `base.html` (dashboard/CLAUDE.md rule).
- No SPA framework introduced.
- Node dependencies (if added) are minimal and pinned.

## Test Verification (NON-NEGOTIABLE)

1. `make css` — succeeds.
2. `make test-unit`, `make test-integration`, `make quality` — all clean.
3. Smoke: open representative pages in the browser, check console.

## Severity Levels

(Same table as S02.)

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00013",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
