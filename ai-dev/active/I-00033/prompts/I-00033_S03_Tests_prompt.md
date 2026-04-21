# I-00033_S03_Tests_prompt

**Work Item**: I-00033 — Code view layout bugs
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` — Design document (especially the "Test to Reproduce" section)
- `ai-dev/active/I-00033/reports/I-00033_S01_Frontend_report.md` — S01 report (for the exact attributes/classes S01 wrote)
- `ai-dev/active/I-00033/reports/I-00033_S02_CodeReview_report.md` — S02 review (must be `pass`)
- `dashboard/templates/fragments/code_job_report.html` — post-S01
- `dashboard/templates/project_code.html` — post-S01
- `dashboard/templates/fragments/code_architecture_view.html` — post-S01
- `dashboard/static/chat/panel.js` — post-S01
- `tests/dashboard/browser/test_chat_panel_smoke.py` — existing browser smoke to model the new test after (same `dashboard_server` + `playwright_session` pattern)
- `tests/CLAUDE.md` — testing rules
- `dashboard/CLAUDE.md` — dashboard conventions

## Output Files

- **Created**: `tests/dashboard/test_code_layout_fixes.py` — three Jinja render reproduction tests (no browser)
- **Created**: `tests/dashboard/browser/test_code_layout_fixes.py` — three Playwright browser smoke tests
- **Report**: `ai-dev/active/I-00033/reports/I-00033_S03_Tests_report.md`

## Context

S01 applied three fixes to the Code view. Your job:

1. Write **Jinja render tests** that assert the template structure produced by S01 is correct (fast, no browser needed). These run in the normal pytest suite.
2. Write **Playwright browser smoke tests** that exercise the end-to-end behavior (dismissal persistence across reload, CSS-variable propagation on collapse, scroll container location). These run under `@pytest.mark.browser` and boot a real dashboard via Uvicorn.

All tests MUST verify **specific values** — not shape-only. See the "Semantic Correctness" section below.

## Requirements

### 1. Jinja render tests — `tests/dashboard/test_code_layout_fixes.py`

Model closely on the scaffold in the design doc's "Test to Reproduce" section. You should end up with exactly three tests:

#### Test 1: `test_last_run_banner_has_dismiss_button`

Renders `fragments/code_job_report.html` with a mock `last_completed_job` (id=12345), `last_completed_duration`, and `current_project` (id="iw-ai-core"). Asserts:

- `'data-dismiss-job-id="12345"' in html` — the specific job id is present as an attribute value.
- `'data-project-id="iw-ai-core"' in html` — the specific project id is present.
- `'aria-label="Dismiss last-run banner"' in html` — the accessibility label matches.
- The dismissal key `iw_code_lastrun_dismissed` appears in the rendered output (either literal in the inline script or referenced via a script tag if S01 extracted to a `.js` file — check S01's report to know which).

**Semantic correctness**: these assertions verify the SPECIFIC values that make dismissal work. Do NOT write `assert "data-dismiss-job-id" in html` — that passes even if the attribute is hardcoded to the wrong id.

#### Test 2: `test_code_content_root_does_not_own_scroll`

Renders `project_code.html` with a minimal context. Asserts:

- The opening tag of `#code-content-root` does NOT contain `overflow-y-auto`.
- `#page-body` contains `lg:gap-4` (the new gutter class).

**Semantic correctness**: do NOT check "does the page render" — you must check the specific class is gone from a specific element.

#### Test 3: `test_architecture_card_owns_scroll`

Renders `fragments/code_architecture_view.html`. Asserts:

- The root `<div>` (card) contains BOTH `overflow-y-auto` AND `h-full` in its `class` attribute.
- The root `<div>` does NOT contain `overflow-hidden` (S01 removes it — the presence of both `overflow-hidden` and `overflow-y-auto` on the same element is a broken state).
- Without `h-full`, the fix is broken (the card grows to fit content, no scrollbar).

**Semantic correctness**: do NOT use `html.strip().splitlines()[0]` — that is fragile to template reformatting. Extract the root div's `class` attribute with a regex against the full rendered HTML, e.g.:

```python
import re

m = re.search(r'<div\\s+[^>]*class="([^"]*)"', html)
assert m, "No <div> with a class attribute found in code_architecture_view.html render"
root_classes = m.group(1).split()
assert "overflow-y-auto" in root_classes, (
    "Architecture card root must own the scroll container (I-00033 bug 2)"
)
assert "h-full" in root_classes, (
    "Architecture card root must have h-full so overflow-y-auto has a container "
    "(I-00033 bug 2 — without a definite height, no scrollbar appears)"
)
assert "overflow-hidden" not in root_classes, (
    "overflow-hidden must be removed from the card root (I-00033 bug 2 — it conflicts with overflow-y-auto)"
)
```

Failure messages must reference I-00033 and explain *why* each class is required, not just "missing class".

#### Fixture setup

Use a module-scoped `jinja_env` fixture that loads templates from `dashboard/templates/`. Do NOT instantiate the full FastAPI app; these are template-level tests. The existing `tests/dashboard/test_chat_templates.py` may have a reusable fixture — check and reuse, or extract to `tests/dashboard/conftest.py` if cleaner. Do not duplicate fixture bodies.

#### Minimal context for `project_code.html`

The template references `current_project`, `index_status`, `running_job`, `last_completed_job`, `last_completed_recent`, `content_html`. Render with safe defaults:

```python
html = tpl.render(
    current_project=types.SimpleNamespace(id="iw-ai-core", display_name="IW"),
    index_status=None,
    running_job=None,
    last_completed_job=None,
    last_completed_recent=False,
    content_html="<p>x</p>",
)
```

If `project_code.html` extends `base.html` and `base.html` requires additional context vars, add them (read `base.html` to confirm). The goal is a clean render — any Jinja error in the test setup is a test bug, not a production bug.

### 2. Playwright browser smoke — `tests/dashboard/browser/test_code_layout_fixes.py`

Model after `tests/dashboard/browser/test_chat_panel_smoke.py`. Reuse the module-scoped `dashboard_server` and `playwright_session` fixtures — **extract them to `tests/dashboard/browser/conftest.py`** if they aren't already there, and import from conftest in both test files. This avoids duplicated Uvicorn boot logic.

Marker: `@pytest.mark.browser` (module-level via `pytestmark = pytest.mark.browser` is cleanest). Run with `uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser -v`.

#### Test 1: `test_bug1_last_run_banner_dismissal_persists`

1. Open the Code page (assume `last_completed_job` exists in the fixture — see "E2E data" below).
2. `playwright-cli snapshot` — find the close button by its `aria-label`.
3. Click it.
4. Assert the banner's root (`#code-last-run-banner`) is `display: none` (via `playwright-cli run-code getComputedStyle(document.getElementById('code-last-run-banner')).display === 'none'`).
5. Reload (`playwright-cli reload`).
6. Re-snapshot. Assert the banner element either is absent from the accessible tree OR has `display: none`.
7. (Optional) Flip the localStorage to a different job id via `playwright-cli run-code localStorage.setItem('iw_code_lastrun_dismissed:iw-ai-core', '999999')`, reload, confirm the banner reappears (because the stored id no longer matches).

#### Test 2: `test_bug2_scroll_container_is_architecture_card`

1. Open the Code page.
2. Use `playwright-cli run-code` with a small JS snippet that walks up from `.prose-doc` and finds the nearest ancestor with `overflowY: auto`. Return its id and className.
3. Assert the returned element:
   - id is NOT `code-content-root` (the old scroll container).
   - className contains `bg-card` (the Architecture card's class).

Example JS:
```javascript
(function(){
  var p = document.querySelector('.prose-doc');
  var e = p;
  while (e) {
    if (getComputedStyle(e).overflowY === 'auto') return (e.id || '') + '|' + e.className;
    e = e.parentElement;
  }
  return 'NONE';
})()
```

Parse the return value (stdout from `playwright-cli run-code`) and assert semantically.

#### Test 3: `test_bug3_chat_collapse_shrinks_grid_track`

1. Open the Code page.
2. Read the initial `--chat-width` — should be the default (400px or whatever the module sets).
3. Click the chat-collapse button (snapshot first to find its ref).
4. Read `getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()` — MUST equal `"48px"`.
5. Measure `document.getElementById('code-content-root').getBoundingClientRect().width` before and after — the text column MUST be wider after collapse (by approximately `savedChatWidth - 48` px, with some slack for border/gap).
6. Click collapse again (expand). Assert `--chat-width` is restored to the saved value (read `localStorage.iw_chat_width` to know the expected value; default 400).

### 3. Semantic correctness (I003 lesson — MANDATORY)

I003's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Your tests must verify SPECIFIC VALUES:

- BAD: `assert "data-dismiss-job-id" in html` (presence only — passes with wrong id)
- GOOD: `assert 'data-dismiss-job-id="12345"' in html` (specific value — only passes when the id renders correctly)

- BAD: `assert el.style.width` (truthy check — passes with any value)
- GOOD: `assert getComputedStyle(el).getPropertyValue('--chat-width').trim() == '48px'` (specific value)

- BAD: `assert 'overflow-y-auto' in html` (presence only — passes even if on the wrong element)
- GOOD: `assert 'overflow-y-auto' NOT in root_tag_of_code_content_root` (specific absence)

Apply this discipline to every assertion.

### 4. Test teardown: localStorage cleanup

Browser tests leave state in the playwright-cli session's storage. In the module-scoped fixture teardown (or a per-test autouse fixture), clear localStorage:

```bash
playwright-cli -s=$SESSION run-code "localStorage.clear()"
```

Otherwise test 1's dismissal bleeds into test 2/3 and changes the DOM.

### 5. E2E data — how to make the banner appear

The Playwright smoke needs `last_completed_job` to be truthy in the `code_ui.py` context. Two approaches:

1. **Preferred**: use the `iw-ai-core` project which has real completed jobs in the dev DB. If your `dashboard_server` fixture connects to a fresh testcontainer with no data, this won't work.
2. **Fallback**: seed a `CodeIndexJob` row via SQLAlchemy in the fixture setup (the existing `test_chat_panel_smoke.py` fixture may already do something similar — check). Seed: a `Project` row (iw-ai-core), one `CodeIndexJob` with `status='completed'`, `completed_at=datetime.now(UTC) - timedelta(minutes=5)` (within the 1h window), `files_indexed=10`, `chunks_created=100`.

Read `test_chat_panel_smoke.py` first — it may already bootstrap the project and enough context for the Code page to render.

If seeding is non-trivial and `test_chat_panel_smoke.py` doesn't already handle it, call it out in your report and **describe the exact fixture you added**. Do not skip the test silently.

## Project Conventions

Read `tests/CLAUDE.md`:

- **NEVER** connect to live DB — use testcontainers. The existing browser smoke fixture already handles this via `dashboard_server`.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` / `setenv()`.
- **Tests MUST NOT append to tracked config files** (per I-00032's rule). You don't write any config files here, so this is just a cross-reference.
- Browser tests MUST use `playwright-cli` exclusively — never `agent-browser`, never `chromium.launch()`, never `npx playwright install`.

## TDD Requirement

1. **RED**: Before running S01's changes, the tests must fail. Since S01 already landed by the time S03 runs, you verify RED by: (a) running the tests first — they should all pass; (b) temporarily `git stash` S01's changes; (c) re-run — they should all fail; (d) `git stash pop`; (e) re-run — all pass. Record this in your report.
   - If you cannot stash cleanly (some files have other uncommitted changes), trace by hand: read the pre-S01 versions from git, show in your report why each assertion would fail against them.
2. **GREEN**: With S01 applied, all tests pass — both the render tests and the browser smoke.
3. **REFACTOR**: If the `playwright-cli run-code` patterns repeat, extract helpers into `tests/dashboard/browser/conftest.py` (e.g., `pw_eval(session, code)` / `pw_snapshot(session)`).

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `uv run pytest tests/dashboard/test_code_layout_fixes.py -v` — 3 passed.
2. Run `uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser -v` — 3 passed. (If the dashboard_server fixture cannot bootstrap the required job data, describe the blocker and mark as `partial` — do NOT silently skip.)
3. Run `uv run ruff check tests/` — clean.
4. Run `uv run ruff format --check tests/` — clean.
5. Do **NOT** report `tests_passed: true` unless the above exit 0 (browser tests may skip if environment unavailable — document in `test_summary`).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00033",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_code_layout_fixes.py",
    "tests/dashboard/browser/test_code_layout_fixes.py",
    "tests/dashboard/browser/conftest.py"
  ],
  "tests_passed": true,
  "test_summary": "3 render tests passed, 3 browser tests passed; RED phase verified via git stash of S01 (all 6 failed); ruff clean",
  "blockers": [],
  "notes": "Describe: (a) whether dashboard_server needed seeding for last_completed_job, and if so what fixture you added; (b) whether conftest.py was created vs modified; (c) RED-phase verification method (stash vs read-git-history)."
}
```
