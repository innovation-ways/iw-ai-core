# I-00033: Code view layout bugs — undismissible "Last run" banner, misplaced scrollbar, wasted space on chat collapse

**Type**: Issue
**Severity**: Low
**Created**: 2026-04-21
**Reported By**: sergio (dashboard usability, hands-on Code view)
**Status**: Draft

---

## Description

The project Code view (`/project/{id}/code`) has three related layout issues on desktop:

1. After running "Generate Code Map", a "Last run · {duration} · {files} files · {chunks} chunks" banner appears and lingers for up to one hour with no way to dismiss it.
2. The vertical scrollbar for the architecture document renders flush against the chat panel's left edge, making it look like the chat panel owns the scrollbar instead of the text frame.
3. Collapsing the chat panel via the header button shrinks the panel's inline width to 48px but leaves the grid-track width untouched, so the text column does not reclaim the freed space and a wide empty gap opens between the shrunken chat and the text.

All three are layout/UX bugs. No data loss, no backend failure, no broken navigation.

## Project Context

Read `CLAUDE.md` (repo root) and `dashboard/CLAUDE.md`. Key rules that apply here:

- Dashboard stack is **FastAPI + Jinja2 + htmx + Tailwind CDN** — there is **no build step** and **no Tailwind purge**. Avoid dynamic Tailwind class construction (e.g., do not build class names from variables at runtime — the CDN has no JIT for unseen class strings).
- Templates in `fragments/` MUST NOT extend `base.html` — they are htmx partial responses.
- Routes are thin — business logic belongs in `orch/`. This incident touches only templates and client-side JS; no router or service logic changes.
- Playwright CLI rules from the root CLAUDE.md apply: use `playwright-cli` exclusively, never `agent-browser`, never install commands, always `kill-all` before a new session.

## Browser Evidence

Pre-fix screenshot of the bug state:

- `ai-dev/active/I-00033/evidences/pre/I-00033-code-view-initial.png` — Code page at `/project/iw-ai-core/code`. Clearly shows the "Last run · 3m 26s · 258 files · 1,391 chunks" banner with **no close affordance**, and the two-column layout where `#code-content-root` is the scroll container (no card-internal scroll gutter).

## Steps to Reproduce

### Bug 1 — "Last run" banner has no close button

1. Open `/project/iw-ai-core/code`.
2. Click **Generate Code Map** → **Generate Code Map** (or **Regenerate Map**). Wait for completion.
3. Observe the banner below the page header: `✓ Last run · {duration} · {files} files · {chunks} chunks`.

**Expected**: A small `×` in the banner's top-right corner that, when clicked, hides the banner until the *next* code-mapping job completes (at which point the banner reappears with the new run's summary). Dismissal is per-project and persists across reloads.

**Actual**: No close button. The banner is rendered whenever `last_completed_job and last_completed_recent` is `True` (see `dashboard/routers/code_ui.py:116-119` — "recent" means `< 1 hour` since `completed_at`). Reloading the page or navigating away and back still shows it. Only time (or another run) changes the state.

### Bug 2 — Scrollbar placement

1. Open `/project/iw-ai-core/code` on a desktop viewport (≥ 1024 px).
2. Scroll the architecture document.

**Expected**: Scrollbar at the right edge of the Architecture **card** (inside the card's right border), with a visible gutter between the card and the chat panel.

**Actual**: Scrollbar renders at the right edge of the `1fr` grid column (`#code-content-root`, after the `pr-4` padding), visually flush against the chat panel's left border. It reads as if the chat panel owns the scrollbar.

### Bug 3 — Chat collapse leaves a gap

1. Open `/project/iw-ai-core/code` on a desktop viewport.
2. Click the chat-collapse button (`>` arrow in the chat header, or press `Cmd/Ctrl + \`).

**Expected**: The chat panel collapses to a thin vertical rail (~48px) with an expand arrow visible, AND the text column grows to fill the freed width.

**Actual**: The panel's `width` inline style is set to `48px`, but the parent grid's track for the chat column is still `var(--chat-width)` (default 400px). The text column stays the same width; there is a ~350px empty gap between the shrunken panel and the text.

## Browser Verification Script

After the fix lands, the post-fix verification path is:

```bash
playwright-cli kill-all
playwright-cli -s=i00033 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/code"

# Bug 1: dismiss banner, reload, confirm hidden; then simulate a new job id and confirm banner returns.
playwright-cli -s=i00033 snapshot                 # locate the "Last run" banner + its new close button
playwright-cli -s=i00033 click <close-btn-ref>    # dismiss
playwright-cli -s=i00033 reload
playwright-cli -s=i00033 snapshot                 # banner MUST NOT be in the DOM (or must be display:none)
playwright-cli -s=i00033 screenshot --filename ai-dev/active/I-00033/evidences/post/I-00033_v1_banner_dismissed.png

# Bug 2: scroll the document, confirm scrollbar sits inside the Architecture card.
playwright-cli -s=i00033 run-code "document.querySelector('#code-content-root').scrollTop = 400"
playwright-cli -s=i00033 screenshot --filename ai-dev/active/I-00033/evidences/post/I-00033_v2_scrollbar_inside_card.png
# Verify via snapshot/eval that the element with `overflow-y: auto` is the card body, not #code-content-root.

# Bug 3: collapse chat, confirm --chat-width == 48px and text column grew.
playwright-cli -s=i00033 click <chat-collapse-btn-ref>
playwright-cli -s=i00033 run-code "getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()"
# Must return "48px".
playwright-cli -s=i00033 screenshot --filename ai-dev/active/I-00033/evidences/post/I-00033_v3_chat_collapsed_no_gap.png
```

## Root Cause Analysis

Three independent defects, in three files, surfaced by the two-column Code layout introduced in recent work.

### Bug 1 — `code_job_report.html` is stateless

`dashboard/templates/fragments/code_job_report.html:4-19` renders the banner unconditionally whenever the parent route's template logic asks it to. There is no close button in the markup and no client-side dismissal bookkeeping. The parent `dashboard/templates/project_code.html:81-83` decides to include the fragment based on `last_completed_job and last_completed_recent`, where `last_completed_recent` means `datetime.now(UTC) - completed_at < timedelta(hours=1)` (`dashboard/routers/code_ui.py:116-119`). Nothing the user does — short of waiting an hour or re-running the job — hides the banner.

**Fix surface**: markup change in `fragments/code_job_report.html` (add dismiss button with `data-job-id`), plus a small client-side script that checks `localStorage` on render and hides the banner when `localStorage.getItem('iw_code_lastrun_dismissed:{project_id}') === '{job_id}'`. The server continues to include the banner — dismissal is purely client-side by job-id, so when a NEW job completes (different id) the banner reappears automatically.

### Bug 2 — outer-column scroll container

`dashboard/templates/project_code.html:89-90`:

```html
<div id="code-content-root"
     class="lg:overflow-y-auto lg:pr-4"
     ...>
```

The scroll container is the grid-column element itself. The scrollbar renders at the column's right edge, after `pr-4` content padding. Visually, it sits a few pixels to the left of the chat panel's left border — not inside the Architecture card.

**Fix surface**: move `overflow-y-auto` **off** `#code-content-root` and **onto** the Architecture card's body (`<div class="p-8 ...">`) inside `dashboard/templates/fragments/code_architecture_view.html`. The wrapping bordered card (`bg-card border border-border rounded-lg`) already has a visible right border; putting scroll inside the body places the scrollbar inside that border, with the column's outer gutter (via column gap or right-margin on the card) providing visible separation from the chat panel.

Caveat: the card currently wraps Architecture + `#code-components-section` + `#code-detail-panel` in one element. To avoid changing which sub-sections scroll together, apply the scroll treatment at the `.p-8` body level (line 5 of `code_architecture_view.html`) or, preferably, at the outer card element — whichever matches the user's mental model ("scroll is inside the text frame"). The chosen scope must be explicit in the implementation prompt so the frontend agent doesn't guess.

Height containment must also be preserved: the parent grid (`project_code.html:87-88`) sets `lg:h-[calc(100vh-12rem)]` on `#page-body`. The new scroll container must have a definite height — either by inheriting from the column (stretch to fill the grid row) or by setting `h-full` on the card. Without a definite height, `overflow-y-auto` yields no scrollbar because the element grows to fit its content.

### Bug 3 — collapse updates panel width, not CSS variable

`dashboard/static/chat/panel.js:17-27`:

```javascript
function applyCollapsedState(collapsed) {
  if (!panel) return;
  panel.dataset.collapsed = collapsed;
  if (collapsed) {
    panel.style.width = '48px';
    if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Expand chat panel (Cmd+\\)');
  } else {
    panel.style.width = '';
    if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Collapse chat panel (Cmd+\\)');
  }
}
```

The parent grid track in `project_code.html:88` is `grid-cols-[1fr_var(--chat-width)]`. `--chat-width` is set to `chatWidth + 'px'` at boot (panel.js:11, default 400) and updated only by the resize handle (panel.js:99). On collapse, the panel shrinks inside a 400px track — `1fr` never grows.

**Fix surface**: in `applyCollapsedState`, on collapse set `document.documentElement.style.setProperty('--chat-width', '48px')`; on expand, restore from the persisted saved width (`localStorage.getItem('iw_chat_width')`, clamped to the same 320..480 range the module already enforces). Also: the inline `panel.style.width` mutation becomes redundant once the grid track drives the width; leave it for belt-and-braces but prefer CSS-variable as the source of truth. Confirm by measurement (`getBoundingClientRect`) that the text column `1fr` expands.

The rail visual: today the collapsed panel shows the chat header (context label truncates inside the rail) and hides the message list behind `overflow: hidden`. Verify the header's collapse button stays tappable at 48px. If the header content overflows ugly, apply `data-collapsed="true"` CSS (added in this incident) that hides the context label while collapsed and keeps the collapse button centered. This is a small CSS-only addition; no class-name construction.

### Cross-cutting

All three bugs are desktop-only (`lg:` breakpoint, ≥ 1024 px). Mobile (< 1024 px) uses a fixed off-canvas drawer for chat, a separate scroll model for the document, and the "Last run" banner is not behaviourally different — but a close button on mobile is still desirable. Scope the fix so mobile behavior doesn't regress.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| "Last run" banner | `dashboard/templates/fragments/code_job_report.html` | Needs dismiss button + `data-job-id`; needs a tiny script (inline `<script>` at the bottom of the fragment or in a new `dashboard/static/code/last_run_banner.js`) that hides the banner on click and persists dismissal by job id in `localStorage` |
| Code page grid | `dashboard/templates/project_code.html` | Remove `lg:overflow-y-auto lg:pr-4` from `#code-content-root`; the scroll now lives inside the Architecture card |
| Architecture card | `dashboard/templates/fragments/code_architecture_view.html` | Add `h-full overflow-y-auto` (or equivalent) to the card body so the scrollbar is inside the card's right border |
| Chat panel collapse | `dashboard/static/chat/panel.js` | On collapse: set `--chat-width: 48px` in addition to the inline panel width; on expand: restore the saved width. Keep the localStorage `iw_chat_width` contract unchanged |
| Chat panel rail (collapsed visual) | `dashboard/templates/chat/panel.html` (+ minor CSS — can be inline on the header) | Hide the context label and right-edge content when `data-collapsed="true"`; keep the collapse button visible as the expand affordance |

No database changes. No migrations. No router changes. No service-layer changes.

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope |
|------|-------|-------|
| S01 | frontend-impl | Apply all three template/JS/CSS fixes described above. One combined step because the three fixes overlap in two files (`project_code.html`, `panel.js`) and share the same verification environment (Code page on desktop). Deliverables: (a) dismiss `×` in `code_job_report.html` + inline script (or new `static/code/last_run_banner.js`) with localStorage dismissal by `{project_id, job_id}`; (b) scroll container moved from `#code-content-root` to the Architecture card body; (c) `--chat-width` toggle in `panel.js`'s `applyCollapsedState`; (d) collapsed-rail CSS on `chat/panel.html` gating via `data-collapsed="true"`. No dynamic Tailwind class construction; all classes are literal. |
| S02 | code-review-impl | Review S01 — verify (a) localStorage keys are scoped by project id (otherwise dismissal leaks across projects); (b) the new scroll container has a definite height (otherwise no scrollbar appears); (c) `--chat-width` is restored on expand to the exact saved value (not clobbered); (d) no regressions to the existing resize handle behavior; (e) no dynamic Tailwind classes; (f) mobile drawer behavior unchanged. |
| S03 | tests-impl | **Reproduction tests** (must fail pre-S01, pass post-S01): (a) Jinja template render test asserting the close button exists in `code_job_report.html`, with `data-dismiss-job-id` attribute wired to the job id; (b) Jinja template render test asserting `#code-content-root` does NOT have `overflow-y-auto` and that the Architecture card body does; (c) Playwright smoke test (new file `tests/dashboard/browser/test_code_layout_fixes.py`) that exercises the three end-to-end paths: dismiss banner → reload → banner hidden; collapse chat → `getComputedStyle(document.documentElement).getPropertyValue('--chat-width')` equals `48px`; scroll container check (find the element with `overflow-y: auto` that contains the architecture prose and assert its id or class). All assertions check specific values, not presence-only. |
| S04 | code-review-impl | Review S03 — tests fail on pre-S01 code (reviewer runs `git stash` on S01's changes, confirms failures, then restores); Playwright test uses the existing `dashboard_server` / `playwright_session` module-scoped fixtures from `tests/dashboard/browser/test_chat_panel_smoke.py` (extract to `conftest.py` if cleaner); localStorage cleanup in test teardown to avoid pollution. |
| S05 | code-review-final-impl | Global review: template/JS/CSS-variable integration; ACs are covered by tests; no leaked changes to other pages; mobile behavior unchanged; no dynamic Tailwind classes. |
| S06 | qv-gate (lint) | `make lint` |
| S07 | qv-gate (format) | `uv run ruff format --check .` |
| S08 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` |
| S09 | qv-gate (unit-tests) | `make test-unit` |
| S10 | qv-gate (integration-tests) | `make test-integration` |
| S11 | qv-browser | Browser verification — reproduce all three verification paths on the isolated E2E stack the daemon provides (`$IW_BROWSER_BASE_URL`). Screenshots to `evidences/post/`. |

No `code-review-fix-impl` / `code-review-fix-final-impl` steps are pre-allocated — the daemon spawns fix cycles on demand when review verdicts are `fail`.

Browser verification (`browser_verification: true`) — this is a UI-visible fix.

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: N/A.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/code_job_report.html` — add close `×` button with `aria-label="Dismiss last-run banner"`, `data-job-id="{{ last_completed_job.id }}"`, and an inline (or small external) script that reads `localStorage.getItem('iw_code_lastrun_dismissed:{{ current_project.id }}')` on DOMContentLoaded and hides the banner if the stored job id matches the current `{{ last_completed_job.id }}`. On click of the close button, write the id and hide the banner.
  - `dashboard/templates/project_code.html` — remove `lg:overflow-y-auto lg:pr-4` from `#code-content-root`. Keep `lg:h-[calc(100vh-12rem)]` on `#page-body` so children have a definite parent height. Add a small right margin or column gap between the text column and the chat column for visible gutter (Tailwind `lg:gap-4` on `#page-body` is the simplest).
  - `dashboard/templates/fragments/code_architecture_view.html` — apply `h-full overflow-y-auto` to the root card `<div>` and **remove** `overflow-hidden` so there is exactly one overflow declaration on that element. Final class list: `bg-card border border-border rounded-lg h-full overflow-y-auto`. Horizontal bleed is already handled inside `.prose-doc` (`pre { overflow-x: auto; }`, `img { max-width: 100%; }`), so `overflow-x: visible` on the card root is safe. The existing "one scroll container for the whole Architecture + Modules + Detail card" behaviour is preserved (no change to child divs).
  - `dashboard/static/chat/panel.js` — in `applyCollapsedState(collapsed)`, set `document.documentElement.style.setProperty('--chat-width', collapsed ? '48px' : chatWidth + 'px')`; on expand, `chatWidth` is already the persisted value. Remove the redundant `panel.style.width = '48px'` (the grid track drives width now) or keep it as belt-and-braces with a comment explaining why.
  - `dashboard/templates/chat/panel.html` — CSS-only tweaks via `data-collapsed="true"` selector (inline `<style>` is acceptable here, matching the pattern used elsewhere in the codebase). Hide `#chat-context-label`, `#chat-messages`, `#chat-scroll-to-bottom-wrap`, and the composer when collapsed; keep only the collapse button. Rotate the arrow icon to point outward in the collapsed state.
- **Files to create**:
  - `tests/dashboard/browser/test_code_layout_fixes.py` — reproduction Playwright smoke test for the three bugs.
  - (Optional, only if the inline script grows past ~20 lines) `dashboard/static/code/last_run_banner.js` — extracted banner-dismissal script.

- **Nature of change**: Pure frontend (templates + client JS + CSS-via-classes). No router, no service, no model, no migration.

## File Manifest

All files for this work item live under `ai-dev/active/I-00033/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00033_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `evidences/pre/I-00033-code-view-initial.png` | Evidence | Pre-fix screenshot of the Code page |
| `prompts/I-00033_S01_Frontend_prompt.md` | Prompt | S01 frontend fix (all three bugs) |
| `prompts/I-00033_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00033_S03_Tests_prompt.md` | Prompt | S03 template + browser reproduction tests |
| `prompts/I-00033_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00033_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent final review |
| `prompts/I-00033_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser end-to-end verification |

Reports and post-fix evidence are created during execution in `ai-dev/active/I-00033/reports/` and `ai-dev/active/I-00033/evidences/post/`.

## Test to Reproduce

Three reproduction tests — one Jinja render test per bug + one Playwright smoke test covering end-to-end behavior. All assertions are value-specific (not shape-only).

### Jinja render tests (pytest, no browser)

```python
# tests/dashboard/test_code_layout_fixes.py
"""Reproduction tests for I-00033.

These tests fail against pre-S01 templates/JS and pass after the fix lands.
They verify the *structure* of the templates; behavior is verified by the
Playwright smoke in tests/dashboard/browser/test_code_layout_fixes.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


@pytest.fixture(scope="module")
def jinja_env() -> Environment:
    templates = Path(__file__).resolve().parents[1] / "dashboard" / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates)),
        autoescape=select_autoescape(["html"]),
    )


def test_last_run_banner_has_dismiss_button(jinja_env):
    """Bug 1: the 'Last run' banner MUST have a close button wired to the job id."""
    tpl = jinja_env.get_template("fragments/code_job_report.html")
    html = tpl.render(
        last_completed_job=type("J", (), {"id": 12345, "files_indexed": 10, "chunks_created": 100})(),
        last_completed_duration="1m 23s",
        current_project=type("P", (), {"id": "iw-ai-core"})(),
    )
    # Semantic assertions — not just "x is in html"
    assert 'data-dismiss-job-id="12345"' in html, (
        "Dismiss button must carry the specific job id (I-00033)"
    )
    assert 'aria-label="Dismiss last-run banner"' in html
    # The dismissal script must read the project-scoped key
    assert "iw_code_lastrun_dismissed:iw-ai-core" in html or \
           "iw_code_lastrun_dismissed:{{ current_project.id }}" in html  # if externalised


def test_code_content_root_does_not_own_scroll(jinja_env):
    """Bug 2: the outer column must NOT be the scroll container."""
    tpl = jinja_env.get_template("project_code.html")
    # Render with a minimal context that exercises the desktop grid path
    html = tpl.render(
        current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
        index_status=None,
        running_job=None,
        last_completed_job=None,
        last_completed_recent=False,
        content_html="<p>x</p>",
    )
    # The specific class we removed must be gone from #code-content-root
    assert 'id="code-content-root"' in html
    # Find the code-content-root block and assert no overflow-y-auto on it
    root_block = html.split('id="code-content-root"', 1)[1].split(">", 1)[0]
    assert "overflow-y-auto" not in root_block, (
        "#code-content-root must not be the scroll container after I-00033"
    )


def test_architecture_card_owns_scroll(jinja_env):
    """Bug 2 (companion): the Architecture card IS the scroll container."""
    import re

    tpl = jinja_env.get_template("fragments/code_architecture_view.html")
    html = tpl.render(content_html="<p>x</p>", project_id="iw-ai-core")
    # Extract the root div's class attribute robustly (no reliance on whitespace/newlines).
    m = re.search(r'<div\s+[^>]*class="([^"]*)"', html)
    assert m, "No <div> with class attribute found in code_architecture_view.html"
    root_classes = m.group(1).split()
    assert "overflow-y-auto" in root_classes, (
        "Architecture card root must own the scroll container (I-00033 bug 2)"
    )
    assert "h-full" in root_classes, (
        "Architecture card root must have h-full so overflow-y-auto has a container "
        "(I-00033 bug 2 — without a definite height, no scrollbar appears)"
    )
    assert "overflow-hidden" not in root_classes, (
        "overflow-hidden must be removed (I-00033 bug 2 — it conflicts with overflow-y-auto)"
    )
```

### Playwright smoke (headless Chromium via `playwright-cli`)

```python
# tests/dashboard/browser/test_code_layout_fixes.py
"""Reproduction browser smoke for I-00033 (bugs 1, 2, 3).

Model after tests/dashboard/browser/test_chat_panel_smoke.py: module-scoped
dashboard_server + playwright_session fixtures, marker = @pytest.mark.browser.
Run: uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser -v
"""
from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.browser


def _snap(session: str) -> str:
    return subprocess.check_output(
        ["playwright-cli", f"-s={session}", "snapshot"], text=True
    )


def _eval(session: str, code: str) -> str:
    return subprocess.check_output(
        ["playwright-cli", f"-s={session}", "run-code", code], text=True
    ).strip()


def test_bug1_last_run_banner_dismissal_persists(playwright_session):
    """Bug 1: dismissing the banner must persist across reload."""
    session = playwright_session
    snap = _snap(session)
    assert 'data-dismiss-job-id' in snap, "Close button missing"
    # ... click close, reload, assert banner not in snapshot.
    # NOTE: exact refs resolved at test time via snapshot parsing.


def test_bug2_scroll_container_is_architecture_card(playwright_session):
    """Bug 2: the element with overflow-y: auto containing the prose is the card, not #code-content-root."""
    session = playwright_session
    val = _eval(
        session,
        "(function(){var p=document.querySelector('.prose-doc');var e=p;"
        "while(e){if(getComputedStyle(e).overflowY==='auto')return e.className+'|'+e.id;e=e.parentElement;}"
        "return 'none';})()",
    )
    assert "id=code-content-root" not in val.replace('|', ',id='), (
        "#code-content-root must not be the scroll container (I-00033)"
    )
    assert "bg-card" in val, "Expected the Architecture card to own the scroll"


def test_bug3_chat_collapse_shrinks_grid_track(playwright_session):
    """Bug 3: collapsing the chat sets --chat-width to 48px, not just the panel's inline width."""
    session = playwright_session
    # Click collapse button, then read the CSS variable.
    # ... (snapshot, find #chat-collapse-btn, click)
    val = _eval(
        session,
        "getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()",
    )
    assert val == "48px", f"Expected --chat-width=48px on collapse, got {val!r} (I-00033)"
```

## Browser Verification Test

See `prompts/I-00033_S11_BrowserVerification_prompt.md` for the full QV browser verification spec. Summary:

- **V1**: Dismiss the "Last run" banner, reload the page, confirm the banner is NOT in the DOM and the dismissal persisted via localStorage.
- **V2**: Read the computed style of the `.prose-doc`'s nearest `overflow-y:auto` ancestor and assert it is the Architecture card, not `#code-content-root`.
- **V3**: Click the chat-collapse button, read `--chat-width`, assert it equals `48px`. Measure the text column's width before and after collapse — must grow by ~(400-48)px.
- **V4**: Expand the chat, confirm `--chat-width` is restored to the saved value (default 400px); click the existing resize handle and drag — width still behaves correctly.
- **V5**: No regressions — mobile drawer behavior unchanged at viewport < 1024px (skip automated test; visual inspection via one screenshot). No new console errors on any page visited during V1..V4.

## Acceptance Criteria

### AC1: Bug 1 is fixed — "Last run" banner is dismissible and respects per-job persistence

```
Given the Code page shows a "Last run" banner after a completed job
When the user clicks the close button on the banner
Then the banner disappears immediately

Given the user dismissed the banner for job id J
When they reload the page and J is still the most recent completed job
Then the banner does NOT reappear

Given the user dismissed the banner for job id J
When a NEW job completes (new id J') and the page is reloaded
Then the banner reappears with the new run's summary (dismissal is per-job-id)
```

### AC2: Bug 2 is fixed — scrollbar sits inside the Architecture card

```
Given the Code page is open on a desktop viewport (≥ 1024 px)
And the architecture document is tall enough to require scrolling
When the user looks at the text panel
Then the vertical scrollbar renders INSIDE the Architecture card's right border,
     with a visible gap between the card and the chat panel
```

### AC3: Bug 3 is fixed — chat collapse reclaims space

```
Given the Code page is open on a desktop viewport
When the user clicks the chat-collapse button (or presses Cmd/Ctrl + \)
Then the value of `getComputedStyle(document.documentElement).getPropertyValue('--chat-width')` is "48px"
AND the text column's width is larger than it was before collapse by approximately (savedChatWidth - 48) px

When the user clicks the collapse button again (to expand)
Then --chat-width is restored to the saved width from localStorage 'iw_chat_width' (default 400)
AND the text column returns to its prior width
```

### AC4: Regression tests exist

```
Given the fix is applied
When `uv run pytest tests/dashboard/test_code_layout_fixes.py` runs
Then all three reproduction tests pass

Given the fix is applied AND an E2E/dashboard browser session is available
When `uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser` runs
Then the Playwright smoke for bugs 1, 2, 3 passes
```

### AC5: No mobile regressions

```
Given the Code page is open on a mobile viewport (< 1024 px)
When the user dismisses the "Last run" banner
Then the same per-job-id persistence behavior applies

Given the Code page is open on a mobile viewport
Then the chat drawer still opens/closes via the existing off-canvas pattern
AND neither the new scroll container nor the CSS-variable change breaks drawer behaviour
```

## Regression Prevention

- **Template-structure tests are permanent.** The three Jinja render tests in `tests/dashboard/test_code_layout_fixes.py` assert the specific classes and attributes that make each fix work. Any future refactor that silently removes them fails the tests.
- **Playwright smoke covers user-visible behavior.** The `test_code_layout_fixes.py` browser test runs in the `@pytest.mark.browser` suite and covers end-to-end dismissal persistence and CSS-variable propagation.
- **Source-of-truth contract for `--chat-width`.** After the fix, `applyCollapsedState` and the resize handler are the only two writers of `--chat-width`. The design document records this so future agents do not add a third writer.
- **Localstorage key format is documented.** `iw_code_lastrun_dismissed:{project_id}` stores the last dismissed job id. Future agents adding new per-project dismissables follow the same scoped-key pattern.

## Dependencies

- **Depends on**: None. All surfaces exist in main.
- **Blocks**: None.

## TDD Approach

- **RED**: Land the three Jinja render tests and the Playwright smoke (S03). Confirm each fails against the pre-S01 templates/JS by running locally against a clean `main` before S01 lands (the orchestrator runs S01 first, so S03 is second; if the Tests agent wants to verify RED, it can `git stash` S01's changes temporarily and re-run).
- **GREEN**: S01's template/JS changes turn all three tests GREEN. Playwright smoke asserts the computed-style contracts.
- **REFACTOR**: Only if the banner-dismissal JS grows past ~20 lines — extract to `dashboard/static/code/last_run_banner.js`. Otherwise keep inline.

## Notes

- Severity is **Low**: no data loss, no broken navigation, no API breakage. Purely UX friction.
- The three bugs are bundled per the user's explicit request — they share two files (`project_code.html`, `panel.js`) and a single verification environment (the Code page on desktop), so splitting into three incidents would triple the review overhead without separating risk.
- No Tailwind-class construction from variables — every Tailwind class used is a literal string in a template. Safe under CDN (no JIT).
- The dismissal script uses `DOMContentLoaded` (or equivalent htmx-aware hook) because the banner may be swapped in by htmx after the initial page load. If the banner is ever swapped via htmx (e.g., on job completion via SSE), the script must re-run — the implementation prompt calls this out explicitly.
