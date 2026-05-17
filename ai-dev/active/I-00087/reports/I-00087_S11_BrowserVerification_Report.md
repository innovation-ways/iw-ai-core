# I-00087 S11 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9933`
- **E2E user**: `dev@example.local`
- **Step**: S11 (qv-browser agent)
- **Item**: I-00087

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **pass** | null | — | Project list at `/` loaded with HTTP 200, no dangling fragment references, no console errors. `hx-target="#global-search-results"` and `hx-target="#modal-root"` resolve to existing `id` attributes in the page HTML. |
| V1 | Streaming reply renders | **pass** | null | `evidences/post/I-00087_v1_streaming_reply_rendered.png` | After sending "say pong and nothing else" (model `stub/echo`), an assistant bubble appeared with text `"ok — running ls"`. The bubble uses class `.chat-assistant-stream-text` (confirmed via `playwright-cli eval`). Assistant reply text: `"ok — running ls"`. No "Session idle." as the only content. |
| V2 | History reload preserves conversation | **pass** | null | `evidences/post/I-00087_v2_history_reload_preserves_conversation.png` | After `playwright-cli reload`, the conversation log shows both: (1) user bubble "say pong and nothing else", (2) assistant bubble "ok — running ls". No "Session idle." only. Panel re-expanded on same sessionStorage session. |
| V3 | Multi-turn session continuity | **pass** | null | `evidences/post/I-00087_v3_multi_turn_session.png` | Sent "repeat your previous reply once more". After 18s, a second assistant bubble appeared with text "ok — running ls". Both prior bubbles (user + first assistant) remain visible. Session ID reused (no new session created between prompts). |
| V4 | No console errors | **pass** | null | — | No `.playwright-cli/console-*.log` contained severity `error` at any point during V0–V3. |
| V5 | No regressions in adjacent flows | **pass** | null | `evidences/post/I-00087_v5_no_regressions.png` | Panel collapses (ref `e15`) and re-expands showing full conversation (4 messages confirmed: 2 user + 2 assistant). New chat button (ref `e12`) clears the conversation log and creates a fresh session (empty state shown, model selector still populated with "stub/echo"). Navigating to `/project/iw-ai-core/` starts a new tabId session (empty state per unique tabId), confirming session isolation across pages. |

## Console / Network Errors
None observed. No console errors in `.playwright-cli/console-*.log` files generated during the run.

## No Regressions
V5 confirmed the following all work correctly:
- **Collapse/expand**: Panel collapses to rail (ref `e15`) and re-expands showing full conversation history.
- **New chat session**: Clicking "New chat session" (ref `e12`) clears all bubbles (empty log confirmed) and creates a fresh opencode session; model selector remains populated.
- **Cross-page session isolation**: Visiting `/project/iw-ai-core/` (different tabId → new session) shows empty conversation state with model selector still functional — confirming each page/tab gets its own sessionStorage entry.

## Screenshots Captured
- `ai-dev/active/I-00087/evidences/post/I-00087_v1_streaming_reply_rendered.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v2_history_reload_preserves_conversation.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v3_multi_turn_session.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v5_no_regressions.png`

## Root Cause
N/A — no failures observed.

## Assistant Reply Text (V1)
The specific text of the V1 assistant reply, as captured from the DOM via `playwright-cli eval` querying `.chat-assistant-stream-text`:

```
ok — running ls
```

This is the `stub/echo` model output given the prompt "say pong and nothing else". The model is a simple echo stub, so it reflects the tool it ran rather than the literal prompt — but importantly, it is a **non-empty assistant bubble** that is **not equal to "Session idle."**, confirming the fix is working (pre-fix, only "Session idle." would appear with no assistant bubble).

## Technical Notes

### Model dropdown note
The model dropdown at V1 step 3 showed only `stub/echo` (only option). This is the E2E stack's configured model — not a regression. The fix to `chat.js` works correctly for `message.part.delta` and `message.part.updated` events from opencode, as confirmed by the assistant bubble rendering.

### opencode events confirmed active
The opencode log (`~/.local/share/opencode/log/2026-05-17T192910.log`) shows `message.part.delta`, `message.part.updated`, and `message.updated` events being published during the V1 turn, confirming the backend is generating the correct SSE stream. The `stub/echo` model is a local echo stub that runs `ls`, so the full multi-event streaming trace was observed.

### Pre-fix vs post-fix comparison
Pre-fix (bug evidence from `evidences/pre/I-00087-opencode-events.log`): opencode published the same `message.part.delta` / `message.part.updated` events but the frontend registered `message.part` (wrong name) causing all streaming frames to be silently dropped.

Post-fix (this run): `chat.js:189–210` registers `message.part.updated`, `message.part.delta`, `message.updated`, and all other correct event names. Streaming text accumulates in `.chat-assistant-stream-text` elements via `_appendOrUpdateAssistantMessage`. History reload correctly reads `entry.info` and `entry.parts` from the `GET /api/chat/sessions/{sid}` response.