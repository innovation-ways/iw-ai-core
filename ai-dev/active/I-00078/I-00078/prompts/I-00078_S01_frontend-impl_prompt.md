# I-00078_S01_frontend-impl_prompt

**Work Item**: I-00078 — Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00078 --json`. `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00078/I-00078_Issue_Design.md` — design document (read first; especially Root Cause Analysis #1–#4 and AC1–AC4)
- `ai-dev/active/I-00078/evidences/pre/` — pre-fix screenshots (`I-00078-dark-mode-item-page.png` shows the dark-mode UI)
- `dashboard/templates/base.html` — the app shell, sidebar, search bar, `<main>`, and `<footer>` (the file you restructure)
- `dashboard/static/theme.css` — CSS custom properties (`:root` + `.dark`) and the `::-webkit-scrollbar*` rules near the bottom (lines ~194-205)
- `dashboard/static/styles.css` — prebuilt Tailwind output + appended plain CSS, incl. `.iw-pipeline-strip` (~line 371)
- `dashboard/static/theme-toggle.js` — `toggleDarkMode()` (self-contained: toggles `.dark` on `<html>`, writes `localStorage`)
- `dashboard/templates/fragments/llm_usage_footer.html` — the htmx-swapped footer body (Claude/MiniMax meters + `IW AI Core v0.1`)
- `dashboard/templates/components/step_pipeline.html` — the `step_pipeline()` macro that renders `<div class="iw-pipeline-strip" …>`
- `dashboard/CLAUDE.md`, `CLAUDE.md` — conventions (Jinja2 `format` rule, where plain CSS goes, `make css`, `make lint` template/JS checks)

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S01_frontend-impl_report.md` — step report
- Modified (expected): `dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html` (and possibly `dashboard/static/tailwind.src.css` if you run `make css`, `dashboard/templates/components/step_pipeline.html`, `dashboard/static/theme-toggle.js`)

## Context

You are implementing **all four** dashboard-chrome fixes for I-00078. Read the design doc in full first, then `dashboard/CLAUDE.md` and `CLAUDE.md`. This is a pure template + CSS change — no Python, no routes, no DB.

## Requirements

### 1. Dark-mode scrollbar contrast (Root Cause #1, AC1) — `dashboard/static/theme.css`

The current rules (~lines 194-205):

```css
::-webkit-scrollbar { width: 12px; height: 12px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px; }
```

In `.dark` (`theme.css:108`) `--border` is `#3e3f45` — barely above the dark background, so the thumb is invisible.

Do:
- Add a dedicated pair of CSS custom properties — `--scrollbar-thumb` and `--scrollbar-thumb-hover` — to **both** `:root` and `.dark`. Light mode: something around `--muted-foreground` lightness or a mid grey (e.g. `#c4c4c8` thumb / `#a8a8ad` hover). Dark mode: a clearly-visible grey (e.g. `#5c5d65` thumb / `#74757d` hover) — must read as a scrollbar against the dark background. Pick values consistent with the existing palette; don't introduce a jarring colour.
- Repaint `::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 6px; }` and add `::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }`.
- Add a Firefox fallback: `* { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }` (or scope to `html`/`body` — but `*` is what gives nested scrollers the thin themed bar too; either is acceptable as long as Firefox shows a thin themed scrollbar).
- Keep the track transparent. Keep the 12×12 webkit dimensions (or shrink slightly if you prefer — not required).

`theme.css` is plain CSS served verbatim — no `make css` needed for this part.

### 2. Step-pipeline scrollbar spacing (Root Cause #2, AC2) — `dashboard/static/styles.css`

`.iw-pipeline-strip` (~line 371) is `display:flex; align-items:center; flex-wrap:nowrap; gap:0; overflow-x:auto;` with no bottom padding, so the horizontal scrollbar (when the pills overflow) butts against the pills. Add `padding-bottom` (e.g. `0.5rem` / `8px`) to `.iw-pipeline-strip` so the scrollbar is visibly separated from the pills. (A `padding-bottom` on a scroll container puts space between the content and the scrollbar — that's what we want.) Don't change the pill/connector styling. You may instead add the spacing via a wrapper element in `step_pipeline.html` if that's cleaner, but the CSS-only change is preferred and lower-risk.

### 3. Single vertical scrollbar + always-visible footer (Root Cause #3, AC3) — `dashboard/templates/base.html` (+ `styles.css` if needed)

Today: `<body>` → `[stale-db banner]` → `[toast/modal/confirm divs]` → `<div class="flex h-screen overflow-hidden">` (sidebar + main column). `h-screen` = `100vh` overflows the visual viewport on browsers with a dynamic toolbar, and *always* overflows when the stale-DB banner is shown (it sits above the `h-screen` shell). Result: a body scrollbar **and** the `<main>` scrollbar, and the `flex-shrink-0` footer pushed off-screen.

Do:
- Size the overall layout with a **dynamic-viewport unit**. Use the `h-dvh` Tailwind utility if it's already in the prebuilt `styles.css` (search it). If it isn't, **append the literal utility rule `.h-dvh{height:100dvh}` to `styles.css`** (plain CSS, served verbatim — no `make css` needed) and put the `h-dvh` class on the shell element. Do **not** invent a differently-named class such as `.iw-app-shell` for this — the S03 regression test keys on the literal token `h-dvh` (or `100dvh`) appearing in the rendered HTML, so the shell element must carry `class="… h-dvh …"`. Also pin `html, body { height: 100%; overflow: hidden; }` (in `theme.css` or `styles.css`) so the body itself never scrolls.
- Make the **whole** body chrome a single flex column that exactly fills the dynamic viewport: the stale-DB banner (when present) is `flex-shrink-0` at the top, the `[sidebar + content]` area is `flex-1` (the row), and the new full-width `<footer>` is `flex-shrink-0` at the bottom. Only `<main>` keeps `flex-1 overflow-y-auto` — it is the *one* scroller.
- After this, on a tall page there must be exactly one vertical scrollbar (the content one), and the footer is visible at the bottom of the viewport without scrolling — banner shown or not.

### 4. Full-width footer with the theme toggle inside it (Root Cause #4, AC4) — `dashboard/templates/base.html` + `dashboard/templates/fragments/llm_usage_footer.html`

Target structure (illustrative — match the project's Tailwind idioms):

```html
<body class="bg-background text-foreground font-sans antialiased h-dvh overflow-hidden flex flex-col">
  {% if is_db_stale(request) %} ...banner... class="... flex-shrink-0" ... {% endif %}
  <div id="toast-container"></div><div id="modal-root"></div><div id="confirm-dialog"></div>

  <!-- app body row: sidebar + content -->
  <div class="flex flex-1 overflow-hidden">
    <div id="sidebar-backdrop" ...></div>
    <aside id="sidebar" class="... w-60 ... overflow-y-auto ...">
      <a href="/" ...>logo</a>
      <nav>...</nav>
      <!-- the "Toggle theme" block that lived here is REMOVED -->
    </aside>
    <div class="flex-1 flex flex-col overflow-hidden">
      <div class="flex-shrink-0 border-b ...">...global search bar...</div>
      <main class="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6">
        {% block oss_status_anchor %}{% endblock %}
        {% block breadcrumb %}{% endblock %}
        {% block content %}{% endblock %}
      </main>
    </div>
  </div>

  <!-- full-width footer, pinned to the bottom, below the sidebar -->
  <footer class="flex-shrink-0 w-full border-t border-border bg-muted px-3 sm:px-6 py-2 flex items-center gap-3 sm:gap-4 text-xs text-muted-foreground">
    <button onclick="toggleDarkMode()"
            class="flex items-center gap-1.5 hover:text-foreground transition-colors flex-shrink-0"
            aria-label="Toggle theme">
      <span id="theme-icon">☾</span><span>Theme</span>
    </button>
    <span class="text-border select-none">·</span>
    <div class="flex-1 flex items-center gap-3 sm:gap-4"
         hx-get="/api/usage/llm/fragment"
         hx-trigger="load, every 300s [document.visibilityState=='visible'], visibilitychange[document.visibilityState=='visible'] from:document"
         hx-swap="innerHTML">
      <span class="font-medium">Claude</span>
      <span>—</span>
      <span class="ml-auto">IW AI Core v0.1</span>
    </div>
  </footer>
  ...scripts...
</body>
```

Critical points:
- **Move the `hx-get`/`hx-trigger`/`hx-swap` off the `<footer>` element onto an inner `<div>` (the meters container).** If the htmx poll's `innerHTML` swap targets `<footer>`, it will wipe the theme-toggle button on the first refresh. Keep the theme toggle a *static sibling inside `<footer>`*, outside the swapped sub-tree.
- `llm_usage_footer.html` already renders only the meters content (Claude block, MiniMax block, `ml-auto IW AI Core v0.1`). It does NOT need to render the theme toggle — leave the fragment producing just the meters. If the wider footer needs a layout-class tweak inside the fragment (e.g. the `ml-auto` still pins the version label to the far right), make the minimal adjustment there.
- `toggleDarkMode()` (in `theme-toggle.js`) is self-contained — no JS change needed for the move. There must remain exactly one element with `id="theme-icon"`. The `theme-toggle.js` `<script>` tag and the inline pre-paint dark-mode script in `<head>` stay as-is.
- The sidebar's old `<div class="px-4 py-3 border-t border-sidebar-border"> <button onclick="toggleDarkMode()"> … </button> </div>` block (base.html ~155-162) is **deleted**.
- The `toggleSidebar()` JS and the mobile sidebar backdrop/transform behaviour must still work — the `<aside id="sidebar">` keeps its `fixed … lg:static …` classes; it just lives inside the new `[sidebar + content]` row instead of directly inside the old `h-screen` shell. Verify the mobile hamburger still opens/closes the sidebar.
- Don't break the `{% block ... %}` names (`title`, `head`, `page_help_slug`, `oss_status_anchor`, `breadcrumb`, `content`, `scripts`) — pages extend `base.html` and reference them.

### Tailwind / CSS build note

If you add new Tailwind utility classes (e.g. `h-dvh`, `w-full` if not already present), run `make css` to regenerate `dashboard/static/styles.css`. If `make css` reports "Nothing to be done" or fails (missing `postcss-selector-parser` in the worktree), append the equivalent **plain CSS** directly to `styles.css` per `CLAUDE.md` — it's served verbatim. Check whether `h-dvh` / `w-full` already exist in the committed `styles.css` before assuming you need a rebuild (`w-full` almost certainly already exists).

## Project Conventions

Read `dashboard/CLAUDE.md` and `CLAUDE.md`: Jinja2 `format`-filter must stay `%`-style; fragment templates under `templates/fragments/` must NOT extend `base.html`; plain CSS goes in `styles.css` when Tailwind can't recompile; `make lint` runs `scripts/check_templates.py` (Jinja2) and `node --check` on dashboard JS. Match the existing Tailwind class idioms in `base.html`.

## TDD Requirement

Follow Red-Green-Refactor where it applies. The behavioural surface is rendered-HTML structure (footer is a full-width sibling of the sidebar, theme toggle in the footer not the sidebar, shell uses a dynamic-viewport unit) and CSS-file content (pipeline-strip bottom padding, non-`--border` scrollbar thumb with hover + Firefox fallback). Before you restructure `base.html`, add at least one minimal failing assertion in `tests/dashboard/test_i00078_layout.py` (e.g. "the theme toggle is in the footer, not the sidebar") and make it pass. S03 (tests-impl) will round out the full test set — but do not ship the restructure with zero tests.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in files you touched:

1. `make format` — auto-fixes formatting drift; re-stage if it changes files.
2. `make typecheck` — zero errors involving your files (this change is template/CSS, so likely a no-op; note any pre-existing errors).
3. `make lint` — **includes `scripts/check_templates.py` (Jinja2) and `node --check` on dashboard JS** — both must pass with zero new violations.

Record results in the `preflight` object. If a tool is unavailable in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted test file you touched — **do NOT run the full suite** (`make test-unit` / `make test-integration` are downstream QV gates):

```bash
uv run pytest tests/dashboard/test_i00078_layout.py -v
```

Do not report `tests_passed: true` unless these pass with zero failures. If you can't run the dashboard tests in your worktree, note it in the report — don't run the full suite "to be safe".

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/base.html", "dashboard/static/theme.css", "dashboard/static/styles.css", "dashboard/templates/fragments/llm_usage_footer.html"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

- `completion_status`: `complete` when all four fixes are done and the targeted tests pass; `partial` if some remain; `blocked` if an external dependency prevents progress.
- `notes`: anything S02/S03 should know — e.g. whether `make css` ran or you appended plain CSS, exact class names you introduced.
