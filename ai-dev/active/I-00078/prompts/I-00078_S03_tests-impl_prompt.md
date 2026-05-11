# I-00078_S03_tests-impl_prompt

**Work Item**: I-00078 — Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00078 --json`.
- `ai-dev/active/I-00078/I-00078_Issue_Design.md` — design document (read `## Test to Reproduce`, `## Acceptance Criteria`, `## TDD Approach` in full)
- `ai-dev/active/I-00078/reports/I-00078_S01_frontend-impl_report.md` — what S01 changed, and any class names it introduced
- `dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html` — the (now fixed) files under test
- `tests/dashboard/conftest.py` — the `client` fixture (and how existing dashboard tests are written) — look at e.g. `tests/dashboard/test_docs_running_jobs.py` for the style
- `tests/CLAUDE.md`, `dashboard/CLAUDE.md`, `CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S03_tests-impl_report.md` — step report
- `tests/dashboard/test_i00078_layout.py` — the reproduction + regression test file (create or extend it; S01 may have seeded a minimal version)

## Context

You are writing the reproduction + regression tests for I-00078. The bug (pre-S01) was: dark-mode scrollbars painted with `var(--border)` (invisible); `.iw-pipeline-strip` had no `padding-bottom`; the app shell used `h-screen` (`100vh`) causing a second body scrollbar that hid the footer; the `<footer>` was nested inside the main content column (not full-width) and the "Toggle theme" button lived in the sidebar. S01 has fixed all four. Your tests must FAIL against the pre-fix code and PASS against the current (fixed) code.

**Test-file location** — `tests/dashboard/test_i00078_layout.py`. These tests render `base.html` via the `client` fixture, which is registered only in `tests/dashboard/conftest.py`; a test placed under `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found` (I-00067). The CSS-file assertions read `dashboard/static/theme.css` / `styles.css` directly — no fixture needed, but keep them in the same file for cohesion.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed — but the bug was NOT fixed. Tests must verify SPECIFIC structure/values, not mere presence of a word:

- BAD: `assert "footer" in html` (shape only — `<footer>` always existed)
- BAD: `assert "padding-bottom" in css` (somewhere in 67 KB of CSS — meaningless)
- GOOD: `assert html.index("<footer") > html.index("</aside>")` (semantic — footer comes after the sidebar closes)
- GOOD: parse the `.iw-pipeline-strip { ... }` block specifically and assert *that block* declares `padding-bottom` with a non-zero value
- GOOD: `assert "var(--border)" not in <the ::-webkit-scrollbar-thumb block>` (semantic — the unwanted value is absent from the right rule)

## Requirements — tests to write (cover every AC)

Create `tests/dashboard/test_i00078_layout.py` with at least the following. Use the design doc's `## Test to Reproduce` block as the starting point; refine it to match the class names S01 actually used (read the S01 report / the files), but keep every semantic check.

1. **`test_i00078_footer_is_full_width_sibling_of_sidebar(client)`** — render `/` (or another page that extends `base.html`); assert `<footer ...>` appears *after* `</aside>` in the HTML, and the `<footer>` opening tag carries a full-width class (attribute-scoped: `re.search(r'class="[^"]*\bw-full\b[^"]*"', footer_tag)` — or whatever full-width class S01 used; check the S01 report). Also assert the old `<div class="flex h-screen overflow-hidden">` shell wrapper string is **absent**. (AC3, AC4)

2. **`test_i00078_theme_toggle_in_footer_not_sidebar(client)`** — slice out the `<aside id="sidebar"> … </aside>` substring and assert `"toggleDarkMode()" not in sidebar_html`; slice out `<footer> … </footer>` and assert `"toggleDarkMode()" in footer_html`. (AC4)

3. **`test_i00078_theme_toggle_outside_htmx_swap_target(client)`** — within the `<footer> … </footer>` slice, assert the element carrying `hx-swap="innerHTML"` (the meters container) does **not** contain `toggleDarkMode()` — i.e. the toggle is a static sibling, not inside the swapped sub-tree. (Regression guard for the "poll wipes the toggle" failure mode.) A reasonable approach: find the substring from `hx-get="/api/usage/llm/fragment"` to the next `</div>` and assert `toggleDarkMode()` is not in it; or assert the `toggleDarkMode()` button appears *before* the `hx-get=...` attribute in the footer slice.

4. **`test_i00078_shell_uses_dynamic_viewport_height(client)`** — render `/`; assert `"h-dvh" in html or "100dvh" in html`; assert `'class="flex h-screen overflow-hidden"' not in html` (the old fixed-viewport shell is gone). (AC3) — per the S01 prompt the shell element carries the literal `h-dvh` class (S01 appends `.h-dvh{height:100dvh}` to `styles.css` if the prebuilt file lacks it), so this token-in-HTML check is the right shape. If the S01 report shows the shell uses a *different* mechanism, follow what S01 actually did but still assert the dynamic-viewport unit is in effect (e.g. read `styles.css` and confirm the shell element's class declares `height: 100dvh`) — do not drop the check.

5. **`test_i00078_only_main_is_the_scroller(client)`** — render `/`; assert the `<main ...>` tag carries `overflow-y-auto` (attribute-scoped); and that the `<body>` / shell wrapper carries `overflow-hidden`. (Sanity that there's one designated content scroller. Note the sidebar `<aside>` also has its own `overflow-y-auto` — that's fine and separate; don't assert it's absent.)

6. **`test_i00078_pipeline_strip_has_scrollbar_spacing()`** — read `dashboard/static/styles.css`; `re.search(r"\.iw-pipeline-strip\s*\{([^}]*)\}", css)` must match; assert that block declares `padding-bottom` (or `padding:` shorthand) with a value that isn't `0`. (AC2)

7. **`test_i00078_dark_scrollbar_high_contrast_thumb()`** — read `dashboard/static/theme.css`; find the `::-webkit-scrollbar-thumb { ... }` block; assert `"var(--border)" not in` that block; assert `"::-webkit-scrollbar-thumb:hover"` appears in the file; assert both `"scrollbar-color"` and `"scrollbar-width"` appear in the file (Firefox fallback). Optionally assert a `--scrollbar-thumb` custom property is defined in both the `:root` and `.dark` rule bodies. (AC1)

8. **`test_i00078_theme_toggle_still_wired(client)`** — assert the footer's toggle button still has `onclick="toggleDarkMode()"` and there is exactly one `id="theme-icon"` element in the page (`html.count('id="theme-icon"') == 1`). (AC4 — the toggle still works after the move.)

If S01 used different class names than the design doc's illustrative ones, follow what S01 actually did — but every *semantic* invariant above is mandatory. Do not weaken a check to "make it pass" — if a check genuinely can't pass against the current code, that's a real finding: report it as a blocker rather than deleting the assertion.

## Project Conventions

Read `tests/CLAUDE.md`: no live DB (port 5433) in tests; the `client` fixture comes from `tests/dashboard/conftest.py`; testcontainers only for DB-backed tests (not needed here). Match the style of existing `tests/dashboard/test_*.py` files. Use `encoding="utf-8"` when opening CSS files.

## TDD Requirement

These tests are the RED→GREEN proof for I-00078. They must fail against pre-S01 `base.html` / `theme.css` / `styles.css` and pass now. You do **not** need to revert source files to "prove RED" — that was done at design time. Just write tests whose assertions clearly target the pre-fix conditions described above.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in the test file you wrote:

1. `make format`
2. `make typecheck` (likely no-op for a test file; note pre-existing errors)
3. `make lint`

Record results in `preflight`.

## Test Verification (NON-NEGOTIABLE)

Run **only** the new test file — do NOT run `make test-integration` or `make test-unit` (those are downstream QV gates S09/S10; running them here burns the step budget — see I-00073/S03 post-mortem):

```bash
uv run pytest tests/dashboard/test_i00078_layout.py -v
```

All assertions must pass with zero failures. Do not report `tests_passed: true` otherwise.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_i00078_layout.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
