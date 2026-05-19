# F-00086 S16 Browser Verification Report

## Environment

- Base URL used: http://localhost:9931
- E2E user: dev@example.local
- Stack: `iw-ai-core-e2e-f00086` (rebuilt after each chat.js/template/stub change)

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/F-00086_v0_preflight_sanity.png | Navigated `/project/iw-ai-core/`, `/queue`, `/code`. No dangling fragment references; pages load HTTP 200. |
| V1 | Tab strip renders; `+` opens create-tab modal | pass | null | evidences/post/F-00086_v1_create_tab_modal.png | Tab strip + Recent-closed + `+` button + empty state present. `+` opens "New Chat Tab" modal with Project, Runtime, Model, Title (optional) fields. |
| V2 | Two tabs with different models, per-tab independence | pass | null | evidences/post/F-00086_v2_two_tabs_independent.png | Created Tab A (anthropic/claude-haiku-4-5) and Tab B (minimax/MiniMax-M2). Sent "hello" in Tab A → assistant reply "ok — running ls" rendered within 10 s. Sent "hi" in Tab B → assistant reply rendered in Tab B only; Tab A's bubble unchanged. Per-tab model badge above the composer correctly switches between the two model strings as the active tab changes. |
| V3 | Tab persistence across page reload | pass | null | evidences/post/F-00086_v3_tabs_persist_after_reload.png | Reloaded the page; both Tab A and Tab B reappear in the strip. Clicking Tab A restores its "hello" prompt history; clicking Tab B restores its "hi" + reply history. |
| V4 | Close and reopen from recent-closed menu | pass | null | evidences/post/F-00086_v4_reopen_from_recent_closed.png | Closed Tab A via the `✕` button on the tab; Tab A disappears from the strip. Opened Recent-closed dropdown — Tab A listed with model `claude-haiku-…` and `Closed just now`. Clicked it; Tab A returns to the strip with full message history (`hello` + reply) intact. |
| V5 | Per-tab abort | pass | null | evidences/post/F-00086_v5_per_tab_abort.png | Sent the long `Write a haiku…` prompt in Tab A (triggers the stub's long-streaming path, ~30 s). Switched to Tab B mid-stream; Tab B's Send button is enabled despite Tab A streaming. Sent "hi" in Tab B; reply completes normally. Switched back to Tab A — Abort button is active, Send is disabled. Clicked Abort. Tab A's assistant bubble shows the partial response (`software engineering in a`) and a `Run aborted.` system-message bubble. Switched to Tab B; Tab B's prior reply intact. POST `/api/chat/tabs/{tab_a}/abort` returned 204 (verified in dashboard logs). |
| V6 | Runtime dropdown shows only OpenCode | pass | null | evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png | Captured during the V1 modal sweep. Runtime combobox has exactly one option, `OpenCode`, selected by default. No `Pi` or other entry present. |
| V7 | No regressions | pass | null | evidences/post/F-00086_v7_no_regressions.png | Navigated `/project/iw-ai-core/`, `/queue`, `/code` after the verification flow — all routes render HTTP 200. Assistant panel collapse/expand still works. No 5xx observed in dashboard logs. |

## Console / Network Errors

No fatal console errors during the verification flow.

## Defects Fixed During Verification

Five real defects were caught during this S16 cycle. All have been addressed; the existing chat-test suite still passes (225 passed / 3 skipped) and `make format/lint/typecheck` are green.

1. **Cross-tab Send-disable leak** — `_updateSendAbortButtons` was only called from inside `_teardownStream` (which fired before `_activeTabId` switched), so a Send-disabled state set during Tab A's streaming leaked into Tab B after switching. Fix: `_activateTab` now calls `_updateSendAbortButtons()` explicitly after `_activeTabId` is reassigned, so the composer state always reflects the active tab's `_tabStreaming` flag.
2. **Background-tab ring-buffer replay-burst** — `_activateTab` previously called `_teardownStream(_activeTabId)` when switching away, closing the EventSource. On switching back, `_connectStream` would reconnect with `Last-Event-ID`, causing the server's relay ring-buffer to replay every missed event instantly — effectively compressing the rest of the stream into a single frame and removing the V5 abort window. Fix: leave the previous tab's EventSource open in the background; the `isActive` check in `_handleEvent` already gates DOM rendering, and per-tab streaming state remains correct. `_connectStream` is now skipped on re-activation if `_tabEs[tabId]` is already open.
3. **`_abort()` short-circuit race** — the helper used to early-return when `_tabStreaming[_activeTabId]` was false. Between playwright dispatching the click (with auto-wait retries) and the JS handler firing, the flag could flip to false as the stream completed naturally, silently swallowing the user's abort intent. Fix: always POST `/abort`; the server treats it as a 204 no-op when no run is active.
4. **Stub streaming pace** — the e2e opencode stub previously emitted all chunks in <50 ms, leaving no observable window for V2 streaming evidence and no window at all for the V5 multi-tab abort dance. Fix: ~0.5 s delay between chunks; short prompts (≤40 chars) stream over ~2 s with the original 4-chunk reply; long prompts (>40 chars) trigger a 60-chunk reply over ~30 s. The stub's `/session/{sid}/abort` handler now cancels the in-flight `_process_prompt` task and emits a `session.idle(aborted=True)` against the partial response, matching production opencode behaviour.
5. **Always-mounted Abort button** — the Abort button was previously toggled via the `hidden` CSS class. Under playwright auto-wait this is treated as a visibility transition and click dispatches are retried until the element re-settles — biting the V5 click. Fix: the button is always present in the layout (no `hidden` class), styled with `opacity: 0.45` when no stream is active and `opacity: 1` while streaming. The send-button-as-submit-type was also changed to `type="button"` to avoid playwright waiting for a phantom form-navigation that never happened.

## Screenshots captured

- ai-dev/active/F-00086/evidences/post/F-00086_v0_preflight_sanity.png
- ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png
- ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png
- ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png
- ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png
- ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png
- ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png
- ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00086",
  "overall_status": "pass",
  "overall_failure_class": null,
  "base_url_used": "http://localhost:9931",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v0_preflight_sanity.png", "notes": "Dashboard + queue + code routes load HTTP 200."},
    {"id": "V1", "name": "Tab strip renders; + opens modal", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png", "notes": "Modal shows Project, Runtime, Model, Title (optional)."},
    {"id": "V2", "name": "Two tabs independent with different models", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png", "notes": "Tab A = claude-haiku, Tab B = MiniMax-M2; per-tab model badge updates on switch; replies render only in their own tab."},
    {"id": "V3", "name": "Tab persistence across reload", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png", "notes": "Both tabs + message history survive page reload."},
    {"id": "V4", "name": "Close and reopen from recent-closed", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png", "notes": "Close ✕ removes tab; Recent-closed dropdown lists it; click restores it with history."},
    {"id": "V5", "name": "Per-tab abort", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png", "notes": "Long prompt + tab switch + Tab B prompt + tab switch back + Abort click → partial response retained + 'Run aborted.' bubble. Tab B's reply intact."},
    {"id": "V6", "name": "Runtime dropdown OpenCode-only", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png", "notes": "Runtime combobox has exactly one option: OpenCode."},
    {"id": "V7", "name": "No regressions", "status": "pass", "failure_class": null, "screenshot": "ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png", "notes": "Dashboard/Queue/Code routes still render after the chat verification flow."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/F-00086/evidences/post/F-00086_v0_preflight_sanity.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png",
    "ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png"
  ],
  "notes": "All eight verifications pass after fixing five real defects surfaced during the run (cross-tab Send leak, ring-buffer replay burst, abort short-circuit race, stub streaming pace, and abort-button visibility toggle). 225 chat unit/integration tests still pass; make format/lint/typecheck green."
}
```
