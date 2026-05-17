# I-00089: AI Assistant panel — in-header collapse button is unusable in both states

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (manual dashboard exploration)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This item does NOT execute any docker commands.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged — no schema or alembic work.

## Description

The collapse / expand affordance for the dashboard's AI Assistant chat panel is broken in both states.

- **Bug A — collapsed state**: a "<" collapse-button icon is still rendered at the top-left of the 40-pixel-wide panel rail when `data-collapsed="true"`. Clicking it is a no-op (the JS handler calls `close()` against an already-closed panel) and it visually competes with the "AI Assistant" expand rail directly below it.
- **Bug B — expanded state**: the "<" collapse button is present in the expanded header DOM and works programmatically, but it is rendered as one of four 14-pixel-tall icons crammed alongside a `flex-1` title and a 90-pixel-wide model dropdown inside a 360-pixel panel. Users cannot visually find a target to collapse the panel; the affordance has no weight relative to the surrounding controls.

Ctrl+/ and the nav-bar toggle button still work, so the panel is reachable — but the in-panel header buttons are unusable as collapse/expand controls.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Relevant constraints for this incident:

- Tailwind CSS is prebuilt via `make css` from `dashboard/templates/**/*.html` and `dashboard/static/**/*.js`. Run it after editing templates that add new Tailwind classes.
- Plain CSS may be appended directly to `dashboard/static/styles.css` when the Tailwind toolchain is unavailable in the worktree (see I-00067). For this incident the cleanest path is the scoped `<style>` block already inside `panel.html` plus the existing `dashboard/static/chat_assistant/chat.css`, which keeps the change isolated and avoids triggering a Tailwind rebuild.
- Browser verification uses `playwright-cli` exclusively. NEVER use `agent-browser` or `chromium.launch()` directly.

## Browser Evidence

Pre-fix evidence captured during incident intake (panel is included on every dashboard page via the chat_assistant include — root `/` is sufficient):

| File | Shows |
|------|-------|
| `evidences/pre/I-00089-bug-A-collapsed-stray-button.png` | "<" collapse button visible at top-left of the 40 px rail while panel is collapsed (Bug A). |
| `evidences/pre/I-00089-bug-A-collapsed-snapshot.yml` | DOM snapshot of collapsed state — both `Collapse AI Assistant panel` and `Expand AI Assistant panel` buttons present in the same `region "AI Assistant chat"`. |
| `evidences/pre/I-00089-bug-B-expanded-no-affordance.png` | Expanded panel — only model dropdown and the tray-toggle "?" icon are visually distinct; the collapse "<" button is in the DOM but indistinguishable from neighbouring 14 px icons (Bug B). |
| `evidences/pre/I-00089-bug-B-expanded-snapshot.yml` | DOM snapshot of expanded state — `Collapse AI Assistant panel` button present (e5) alongside Toggle skills, Toggle session history, New chat session. |

## Steps to Reproduce

1. Start the dashboard (`./ai-core.sh start` or ensure port 9900 is up).
2. `playwright-cli kill-all && playwright-cli open http://localhost:9900/`.
3. `playwright-cli screenshot` — observe the collapsed state.
4. `playwright-cli snapshot` and click the `Expand AI Assistant panel` button to expand.
5. `playwright-cli screenshot` — observe the expanded state.

**Expected**:
- Collapsed: only the vertical "AI Assistant" expand rail (with the ">" chevron) is visible inside the panel. No "<" icon present.
- Expanded: a visually obvious collapse affordance — clearly distinguishable from the tray-toggle, history-toggle, and new-chat icons — is present in the header. Hovering shows a "Collapse AI Assistant panel" tooltip. Clicking it collapses the panel.

**Actual**:
- Collapsed: a "<" icon is still rendered in the top-left of the rail. Clicking it does nothing because `close()` (`dashboard/static/chat_assistant/chat.js:955`) is a no-op on an already-closed panel.
- Expanded: the "<" collapse button exists in the DOM (ref `e5` in the captured snapshot) and works when clicked programmatically, but is visually indistinguishable from the three other 14 px icons clustered to the right of the model dropdown. Users cannot find a click target.

## Browser Verification Script

The following Playwright CLI commands reproduce the bug. They will be re-used to verify the fix in S11 (qv-browser).

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"

# Collapsed-state observation (default page state)
playwright-cli snapshot
# → Expect: panel region contains ONLY an "Expand AI Assistant panel" button.
#   FAIL (pre-fix): also contains a "Collapse AI Assistant panel" button.
playwright-cli screenshot
# Visual: no "<" icon at top of the 40 px rail.

# Expand the panel
playwright-cli click <ref-of-Expand-AI-Assistant-panel-button>
playwright-cli snapshot
# → Expect: panel header contains a Collapse button with discoverable styling
#   (visible border / background that distinguishes it from the three sibling
#   icon buttons), a "Collapse AI Assistant panel (Ctrl+/)" aria-label, and a
#   matching title attribute (tooltip).
playwright-cli screenshot
# Visual: the collapse "<" icon is the visually-distinct control at the right
# edge of the header — separated from the cluster of toggle icons.

# Confirm the in-panel button actually collapses
playwright-cli click <ref-of-Collapse-AI-Assistant-panel-button>
playwright-cli snapshot
# → Expect: panel back to collapsed state — only the Expand rail visible.
```

## Root Cause Analysis

### Bug A — stray collapse button when collapsed

File: `dashboard/templates/chat_assistant/panel.html`, lines 1-11.

```html
<style>
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-title,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-model,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-context-pct,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-tray-toggle,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-history-toggle,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-new-btn,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-messages,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-skills-tray,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-history-dropdown,
  #chat-assistant-panel[data-collapsed="true"] #chat-assistant-composer-wrap { display: none; }
  #chat-assistant-panel:not([data-collapsed="true"]) #chat-assistant-expand-rail { display: none; }
</style>
```

The `display: none` selector list enumerates every header child that should disappear when the panel is collapsed — except `#chat-assistant-collapse-btn` (defined later at lines 65-71). Because the header element itself is not collapsed/hidden as a whole, that button remains visible.

The button is wired in `dashboard/static/chat_assistant/chat.js:953-956`:

```js
var collapseBtn = document.getElementById('chat-assistant-collapse-btn');
if (collapseBtn) {
  collapseBtn.addEventListener('click', function () { close(); });
}
```

`close()` only mutates `data-collapsed` from `"false"` to `"true"`, so when it is already `"true"` the click has no effect — confirming the "does nothing" symptom.

### Bug B — expanded-state collapse button has no visual weight

File: `dashboard/templates/chat_assistant/panel.html`, lines 23-72.

The header is a single flex row containing, in order:

1. `<span id="chat-assistant-title" class="text-sm font-medium truncate flex-1">AI Assistant</span>`
2. `<select id="chat-assistant-model" class="… max-w-[90px] hidden">` (becomes visible once models load)
3. `<button id="chat-assistant-tray-toggle">` — 14 px icon (`w-3.5 h-3.5`)
4. `<button id="chat-assistant-history-toggle">` — 14 px icon
5. `<button id="chat-assistant-new-btn">` — 14 px icon
6. `<button id="chat-assistant-collapse-btn">` — 14 px icon, SVG path `d="M15 19l-7-7 7-7"`

Inside a 360 px panel (`#chat-assistant-panel:not([data-collapsed="true"]) { width: 360px; }` — `dashboard/static/chat_assistant/chat.css:14-16`) the collapse button is the fourth icon in a tight horizontal cluster, with identical sizing, identical hover-state (`hover:bg-muted`), no border, no background, and no visible separator from the three "open a panel" toggles to its left. It blends in.

The button also has no `title` attribute (only `aria-label`), so a mouse user who hovers it never sees a label telling them what it does.

The combination of poor size, neighbour density, identical hover affordance, and missing tooltip means a typical user cannot identify it as the collapse control. The user-visible symptom is "I can't find a way to close the panel".

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Chat panel template | `dashboard/templates/chat_assistant/panel.html` | Stray collapse button visible while collapsed (Bug A); collapse button blends in while expanded (Bug B) |
| Chat panel CSS | `dashboard/static/chat_assistant/chat.css` | Styling rules supporting the fix may be appended here (alternative to extending the inline `<style>` block in `panel.html`) |
| (No JS / no backend / no DB) | — | The click handler in `chat.js:953-956` is correct and works programmatically once the button is clickable; no JS changes are required |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Fix Bug A (extend the `display:none` selector list to hide `#chat-assistant-collapse-btn` when collapsed, or hide the whole `#chat-assistant-header`). Fix Bug B (give the collapse button visible weight in the expanded header — increase tap target, add a border/background that distinguishes it from the three toggle icons, add a `title` attribute for the hover tooltip, and add a small left-margin separator so it reads as "this collapses the panel" rather than "another header action"). | — |
| S02 | code-review-impl | Per-agent review of S01: CSS scoping, no regressions in other dashboard pages that include this template, accessibility (aria-label preserved, tab order intact), no Tailwind classes added that would require `make css` if the project's worktree can't run it. | — |
| S03 | tests-impl | Add reproduction tests under `tests/dashboard/test_chat_assistant_header.py` proving Bug A (rendered HTML for the panel must not show a visible-when-collapsed `#chat-assistant-collapse-btn`) and Bug B (the collapse button must have the new distinguishing attribute(s): a `title` attribute, and a class marker that the CSS uses to give it visible weight). Use the `client` fixture (per CLAUDE.md, dashboard tests live under `tests/dashboard/`). | — |
| S04 | code-review-impl | Per-agent review of S03: semantic-correctness (assert specific class names / attribute values, not just shape), attribute-scoped substring matching per the CLAUDE.md note (avoid `"my-class" in html` false positives), test isolation. | — |
| S05 | code-review-final-impl | Global cross-step review: AC traceability (AC1, AC2, AC3), no scope creep, the change does not regress the Ctrl+/ keybinding or the nav-bar toggle, and the file diff matches the scope.allowed_paths list in the manifest. | — |
| S06..S10 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S11 | qv-browser | End-to-end browser verification — capture both collapsed and expanded screenshots showing the fixed affordance. | — |
| S12 | self-assess-impl | Mandatory self-assessment (project has `self_assess = true` in `projects.toml`). | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no DB work at all.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/chat_assistant/panel.html` — extend collapsed-state hide list; restyle the collapse button in the expanded header; add `title` attribute.
  - `dashboard/static/chat_assistant/chat.css` — supporting rule(s) for the new collapse-button visual treatment (border, background, hover state, tap target size). Plain CSS appended here is served as-is and avoids a Tailwind recompile in worktrees where `make css` doesn't work (I-00067).
- **Files to add (tests)**:
  - `tests/dashboard/test_chat_assistant_header.py` — reproduction + regression coverage.
- **Nature of change**: HTML/CSS only. No JS, no Python, no DB.

## File Manifest

All files for this work item live under `ai-dev/active/I-00089/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00089_Issue_Design.md` | Design | This document |
| `I-00089_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00089_S01_Frontend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00089_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00089_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00089_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00089_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00089_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser script |
| `prompts/I-00089_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment |

Reports are created during execution in `ai-dev/active/I-00089/reports/`.

## Test to Reproduce

Write failing tests that demonstrate both bugs before fixing them.

**Test-file location**: `tests/dashboard/test_chat_assistant_header.py`. Dashboard tests live under `tests/dashboard/` because the integration-style `db_session` / `test_project` fixtures are re-exported there from `tests/integration/conftest.py`. The dashboard `client` fixture is **not** registered globally — by convention each dashboard test file defines its own inline `client` fixture that overrides `get_db` to point at the test `db_session` (see the canonical pattern at `tests/dashboard/test_chat_panel_default_collapsed.py:25-42`). Placing this file under `tests/unit/` or `tests/integration/` does not give access to the `db_session` re-exports the inline fixture needs.

```python
import os
import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Inline TestClient fixture — same pattern as test_chat_panel_default_collapsed.py."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def test_i00089_bug_a_collapse_button_hidden_when_collapsed(client: TestClient) -> None:
    """RED before fix: the in-header '<' collapse button is rendered even when
    the panel is collapsed (data-collapsed='true'), and clicking it is a no-op.

    The fix must ensure the collapse button is not visible (display: none, OR
    not rendered, OR hidden via a 'when-collapsed' class) while the panel is
    in its default collapsed state.
    """
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # The panel is rendered with the default data-collapsed="true" state.
    assert 'id="chat-assistant-panel"' in html
    assert 'data-collapsed="true"' in html

    # The fix introduces one of:
    #   (a) a CSS rule that hides #chat-assistant-collapse-btn while collapsed,
    #   (b) a wrapper class such as "collapsed-hidden" on the button.
    # Either way the rendered HTML must show the button is NOT meant to be
    # visible while collapsed. We assert the inline <style> block names the
    # collapse-btn id in its display:none selector list.
    style_block_pattern = re.compile(
        r"#chat-assistant-panel\[data-collapsed=\"true\"\][^{]*"
        r"#chat-assistant-collapse-btn",
        re.DOTALL,
    )
    assert style_block_pattern.search(html), (
        "Expected the panel's inline <style> block to include "
        "#chat-assistant-collapse-btn in the 'display: none when collapsed' "
        "selector group. Bug A is still present."
    )


def test_i00089_bug_b_collapse_button_has_discoverable_affordance(
    client: TestClient,
) -> None:
    """RED before fix: the expanded-state collapse button has no visible weight
    (14 px icon, no border, no tooltip) and is indistinguishable from the three
    toggle icons next to it. The fix must give it a discoverable visual
    treatment AND a tooltip.

    We assert two concrete, semantic markers:
      1. The button carries a `title="Collapse panel"` (or similar) attribute
         so a mouse hover reveals the action.
      2. The button carries a distinguishing CSS class (the design adopts a
         dedicated marker — at minimum the existing button must gain an
         additional class indicating its 'collapse' affordance).
    """
    response = client.get("/")
    html = response.text

    # Locate the collapse-btn element. Attribute-scoped match (NOT bare
    # substring) per CLAUDE.md's regression-prevention note (I-00067).
    button_match = re.search(
        r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>',
        html,
    )
    assert button_match is not None, (
        "Expected the chat-assistant-collapse-btn element to be present."
    )
    button_tag = button_match.group(0)

    # (1) The collapse button must have a `title` attribute for hover tooltip.
    assert re.search(r'\btitle="[^"]+"', button_tag), (
        "Expected the collapse button to have a `title` attribute for hover "
        "tooltip. Bug B is still present."
    )

    # (2) The collapse button must carry a class marker indicating its
    # distinguishing visual treatment. The fix chooses one of:
    #     class="… chat-assistant-collapse-btn-distinct …"
    # OR adds a border-utility class (e.g. `border` from Tailwind, or a custom
    # `border-l` separator). At least one of these markers must be present so
    # the button is visually separated from the toggle-icon cluster.
    has_distinct_marker = (
        "chat-assistant-collapse-btn-distinct" in button_tag
        or re.search(r'class="[^"]*\bborder(-l)?\b[^"]*"', button_tag) is not None
    )
    assert has_distinct_marker, (
        "Expected the collapse button to carry a distinguishing class marker "
        "('chat-assistant-collapse-btn-distinct' OR a Tailwind border class) "
        "so it stands out from the adjacent toggle icons. Bug B is still "
        "present."
    )
```

## Acceptance Criteria

### AC1: Bug A — collapsed-state stray button is gone

```
Given the AI Assistant panel is in its default collapsed state (data-collapsed="true")
When the user views any dashboard page
Then the in-header collapse "<" button is not visible (no perceivable click target above the expand rail)
And the only collapse/expand affordance visible is the ">" Expand rail
```

### AC2: Bug B — expanded-state collapse button is discoverable

```
Given the AI Assistant panel is expanded
When the user looks at the panel header
Then the collapse button is visually distinguishable from the tray-toggle, history-toggle, and new-chat icon buttons
And hovering over the collapse button reveals a tooltip (via the title attribute) identifying it as "Collapse" the panel
And clicking the collapse button collapses the panel
```

### AC3: Regression test exists

```
Given the fix is applied
When the dashboard test suite runs
Then the two reproduction tests in tests/dashboard/test_chat_assistant_header.py pass
And no other dashboard tests regress
```

## Regression Prevention

- Add explicit dashboard tests that assert (a) the inline `<style>` block hides `#chat-assistant-collapse-btn` while `data-collapsed="true"`, and (b) the collapse button carries a `title` attribute and a distinguishing class marker. Both are exact, semantic assertions on attribute presence — not substring shape — so future template edits that re-introduce either bug will fail in CI before reaching production.
- The CLAUDE.md attribute-scoped-substring note (I-00067) is followed: tests match `id="chat-assistant-collapse-btn"` with a regex scoped to the opening tag, not a bare substring that could false-positive on inline `<script>` JSON or comments.
- The fix preserves the existing keyboard shortcut (Ctrl+/) and the nav-bar toggle button as alternative collapse paths — even if the in-panel button is hidden by an ad-blocker or a stylesheet override, users still have two working alternatives.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/static/chat_assistant/chat.css`
- `tests/dashboard/test_chat_assistant_header.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_a_collapse_button_hidden_when_collapsed` (fails before fix, passes after). Assert the inline `<style>` block names `#chat-assistant-collapse-btn` in its `display:none` selector group.
- **Reproducing test (Bug B)**: `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_b_collapse_button_has_discoverable_affordance` (fails before fix, passes after). Assert the collapse button has a `title` attribute and a distinguishing class marker.
- **Unit tests**: N/A (no Python logic; HTML/CSS template change only).
- **Integration tests**: The full dashboard + integration suite (`make allure-integration`, gate S10) re-renders the panel template via the FastAPI test client and runs the two reproduction tests above.
- **Browser verification**: S11 qv-browser exercises the actual rendered page in a real Chromium and captures post-fix screenshots showing (a) no stray "<" while collapsed, (b) a discoverable collapse affordance while expanded.

**Assertion scoping for CSS class names** — Tests use attribute-scoped substring matching (`re.search(r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>', html)`) per the CLAUDE.md regression-prevention note (I-00067). The bare-substring form `"chat-assistant-collapse-btn" in html` would false-positive against the `chat.js` source served at `/static/chat_assistant/chat.js` if the test ever reached that asset.

## Notes

- The skill template warning about Semantic Correctness Over Shape Checking (I003 lesson) is applied: tests assert specific attribute presence (`title=`) and specific class markers, not just `"button" in html` or "the rendered length is non-zero".
- The fix should NOT change the JS click handler in `chat.js:953-956`. `close()` is already correct; the bug is purely in template + CSS.
- After modifying `panel.html`, if the change introduces NEW Tailwind utility classes that aren't already in the prebuilt `styles.css`, the implementer must either (a) run `make css` to regenerate (preferred when toolchain works), or (b) add plain CSS rules to `dashboard/static/chat_assistant/chat.css` (preferred when `make css` fails in the worktree — see I-00067). The fix direction recommends option (b) because `chat.css` is already a plain-CSS file in this component.
- No browser keyboard-shortcut regression risk: Ctrl+/ is handled by a `keydown` listener on `document` (`chat.js:937-942`) — completely independent of the in-panel button.
