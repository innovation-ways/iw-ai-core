# I-00060 S15 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S15 of work item I-00060 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00060/ai-dev/active/I-00060/I-00060_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00060 S15 QvBrowser Report

## Environment
- **Base URL used:** `http://localhost:9922` (from `$IW_BROWSER_BASE_URL`)
- **E2E user:** `dev@example.local`
- **Project:** `iw-ai-core` (E2E seed — has RAG index: 42 files, 100 chunks)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Submit scrolls user bubble into view (AC1) | **fail** | `evidences/post/I-00060_v1_submit_scrolls.png` | After 8 warmup questions, scrolled `#chat-messages` to top (scrollTop=0), sent 9th question, immediately measured. Result: `lastBottom=1984.98px`, `cbot=586px`. Condition `lastBottom <= cbot` evaluates to `1984.98 <= 586` — FALSE. Bubble is NOT scrolled into view. Root cause: `scrollToBottom()` in `composer.js:291` calls `anchor.scrollIntoView({ behavior: 'instant', block: 'end' })` but after the call `scrollTop` remains 0 — the scroll does not fire. |
| V2 | Empty assistant bubble compact pre-stream (AC2) | **fail** | `evidences/post/I-00060_v2_empty_bubble_compact.png` | ENV_DATA_MISSING — E2E stub responds in <200ms; measured `height=120px, body_text_len=102` immediately after click (stream already arrived). Cannot capture pre-stream state. Retry impossible since all stub responses complete before human reaction time. |
| V3 | Conditional follow-scroll while streaming (AC3) | **pass** | `evidences/post/I-00060_v3_conditional_follow_scroll.png` | Mid-stream: scrolled messages container up 300px (scrollTop: ~156 → 0). Waited 3s for more tokens. Final `scrollTop=0` — stream did NOT snap back. Expected `scrollHeight - clientHeight = 156`; observed `scrollTop = 0`. V3 PASS. |
| V4 | No regressions (citations, mermaid, collapse, console) | **pass** | `evidences/post/I-00060_v4_no_regressions.png` | Console: 0 errors, 0 warnings. Collapse/expand works. Stub does not emit `[data-cite]` citations or mermaid SVG (E2E stub limitation). No page crashes. |

## Console / Network Errors
None. Console messages: 0 (Errors: 0, Warnings: 0).

## No Regressions
- Console is clean across all pages visited
- Chat panel collapse/expand (button `#chat-collapse-btn` / `#chat-expand-rail`) functions correctly
- Stub responses return correctly on all pages
- No unhandled exceptions or HTTP errors

## Screenshots captured
- `ai-dev/active/I-00060/evidences/post/I-00060_v1_submit_scrolls.png`
- `ai-dev/active/I-00060/evidences/post/I-00060_v2_empty_bubble_compact.png`
- `ai-dev/active/I-00060/evidences/post/I-00060_v3_conditional_follow_scroll.png`
- `ai-dev/active/I-00060/evidences/post/I-00060_v4_no_regressions.png`

## Root Cause — V1 (Code Defect)

**File:** `dashboard/static/chat/composer.js:403-408`

```javascript
function scrollToBottom() {
  var anchor = document.getElementById('chat-scroll-anchor');
  if (anchor) {
    anchor.scrollIntoView({ behavior: 'instant', block: 'end' });
  }
}
```

**Diagnosis:** After appending the user bubble (`appendUserBubble()` at line 283) and the assistant bubble placeholder (`appendAssistantBubble()` at line 287), `scrollToBottom()` is called at line 291. However, `scrollTop` remains at 0 after this call — the browser does NOT scroll `#chat-messages` to bring `#chat-scroll-anchor` into view.

The `getBoundingClientRect()` measurements confirm the last user bubble (`lastBottom=1984.98px` in viewport coordinates) is physically below the container's visible area (`cbot=586px`). The condition `lastBottom <= cbot` fails (1984.98 > 586).

Possible cause: `Element.scrollIntoView({ block: 'end' })` may not scroll when the anchor is already positioned at the end of the scroll container's content due to the way the empty-state `<div>` at the top pushes layout. Alternatively, the `scroll-behavior: auto` CSS on `#chat-messages` (`chat.css:7`) may interfere with the instantaneous scroll. Or `scrollIntoView` calculates the target position as "element's top edge aligned to container's top edge" (block:start default) rather than "element's bottom edge aligned to container's bottom edge" even with `block:end`.

**Fix direction:** Replace `anchor.scrollIntoView({ behavior: 'instant', block: 'end' })` with a direct `scrollTop` assignment:
```javascript
var messages = document.getElementById('chat-messages');
messages.scrollTop = messages.scrollHeight;
```
This guarantees the container scrolls to the bottom regardless of scrollIntoView quirks.

## Root Cause — V2 (ENV_DATA_MISSING)
E2E stub backend (`stub:latest`) responds to all questions within ~100ms, far faster than a real LLM (1-5s to first token). The pre-stream empty assistant bubble state is impossible to capture with the stub. V2 cannot be verified in this environment. Real LLM providers (openai, anthropic, ollama) would show the compact empty bubble for ~1-3 seconds before the first token arrives.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S15` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00060/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00060/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
