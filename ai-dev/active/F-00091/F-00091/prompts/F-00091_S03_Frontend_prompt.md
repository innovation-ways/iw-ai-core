# F-00091_S03_Frontend_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read Scope → S03, AC2, Invariants 6, and Boundary row 5)
- `dashboard/static/chat_assistant/chat.js` — Current sessionStorage usage at lines 11–19, 198, 209, 248
- S02 report: `ai-dev/work/F-00091/reports/F-00091_S02_Frontend_report.md` — Confirms `_assistantProjectId()` is in place

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S03_Frontend_report.md`

## Context

The active-tab pointer today lives in `sessionStorage` under a single key keyed only by browser-tab id, not by project. As a result, switching projects (or closing the window) drops the user onto `_tabs[0]` instead of the tab they were last on. This step migrates that pointer to `localStorage`, namespaced per project, so it survives both project switches and browser-window-close.

Read **Scope → S03**, **AC2**, **Invariant 6**, and Boundary row 5 in full before touching code.

## Requirements

### 1. Storage key migration

In `dashboard/static/chat_assistant/chat.js`:

- Add a helper `_activeTabKey(projectId)` that returns the string `'iw-chat-active-tab:' + projectId`. Use a colon (`:`), not a dash — this is enforced by Invariant 6 to avoid collision with the pre-existing key shape `iw-chat-active-tab-<browserTabId>`.
- Replace EVERY write to the old sessionStorage key with `localStorage.setItem(_activeTabKey(_assistantProjectId()), tabId)`. The current writes live at `chat.js:248` (`_activateTab` body).
- Replace EVERY read with `localStorage.getItem(_activeTabKey(_assistantProjectId()))`. Current reads:
  - `chat.js:177` — inside the **retry callback** path of `_bootstrapTabs()` (the 100ms-delayed second fetch when the first load returns zero tabs)
  - `chat.js:198` — main `_bootstrapTabs()` path
  - `chat.js:209` — same `_bootstrapTabs()` scope (used in the `target` fallback computation)
- Wrap all storage access in try/catch — private-mode quota errors must not bubble up (Boundary row 6 from the design doc).
- Delete the now-unused `_browserTabId` block at `chat.js:11–19` ONLY IF no other code path still reads it. Search the file carefully. If it is still referenced, leave it untouched and add a `// TODO(F-00091): _browserTabId unused after S03` comment.

### 2. Bootstrap flow

The new flow inside `_bootstrapTabs()`:

1. `projectId = _assistantProjectId()`. If `null`, render the empty no-tabs state and return (already handled).
2. Fetch tabs as today.
3. Read the namespaced active-tab pointer.
4. If it matches a tab id in the returned list, activate that tab.
5. Else, fall back to `_tabs[0]` (the server already orders by `last_active_at DESC`).
6. If the stale pointer was present but unmatched, REMOVE the stale localStorage entry — don't leave junk keys lying around.

### 3. Project-switch handler

When the dropdown change handler from S02 fires:

1. The previous project's active-tab pointer is in localStorage under the OLD project's key — leave it alone (it must persist for restoration).
2. The new project's pointer is read inside `_bootstrapTabs()` after the projectId switch.
3. The previous active in-memory tab id `_activeTabId` is reset to `null` so `_activateTab(...)` does not no-op when the bootstrap fires (`if (_activeTabId === tabId) return;` is at the top of `_activateTab`).

### 4. TDD

Add `tests/dashboard/test_active_tab_restoration.py`:

- Drive the dashboard via TestClient + a hand-rolled JS evaluation (or, if a JS test harness is in place, use it).
- Seed three chat tabs for project A and two for project B in the test DB via the fixture pattern.
- Simulate setting the localStorage keys to known values, fetch the panel HTML, evaluate the relevant JS init function (or assert that the served JS contains the expected helper definitions).
- Assert that `_activeTabKey('iw-ai-core')` resolves to `'iw-chat-active-tab:iw-ai-core'` (string concatenation contract).
- Assert NO write path uses the old `iw-chat-active-tab-<browserTabId>` key after S03.

If a true browser-driven test isn't feasible at the unit level, write the test as a smoke-level integration test under `tests/integration/test_chat_panel_active_tab_storage.py` that loads the served `chat.js`, parses it, and asserts the expected helper bodies via regex. The S19 browser verification covers the full UX path.

Capture RED → GREEN.

### 5. Backwards compatibility

There is no migration of existing sessionStorage keys. Users with stale `iw-chat-active-tab-<browserTabId>` entries simply get the fall-back `_tabs[0]` on first load after F-00091 ships, then the new localStorage key is established. Stale sessionStorage keys evaporate when the browser tab is closed. Document this in your `notes`.

## Project Conventions

Match the chat.js ES5 IIFE style. Do NOT introduce `const`/`let`/arrow functions in new helpers. Read `CLAUDE.md` and `dashboard/CLAUDE.md`.

## TDD Requirement

Standard RED → GREEN → REFACTOR. Record the failing assertion in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the test file(s) you wrote:

```bash
uv run pytest tests/dashboard/test_active_tab_restoration.py -v
# or
uv run pytest tests/integration/test_chat_panel_active_tab_storage.py -v
```

Do NOT run the wider suite.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_active_tab_restoration.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_active_tab_restoration.py::test_namespaced_key_shape — AssertionError: 'iw-chat-active-tab:iw-ai-core' not found",
  "blockers": [],
  "notes": ""
}
```
