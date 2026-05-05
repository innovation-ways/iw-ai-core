# I-00065: Code-view chat panel — "+ New" visible when collapsed and duplicates greeting

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-05
**Reported By**: sergio (manual UI inspection of `/project/{id}/code` chat panel)
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

This incident does not require any database migration. No alembic
commands of any kind should be run by the implementation agents.

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The AI chat panel inside the project Code view (`/project/{id}/code`) has two related defects: when the panel is collapsed to its rail icon, the "+ New" button is still rendered (it should only appear in the expanded panel header alongside the collapse chevron). And in the expanded panel, clicking "+ New" clears the chat history but appends a fresh "Ask about this module" greeting on top of the existing one, so N clicks stack N copies of the greeting block.

## Project Context

Read the project's `CLAUDE.md` (and `dashboard/CLAUDE.md`) for architecture, conventions, and hard rules. Specifically: the dashboard uses FastAPI + Jinja2 + htmx + prebuilt Tailwind CSS; chat panel markup lives under `dashboard/templates/chat/` and chat-panel JS under `dashboard/static/chat/`. No build step is needed for `panel.js` (plain JS, served as a static asset). If the CSS edit introduces any new Tailwind utility class, run `make css` to refresh `dashboard/static/styles.css` — the current fix only manipulates the existing `data-collapsed` style block, so `make css` is not required.

## Browser Evidence

Capturing pre-fix evidence is **deferred** — the dev environment was not started during incident creation. The bugs are trivial to reproduce manually (see Steps to Reproduce); the qv-browser step (S15) will produce the post-fix evidence in `ai-dev/active/I-00065/evidences/post/`.

## Steps to Reproduce

1. Open the dashboard at `http://localhost:9900/`.
2. Pick any registered project that has a code index built and click into it.
3. Open the project's "Code" tab → `/project/{id}/code`.
4. Wait for the chat panel on the right to render. By default it is **collapsed** (rail-only).
5. **Bug 1 observation**: Inspect the rail. The "+ New" button is visible inside the header above the rail icon, even though the rest of the chat header (title, collapse chevron, composer) is correctly hidden.
6. Click the rail (or `Cmd+\`) to **expand** the panel.
7. Click "+ New" in the header. The article bubbles disappear and the empty-state "Ask about this module / Try: …" greeting is rendered.
8. Click "+ New" again. A second copy of the greeting appears below the first.
9. **Bug 2 observation**: After N clicks, you see N "Ask about this module" greeting blocks stacked vertically.

**Expected**:
- Bug 1: The "+ New" button is hidden when `#chat-panel` has `data-collapsed="true"` — only the rail icon is visible.
- Bug 2: Clicking "+ New" results in **exactly one** "Ask about this module" greeting block being visible, regardless of how many times the button is clicked.

**Actual**:
- Bug 1: "+ New" remains visible in the rail.
- Bug 2: Each "+ New" click appends another greeting block; the count grows monotonically.

## Browser Verification Script

Reproduce in playwright-cli (post-login, navigated to the Code tab of a project with an indexed module):

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
# ... login and navigate to /project/{id}/code ...
playwright-cli snapshot                       # Should show #chat-new-btn HIDDEN when rail is collapsed
playwright-cli click <rail-element-ref>       # Expand
playwright-cli click <new-btn-ref>            # First click
playwright-cli click <new-btn-ref>            # Second click
playwright-cli click <new-btn-ref>            # Third click
playwright-cli snapshot                       # Should show EXACTLY ONE "Ask about this module" block
```

## Root Cause Analysis

Both bugs are localised to the chat panel's frontend assets — no backend, API, or database surface is involved.

**Bug 1 — `dashboard/templates/chat/panel.html:1-8`**

The `<style>` block at the top of the file enumerates which expanded-only header elements are hidden when `#chat-panel` is collapsed:

```html
#chat-panel[data-collapsed="true"] #chat-context-label,
#chat-panel[data-collapsed="true"] #chat-messages,
#chat-panel[data-collapsed="true"] #chat-scroll-to-bottom-wrap,
#chat-panel[data-collapsed="true"] #chat-composer,
#chat-panel[data-collapsed="true"] #chat-collapse-btn { display: none; }
```

`#chat-new-btn` (defined at lines 24-31 of the same template) is missing from this selector list, so the button stays in the DOM flow and remains visible inside the collapsed rail.

**Bug 2 — `dashboard/static/chat/panel.js:175-189` (`showEmptyState`)**

```javascript
function showEmptyState() {
  var messages = document.getElementById('chat-messages');
  if (!messages) return;
  // Remove all article bubbles but keep the scroll anchor
  var articles = messages.querySelectorAll('article');
  articles.forEach(function (a) { a.remove(); });
  var anchor = document.getElementById('chat-scroll-anchor');
  var empty = document.createElement('div');
  empty.id = 'chat-empty-state';
  empty.className = 'text-sm text-muted-foreground py-8 px-2 text-center space-y-2';
  empty.innerHTML = '<p class="font-medium text-foreground">Ask about this module</p>'
    + '<p>Try: <span class="font-mono">What does this component do?</span></p>'
    + '<p class="text-xs">Type <kbd class="px-1 py-0.5 rounded border border-border bg-muted">/</kbd> for commands</p>';
  messages.insertBefore(empty, anchor);
}
```

The function removes every `<article>` (chat bubble) but does **not** check for an existing `#chat-empty-state` element before creating a new one. The original empty-state from `panel.html:59-63` is in the DOM at page load with the same `id="chat-empty-state"`. Because `insertBefore` is used (not `replaceChild`), and because no removal of the prior `#chat-empty-state` happens, every "+ New" click leaves the previous greeting block in place and inserts a new sibling. Multiple elements with the same `id` is also an HTML correctness violation.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/chat/panel.html` (CSS hide-when-collapsed selector) | "+ New" button visible in collapsed rail |
| `dashboard/static/chat/panel.js` (`showEmptyState`) | Greeting block duplicates on every "+ New" click; multiple elements share `id="chat-empty-state"` |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Add `#chat-new-btn` to the collapsed-state hide selector in `panel.html`; in `panel.js` `showEmptyState`, remove any pre-existing `#chat-empty-state` before inserting the fresh one | — |
| S02 | CodeReview | Review S01 | — |
| S03 | Tests | Reproduction + regression tests (DOM assertions on the rendered template, plus a JS-level test of `showEmptyState` idempotency via `dashboard.TestClient` rendering and a small DOM simulation) | — |
| S04 | CodeReview | Review S03 | — |
| S05 | CodeReview_Final | Global cross-step review | — |
| S06 | SelfAssess | iw-item-analyze post-execution analysis (project has `self_assess = true`) | — |
| S07 | QV gate | `make lint` | — |
| S08 | QV gate | `make format-check` | — |
| S09 | QV gate | `make type-check` | — |
| S10 | QV gate | `make arch-check` | — |
| S11 | QV gate | `make security-sast` | — |
| S12 | QV gate | `make test-unit` | — |
| S13 | QV gate | `make test-frontend` | — |
| S14 | QV gate | `make test-integration` | — |
| S15 | QV browser | qv-browser end-to-end verification of both bugs against the per-worktree stack | — |

The `frontend-tsc` gate is intentionally omitted — the repo has no `frontend/` directory; that gate would fail unconditionally and stall the item.

Agent slugs: `frontend-impl`, `code-review-impl`, `tests-impl`, `code-review-final-impl`, `self-assess-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**:
  - `dashboard/templates/chat/panel.html` — add `#chat-new-btn` to the `[data-collapsed="true"]` hide selector
  - `dashboard/static/chat/panel.js` — in `showEmptyState`, remove any existing `#chat-empty-state` before inserting; reuse single source of truth for the greeting markup
- **New test files**:
  - `tests/dashboard/test_chat_panel_template.py` — assert the rendered `panel.html` includes `#chat-new-btn` inside the `[data-collapsed="true"]` hide rule
  - `tests/dashboard/test_chat_panel_empty_state.py` — JS-behavior unit test (Python-level DOM-snippet assertion via lxml/BeautifulSoup or, if simpler, a Node-style assertion using `node --check` is **not** suitable; use a Python parser to confirm the `showEmptyState` function source is idempotent by reading the JS file and asserting a guard against duplicate `#chat-empty-state`)

The Tests step has discretion on test mechanics; the contract is "assert both bugs cannot recur" — see Acceptance Criteria.

## File Manifest

All files for this work item live under `ai-dev/active/I-00065/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00065_Issue_Design.md` | Design | This document |
| `I-00065_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00065_S01_Frontend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00065_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00065_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00065_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00065_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00065_S06_SelfAssess_prompt.md` | Prompt | S06 self-assessment |
| `prompts/I-00065_S15_BrowserVerification_prompt.md` | Prompt | S15 browser verification |

Reports are created during execution in `ai-dev/active/I-00065/reports/`.

## Test to Reproduce

The Tests step writes the following two assertions (illustrative — exact mechanics are at the agent's discretion as long as both checks would FAIL against the pre-fix code and PASS against the fixed code):

```python
# tests/dashboard/test_chat_panel_template.py
from pathlib import Path

PANEL_HTML = Path("dashboard/templates/chat/panel.html").read_text()


def test_i00065_new_button_hidden_when_collapsed():
    """RED before fix: '#chat-new-btn' is NOT in the data-collapsed='true' hide selector,
    so the '+ New' button leaks into the collapsed rail.
    GREEN after fix: '#chat-new-btn' is part of the hide rule.
    """
    # Locate the hide rule block at the top of the template
    style_block = PANEL_HTML.split("</style>")[0]
    assert "#chat-panel[data-collapsed=\"true\"] #chat-new-btn" in style_block, (
        "Expected '#chat-new-btn' to be in the data-collapsed='true' hide selector "
        "so the New button is not visible in the collapsed rail."
    )
```

```python
# tests/dashboard/test_chat_panel_empty_state.py
from pathlib import Path

PANEL_JS = Path("dashboard/static/chat/panel.js").read_text()


def test_i00065_show_empty_state_removes_existing_before_insert():
    """RED before fix: showEmptyState only removes <article> elements, never removes
    a pre-existing #chat-empty-state, so each call appends a new greeting.
    GREEN after fix: showEmptyState explicitly removes any existing #chat-empty-state
    before inserting a fresh one.
    """
    # Find the showEmptyState function body
    start = PANEL_JS.index("function showEmptyState()")
    end = PANEL_JS.index("\n  }\n", start) + 4
    body = PANEL_JS[start:end]

    # The fix must remove any pre-existing #chat-empty-state before inserting
    assert "getElementById('chat-empty-state')" in body or \
           "querySelector('#chat-empty-state')" in body, (
        "showEmptyState must look up any existing #chat-empty-state element."
    )
    assert ".remove()" in body, (
        "showEmptyState must remove the pre-existing greeting block before inserting."
    )
```

The Tests agent is free to add stronger assertions (e.g. parsing the CSS selector list, snapshot-testing the function body) as long as the two underlying behaviors above are verified.

## Acceptance Criteria

### AC1: "+ New" hidden in collapsed rail

```
Given the user is on /project/{id}/code with the chat panel collapsed
When the page renders the chat panel rail
Then the "+ New" button is not visible (display: none via the data-collapsed style rule)
And the rail icon and rotated "Chat" label remain visible
```

### AC2: "+ New" produces exactly one greeting block

```
Given the chat panel is expanded and the user has had any chat history (or no history at all)
When the user clicks "+ New" any number of times in succession
Then exactly one "Ask about this module" greeting block is visible after each click
And there is never more than one DOM element with id="chat-empty-state" in #chat-messages
```

### AC3: Regression tests exist

```
Given the fix is applied
When the test suite runs
Then test_i00065_new_button_hidden_when_collapsed passes
And test_i00065_show_empty_state_removes_existing_before_insert passes
```

## Browser Verification Test

The S15 qv-browser step uses `playwright-cli` against the per-worktree stack to confirm both bugs end-to-end. See `prompts/I-00065_S15_BrowserVerification_prompt.md` for the V1..V3 verification script.

## Regression Prevention

- The Python-level template + JS-source assertions in `tests/dashboard/` will catch any future regression where someone removes `#chat-new-btn` from the hide selector or removes the pre-existing-element-removal call from `showEmptyState`.
- The `make test-frontend` (alias of `make test-dashboard`) gate runs every dashboard test in CI.
- The qv-browser step provides a live end-to-end backstop on every merge.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/chat/panel.html`
- `dashboard/static/chat/panel.js`
- `tests/dashboard/test_chat_panel_template.py`
- `tests/dashboard/test_chat_panel_empty_state.py`

## TDD Approach

- **Reproducing tests**: `test_i00065_new_button_hidden_when_collapsed` and `test_i00065_show_empty_state_removes_existing_before_insert` (both fail against the current code, pass after the fix).
- **Unit tests**: The two Python tests above are sufficient — the affected surface is purely declarative markup + a single small JS function; full DOM simulation is overkill.
- **Integration tests**: The qv-browser step replaces a heavier integration test by exercising the real rendered page in a per-worktree stack.

## Notes

- The fix scope is intentionally tiny. Do NOT refactor `showEmptyState`, do NOT introduce a Jinja2 macro for the empty-state markup, do NOT change the empty-state copy. The only behavioral changes are: (a) one CSS selector gets one new clause, (b) `showEmptyState` removes a pre-existing element before inserting.
- The `data-collapsed="true"` hide selector list is the single source of truth for "what is hidden in the rail" — keep it in alphabetical or DOM-order grouping when adding `#chat-new-btn`.
- The original `#chat-empty-state` markup in `panel.html:59-63` is intentionally retained as the page-load default. The JS fix only matters once the user clicks "+ New" at least once.
