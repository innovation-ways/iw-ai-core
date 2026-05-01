# I-00057: Chat panel collapse toggle is intrusive and panel starts open

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-01
**Reported By**: sergio
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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Allowed for OPERATORS only (not agents):
  - uv run iw migrations apply --i-am-operator
  - ./ai-core.sh / make db-migrate

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The Code page's chat panel collapse toggle currently floats as an absolute-positioned vertical tab pinned to the middle of the chat panel slot's left edge, overlapping the architecture content. The panel also opens by default, taking screen real estate before the user has asked anything. This incident relocates the toggle into the chat panel itself (header when expanded, integrated rail when collapsed), defaults the panel to collapsed, and persists the user's preference globally via localStorage.

## Project Context

Read the project's `CLAUDE.md` (root) and `dashboard/CLAUDE.md`. The chat panel is part of the Code Understanding view (`/project/{id}/code`) and reused on related screens. Its template lives at `dashboard/templates/chat/panel.html` and its JS at `dashboard/static/chat/panel.js`.

## Browser Evidence

- `evidences/pre/I-00057-chat-toggle-light.png` — Code page in light mode showing the floating `>` tab in the middle of the architecture column where the chat panel meets the architecture panel.

The DOM snapshot taken during investigation shows the offending element at `#chat-toggle-tab`, positioned `absolute top-1/2 -translate-y-1/2` with `style="left: -48px;"` on the chat panel slot (`#chat-panel-slot`).

## Steps to Reproduce

1. Visit `http://iw-dev-01:9900/project/iw-ai-core/code`.
2. Observe the right-hand chat panel and the visible UI between the architecture column and the chat column.

**Expected**:
- The chat panel ships collapsed by default (slim vertical rail, ~48px wide).
- The collapse/expand control is part of the chat panel itself — header button when expanded, integrated rail affordance when collapsed.
- After the user expands or collapses the panel, the choice is remembered across page reloads and project navigations.

**Actual**:
- The chat panel is open by default, taking ~400px of horizontal space.
- The collapse control is a floating tab (`#chat-toggle-tab`) absolute-positioned at the vertical centre of the slot's left edge — it overlaps the reading area and looks like an unrelated stray UI fragment.
- Collapsed-state preference is not persisted across reloads (only width is).

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/code"
playwright-cli snapshot
# Initial state: panel collapsed, no floating left-edge tab anywhere
playwright-cli evaluate "(()=>{
  const panel = document.querySelector('#chat-panel');
  const floatingTab = document.querySelector('#chat-panel-slot > #chat-toggle-tab');
  return { collapsed: panel?.dataset.collapsed, floatingTabPresent: !!floatingTab };
})()"
```

Expect `{ collapsed: 'true', floatingTabPresent: false }`.

## Root Cause Analysis

Three issues, all in the chat panel surface:

1. **Toggle button placement** — `dashboard/templates/chat/panel.html:11-31` declares `<button id="chat-toggle-tab">` with classes `absolute top-1/2 -translate-y-1/2 z-50 ... left:-48px` (inline `style="left: -48px;"`). It lives inside the relative wrapper at `dashboard/templates/chat/panel.html:9` (`<div class="relative flex-1 min-h-0">`), pinning it to the middle of the slot's left edge — over the neighbouring column's content.

2. **Default open state** — `dashboard/templates/chat/panel.html:38` sets `data-collapsed="false"` on `#chat-panel`. The panel always renders open on first visit.

3. **No collapsed-state persistence** — `dashboard/static/chat/panel.js` reads/writes `localStorage['iw_chat_width']` for width but never reads/writes `iw_chat_collapsed`. Even if the user collapses, navigating to another page or reloading restores the open state.

The `applyCollapsedState(collapsed)` function in `panel.js` already toggles a 48px rail width via `--chat-width` and updates `panel.dataset.collapsed`. We do NOT need new collapsed-rail layout primitives — the rail mechanic already works. We need to (a) move the toggle out of the absolute-positioned slot and into the panel itself, (b) ensure the rail is the default visual, and (c) persist the choice.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/chat/panel.html` | Floating toggle tab; default-open state; rail layout markup absent inside the panel |
| `dashboard/static/chat/panel.js` | No localStorage read/write for collapsed preference |
| `dashboard/static/chat.css` | Lines 11-27 carry rules for `#chat-toggle-tab .chat-tab-icon / .chat-tab-label / .toggle-collapse-icon / .toggle-expand-icon` — become orphan CSS once the tab is deleted; must be removed |
| `dashboard/static/styles.css` | May regenerate via `make css` if new Tailwind classes are introduced |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | (a) Remove the absolute-positioned `#chat-toggle-tab` button from outside the chat panel; restructure `dashboard/templates/chat/panel.html` so the panel itself contains both the expanded header (title + small collapse chevron) AND a collapsed-rail body (icon + rotated "Chat" label + expand button). Use the existing `data-collapsed` mechanic + new CSS rules to swap visibility. (b) Default `data-collapsed="true"`. (c) `panel.js`: on load, read `localStorage['iw_chat_collapsed']` (default `"true"`); persist on every `togglePanel()`. | — |
| S02 | CodeReview_Frontend | Review S01 — markup correctness, no orphaned IDs, accessibility, persistence | — |
| S03 | Tests | Server-rendered HTML test: panel ships with `data-collapsed="true"`; no element with class chain matching the old absolute-positioned tab pattern (`absolute ... left: -48px`) outside the panel; an expand control exists inside the panel for both expanded and collapsed states. | — |
| S04 | CodeReview_Tests | Review S03 | — |
| S05 | CodeReview_Final | Cross-step review | — |
| S06..S10 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |
| S11 | QV Browser | Initial state collapsed; expand → state persists across reloads; collapse → state persists; no floating tab anywhere on the page | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `dashboard/templates/chat/panel.html`, `dashboard/static/chat/panel.js`, `dashboard/static/chat.css` (remove orphan `#chat-toggle-tab` rules), possibly `dashboard/static/styles.css` (regenerated)
- **Nature of change**: HTML restructure + JS persistence + dead-CSS removal; no Python.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00057_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00057_S01_Frontend_prompt.md` | Prompt | S01 implementation |
| `prompts/I-00057_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review |
| `prompts/I-00057_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00057_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review |
| `prompts/I-00057_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-step review |
| `prompts/I-00057_S11_BrowserVerification_prompt.md` | Prompt | S11 browser verification |
| `evidences/pre/I-00057-chat-toggle-light.png` | Evidence | Pre-fix screenshot |

## Test to Reproduce

The reproduction lives in `tests/dashboard/test_chat_panel_default_collapsed.py`:

```python
def test_i00057_chat_panel_ships_collapsed_and_no_floating_tab(client, db):
    """RED until I-00057 lands. Asserts the chat panel template ships with
    data-collapsed='true' and no absolute-positioned toggle tab leaks out
    of the panel."""
    project = make_project(db, "p")

    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200

    html = resp.text
    # Panel ships collapsed
    assert 'id="chat-panel"' in html
    assert 'data-collapsed="true"' in html
    # No absolute left:-48px toggle leaking out of the panel
    assert 'style="left: -48px;"' not in html
    # Expand affordance present inside the panel
    assert 'aria-label="Expand chat panel' in html or 'aria-label="Toggle chat panel' in html
```

## Acceptance Criteria

### AC1: Panel defaults to collapsed

```
Given a fresh browser visit to the Code page (no localStorage value for iw_chat_collapsed)
When the page loads
Then #chat-panel has data-collapsed="true" and renders as a slim ~48px rail
```

### AC2: No floating tab outside the panel

```
Given the Code page is rendered
When the response HTML is inspected
Then no toggle button uses the absolute "left: -48px" positioning pattern
And the only collapse/expand control lives inside #chat-panel
```

### AC3: Collapsed-state preference persists globally

```
Given the user toggles the chat panel state
When the user reloads the page or navigates to a different project's Code page
Then the panel reflects the previously chosen state (read from localStorage["iw_chat_collapsed"])
```

### AC4: Expand affordance visible when collapsed

```
Given the panel is collapsed (48px rail)
When the user looks at the panel
Then a chat icon, a rotated "Chat" label, and an expand chevron are visible
And clicking anywhere on the rail (or specifically the expand button) opens the panel
```

### AC5: Collapse affordance visible when expanded

```
Given the panel is expanded
When the user looks at the panel header
Then a small collapse button (chevron) is visible inside the header alongside the title
And clicking it collapses the panel
```

### AC6: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the dashboard test (default-collapsed + no-floating-tab) passes
```

## Regression Prevention

- Dashboard test pins the default-collapsed state so a future template edit cannot silently re-open the panel.
- Negative substring assertion (`'style="left: -48px;"' not in html`) prevents the floating-tab pattern from being reintroduced.
- The localStorage key (`iw_chat_collapsed`) sits next to the existing `iw_chat_width` key — same persistence pattern, easy to find for future edits.

## Dependencies

- **Depends on**: None.
- **Blocks**: None. (Independent of I-00055 and I-00056; can ship in any order.)

## TDD Approach

- Reproducing test: dashboard test asserting `data-collapsed="true"` and absence of the floating-tab pattern.
- Browser test (S11) covers JS-driven persistence (localStorage round-trip).
- No JS unit harness in this repo — JS behaviour is verified end-to-end through Playwright.

## Notes

- We considered persisting the collapsed state per-project (e.g. `iw_chat_collapsed:iw-ai-core`). Decided against — global is simpler, matches user intent ("don't show me the chat unless I ask for it"), and matches the existing `iw_chat_width` key style.
- We considered making the rail click anywhere expand the panel. Recommended: yes, the entire rail is clickable. The existing `applyCollapsedState` already updates `aria-label` so screen readers describe the affordance correctly.
- The `--chat-width` CSS variable already toggles between `48px` (collapsed) and the user's chosen width (320–480px) — no need to introduce new dimensions.
