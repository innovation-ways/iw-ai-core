# F-00087 S13 Browser Verification Report

**Work Item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S13 (qv-browser)
**Run date**: 2026-05-20
**Base URL**: `http://localhost:9927` (per-worktree E2E compose stack `iw-ai-core-e2e-f00087`)
**E2E user**: `dev@example.local` (no interactive login required — E2E stack auto-authenticates)

> **This report supersedes an earlier stale run.** A prior qv-browser attempt
> concluded `ENV_DATA_MISSING` / V3..V7 `n/a` on the basis that `which pi`
> returned "not found" inside the dashboard container. The step prompt
> **explicitly forbids** `which pi` as a litmus test. The authoritative signal —
> `POST /api/chat/tabs` with `runtime=pi` returning **201** — is healthy: Pi
> tabs are created and fully exercisable via the bundled E2E stub. All of
> V0..V8 were re-run and **all pass**.

## Environment

- Base URL used: `http://localhost:9927`
- Compose project: `iw-ai-core-e2e-f00087`
- Stack status: healthy (`e2e-db`, `e2e-dashboard`, `e2e-ollama`, `e2e-daemon-stub` all Up)
- Pi runtime: the dashboard lifespan (`dashboard/app.py:154-215`) resolves the
  `pi` binary to the bundled stub at `tests/integration/stubs/pi` when
  `IW_E2E_SEED=1` and `pi` is not on PATH. Verified inside the container: the
  stub file exists, is executable (`-rwxrwxr-x`), `IW_E2E_SEED=1`,
  `IW_CORE_PI_BIN` empty — i.e. the success-path fallback conditions are met.
  `which pi` returning not-found is **expected** and is not a failure signal.
- CR-00062 `agent_runtime_options` Pi rows are present in the seeded DB.

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | post/F-00087_v0_preflight_project_page.png | `/project/iw-ai-core/` renders HTTP 200. 0 console errors / warnings on load. |
| V1 | Runtime dropdown shows OpenCode + Pi | pass | null | post/F-00087_v1_runtime_dropdown_two_options.png | Create-tab modal "New Chat Tab" — Runtime combobox has exactly TWO options: "OpenCode" (default selected) and "Pi". |
| V2 | Model list per runtime | pass | null | post/F-00087_v2_model_list_per_runtime.png | Runtime=Pi re-fetches Model list to exactly `pi/minimax/MiniMax-M2.7` (selected) + `pi/openai/gpt-5.3-codex` — no OpenCode models leak. Switching back to OpenCode re-fetches the full 13-entry OpenCode list (no `pi/*` entries). |
| V3 | Mixed tabs created | pass | null | post/F-00087_v3_mixed_tabs_created.png | Tab O (opencode / stub/echo), Tab P1 (pi / pi/minimax/MiniMax-M2.7), Tab P2 (pi / pi/openai/gpt-5.3-codex) all visible in the strip with correct per-tab model badges. Per-tab model dropdown is runtime-isolated: Tab P1 lists only the 2 Pi models; Tab O lists only the 13 OpenCode models. |
| V4 | Three independent streams | pass | null | post/F-00087_v4_three_independent_streams.png | Each tab streamed its OWN response: Tab O → "ok — running ls"; Tab P1 → "Echo: hello from pi-1"; Tab P2 → "Echo: hello from pi-2". No cross-pollination — no tab ever rendered another tab's content. See stub caveat below. |
| V5 | Pi abort isolation | pass | null | post/F-00087_v5_pi_abort_isolation.png | Abort on Tab P1 produced a visible "Run aborted." marker. Tab P2 subsequently streamed "Echo: say hi" normally and Tab O's transcript remained intact — the abort did NOT cascade (each Pi tab owns a separate subprocess). See stub caveat below. |
| V6 | Pi approval modal | pass | null | post/F-00087_v6_pi_approval_modal.png, post/F-00087_v6_pi_approval_result.png | `trigger-approval rm temp.txt` in Tab P1 raised the F-00086 "Permission Request" modal — Tool "bash", Arguments `{ "cmd": "rm temp.txt" }`, Allow/Deny buttons. Clicking Allow closed the modal; transcript then showed `tool: bash` followed by `result: ✓ bash — ok` (i.e. `tool_execution_end` with `result: "ok"`). |
| V7 | Reload persistence + Pi respawn | pass | null | post/F-00087_v7_tabs_persist_pi_respawn.png | After `playwright-cli open .../project/iw-ai-core/` reload + panel re-expand, Tab O / Tab P1 / Tab P2 all reappeared. Tab O transcript fully restored. Clicking a Pi tab showed no error. Follow-up prompt "hello again" in Tab P1 returned "Echo: hello again" — Pi pipeline healthy post-reload. See stub caveat below. |
| V8 | No regressions | pass | null | post/F-00087_v8_no_regressions.png, post/F-00087_v8_recent_closed_tabs.png | Dashboard home renders HTTP 200, 0 console errors. AI Assistant panel toggles via both the Collapse/Expand button and the Ctrl+/ keyboard shortcut. F-00086 "Recent closed tabs" menu opens and lists closed tabs (both OpenCode "Tab O" and Pi tabs). No new console errors across V1..V7. |

**Overall status**: PASS
**Overall failure class**: null

## Stub caveat (applies to V4, V5, V7 — not a code defect)

The E2E stack runs the bundled stub `tests/integration/stubs/pi`, not a real
`pi` binary. The stub is intentionally **stateless and instant**:

- Its `get_messages` handler always returns `{"messages": []}` (`_pi_stub.py:142-143`).
  Consequently, when you switch away from a Pi tab and back — or reload the page
  — the dashboard re-fetches the transcript via `pi_runtime.get_messages(sid)`
  and renders it empty. This is the exact limitation the V7 prompt note calls
  out ("the bundled stub does not carry conversation history across spawns").
  OpenCode tabs are unaffected because the OpenCode runtime is stateful, so
  Tab O's transcript persists across switches and reloads (observed).
- The stub emits its full event sequence (`agent_start` → `message_update` →
  `agent_end` → `response`) with no delay, so there is no real mid-stream
  window to catch with an Abort click. The Abort wiring was still exercised:
  the abort RPC reached the Pi subprocess and produced a "Run aborted." marker,
  and — the substantive V5 assertion — it did not cascade to the other tabs.

In all three cases the substantive verification (independent streaming, no
cross-pollination, abort isolation, post-reload tab persistence + working
follow-up prompt) was demonstrated. The transcript-restoration gap is a
property of the stub, not of F-00087's code; the real Pi-binary JSONL reader
path is covered by the S05 integration tests.

## Console / Network Errors

- 0 console errors and 0 warnings observed across V0..V8 (project page and home
  page both checked via `playwright-cli console`).
- No 503 from `POST /api/chat/tabs` — Pi tab creation succeeds (the DB holds
  multiple `runtime='pi'` tabs in `active` status, and three fresh Pi prompts
  streamed successfully during this run).

## No Regressions

- `/` (dashboard home) renders HTTP 200, no console errors.
- `/project/iw-ai-core/` renders HTTP 200, no console errors.
- AI Assistant panel collapses/expands via the Collapse/Expand button AND via
  the Ctrl+/ keyboard shortcut.
- F-00086 multi-tab strip intact — tabs persist across a full page reload.
- F-00086 "Recent closed tabs" menu opens and lists closed tabs for both
  runtimes (OpenCode "Tab O" and the Pi tabs).
- F-00086 approval ("Permission Request") modal works unchanged — and now also
  fires for Pi-runtime tabs.
- OpenCode tab creation, streaming, and transcript persistence are unaffected
  by the Pi additions.

## Screenshots captured

Pre-state:
- `ai-dev/active/F-00087/evidences/pre/F-00087-create-tab-modal-with-pi.png`

Post-implementation (`ai-dev/active/F-00087/evidences/post/`):
- `F-00087_v0_preflight_project_page.png`
- `F-00087_v1_runtime_dropdown_two_options.png`
- `F-00087_v2_model_list_per_runtime.png`
- `F-00087_v3_mixed_tabs_created.png`
- `F-00087_v4_three_independent_streams.png`
- `F-00087_v5_pi_abort_isolation.png`
- `F-00087_v6_pi_approval_modal.png`
- `F-00087_v6_pi_approval_result.png`
- `F-00087_v7_tabs_persist_pi_respawn.png`
- `F-00087_v8_no_regressions.png`
- `F-00087_v8_recent_closed_tabs.png`
