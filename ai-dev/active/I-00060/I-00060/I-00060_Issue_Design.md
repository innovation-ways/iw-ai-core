# I-00060: Code chat — pin user message on Enter and tighten empty Assistant bubble

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-02
**Reported By**: sergiog (dashboard usability report)
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

This work item makes NO database changes. Any migration command should be
treated as a blocker — if you think you need one, you've misunderstood
the scope.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

In the dashboard "Code" page chat panel (`#chat-panel`), two usability
defects make ongoing conversations awkward:

1. After the user types a question and presses Enter (or clicks **Send**),
   the chat scroll container does **not** scroll to the bottom. Once the
   conversation overflows the viewport, the just-sent user message and the
   new Assistant placeholder are pushed below the fold and the user can no
   longer see what they wrote.
2. When a new Assistant bubble is appended in response to a submission, the
   empty bubble (no streamed tokens yet) renders too tall, leaving a large
   block of dead space below the "Assistant" label until the first token
   arrives.

Together they make the panel feel "lost" the moment the conversation gets
longer than the viewport.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture,
conventions, and hard rules. Note that `dashboard/CLAUDE.md` references
`make css` for Tailwind regeneration, but that target is currently a
no-op in `Makefile` (see `make -n css` output). For this fix the CSS
edit lives in the hand-written `dashboard/static/chat.css`, not in the
Tailwind output `dashboard/static/styles.css`, so `make css` is not
relevant.

This is a **frontend-only** fix. No routes, no Python, no DB.

## Browser Evidence

Browser pre-evidence capture is **deferred** — at design time the dev
environment is not running on this machine and the bug is reproducible
purely from the static templates / JS. The QV browser step (S11) will
capture both pre-fix-style failure-mode evidence and post-fix evidence in
`evidences/post/` against the isolated worktree stack.

## Steps to Reproduce

1. Start the dashboard (`./ai-core.sh start`) and open a project's Code page
   (`/project/{id}/code`) that has the RAG index built.
2. Expand the right-hand chat panel (Cmd+\ or click the chevron).
3. Send 8–10 questions back to back so the `#chat-messages` container has
   to scroll.
4. Scroll the chat panel up so older messages are visible and the bottom
   anchor is **out of view**.
5. Type a new question in `#chat-input` and press Enter.

**Expected**:
- The chat container scrolls all the way down so the user's just-typed
  bubble (`<article data-role="user">`) AND the freshly created Assistant
  bubble are visible.
- The empty Assistant bubble renders compact — just the "Assistant" label
  (and an optional typing indicator), height of roughly one line + small
  padding. As tokens stream in via SSE the bubble grows naturally.

**Actual**:
- The container does not move — the user's new message stays scrolled
  off-screen below the fold (the floating "↓ Latest" button at
  `#chat-scroll-to-bottom` is the only affordance).
- The empty Assistant bubble renders with noticeably more vertical padding
  / placeholder space than its content requires, leaving dead air below
  the "Assistant" label.

## Browser Verification Script

Reproduces the bug end-to-end with `playwright-cli` once the dashboard
worktree stack is up. The QV browser step (S11) follows
`templates/design/QVBrowser_Prompt_Template.md` for the standard flow; the
verification-specific commands are:

```bash
# 1. Pre-flight
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"

# 2. Log in (snapshot for refs first)
playwright-cli snapshot
playwright-cli fill <user-field-ref>     "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>

# 3. Navigate to a project's Code page that already has an index
playwright-cli open "$IW_BROWSER_BASE_URL/project/<project-slug>/code"

# 4. Expand the chat panel and send several questions to force overflow.
#    For each question:
#      playwright-cli snapshot
#      playwright-cli fill <chat-input-ref> "Question N"
#      playwright-cli click <chat-send-ref>
#      sleep 2   # let SSE stream finish
#
# 5. Manually scroll the messages container upward (use a JS evaluate via
#    playwright-cli) so #chat-scroll-anchor is out of view.

# 6. Send another question and verify the container snaps to the bottom.

# 7. Inspect the freshly created empty Assistant bubble's bounding height
#    *before* the first token arrives — must be ≤ ~40px (label + minimal
#    padding) and not the previous larger empty box.
```

## Root Cause Analysis

### Bug 1 — submit handler never scrolls

`dashboard/static/chat/composer.js:260-345` — the `chat-send` click handler:

- Line 283: `appendUserBubble(question)` appends the user's `<article>` to
  `#chat-messages`.
- Line 287: `var assistantBubble = appendAssistantBubble();` appends the
  empty Assistant `<article>`.
- Lines 303–342: `streamAnswer({...})` is invoked — SSE tokens arrive
  asynchronously.

`composer.js:390-395` defines a `scrollToBottom()` helper that calls
`document.getElementById('chat-scroll-anchor').scrollIntoView({behavior:'instant', block:'end'})`,
and `panel.html:55` provides the `<div id="chat-scroll-anchor">` at the
bottom of `#chat-messages`. The anchor + helper are in place — **the
submit handler simply never calls `scrollToBottom()`** after appending the
two bubbles. The `IntersectionObserver` at `composer.js:405-412` only
toggles the visibility of the floating "↓ Latest" button; it never
auto-scrolls.

Fix: call `scrollToBottom()` after `appendUserBubble` and after
`appendAssistantBubble` in the submit handler. As tokens stream in via
`onToken`, also re-scroll if the user is already near the bottom (i.e.
they have not deliberately scrolled away) so the answer follows the
caret. The "user has scrolled away" detection should reuse the existing
`IntersectionObserver` signal — when the anchor is intersecting the
viewport we are at the bottom and follow-scrolling is safe; when it is
not intersecting, the user is reading older content and we must NOT yank
them to the bottom mid-stream.

### Bug 2 — empty Assistant bubble too tall

The actual culprit is a **hand-written CSS rule** in
`dashboard/static/chat.css:3`:

```css
#chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }
```

This forces the **last** assistant article to be at least 50% of the
dynamic viewport height regardless of its content. So the empty
pre-stream Assistant bubble is forced to roughly half the visible chat
area before any tokens arrive — the dead vertical space the user sees.

This file is **NOT** the Tailwind-generated `dashboard/static/styles.css`;
it is a separate stylesheet that is hand-edited and committed directly.
`make css` does not regenerate it. Edits go straight into `chat.css`.

For reference, the bubble structure built by
`dashboard/static/chat/composer.js:371-388` is:

```
<article class="chat-message bg-background border border-border rounded-lg px-3 py-2 text-sm mr-8" data-role="assistant">
  <header class="font-medium text-xs text-muted-foreground block mb-1">Assistant</header>
  <div class="chat-message-body text-sm leading-relaxed" id="chat-current-response"></div>
</article>
```

Without the `min-height: 50dvh` rule, this article collapses to
roughly `padding-y (16px) + header (~16px) + mb-1 (4px) + empty body
(0px)` ≈ 36px — well within the ≤ 48px target.

Fix: **remove the `min-height: 50dvh` rule from `chat.css:3`** (or
restrict it so it only applies once content has streamed in). The
intent of that rule appears to have been to keep the streaming bubble
"in view" while answers grow, but that goal is now served correctly
by the AC1/AC3 follow-scroll behaviour added by Bug 1's fix. The
rule should be deleted, not replaced — the active scrolling makes it
redundant.

Note: the implementer should still do a quick browser sanity check
(via `playwright-cli`) to confirm:

1. Removing the rule brings the empty bubble down to ≤ 48px.
2. The renderer's lazily-injected `phase-strip`
   (`dashboard/static/chat/render.js:330-336`) does NOT pre-render with
   any content before the first phase event arrives; it is created
   only inside `onPhase`, so the empty pre-stream bubble has no phase
   strip. If for any reason the implementer observes the strip
   pre-existing or an alternate min-height rule, document the actual
   contributor in the report and adjust accordingly.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/static/chat/composer.js` (submit handler) | Missing `scrollToBottom()` calls on submit and on stream tokens |
| `dashboard/static/chat.css:3` | `#chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }` — forces empty assistant bubble to ~50% of viewport height; **this is the root cause of Bug 2** |
| `dashboard/static/chat/render.js` (createAssistantRenderer) | Phase-strip is inserted lazily on phase events (line 330-336); confirm it does not pre-render before tokens arrive |
| Tests | No coverage of scroll-on-submit; no coverage of empty bubble height |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Add `scrollToBottom()` calls on submit + token-arrival (only when user is at the bottom). Remove the `min-height: 50dvh` rule at `dashboard/static/chat.css:3` to fix Bug 2. Edits limited to `dashboard/static/chat/composer.js` and `dashboard/static/chat.css`; `dashboard/static/chat/render.js` only if the live browser check exposes an additional contributor. | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Tests | Reproduction + regression coverage. See Test to Reproduce. Includes Playwright-driven browser tests because both bugs are layout/scroll issues that cannot be verified in pure unit tests. New tests live under `tests/dashboard/browser/` and run with the existing `-m browser` marker. | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Cross-agent global review | — |
| S06..S10 | qv-gate | lint, format, typecheck, unit-tests, integration-tests (the gates that actually exist in this project's Makefile) | — |
| S11 | qv-browser | End-to-end browser verification of scroll + empty-bubble behaviour, plus no-regression sweep of citations / mermaid / "↓ Latest" button | — |

Agent slug: `frontend-impl` for S01.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — frontend-only fix.

### Code Changes

- **Files to modify**:
  - `dashboard/static/chat/composer.js` — call `scrollToBottom()` after both bubble appends; on stream `onToken`/`onPhase`/`onDone`, conditionally scroll only when user is already at the bottom (use existing IntersectionObserver signal).
  - `dashboard/static/chat.css` — delete the `#chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }` rule at line 3 (the root cause of Bug 2). This file is hand-edited; `make css` does not regenerate it.
  - `dashboard/static/chat/render.js` — only if the live browser check identifies a renderer-injected placeholder additionally inflating the empty bubble. Default expectation: no edit needed.
- **Nature of change**: bug fix only; no new features, no refactor of streaming protocol or citation logic.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00060/I-00060_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00060/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/I-00060/prompts/I-00060_S01_Frontend_prompt.md` | Prompt | S01 fix instructions |
| `ai-dev/active/I-00060/prompts/I-00060_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review |
| `ai-dev/active/I-00060/prompts/I-00060_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `ai-dev/active/I-00060/prompts/I-00060_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `ai-dev/active/I-00060/prompts/I-00060_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent review |
| `ai-dev/active/I-00060/prompts/I-00060_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser end-to-end check |

Reports are created during execution under `ai-dev/active/I-00060/reports/`.
Browser evidence under `ai-dev/active/I-00060/evidences/post/`.

## Test to Reproduce

Both bugs are layout / scroll behaviours that only meaningfully show up in
a real browser, so the reproduction test is a Playwright spec invoked via
`playwright-cli` and a pytest helper that drives it. The Tests step (S03)
must add the new browser tests under the existing
**`tests/dashboard/browser/`** lane (the project's established
convention — see `tests/dashboard/browser/conftest.py`,
`tests/dashboard/browser/test_chat_panel_smoke.py`,
`tests/dashboard/browser/test_chat_mermaid.py`). The new module should be
named `tests/dashboard/browser/test_chat_scroll_i00060.py` and use the
existing `-m browser` marker pattern.

```python
# tests/dashboard/browser/test_chat_scroll_i00060.py (illustrative)

def test_i00060_repro_submit_scrolls_to_bottom(playwright_session, project_with_index):
    """RED: Without the fix, after sending a message the user bubble is below the fold.
    GREEN: After the fix, the user bubble is in view (its bounding rect bottom <=
    the messages container's bottom)."""
    page = playwright_session.open(project_with_index.code_url)
    page.click("#chat-collapse-btn")  # expand panel

    # Pre-fill with several messages to force overflow.
    for i in range(8):
        page.fill("#chat-input", f"warmup question {i}")
        page.click("#chat-send")
        page.wait_for_stream_complete()

    # Scroll to top so the anchor is out of view.
    page.evaluate("document.getElementById('chat-messages').scrollTop = 0")

    page.fill("#chat-input", "the question we care about")
    page.click("#chat-send")

    # Immediately after submit (no need to wait for stream), the user bubble
    # MUST be visible inside the messages container.
    assert page.user_bubble_visible(text="the question we care about"), \
        "I-00060 bug 1: user message was not scrolled into view on submit"


def test_i00060_repro_empty_assistant_bubble_is_compact(playwright_session, project_with_index):
    """RED: The empty assistant bubble (before any tokens) renders > 80px tall.
    GREEN: It renders <= 48px tall (label + minimal padding)."""
    page = playwright_session.open(project_with_index.code_url)
    page.click("#chat-collapse-btn")

    page.fill("#chat-input", "explain this module")
    page.click("#chat-send")

    # Capture the assistant bubble height BEFORE the first token streams in.
    height_px = page.evaluate(
        "document.querySelector('article[data-role=\"assistant\"]:last-of-type').getBoundingClientRect().height"
    )
    assert height_px <= 48, (
        f"I-00060 bug 2: empty assistant bubble is {height_px}px tall, "
        "expected <= 48px (label + minimal padding)"
    )
```

The Tests agent is free to adapt the harness to the project's existing
patterns (see `tests/CLAUDE.md` and any `tests/dashboard/` files), but the
two assertions above are non-negotiable: **scroll-into-view of the user's
just-sent bubble**, and **compact height of the empty assistant bubble
before any tokens arrive**.

## Acceptance Criteria

### AC1: Submit always pins the just-typed message and the new assistant bubble

```
Given the chat panel is open and the messages container has been scrolled
  upward so #chat-scroll-anchor is out of view
When the user types a question into #chat-input and presses Enter
Then #chat-messages scrolls so the just-appended user <article data-role="user">
  AND the just-appended assistant <article data-role="assistant"> are both
  fully visible inside the container's viewport.
```

### AC2: Empty Assistant bubble is compact

```
Given a question has just been submitted and the assistant bubble has been
  appended but no tokens / phase events have arrived yet
When the layout settles
Then the assistant <article data-role="assistant">'s bounding box height is
  no greater than 48px (label "Assistant" + small padding), and contains no
  visibly empty placeholder regions.
```

### AC3: Streamed content follows the caret only when the user is at the bottom

```
Given the assistant is streaming tokens
When the user has NOT scrolled away from the bottom (anchor is intersecting)
Then the container auto-scrolls to keep the latest tokens in view
And when the user HAS scrolled up to read older content
Then the container does NOT yank them to the bottom; the floating
  "↓ Latest" button remains the way to return.
```

### AC4: Reproduction test exists

```
Given the fix is applied
When the test suite runs
Then the I-00060 reproduction tests for AC1 and AC2 pass.
```

### AC5: No regressions

```
Given the fix is applied
When the user sends a question, citations are returned, mermaid diagrams
  are rendered, the "↓ Latest" button is clicked, and the panel is
  collapsed/expanded
Then all existing behaviour remains intact and no new console errors appear.
```

## Regression Prevention

- The reproduction tests added in S03 directly assert the two failure
  modes — they will fail loudly if the scroll call is removed or if the
  empty bubble grows again.
- The QV browser step (S11) is wired into the workflow as a hard gate, so
  any future change that breaks scroll-on-submit or inflates the empty
  bubble height will fail before merge.
- Implementer should add a short comment in `composer.js` next to the new
  `scrollToBottom()` call explaining **why** (the user-typed message must
  remain visible after Enter) — that's a non-obvious WHY worth keeping.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: two browser-driven assertions described in
  *Test to Reproduce* — both fail against the current code and pass after
  the fix.
- **Unit tests**: not applicable — the bugs are scroll/layout behaviours
  that need a real browser. Any composer-side logic that becomes unit-
  testable as a side effect of the fix (e.g. a helper that decides whether
  to follow-scroll based on the IntersectionObserver state) MAY be unit
  tested with a JSDom-style harness if one already exists in the repo;
  otherwise stick to the browser tests.
- **Integration tests**: covered by the QV browser step (S11) end-to-end.

## Notes

- Scope is intentionally tight: do NOT refactor the streaming protocol,
  citation popovers, mermaid rendering, sources panel, or any unrelated
  piece of `composer.js` / `render.js`. Make the smallest change that
  satisfies all acceptance criteria.
- If the implementer discovers the empty-bubble height comes from a
  renderer placeholder that is also visible in pre-existing assistant
  bubbles loaded from history, that's still in scope — fix it. But do not
  silently change the appearance of bubbles that already have content.
- Tailwind: this fix does not add or change Tailwind class strings. The
  CSS change is to `dashboard/static/chat.css` (hand-written). Avoid
  adding new Tailwind classes in scope of this issue.
