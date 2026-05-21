# CR-00068 S07 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S07 of work item CR-00068 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/templates/chat_assistant/panel.html
  dashboard/static/chat_assistant/chat.js
  dashboard/static/chat_assistant/chat.css
  tests/dashboard/**
  ai-dev/active/CR-00068/**
  ai-dev/work/CR-00068/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00068/ai-dev/active/CR-00068/CR-00068_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00068-S07 Browser Verification Report

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S07 (qv-browser)
**Date**: 2026-05-21
**Base URL**: `http://localhost:9937`
**E2E Credentials**: `dev@example.local` / `DevPass2026!`

---

## Verification Summary

| ID | Name | Status | Failure Class | Notes |
|----|------|--------|---------------|-------|
| V0 | Pre-flight page sanity | **PASS** | — | Project home loaded at HTTP 200, no unhandled exception page, no load-time console errors |
| V1 | Model bar is gone | **FAIL** | `code_defect` | Model bar was already gone, but a `ReferenceError` was thrown preventing tab creation entirely |
| V2 | Model changeable via settings panel | **FAIL** | `code_defect` | Cannot reach V2: tab creation is blocked by the same error |
| V3 | Tab-strip model badge kept | **FAIL** | `code_defect` | Cannot reach V3: no tab was created to inspect |
| V4 | No regressions | **FAIL** | `code_defect` | Cannot reach V4: chat functionality is entirely broken |

**Overall**: `fail` — **code_defect**

---

## Root Cause

The `chat.js` diff (uncommitted CR-00068 changes) **removed** the `var _defaultModel = ''` declaration at line 55 of `dashboard/static/chat_assistant/chat.js`:

```diff
-  var _defaultModel = '';
     _defaultModel = data.default_model || '';
+        // _defaultModel is kept current so _instantCreateTab() picks the right default.
     _defaultModel = '';
```

Without the `var` declaration, the variable `_defaultModel` is in the temporal dead zone in strict-mode JavaScript (the browser's module). When `_instantCreateTab()` (line 1074) reads `_defaultModel`:

```js
var model = (activeTab && activeTab.model) || _defaultModel || '';
```

it throws:

```
ReferenceError: _defaultModel is not defined
    at _instantCreateTab (chat.js:1074:51)
    at HTMLButtonElement.<anonymous> (chat.js:2077:57)
```

The first console error appeared ~50 s after page load (matching the `_scheduleModelRefresh` 30-second interval + fetch latency), meaning the second error appears consistently on every "New Chat" click thereafter.

**File**: `dashboard/static/chat_assistant/chat.js`
**Line**: 55 (where `var _defaultModel = '';` should be restored)

The fix is a one-line restoration: add `var _defaultModel = '';` at module scope (above the assignment sites), or equivalently ensure `_refreshModels` uses a properly-scoped module-level variable.

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `evidences/post/V0_project_home.png` | V0: Projects home page loaded successfully |
| `evidences/post/V1_no_model_bar.png` | V1: Chat panel showing "No chats yet" — model bar is gone, but New Chat is broken |

---

## Console Errors Observed

```
[49911ms]  ReferenceError: _defaultModel is not defined
    at _instantCreateTab (http://localhost:9937/static/chat_assistant/chat.js?v=9e7ae61:1074:51)
    at HTMLButtonElement.<anonymous> (http://localhost:9937/static/chat_assistant/chat.js?v=9e7ae61:2077:57)

[291301ms] ReferenceError: _defaultModel is not defined
    at _instantCreateTab (http://localhost:9937/static/chat_assistant/chat.js?v=9e7ae61:1074:51)
    at HTMLButtonElement.<anonymous> (http://localhost:9937/static/chat_assistant/chat.js?v=9e7ae61:2077:57)
```

Both errors reference the same line (`chat.js:1074:51`) in `_instantCreateTab()`.

---

## V1 Assessment (Partial)

V1 is partially verified: the model bar's HTML elements (`#chat-assistant-tab-model-bar`, `#chat-assistant-tab-model-badge`, `#chat-assistant-tab-model-dropdown`) are **confirmed absent** from the panel snapshot. However, the verification could not be completed because a chat tab could not be created due to the `ReferenceError`.

---

## No Regressions (V4)

Not assessable — the core "New Chat" functionality is broken due to the missing `var _defaultModel` declaration. Cannot exercise tab switching, skills tray, composer, or streaming. The regression check must be re-run after the fix is applied.

---

## Recommended Fix

Restore the variable declaration at module scope in `dashboard/static/chat_assistant/chat.js` (before line 55 or wherever the first assignment site is):

```js
var _defaultModel = '';
```

Alternatively, use `let _defaultModel = ''` for block-scoped correctness. This is a one-line fix that restores the model variable scoping so that all three assignment sites (`_defaultModel = data.default_model || ''` in `_refreshModels`, and `_defaultModel = ''` in `_scheduleModelRefresh`) work correctly.


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S07` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00068/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00068/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
