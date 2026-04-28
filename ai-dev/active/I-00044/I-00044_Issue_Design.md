# I-00044: Code View Chat Panel — Ugly Collapse State and Viewport Drift

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-28
**Reported By**: Sergio (user report, normal use of code view)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The code view (`/project/{id}/code`) has two distinct UX defects in the chat panel.
**Bug 1**: When the chat is collapsed, the panel shrinks to a 48 px wide strip showing only
a bare `<` chevron — no label, no icon, no tooltip — making it visually unrecognisable and
impossible to expand without guessing. **Bug 2**: The chat panel shares the same scroll
container (`<main class="overflow-y-auto">`) as the left content column; when a long module
is selected (e.g. Orchestration Daemon), either the page scrolls automatically (via
`scrollIntoView()`) or the user must scroll manually, and the chat panel scrolls away with
the page, forcing the user to scroll all the way down to reach the composer and all the way
back up to read the response.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Key area: `dashboard/CLAUDE.md` — FastAPI + Jinja2 + htmx + Tailwind (pre-built via `make css`).
Critical rule: after editing templates that add new Tailwind classes, run `make css`.

## Browser Evidence

Screenshots captured during investigation on 2026-04-28:

| File | Shows |
|------|-------|
| `evidences/pre/I-00044-bug1-collapsed-state.png` | Bug 1 — collapsed panel with bare `<` chevron |
| `evidences/pre/I-00044-bug2-initial-state.png` | Bug 2 — initial two-column layout (chat visible, correct) |
| `evidences/pre/I-00044-bug2-module-chat-missing.png` | Bug 2 — after selecting Orchestration Daemon module; chat panel scrolled off |

## Steps to Reproduce

### Bug 1 — Ugly collapsed state

1. Navigate to `http://iw-dev-01:9900/project/iw-ai-core/code`.
2. Wait for the page to load (architecture map renders, chat panel appears on the right).
3. Click the `>` collapse button in the chat panel header.

**Expected**: The collapsed state clearly communicates "this is the chat panel — click to expand." A rotated "Chat" label or recognisable icon with an expand affordance should be visible.

**Actual**: The panel collapses to a 48 px strip showing only a bare `<` arrow. No label, no icon, no tooltip. The strip is indistinguishable from a page border to a new user.

### Bug 2 — Chat drifts with page scroll

1. Navigate to `http://iw-dev-01:9900/project/iw-ai-core/code`.
2. In the components list (below the architecture map), click **Orchestration Daemon**.
3. The module detail panel loads (long content). The page auto-scrolls via `scrollIntoView()`.
4. Observe the chat panel on the right.

**Expected**: The chat panel remains anchored to the visible viewport area — the left content column scrolls independently inside its own scroll container; the chat is always accessible without page-level scrolling.

**Actual**: The entire `#page-body` grid (both columns) scrolls within `<main>`. After the auto-scroll, the chat panel is above the fold. To type a question, the user must scroll to the bottom of the module content; to read the answer, the user must scroll back to the top. The composer and messages are never simultaneously visible with the module content.

## Browser Verification Script (reproduction)

```bash
playwright-cli kill-all
playwright-cli open http://iw-dev-01:9900/project/iw-ai-core/code
# Wait for page to load
playwright-cli screenshot  # shows correct initial two-column layout

# Bug 1: collapse the chat
playwright-cli snapshot    # get button ref
# click "Collapse chat panel (Cmd+\)" button
playwright-cli screenshot  # shows 48px strip with bare '<' chevron

# Bug 2: select a long module
playwright-cli snapshot    # get "Orchestration Daemon" link ref
playwright-cli click <orch-daemon-ref>
playwright-cli screenshot  # chat panel scrolled off, only content visible
```

## Root Cause Analysis

### Bug 1 — `dashboard/templates/chat/panel.html` + `dashboard/static/chat/panel.js`

The collapse button lives at `panel.html:26-32`. The style rule at `panel.html:1-7` hides
`#chat-context-label`, `#chat-messages`, `#chat-scroll-to-bottom-wrap`, and `#chat-composer`
when `data-collapsed="true"`. The header element itself (`<header>`) is **not** hidden, so
only the button remains visible. `panel.js:applyCollapsedState()` (lines 17-29) sets
`--chat-width` to `48px` and rotates the SVG arrow 180°. No text label, icon, or tooltip is
added to the collapsed strip, producing a meaningless bare chevron.

### Bug 2 — `dashboard/templates/project_code.html:106` + `dashboard/templates/base.html:172`

The `#page-body` grid is declared with:
```html
class="grid gap-0 lg:gap-4 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)] lg:h-[calc(100vh-12rem)]"
```
`lg:h-[calc(100vh-12rem)]` sets the grid **container** height. However, because no
`grid-template-rows` is specified, the single row auto-sizes to its **content** height. When
content in the left column is taller than `calc(100vh-12rem)`, the row (and the grid) exceeds
its container height. The grid overflows into `<main class="flex-1 overflow-y-auto ...">` at
`base.html:172`, which then scrolls — taking both columns (content AND chat) with it.

Two additional calls in `project_code.html` make this worse:
- Line 201: `panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' })` on `htmx:beforeRequest`
- Line 206: `e.detail.target.scrollIntoView({ block: 'nearest', behavior: 'smooth' })` on `htmx:afterSwap`

Both explicitly ask the browser to scroll `<main>` to reveal the detail panel, which pushes
the chat panel above the viewport fold.

**Fix**: Add `lg:grid-rows-[1fr]` to `#page-body`. This forces `grid-template-rows: 1fr`,
making the single row consume exactly the grid container height (`calc(100vh-12rem)`). Grid
items are constrained to this height; their children with `overflow-y-auto` scroll
internally. The `scrollIntoView()` calls now target content INSIDE the left column's
`overflow-y-auto` wrapper (the architecture card) and scroll only that column, not `<main>`.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Chat collapse toggle | `dashboard/templates/chat/panel.html:26-32` | Bug 1: collapsed UI has no affordance |
| Chat panel JS | `dashboard/static/chat/panel.js:17-29` | Bug 1: `applyCollapsedState()` only adjusts width and rotates arrow |
| Chat panel CSS | `dashboard/static/chat.css` | Bug 1: no styles for a meaningful collapsed state |
| Page body grid | `dashboard/templates/project_code.html:106` | Bug 2: missing `grid-template-rows` allows row to exceed container height |
| Main scroll container | `dashboard/templates/base.html:172` | Bug 2: `overflow-y-auto` on `<main>` scrolls the entire grid |
| Tailwind output | `dashboard/static/styles.css` | Must be rebuilt after template class changes (`make css`) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Fix both bugs; run `make css` | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Tests | Reproduction + regression tests (template rendering, no browser) | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Global cross-layer review | — |
| S06 | QV: lint | `make lint` | — |
| S07 | QV: format | `make format` | — |
| S08 | QV: typecheck | `make typecheck` | — |
| S09 | QV: unit-tests | `make test-unit` | — |
| S10 | QV: integration-tests | `make allure-integration` | — |
| S11 | QV: Browser | Playwright verification of both fixes | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — frontend-only fix

### Code Changes

**Bug 1 fix** (`dashboard/templates/chat/panel.html`, `dashboard/static/chat/panel.js`, `dashboard/static/chat.css`):

Replace the in-header `#chat-collapse-btn` with a slide-out toggle tab design (Option C).
The tab lives on the LEFT edge of `#chat-panel-slot`, is always visible regardless of
collapsed state, and carries a clear visual identity:

- **Expanded state**: The tab shows a compact collapse icon (e.g. `»` or `→`) with
  `aria-label="Collapse chat panel"`. The panel header no longer needs a collapse button.
- **Collapsed state**: The entire panel body shrinks/hides; the tab expands to show a
  recognisable vertical pill with a chat bubble icon and a rotated "Chat" label, plus an
  expand icon (`«` or `←`).
- The tab is positioned `absolute left-0 top-1/2 -translate-x-full -translate-y-1/2`
  (hanging off the LEFT edge of `#chat-panel-slot`), or alternatively integrated as a
  dedicated left-edge strip within the slot.
- `panel.js:applyCollapsedState()` updates the tab's aria-label and visual state.
- CSS for the tab goes in `chat.css`.

**Bug 2 fix** (`dashboard/templates/project_code.html:106`):

Add `lg:grid-rows-[1fr]` to `#page-body`:
```html
class="grid gap-0 lg:gap-4 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)]
       lg:h-[calc(100vh-12rem)] lg:grid-rows-[1fr]"
```

No other changes needed — the left column already has `overflow-y-auto` on its inner card,
and the chat panel already has `h-full` + internal scroll.

After all template/JS/CSS changes, run `make css` to rebuild `styles.css`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00044/I-00044_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00044/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/I-00044/prompts/I-00044_S01_Frontend_prompt.md` | Prompt | S01 fix instructions |
| `ai-dev/active/I-00044/prompts/I-00044_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review of S01 |
| `ai-dev/active/I-00044/prompts/I-00044_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `ai-dev/active/I-00044/prompts/I-00044_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `ai-dev/active/I-00044/prompts/I-00044_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `ai-dev/active/I-00044/prompts/I-00044_S11_BrowserVerification_prompt.md` | Prompt | S11 QV browser verification |
| `ai-dev/active/I-00044/evidences/pre/I-00044-bug1-collapsed-state.png` | Evidence | Bug 1 screenshot — bare chevron |
| `ai-dev/active/I-00044/evidences/pre/I-00044-bug2-initial-state.png` | Evidence | Bug 2 screenshot — correct initial layout |
| `ai-dev/active/I-00044/evidences/pre/I-00044-bug2-module-chat-missing.png` | Evidence | Bug 2 screenshot — chat scrolled off after module load |

## Test to Reproduce

```python
# tests/dashboard/test_i00044_chat_panel_layout.py
# These tests FAIL against pre-fix code and PASS after S01.

def test_i00044_bug2_page_body_has_grid_rows_1fr(jinja_env):
    """Bug 2: #page-body must have lg:grid-rows-[1fr] to constrain the
    grid row height and prevent <main> from scrolling."""
    mock_request = MagicMock()
    mock_request.url.path = "/project/iw-ai-core/code"
    tpl = jinja_env.get_template("project_code.html")
    html = tpl.render(
        current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
        index_status=None,
        running_job=None,
        last_completed_job=None,
        last_completed_recent=False,
        content_html="<p>x</p>",
        request=mock_request,
    )
    page_body_match = re.search(r'<div[^>]+id="page-body"[^>]*>', html)
    assert page_body_match, "#page-body must be present"
    assert "lg:grid-rows-[1fr]" in page_body_match.group(0), (
        "#page-body must have lg:grid-rows-[1fr] to constrain grid row "
        "height (I-00044 bug 2)"
    )


def test_i00044_bug1_collapse_toggle_has_chat_label(jinja_env):
    """Bug 1: the collapsed state must show a meaningful label (not just
    a bare chevron)."""
    tpl = jinja_env.get_template("chat/panel.html")
    html = tpl.render()
    # A visible "Chat" label must exist in the collapsed toggle affordance.
    assert "Chat" in html, (
        "The collapse toggle must include a visible 'Chat' label in the "
        "collapsed affordance (I-00044 bug 1)"
    )
    # The toggle must carry an accessible aria-label that mentions chat.
    assert 'aria-label' in html and 'chat' in html.lower(), (
        "Collapse toggle must have an aria-label referencing the chat panel "
        "(I-00044 bug 1)"
    )
```

## Acceptance Criteria

### AC1: Collapsed chat is visually recognisable

```
Given the user is on the code view page with the chat panel expanded
When the user clicks the collapse toggle
Then the collapsed state shows a clearly recognisable toggle tab with a
  chat bubble icon and a "Chat" label (rotated), and an expand icon —
  NOT a bare anonymous chevron
```

### AC2: Chat panel stays in viewport when left column scrolls

```
Given the user is on the code view page and selects the Orchestration Daemon module
When the module detail loads (with long content) and the left column scrolls
Then the chat panel remains visible in the right side of the viewport;
  the composer input is accessible without any page-level scrolling;
  the chat history is visible alongside the module content
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs (make test-unit)
Then tests/dashboard/test_i00044_chat_panel_layout.py passes:
  - test_i00044_bug2_page_body_has_grid_rows_1fr
  - test_i00044_bug1_collapse_toggle_has_chat_label
```

## Regression Prevention

- The template test `test_i00044_bug2_page_body_has_grid_rows_1fr` ensures no future
  refactor removes `lg:grid-rows-[1fr]` from `#page-body` silently.
- The template test `test_i00044_bug1_collapse_toggle_has_chat_label` ensures no future
  refactor strips the "Chat" label from the toggle affordance.
- A follow-up `make css` step in CI should be enforced for any PR touching dashboard
  templates with new Tailwind classes.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing tests**: `test_i00044_bug2_page_body_has_grid_rows_1fr` (fails before S01),
  `test_i00044_bug1_collapse_toggle_has_chat_label` (fails before S01)
- **Unit tests**: Jinja2 template rendering tests using the pattern from
  `tests/dashboard/test_code_layout_fixes.py` — no browser, no DB, fast
- **Integration tests**: Existing suite covers chat panel JS interactions implicitly;
  the QV Browser step (S11) provides the visual proof

## Notes

The existing `tests/dashboard/test_code_layout_fixes.py` (added for I-00033) is the
established pattern for template structure tests. S03 must follow the same Jinja2
fixture setup (`_template_dir()`, `jinja_env` fixture with stubbed filters/globals).

The `dashboard/static/styles.css` file is pre-built by Tailwind CLI. The Frontend agent
(S01) MUST run `make css` after template/JS/CSS changes so that new classes (especially
`lg:grid-rows-[1fr]` if not already in the generated output) are included. The rebuilt
`styles.css` must be committed.
