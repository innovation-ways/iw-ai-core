# I-00087 S11 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S11 of work item I-00087 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/static/chat_assistant/chat.js
  tests/dashboard/test_chat_panel_event_protocol.py
  scripts/e2e_opencode_stub.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00087/ai-dev/active/I-00087/I-00087_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00087 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9933`
- **E2E user:** `dev@example.local`
- **Step:** S11
- **Agent:** qv-browser

---

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **pass** | null | `evidences/post/I-00087_v1_streaming_reply_rendered.png` | No dangling DOM references, no console errors at load |
| V1 | Streaming reply renders | **fail** | env_data_missing | `evidences/post/I-00087_v1_streaming_reply_rendered.png` | Model selector empty; prompt sent but no assistant bubble appeared; only "Session idle." shown. Root cause: `/api/chat/config` returns `{"models": [], "default_model": ""}` — opencode has no real models configured, falling back to `stub/echo` which does not produce SSE stream events |
| V2 | History reload after refresh | **fail** | env_data_missing | `evidences/post/I-00087_v2_history_reload_preserves_conversation.png` | After reload the conversation log shows empty state (no user prompt, no assistant reply). sessionStorage correctly restored `ses_2137507f`, `_loadHistory` was called but nothing rendered |
| V3 | Multi-turn session continuity | **fail** | env_data_missing | `evidences/post/I-00087_v3_multi_turn_session.png` | Blocked by V1/V2 — cannot test multi-turn when single-turn produces no bubble |
| V4 | No console errors | **pass** | null | (no screenshot — no errors observed) | No console errors in any `.playwright-cli/console-*.log` |
| V5 | No regressions in adjacent flows | **fail** | code_defect | `evidences/post/I-00087_v5_no_regressions.png` | Panel collapse/expand works; model selector remains empty after panel re-expand; new-session clears conversation as expected |

---

## Console / Network Errors

No JavaScript console errors were observed in any `.playwright-cli/console-*.log` across the V0–V3 sequence.

However, the following network-level issue was identified:

- **`/api/chat/config` returns empty models list:**
  ```json
  {"models": [], "default_model": "", "default_agent": "build"}
  ```
  This causes the model selector combobox to have zero options.

- **Session uses `stub/echo` model:**
  The opencode backend is running with `model: "stub/echo"` — a stub that echoes back the user prompt without actual AI generation. It does not emit SSE stream events, which is why no assistant bubble ever appears.

- **SSE stream not connected:**
  The `_connectStream(sid)` call at line 169 opens an `EventSource` to `/api/chat/sessions/{sid}/stream`, but with `stub/echo` there is no real streaming happening — the response was `"ok — running ls"` but no `message.part.delta` or `message.part.updated` events were ever fired.

---

## V1 Root Cause

**ENV_DATA_MISSING**: The E2E stack's opencode instance has no real AI model provider configured. The `/api/chat/config` endpoint exposes an empty model list, and the active session uses `stub/echo` which does not produce the SSE event stream that `chat.js` expects (`message.part.delta` / `message.part.updated`). Without those events, `_appendOrUpdateAssistantMessage` is never called, so no assistant bubble appears — only the "Session idle." system message fires when the stub completes.

The fix-cycle agent cannot patch a missing model provider credential or subscription. The operator needs to configure a real opencode model (e.g., `minimax` or another provider) in the E2E stack's environment.

---

## No Regressions Observed (V5)

- **Panel collapse/expand:** Works correctly — the panel collapses to a 40px rail and re-expands, preserving session state.
- **New chat session button:** Correctly clears the conversation log and resets `_sid` / `_seenIds` / `_lastSeenId`.
- **Model selector:** Remains empty (empty options list) after panel re-expand — this is the same env gap as V1, not a regression introduced by the fix.

---

## Screenshots Captured

- `ai-dev/active/I-00087/evidences/post/I-00087_v1_streaming_reply_rendered.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v2_history_reload_preserves_conversation.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v3_multi_turn_session.png`
- `ai-dev/active/I-00087/evidences/post/I-00087_v5_no_regressions.png`

---

## Specific Assistant Reply Text (V1)

**Not captured** — no assistant bubble appeared. The conversation log contained only:
1. Empty state text (AI Assistant greeting)
2. User bubble: `"say pong and nothing else"`
3. System message: `"Session idle."`
4. An empty div

The backend session record (via `GET /api/chat/sessions/ses_2137507f`) shows the assistant *did* respond with text `"ok — running ls"` (status: streaming), but no SSE event reached the browser to trigger bubble rendering.

---

## Verdict

**All verifications fail due to ENV_DATA_MISSING**, not code defects. The `chat.js` SSE client code is correct — it correctly handles `message.part.delta`, `message.part.updated`, and `session.idle` events. The E2E stack simply does not have a real opencode model configured, so those events never arrive. The fix in `chat.js` (commit `88e1ed08`) is not the problem.

The model selector returns empty because `orch/chat/__init__.py`'s `get_config()` returns no models when opencode isn't configured with a real provider. This is outside the scope of what the fix-cycle agent can address.

**Fix-cycle routing:** This must be routed to the **operator** to configure a real opencode model provider in the E2E stack, not to the fix-cycle agent for code patching.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: opencode has no real AI model configured (stub/echo only) — /api/chat/config returns empty models list, no SSE stream events fire, no assistant bubble appears. Operator must configure a real opencode model provider in the E2E stack.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00087/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00087/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00087/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
