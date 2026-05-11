# I-00078: Dashboard layout — invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a footer that should be full-width with the theme toggle inside it

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-11
**Reported By**: sergio (user report)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migrations and touches no database schema** — it is a pure dashboard template + CSS change.

## Description

The dashboard chrome has four coupled layout defects: (1) scrollbar thumbs are nearly invisible in dark mode because they're painted with `var(--border)`, which is barely above the dark background; (2) the horizontal scrollbar under the step pipeline strip sits flush against the step pills with no visual separation; (3) the app shell is sized with `h-screen` (`100vh`), which on browsers with a dynamic toolbar (and whenever a top banner is present) overflows the visual viewport — producing a second, body-level vertical scrollbar in addition to the `<main>` content scrollbar and pushing the footer below the visible area; (4) the LLM-usage footer (Claude / MiniMax meters) lives inside the main content column so it cannot span the full window width, and the "Toggle theme" control lives at the bottom of the left sidebar instead of in that footer. Net user impact: confusing double scrollbars, the Claude/MiniMax usage meters frequently requiring a scroll to see, and hard-to-grab scrollbars in dark mode.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules — in particular: Jinja2 `format`-filter must stay `%`-style; `make css` regenerates `dashboard/static/styles.css` from templates and may be a no-op or fail in worktrees, in which case append **plain CSS** directly to `styles.css` (served as-is); `make lint` runs `scripts/check_templates.py` (Jinja2) and `node --check` on dashboard JS; clipboard buttons use `window.iwClipboard.copy`.

## Steps to Reproduce

1. Open the dashboard (`/`) in a browser and switch to dark mode (the "Toggle theme" button at the bottom of the left sidebar, or OS dark preference).
2. Open any page with a long page body — e.g. `/project/iw-ai-core/item/I-00077`.
3. Observe the right edge of the window and the step-pipeline strip near the top of the Overview tab.

**Expected**:
- Scrollbar thumbs are clearly visible (good contrast) in both light and dark themes, with a hover state, and Firefox shows a thin themed scrollbar.
- The horizontal scrollbar under the step-pipeline pills has clear vertical separation from the pills.
- Exactly **one** vertical scrollbar exists — the content scroller. The footer (Claude/MiniMax usage meters) is always visible, anchored at the bottom, and spans the **full window width** including under the sidebar.
- The "Toggle theme" control lives in the footer (left side, before the meters), not in the sidebar.

**Actual**:
- Dark-mode scrollbar thumbs are almost invisible (painted with `var(--border)` = `#3e3f45`, barely lighter than the dark background); no hover state; no Firefox `scrollbar-color` / `scrollbar-width`.
- The pipeline horizontal scrollbar butts directly against the pills (`.iw-pipeline-strip { overflow-x: auto }` with no `padding-bottom`).
- Two vertical scrollbars appear (body + `<main>`); the `flex-shrink-0` footer is pushed below the viewport and the Claude/MiniMax meters often require scrolling to see.
- "Toggle theme" is at the bottom of the `<aside id="sidebar">` panel; the footer only spans the content column, not the full width.

## Root Cause Analysis

1. **Dark-mode scrollbar contrast** — `dashboard/static/theme.css:194-205` defines `::-webkit-scrollbar` (12×12) with `::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px }` and a transparent track. In `.dark` (`theme.css:108`) `--border` is `#3e3f45`, only marginally lighter than the dark background, so the thumb reads as "no scrollbar". There is no `::-webkit-scrollbar-thumb:hover` rule and no Firefox `scrollbar-width` / `scrollbar-color` declaration anywhere.

2. **Pipeline scrollbar spacing** — `dashboard/static/styles.css:371-377` (`.iw-pipeline-strip`) sets `display:flex; align-items:center; flex-wrap:nowrap; gap:0; overflow-x:auto;` with no `padding-bottom`, so when the pills overflow horizontally the scrollbar renders directly under them. The strip is rendered by the `step_pipeline()` macro in `dashboard/templates/components/step_pipeline.html` (`<div class="iw-pipeline-strip" …>`).

3. **Double vertical scrollbar / footer below the fold** — `dashboard/templates/base.html:72` opens the app shell as `<div class="flex h-screen overflow-hidden">`, with `<main class="flex-1 overflow-y-auto">` (`base.html:197`) as the intended content scroller and `<footer class="flex-shrink-0 …">` (`base.html:207`) at the bottom of the inner column. `h-screen` resolves to `100vh`, which on browsers with a dynamic/animated toolbar is *taller* than the actual visual viewport — so `<body>` itself overflows and grows its own scrollbar, and the `flex-shrink-0` footer is shoved off the bottom of the viewport. The condition is *guaranteed* whenever the stale-DB banner (`base.html:43-60`) is shown, since that banner sits **above** the `h-screen` shell, making `banner-height + 100vh > viewport`.

4. **Footer not full-width + theme toggle misplaced** — In `base.html` the `<footer>` is nested inside `<div class="flex-1 flex flex-col overflow-hidden">` (`base.html:166`), the main column that sits to the *right* of `<aside id="sidebar" class="… w-60 …">`. So the footer's width is the content-column width, not the window width. The "Toggle theme" `<button onclick="toggleDarkMode()">` lives inside the sidebar (`base.html:155-162`). Note `toggleDarkMode()` in `dashboard/static/theme-toggle.js` is self-contained — it toggles the `.dark` class on `<html>` and writes `localStorage` — so the button can be relocated freely; the `<span id="theme-icon">☾</span>` is purely decorative (it never changes) and stays a single instance wherever the button lives.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/static/theme.css` | Scrollbar colours: introduce a high-contrast thumb colour for both themes + `:hover` + Firefox `scrollbar-color`/`scrollbar-width`. |
| `dashboard/static/styles.css` | Add `padding-bottom` to `.iw-pipeline-strip`; possibly host the footer/shell layout CSS if new utilities can't be JIT-compiled in the worktree. |
| `dashboard/templates/base.html` | Restructure the app shell to a column: `[sidebar + content]` row on top, a full-width `<footer>` below; size the shell with a dynamic-viewport unit (`100dvh` / `h-dvh`) and pin `html,body` so there's exactly one content scrollbar; move the "Toggle theme" button out of the sidebar into the footer. |
| `dashboard/templates/fragments/llm_usage_footer.html` | The htmx-swapped footer body — must not get clobbered by the relocated theme toggle (toggle goes in a static sub-element of `<footer>`, the `hx-get … hx-swap="innerHTML"` lives on an inner `<div>`). May gain layout-class tweaks for the wider footer. |
| `dashboard/templates/components/step_pipeline.html` | Likely unchanged (the padding fix is CSS-only) — in scope only in case a wrapper element is the cleaner fix. |
| `dashboard/static/theme-toggle.js` | Likely unchanged; in scope only in case the relocated button needs a tiny wiring tweak. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | All four fixes: dark-mode scrollbar contrast (+hover +Firefox), pipeline-strip `padding-bottom`, shell restructure to a full-width-footer column layout with `100dvh`/`h-dvh` + pinned `html,body` (exactly one content scrollbar, footer always visible), move "Toggle theme" into the footer (left side). | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | tests-impl | Reproduction + regression tests (rendered-HTML structure assertions; see TDD Approach) | — |
| S04 | code-review-impl | Review S03 output | — |
| S05 | code-review-final-impl | Global cross-agent review | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make test-integration` | — |
| S11 | qv-browser | Browser verification in the isolated worktree stack | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill (project has `self_assess = true`) | — |

Agent slugs: `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no schema change.

### Code Changes

- **Files to modify**: `dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html` (and possibly `dashboard/templates/components/step_pipeline.html`, `dashboard/static/theme-toggle.js`, `dashboard/static/tailwind.src.css` if `make css` is run). Plus the new test file `tests/dashboard/test_i00078_layout.py`.
- **Nature of change**: CSS adjustments + a Jinja2 layout restructure. No Python, no routes, no DB.

## File Manifest

All files for this work item live under `ai-dev/active/I-00078/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00078_Issue_Design.md` | Design | This document |
| `I-00078_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00078_S01_frontend-impl_prompt.md` | Prompt | S01 — implement all four layout fixes |
| `prompts/I-00078_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00078_S03_tests-impl_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00078_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00078_S05_CodeReview_Final_prompt.md` | Prompt | S05 — global cross-agent review |
| `prompts/I-00078_S11_BrowserVerification_prompt.md` | Prompt | S11 — qv-browser end-to-end verification |
| `prompts/I-00078_S12_SelfAssess_prompt.md` | Prompt | S12 — self-assessment |

QV gate steps S06–S10 are script-driven (no prompt file). Pre-fix browser evidence is in `ai-dev/active/I-00078/evidences/pre/`. Reports are created during execution in `ai-dev/active/I-00078/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

**Test-file location** — these tests render `base.html` via the dashboard `client` fixture, so they MUST live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py`; a test placed elsewhere fails with `fixture 'client' not found`, see I-00067).

```python
# tests/dashboard/test_i00078_layout.py
import re


def test_i00078_footer_is_full_width_sibling_of_sidebar(client):
    """The LLM-usage footer must NOT be nested inside the main content column;
    it must be a sibling of the [sidebar + content] row so it spans the full
    window width. Pre-fix this FAILS because <footer> sits inside the .flex-1
    main column."""
    html = client.get("/").text
    # The sidebar <aside id="sidebar"> ... </aside> closes before <footer> opens,
    # and <footer> is not inside any element that also contains <aside ...>.
    aside_end = html.index("</aside>")
    footer_start = html.index("<footer")
    assert footer_start > aside_end, "footer must come after the sidebar closes"
    # And the shell wrapper that holds the row must close before the footer:
    # the [sidebar+content] flex row must not still be open when <footer> opens.
    # (Asserted indirectly: the footer must carry a full-width marker class.)
    footer_tag = html[footer_start:footer_start + 400]
    assert re.search(r'class="[^"]*\bw-full\b[^"]*"', footer_tag), (
        "footer must be full-width (w-full)"
    )


def test_i00078_theme_toggle_lives_in_footer_not_sidebar(client):
    """The 'Toggle theme' button moved from the sidebar into the footer.
    Pre-fix this FAILS — the button is inside <aside id="sidebar">."""
    html = client.get("/").text
    aside_start = html.index('id="sidebar"')
    aside_end = html.index("</aside>", aside_start)
    sidebar_html = html[aside_start:aside_end]
    assert "toggleDarkMode()" not in sidebar_html, (
        "theme toggle must no longer be in the sidebar"
    )
    footer_start = html.index("<footer")
    footer_end = html.index("</footer>", footer_start)
    footer_html = html[footer_start:footer_end]
    assert "toggleDarkMode()" in footer_html, (
        "theme toggle must be inside the footer"
    )


def test_i00078_shell_uses_dynamic_viewport_height(client):
    """The app shell must be sized with a dynamic-viewport unit (h-dvh / 100dvh)
    rather than h-screen / 100vh, so it does not overflow the visual viewport.
    Pre-fix this FAILS — base.html uses h-screen."""
    html = client.get("/").text
    assert ("h-dvh" in html) or ("100dvh" in html), (
        "shell height should use a dynamic viewport unit"
    )
    # The old fixed-viewport shell wrapper must be gone.
    assert 'class="flex h-screen overflow-hidden"' not in html


def test_i00078_pipeline_strip_has_scrollbar_spacing():
    """.iw-pipeline-strip must carry bottom padding so the horizontal scrollbar
    is separated from the step pills. Pre-fix this FAILS."""
    css = open("dashboard/static/styles.css", encoding="utf-8").read()
    # Find the .iw-pipeline-strip { ... } block and assert it declares padding-bottom
    # (or shorthand padding) with a non-zero value.
    m = re.search(r"\.iw-pipeline-strip\s*\{([^}]*)\}", css)
    assert m, ".iw-pipeline-strip rule must exist"
    block = m.group(1)
    assert re.search(r"padding(-bottom)?\s*:", block), (
        ".iw-pipeline-strip must declare padding-bottom"
    )


def test_i00078_dark_scrollbar_uses_high_contrast_thumb():
    """Dark-mode scrollbar thumb must not be painted with the low-contrast
    --border token; there must also be a :hover state and a Firefox
    scrollbar-color/scrollbar-width declaration. Pre-fix this FAILS."""
    css = open("dashboard/static/theme.css", encoding="utf-8").read()
    m = re.search(r"::-webkit-scrollbar-thumb\s*\{([^}]*)\}", css)
    assert m, "::-webkit-scrollbar-thumb rule must exist"
    assert "var(--border)" not in m.group(1), (
        "scrollbar thumb must use a higher-contrast colour than --border"
    )
    assert "::-webkit-scrollbar-thumb:hover" in css, "needs a hover state"
    assert "scrollbar-color" in css and "scrollbar-width" in css, (
        "needs Firefox scrollbar-color / scrollbar-width"
    )
```

(These exact assertions are illustrative — S03 may refine them, but the *semantic* checks above are mandatory: footer is a full-width sibling of the sidebar, theme toggle is in the footer not the sidebar, shell uses a dynamic-viewport unit, pipeline strip has bottom padding, dark scrollbar thumb is not `var(--border)` and has a hover + Firefox fallback. Shape-only checks like "the word `footer` appears" are NOT acceptable.)

## Acceptance Criteria

### AC1: Dark-mode scrollbars are visible with a hover state and a Firefox fallback

```
Given the dashboard is in dark mode
When a scrollable area (the page content, a code block, the pipeline strip) overflows
Then the scrollbar thumb is clearly visible against the dark background
And the thumb darkens/lightens on hover
And Firefox renders a thin themed scrollbar (scrollbar-width: thin; scrollbar-color set)
```

### AC2: The step-pipeline horizontal scrollbar is separated from the pills

```
Given an item page whose step pipeline overflows horizontally
When the horizontal scrollbar is shown under the pills
Then there is visible vertical spacing between the bottom of the pills and the scrollbar
```

### AC3: Exactly one vertical scrollbar; the footer is always visible

```
Given any dashboard page (with or without the stale-DB banner shown)
When the page body is taller than the viewport
Then there is exactly one vertical scrollbar (the content scroller)
And the LLM-usage footer is fully visible, anchored at the bottom of the viewport,
    without scrolling
```

### AC4: The footer is full-width and contains the theme toggle

```
Given any dashboard page
When the page renders
Then the footer spans the full window width (it extends under the left sidebar)
And the "Toggle theme" control is in the footer (left side, before the Claude/MiniMax meters)
And the sidebar no longer contains a theme toggle
And clicking the footer's theme toggle still flips light/dark and persists the choice
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_i00078_layout.py passes
```

## Regression Prevention

- The new `tests/dashboard/test_i00078_layout.py` pins the structural invariants (footer is a full-width sibling of the sidebar, theme toggle in the footer, dynamic-viewport shell, pipeline-strip bottom padding, non-`--border` scrollbar thumb with hover + Firefox fallback) so a future refactor that regresses any of them fails CI.
- Use a dedicated CSS custom property (e.g. `--scrollbar-thumb` / `--scrollbar-thumb-hover`) defined in both `:root` and `.dark` rather than reusing a semantic token whose value may drift — keeps "scrollbar visibility" decoupled from "border colour".

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

```
dashboard/templates/base.html
dashboard/static/theme.css
dashboard/static/styles.css
dashboard/static/tailwind.src.css
dashboard/static/theme-toggle.js
dashboard/templates/fragments/llm_usage_footer.html
dashboard/templates/components/step_pipeline.html
tests/dashboard/test_i00078_layout.py
```

## TDD Approach

- Reproducing test: `tests/dashboard/test_i00078_layout.py` — the five functions above fail against pre-fix `base.html` / `theme.css` / `styles.css` and pass after the fix.
- Unit/dashboard tests: rendered-HTML structure assertions via the `client` fixture (footer placement, theme-toggle relocation, dynamic-viewport class) plus direct CSS-file assertions (pipeline padding, scrollbar thumb colour + hover + Firefox declarations).
- Integration tests: none new — `make test-integration` runs the full suite in QV S10 to confirm no regression.

**Assertion scoping for CSS class names** — when asserting a CSS class is present in rendered HTML, prefer the attribute-scoped form (`assert 'class="…w-full…"' in html` or a `class\s*=\s*"[^"]*w-full[^"]*"` regex) rather than a bare-substring `assert "w-full" in html`, because the token may appear in inline JSON, a `data-*` attribute, or a comment even when the production element is absent (I-00067).

## Notes

- `make css` rewrites all of `dashboard/static/styles.css` from the templates. If the Tailwind toolchain is broken in the worktree (`make css` reports "Nothing to be done" or fails on a missing `postcss-selector-parser`), append the needed rules as **plain CSS** to `styles.css` — it's served verbatim, no recompile needed (per `CLAUDE.md`). The scrollbar rules already live in `theme.css` (plain CSS), so the scrollbar fix needs no Tailwind at all.
- The footer's `hx-get="/api/usage/llm/fragment"` / `hx-swap="innerHTML"` currently targets the `<footer>` element itself. After moving the theme toggle into the footer, the `hx-get`/`hx-swap` MUST be moved to an *inner* `<div>` (the meters container) so a poll refresh doesn't wipe the toggle button. The `llm_usage_footer.html` fragment already provides the inner spans including the `ml-auto IW AI Core v0.1` label — keep that fragment rendering only the meters; the theme toggle is a static sibling inside `<footer>`.
- Out of scope: the `<span id="theme-icon">☾</span>` never updates to ☀ in dark mode — that pre-existing cosmetic quirk is not part of this incident.
