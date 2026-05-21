# CR-00067: AI Assistant — Context Usage Percentage Indicator

**Type**: Change Request
**Priority**: Medium
**Reason**: New requirement — users have no visibility into how much LLM context is consumed in an AI Assistant chat tab, leading to confusing model behaviour as the context fills up.
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR adds no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** migrations — it adds a
backend computation and a frontend display, but no schema change.

## Description

The dashboard AI Assistant panel gives no indication of how much of the LLM
context window is consumed in the active chat tab. This CR computes a context
usage percentage in the backend and surfaces it as a small percentage label
(e.g. `42%`) in the composer footer, immediately left of the "Clear" button,
colour-coded neutral / amber (≥70%) / red (≥90%). The percentage is fetched
immediately when a tab is activated and refreshed by the existing poll while a
response is streaming.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture,
conventions, and hard rules. Relevant:

- The AI Assistant chat endpoints live in `dashboard/routers/chat.py`. Chat
  runtime adapters live in `orch/chat/` (`opencode/`, `pi/`).
- The AI Assistant UI lives in `dashboard/templates/chat_assistant/` (Jinja2
  includes) and `dashboard/static/chat_assistant/` (`chat.js`, `chat.css`).
- `chat_assistant/chat.css` is plain CSS loaded via a `<link>` tag — no Tailwind
  recompile is needed for rules added there.
- Routers are thin; business logic belongs in the `orch/` layer.

## Current Behavior

**No backend computation exists.** A repo-wide search finds the token
`context_pct` in exactly one place — `chat.js:1926`. No Python code computes or
returns it. `GET /api/chat/tabs/{tab_id}` (`get_tab`, `chat.py:671`) returns
`{tab, session, messages}` where `session` is the **raw runtime session object**:
`client.get_session()` returns the OpenCode `GET /session/{sid}` body verbatim,
and `PiRuntime.get_session()` returns only `{"id", "pi_session_path"}`. Neither
runtime's session object carries a `context_pct` field.

**The frontend reads a field that is never populated.** `chat.js` has a
context-percentage poll, `_startContextPoll()` (around `chat.js:1917`). It runs a
`setInterval` every 5000 ms that fetches `GET /api/chat/tabs/{id}`, reads
`session.context_pct`, and tries to write it into a DOM element with id
`chat-assistant-context-pct`:

```
var el = document.getElementById('chat-assistant-context-pct');
if (el && typeof pct === 'number') { el.textContent = pct + '%'; el.classList.remove('hidden'); }
```

Two things are wrong:

1. `session.context_pct` is always `undefined` (no backend produces it), so the
   `typeof pct === 'number'` guard never passes.
2. **No template renders an element with id `chat-assistant-context-pct`**, so the
   `getElementById` lookup always returns `null` anyway.

**The poll is streaming-scoped, not active-tab-scoped.** `_startContextPoll()` is
invoked only when a response starts streaming (in `_sendPrompt()` at `chat.js:1821`
and in the SSE streaming-start handlers around lines 465 / 483 / 508 / 614 / 664),
and `_stopContextPoll()` runs on `session.idle` / errors / stream teardown. While a
tab is merely open and idle, **no poll runs at all** — so a freshly activated tab
would show nothing indefinitely, not merely "for up to 5 seconds". There is no
fetch on tab activation.

Net effect: the context percentage is never displayed under any circumstances.

## Desired Behavior

### Backend

- `GET /api/chat/tabs/{tab_id}` returns a numeric `context_pct` inside the
  `session` object when it can be computed for the active session.
- For **OpenCode** tabs, `context_pct` is computed as
  `used_tokens / model_context_window * 100`, where:
  - `used_tokens` is the cumulative token count of the most recent assistant
    message that carries token usage (`tokens.input + tokens.output +
    tokens.reasoning + tokens.cache.read + tokens.cache.write`, each field
    treated as `0` when absent).
  - `model_context_window` is the active model's `limit.context` value from the
    OpenCode `/config/providers` response.
- For **Pi** tabs, `context_pct` is computed the same way **if** Pi's session /
  message data exposes usable token counts and a context-window limit; otherwise
  `context_pct` is omitted (the label then stays hidden — see below). This Pi
  limitation is documented in Notes.
- When usage cannot be computed (no assistant message with token data, unknown
  model context window, runtime unavailable), `context_pct` is **omitted** from
  the `session` payload — it is never reported as `0`.
- The percentage is clamped to the range `[0, 100]`.
- No new HTTP round-trip is added to every poll: the `/config/providers` lookup
  used for model context limits MUST be served from a short-TTL cache (reuse or
  mirror the existing 30 s `_config_cache` pattern in `chat.py`).

### Frontend

- A small inline label appears in the composer's Send/Abort row, immediately to
  the **left of the "Clear" button**, showing the active tab's context usage as a
  whole-number percentage with a trailing `%` (e.g. `42%`).
- The label is hidden when no context data is available (no active tab, or the
  API has not returned a numeric `context_pct`).
- The label is colour-coded by usage band:
  - **< 70%** — neutral (muted foreground colour).
  - **≥ 70% and < 90%** — amber/warning colour.
  - **≥ 90%** — red/destructive colour.
- The percentage is fetched **immediately when a tab is activated** (in addition
  to the existing streaming poll), so the value is visible without waiting for a
  message to be sent.
- While a response is streaming, the existing 5-second poll keeps the value
  current as the context grows. When the tab is idle the value is static — which
  is correct, because the context does not change while idle.
- The label has an accessible title/`aria-label` such as "Context window used:
  42%" so its meaning is clear on hover and to screen readers.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/chat/context_usage.py` | Does not exist | New pure helper module — sums message token usage and computes a clamped percentage from a model context-window limit |
| `dashboard/routers/chat.py` (`get_tab`) | Returns the raw runtime `session` object | Computes `context_pct` (via the new helper + a cached model-limit lookup) and injects it into the returned `session` dict |
| `chat_assistant/composer.html` | Send/Abort row has Clear, Abort, Send buttons only | Adds a `#chat-assistant-context-pct` `<span>` left of the Clear button |
| `chat_assistant/chat.css` | No context-percentage styling | Adds `.chat-assistant-context-pct` base + `.is-warn` / `.is-crit` modifier rules |
| `chat_assistant/chat.js` | Polls `context_pct` every 5 s; writes to a non-existent element; no fetch on activation | Adds an immediate context fetch on tab activation; applies colour-band CSS classes; hides the label when no data |

### Breaking Changes

- None. The `GET /api/chat/tabs/{id}` response gains an **optional** field
  (`session.context_pct`); existing consumers ignore unknown fields. No DB
  schema, no removed/renamed fields, no behaviour change outside the AI
  Assistant panel.

### Data Migration

- None. No schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | New `orch/chat/context_usage.py` helper; compute + inject `context_pct` into the `get_tab` `session` payload; cached model-limit lookup; TDD unit tests | — |
| S02 | frontend-impl | Add the context-% element, CSS, and JS (immediate fetch on activation + colour bands); add a `tests/dashboard/` template-render test | — |
| S03 | code-review-impl | Review S01 + S02 output | — |
| S04 | code-review-fix-impl | Fix CRITICAL/HIGH/MEDIUM_FIXABLE findings | — |
| S05 | code-review-final-impl | Cross-agent final review | — |
| S06 | code-review-fix-final-impl | Fix final review findings | — |
| S07 | qv-gate | `make test-unit` | — |
| S08 | qv-gate | `make test-integration` | — |
| S09 | qv-browser | Browser verification — context % visible, colour bands correct | — |
| S10 | self-assess-impl | Post-execution self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `GET /api/chat/tabs/{id}` — the `session` object in the
  response gains an optional numeric `context_pct` field. Additive only.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: `#chat-assistant-context-pct` span in the composer footer
- **Modified components**: `chat_assistant/composer.html`, `chat_assistant/chat.css`, `chat_assistant/chat.js`
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00067/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00067_CR_Design.md` | Design | This document |
| `CR-00067_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00067_S01_Backend_prompt.md` | Prompt | S01 backend implementation instructions |
| `prompts/CR-00067_S02_Frontend_prompt.md` | Prompt | S02 frontend implementation instructions |
| `prompts/CR-00067_S03_CodeReview_prompt.md` | Prompt | S03 code review instructions |
| `prompts/CR-00067_S04_CodeReviewFix_prompt.md` | Prompt | S04 review-fix instructions |
| `prompts/CR-00067_S05_CodeReviewFinal_prompt.md` | Prompt | S05 final review instructions |
| `prompts/CR-00067_S06_CodeReviewFixFinal_prompt.md` | Prompt | S06 final review-fix instructions |
| `prompts/CR-00067_S09_BrowserVerification_prompt.md` | Prompt | S09 browser verification instructions |
| `prompts/CR-00067_S10_SelfAssess_prompt.md` | Prompt | S10 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00067/reports/`
(implementation / review steps) and `ai-dev/active/CR-00067/reports/`
(browser verification).

## Acceptance Criteria

### AC1: Backend computes and returns the context percentage

```
Given an active OpenCode chat tab whose most recent assistant message carries token usage
And the active model's context-window limit is known
When GET /api/chat/tabs/{id} is called
Then the response session object contains a numeric context_pct equal to
     round-tripping used_tokens / model_context_window * 100, clamped to [0, 100]
```

### AC2: context_pct is omitted when usage cannot be computed

```
Given a chat tab with no assistant message carrying token usage,
     or an unknown model context window, or a runtime that cannot supply the data
When GET /api/chat/tabs/{id} is called
Then the response session object does NOT contain a numeric context_pct
     (the field is absent — it is never reported as 0)
```

### AC3: Context percentage is visible left of the Clear button

```
Given the AI Assistant panel is open with an active chat tab whose API response has a numeric context_pct
When the tab's context data is fetched
Then a percentage label (e.g. "42%") is displayed in the composer footer immediately to the left of the "Clear" button
```

### AC4: Label is hidden when no context data is available

```
Given the AI Assistant panel is open
When there is no active tab, or the API has not returned a numeric context_pct
Then the context percentage label is not visible (no "0%" placeholder is shown)
```

### AC5: Colour bands reflect usage

```
Given the active tab reports a context_pct value
When context_pct is below 70
Then the label uses the neutral colour
And when context_pct is at or above 70 but below 90 the label uses the amber/warning colour
And when context_pct is at or above 90 the label uses the red/destructive colour
```

### AC6: Percentage appears immediately on tab activation

```
Given the AI Assistant panel is open
When the user activates a chat tab
Then the context percentage is fetched and displayed without waiting for a message to be sent
```

## Rollback Plan

- **Database**: Not applicable — no schema changes.
- **Code**: Revert the squash-merge commit for CR-00067. `orch/chat/context_usage.py`
  is removed, `get_tab` returns the raw `session` object again, and the three
  touched frontend files return to their prior state. The orphaned `context_pct`
  polling code in `chat.js` reverts to its prior (harmless) no-op behaviour.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/chat/context_usage.py`
- `dashboard/routers/chat.py`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.css`
- `dashboard/static/chat_assistant/chat.js`
- `tests/unit/**`
- `tests/integration/**`
- `tests/dashboard/**`

## TDD Approach

- **Unit tests (S01, owned by backend-impl)**: `tests/unit/test_context_usage.py`
  for the pure `orch/chat/context_usage.py` helper — token summing with missing
  fields, percentage computation, `[0, 100]` clamping, and the "return `None`
  when not computable" path (no token data, zero/unknown context window).
  backend-impl follows RED → GREEN → REFACTOR and records the RED output.
- **Integration test (S01, owned by backend-impl)**: extend the chat-tabs API
  integration coverage (`tests/integration/`) so `GET /api/chat/tabs/{id}`
  returns `session.context_pct` when the fake OpenCode runtime is seeded with
  assistant-message token usage and a model `limit.context`, and omits it when
  no token data is present. This will require extending `tests/integration/_fake_opencode.py`
  to serve `tokens` on messages and `limit` on provider models.
- **Dashboard test (S02, owned by frontend-impl)**: a `tests/dashboard/` test
  asserting `chat_assistant/composer.html` renders a `#chat-assistant-context-pct`
  element positioned before the `#chat-assistant-clear` button and carrying the
  `hidden` class by default.
- **Browser verification (S09)**: confirms the label appears, is positioned left
  of Clear, and that colour bands apply at the 70% and 90% thresholds.

## Notes

- The frontend contract is unchanged: `chat.js` continues to read
  `data.session.context_pct`. The backend injects `context_pct` into the
  existing `session` dict rather than adding a new top-level field, so the
  frontend lookup path stays identical.
- The colour-band JS must treat a missing/non-numeric `context_pct` as "hide the
  label", not "show 0%".
- `chat_assistant/chat.css` is plain CSS served as-is — appending rules there
  needs no `make css` / Tailwind recompile.
- Use the project's existing CSS custom properties (`--muted-foreground`,
  `--destructive`, etc.) for colours where possible; pick an amber value
  consistent with other warning UI in the dashboard (`#92400e` is used for the
  `#chat-assistant-settings-warn` message in `chat_assistant/panel.html`).
- The on-activation fetch belongs **inside `_activateTab()`** (`chat.js:226–279`)
  — `_activateTab()` does NOT currently call `_startContextPoll()`, and the
  poll's existing call sites are all streaming-start paths, not activation. Do
  not attempt to make the poll run continuously while idle; the immediate fetch
  on activation plus the streaming-scoped poll is the intended design (context
  usage only changes while a response is being generated).
- **Known limitation (Pi runtime)**: `PiRuntime.get_session()` returns only
  `{"id", "pi_session_path"}`, and Pi message token exposure is unverified. S01
  must investigate Pi's message shape; if Pi cannot supply token usage,
  `context_pct` is omitted for Pi tabs and the label simply stays hidden for
  them — an acceptable graceful degradation. Surfacing context usage for Pi tabs
  can be a follow-up if Pi later exposes the data.
