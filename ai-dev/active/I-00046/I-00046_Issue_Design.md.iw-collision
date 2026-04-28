# I-00046: Code view chat panel — toggle button clipped and viewport drift on module select

**Type**: Issue
**Severity**: High
**Created**: 2026-04-28
**Reported By**: User (post-merge regression after I-00044)
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

Migrations are not needed for this fix. No Alembic commands should be run.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

After I-00044 merged, two regressions are present on the Code view page.
First, the chat panel collapse toggle button is invisible and unclickable because the
outer `<aside id="chat-panel-slot">` has `lg:overflow-hidden` which clips the button
that is absolutely positioned at `left: -48px`.
Second, when a long module detail is loaded, the page height grows unboundedly and the
chat panel scrolls off-screen, because `#code-content-root` lacks `min-h-0` to constrain
it to its CSS grid row.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Dashboard is FastAPI +
Jinja2 + htmx + Tailwind CSS. The `make css` step rebuilds `dashboard/static/styles.css`
from templates — run it after adding new Tailwind classes. Code view templates are in
`dashboard/templates/project_code.html` and `dashboard/templates/chat/panel.html`.

## Browser Evidence

Screenshots captured with Playwright CLI on 2026-04-28:

- `ai-dev/active/I-00046/evidences/pre/I-00046_v0_initial_code_page.png` — initial state,
  toggle button invisible (should appear on left edge of chat panel)
- `ai-dev/active/I-00046/evidences/pre/I-00046_v1_module_selected_chat_gone.png` — after
  clicking "Orchestration Daemon" module; chat panel disappears from right side

## Steps to Reproduce

1. Navigate to `http://localhost:9900/project/iw-ai-core/code`
2. Observe the chat panel on the right — no collapse/expand toggle button is visible on
   its left edge (bug a)
3. Click any module link (e.g. "Orchestration Daemon") — the chat panel disappears from
   the right side and the content fills the full width (bug c, viewport drift)
4. With module detail visible, scroll the page — if the module content is long, the page
   grows taller than the viewport and the chat panel scrolls off-screen

**Expected**:
- A slide-out toggle button should be visible on the left edge of the chat panel at all
  times, allowing the user to collapse/expand it
- Selecting a module must not cause the page to grow beyond the viewport; the chat panel
  must remain anchored at the right side

**Actual**:
- Toggle button is clipped and invisible/unclickable
- Selecting a module causes the content column to expand the page height, pushing the
  chat panel out of view

## Root Cause Analysis

### Bug (a): Toggle button clipped by `overflow-hidden`

I-00044 introduced a new inner `<div id="chat-panel-slot" class="relative lg:overflow-visible">`
wrapper inside `dashboard/templates/chat/panel.html` (line 9). This wrapper contains the
absolutely-positioned toggle button at `style="left: -48px"`.

However, the outer container in `dashboard/templates/project_code.html` (line 123) is:
```html
<aside id="chat-panel-slot"
       class="lg:border-l lg:border-border flex flex-col lg:overflow-hidden"
       aria-label="Code module chat">
```

The `lg:overflow-hidden` on the `<aside>` clips everything that extends beyond its bounds.
The toggle button at `left: -48px` relative to the inner wrapper div extends 48px to the
left of the `<aside>` — it is clipped and invisible.

Additionally, I-00044 introduced a **duplicate `id="chat-panel-slot"`**: the outer `<aside>`
already has this ID, and `panel.html` wraps its content in a second `<div id="chat-panel-slot">`.
`panel.js` calls `document.getElementById('chat-panel-slot')` which returns the outer
`<aside>` (first match), so the JS is correct, but the duplicate is a DOM violation.

**Files**: `dashboard/templates/project_code.html:123`, `dashboard/templates/chat/panel.html:9`

### Bug (c): Page grows beyond viewport on module select

The grid in `project_code.html` (line 105-107) is:
```html
<div id="page-body"
     class="grid gap-0 lg:gap-4 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)]
            lg:h-[calc(100vh-12rem)] lg:grid-rows-[1fr]">
```

The grid has a defined height and a single `1fr` row. In CSS Grid, `1fr` rows can still
grow beyond their computed size because grid items default to `min-height: min-content`.
Without `min-h-0` on the grid children, a long module detail loaded into `#code-detail-panel`
(inside `code_architecture_view.html`) causes `#code-content-root` to expand the `1fr`
row beyond the viewport height, making the whole page scroll instead of the architecture
card's `overflow-y-auto` container.

**File**: `dashboard/templates/project_code.html:108` (`#code-content-root` missing `lg:min-h-0`)

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Chat panel toggle | `dashboard/templates/chat/panel.html:9-31` | Toggle button clipped, unusable |
| Code page aside | `dashboard/templates/project_code.html:123-127` | `overflow-hidden` clips toggle; missing `min-h-0` causes aside to grow |
| Code content root | `dashboard/templates/project_code.html:108-120` | Missing `min-h-0` lets column grow grid row |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Fix templates: remove duplicate ID, fix overflow, add min-h-0 | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Tests | Write reproduction + regression tests | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06 | QV lint | `make lint` | — |
| S07 | QV format | `make format` | — |
| S08 | QV typecheck | `make typecheck` | — |
| S09 | QV unit-tests | `make test-unit` | — |
| S10 | QV integration-tests | `make allure-integration` | — |
| S11 | QV Browser | Browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None required

### Code Changes

**`dashboard/templates/project_code.html`** — two targeted changes:
1. `#code-content-root` (line 108): add `class="lg:min-h-0"` so the grid item respects the row's `1fr` size
2. `<aside id="chat-panel-slot">` (line 123): remove `lg:overflow-hidden`, add `lg:min-h-0`
   so the toggle button is no longer clipped and the aside respects its grid row size

**`dashboard/templates/chat/panel.html`** — one targeted change:
1. Line 9: change `<div id="chat-panel-slot" class="relative lg:overflow-visible">` to
   `<div class="relative flex-1 min-h-0">` — removes the duplicate ID and adds `flex-1`
   so the wrapper fills the aside's height

**`dashboard/static/styles.css`** — rebuild via `make css` after template changes if new
Tailwind utility classes are introduced (check if `min-h-0`, `flex-1` are already present).

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00046_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00046_S01_Frontend_prompt.md` | Prompt | S01 template fix |
| `prompts/I-00046_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00046_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00046_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00046_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00046_S11_BrowserVerification_prompt.md` | Prompt | S11 browser QV |

QV gate steps (S06–S10) are script-driven — no prompt files needed.

## Test to Reproduce

```python
# tests/dashboard/test_chat_panel_layout_i00046.py

def test_i00046_no_duplicate_chat_panel_slot_id(jinja_env):
    """Duplicate id='chat-panel-slot' must not appear in rendered HTML.

    FAILS before fix (panel.html wraps content in <div id='chat-panel-slot'>).
    PASSES after fix (inner wrapper no longer has that ID).
    """
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
    count = html.count('id="chat-panel-slot"')
    assert count == 1, (
        f"Expected exactly 1 element with id='chat-panel-slot', found {count}. "
        "I-00044 introduced a duplicate id in panel.html — I-00046 fix removes it."
    )


def test_i00046_aside_no_overflow_hidden(jinja_env):
    """The <aside id='chat-panel-slot'> must NOT have overflow-hidden.

    FAILS before fix (aside has lg:overflow-hidden which clips the toggle button).
    PASSES after fix (overflow-hidden removed).
    """
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
    aside_match = re.search(r'<aside[^>]+id="chat-panel-slot"[^>]*>', html)
    assert aside_match, "Could not find <aside id='chat-panel-slot'> in rendered HTML"
    aside_tag = aside_match.group(0)
    assert "overflow-hidden" not in aside_tag, (
        "<aside id='chat-panel-slot'> must not have overflow-hidden — "
        "it clips the toggle button at left:-48px (I-00046 bug a)"
    )


def test_i00046_code_content_root_has_min_h_0(jinja_env):
    """#code-content-root must have lg:min-h-0 to contain grid row height.

    FAILS before fix (no min-h-0, grid item can grow beyond 1fr row).
    PASSES after fix.
    """
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
    root_match = re.search(r'<div[^>]+id="code-content-root"[^>]*>', html)
    assert root_match, "Could not find #code-content-root in rendered HTML"
    assert "min-h-0" in root_match.group(0), (
        "#code-content-root must have min-h-0 so the CSS grid 1fr row is not "
        "expanded by module detail content (I-00046 bug c)"
    )
```

## Acceptance Criteria

### AC1: Toggle button is visible and clickable

```
Given the user navigates to /project/{id}/code
When the chat panel is visible on desktop
Then a collapse/expand toggle button is visible on the left edge of the chat panel
And clicking it collapses/expands the panel
```

### AC2: Page height is bounded when a module is selected

```
Given the user is on the Code view page
When they click on any module to load its detail
Then the page does not grow taller than the viewport
And the chat panel remains visible on the right side
```

### AC3: Regression test exists

```
Given the fix is applied
When the unit test suite runs
Then test_i00046_no_duplicate_chat_panel_slot_id passes
And test_i00046_aside_no_overflow_hidden passes
And test_i00046_code_content_root_has_min_h_0 passes
```

## Regression Prevention

- Template tests in `tests/dashboard/` now structurally verify the `<aside>` overflow
  property and the absence of duplicate IDs — these will catch any future regression
  that reintroduces `overflow-hidden` or a duplicate `chat-panel-slot` ID.
- `min-h-0` is a standard CSS Grid containment pattern; documenting it in the test
  assertions makes the constraint explicit and enforced.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- Reproducing tests: `tests/dashboard/test_chat_panel_layout_i00046.py` — all three
  tests FAIL against pre-fix templates, PASS after fix
- Unit tests: Template structural tests (Jinja rendering, no browser required)
- Integration tests: Existing integration suite must remain green

## Notes

- `make css` must be run after template changes if new Tailwind classes are introduced
  (e.g. `flex-1` or `min-h-0`). The agent must check if these classes already exist in
  `dashboard/static/styles.css` before rebuilding.
- The `panelSlot` variable in `panel.js` is declared but never used — this is pre-existing
  dead code and is out of scope for this fix.
- The CSS collapse rules in `panel.html`'s `<style>` block target `#chat-panel[data-collapsed]`
  — these remain correct after the wrapper div's ID is removed.
- Bugs are labeled **(a)** and **(c)** throughout this document. Label **(b)** was skipped
  because an intermediate DOM nesting inconsistency was considered during triage but ruled
  out as a separate concern (the duplicate ID is treated as part of bug (a) rather than a
  distinct bug). Agents should treat (a) and (c) as the two independent bugs to fix.
