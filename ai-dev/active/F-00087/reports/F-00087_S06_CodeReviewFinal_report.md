```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "F-00087",
  "steps_reviewed": ["S01", "S04", "S05"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "integration",
      "file": "dashboard/routers/chat.py",
      "line": 250,
      "description": "The create_tab, send_prompt, abort_tab, reply_permission, get_tab, and stream_tab endpoints are all wired exclusively to OpencodeRuntime/OpencodeClient. None of them use get_runtime_for_tab() to dispatch to PiRuntime for Pi tabs. create_tab (line 282) gates on 'not healthy or client is None' where 'client' is the OpenCode client — then calls 'await client.create_session()' (line 352) and stores the result in 'opencode_session_id' (line 370). For a runtime='pi' tab, this would either create an OpenCode session (wrong runtime) or fail entirely if OpenCode is down. The send_prompt endpoint (line 653) reads tab.opencode_session_id and calls 'await client.prompt()' via OpenCode. abort_tab (line 699) and reply_permission (line 722) have the same flaw. The get_runtime_for_tab() helper was created in orch/chat/__init__.py but is never imported or called in dashboard/routers/chat.py. AC3 (approval modal works on Pi tabs) cannot work because reply_permission calls client.reply_permission() (OpenCode) not pi_runtime.reply_permission(). This is the primary missing integration layer — all per-tab runtime-dispatching endpoints must be updated to resolve the runtime via get_runtime_for_tab and dispatch accordingly.",
      "suggestion": "For each affected endpoint: (1) import get_runtime_for_tab from orch.chat; (2) look up the tab from DB; (3) call runtime = get_runtime_for_tab(tab, request.app.state); (4) dispatch to runtime.create_session()/prompt()/abort()/reply_permission() etc. The 'client: OpencodeClient | None = Depends(_get_client)' dependency injection is OpenCode-specific and must be supplemented with per-tab runtime dispatch. For create_tab specifically, dispatch should be based on body.runtime before the tab is created. For stream_tab, the RelayManager approach may need a Pi-specific SSE path or the RelayManager needs to support PiRuntime's subscribe() interface.",
      "cross_cutting": true
    },
    {
      "severity": "CRITICAL",
      "category": "integration",
      "file": "dashboard/routers/chat.py",
      "line": 265,
      "description": "The create_tab docstring still says 'Runtime allowlist: currently {\"opencode\"}; attempting \"pi\" or any other value returns 400.' This is factually wrong after F-00087 — ALLOWED_RUNTIMES now includes 'pi' and the allowlist check at line 271 will pass for runtime='pi'. However the rest of the function uses OpenCode-only paths, so the tab IS created but with a misrouted session. The stale docstring also signals that the Pi dispatch path was never implemented, not merely documented incorrectly.",
      "suggestion": "Update the docstring to reflect the actual allowlist. More importantly, implement the Pi dispatch path so the docstring matches the behavior.",
      "cross_cutting": false
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/",
      "line": 0,
      "description": "All integration tests (test_chat_pi_approval_flow.py, test_chat_pi_lifecycle.py, test_chat_pi_mixed_tabs_independence.py) bypass the HTTP router layer and invoke PiRuntime directly. No integration test exercises the HTTP API path: POST /api/chat/tabs with runtime=pi, POST /api/chat/tabs/{id}/prompt for a Pi tab, or POST /api/chat/tabs/{id}/permissions/{rid} for a Pi tab. The router-layer gap identified above (CRITICAL finding) is therefore not caught by any test — the tests pass precisely because they don't go through the broken router.",
      "suggestion": "Add router-level integration tests using FastAPI TestClient (or the testcontainer db_session + app.dependency_overrides pattern from tests/dashboard/) that: (a) POST /api/chat/tabs with runtime=pi and verify a Pi session is created in PiRuntime (not OpenCode); (b) POST /api/chat/tabs/{id}/prompt for a Pi tab and verify the stub Pi binary receives the command; (c) POST /api/chat/tabs/{id}/permissions/{rid} for a Pi tab and verify the approval is routed to PiRuntime.reply_permission().",
      "cross_cutting": false
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "conventions",
      "file": "dashboard/routers/chat.py",
      "line": 147,
      "description": "_get_runtime() at line 147 hardcodes 'opencode_runtime': 'return getattr(request.app.state, \"opencode_runtime\", None)'. This is the FastAPI dependency used for health-gating and client access across all tab endpoints. It only exposes the OpenCode runtime, making it structurally impossible for the existing Depends() chain to serve Pi tabs correctly. The _check_runtime_healthy() dependency at line 162 likewise checks only the OpenCode runtime's health.",
      "suggestion": "Either: (a) make _get_runtime() accept the tab's runtime parameter and dispatch accordingly (but FastAPI dependency injection does not naturally thread per-request path params into a Depends()); or (b) refactor the affected endpoints to not use _get_runtime() for Pi tabs — instead resolve the runtime inside each endpoint handler after reading the tab from DB.",
      "cross_cutting": false
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "dashboard/routers/chat.py",
      "line": 834,
      "description": "S02 flagged the inline 'from sqlalchemy import select' with noqa: PLC0415 inside get_config. S03 noted it was cosmetic and skipped it. Still present in the code.",
      "suggestion": "Move to top-level imports alongside other sqlalchemy imports. Remove the noqa suppression.",
      "cross_cutting": false
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "orch/chat/pi/pi_rpc_client.py",
      "line": 135,
      "description": "close() uses proc.terminate() (SIGTERM) and proc.kill() (SIGKILL) on the leader only, not the process group, despite start_new_session=True. S02 flagged this as MEDIUM_SUGGESTION; S03 deferred it to 'Out of Scope: Crash-recovery reaper'. The docstring at line 17 still says 'so SIGTERM to the process group cleans up any child processes Pi might have spawned' which overstates what the code actually does.",
      "suggestion": "Update the docstring to accurately describe what the code does (leader-only SIGTERM). The actual killpg fix can remain out-of-scope as agreed, but the docstring should not promise behavior the code does not deliver.",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "targeted: 66 tests/unit/chat/test_pi_* passed; 13 tests/integration/test_chat_pi_* passed (total 79); make lint: All checks passed; make format-check: 807 files already formatted; make type-check: Success: no issues found in 267 source files",
  "missing_requirements": [
    "Router dispatch to PiRuntime for create_tab, send_prompt, abort_tab, reply_permission, get_tab, stream_tab endpoints",
    "Router-level integration tests for Pi tab HTTP API paths"
  ],
  "notes": "The orch/chat/pi/ Python subpackage, PiRuntime ABC implementation, JSONL reader, event normalizer, sync engine extension, CLI output, frontend dropdown, and all 79 unit/integration tests are correct and well-implemented. The single critical gap is the missing router-level dispatch: the get_runtime_for_tab() helper was created but never wired into dashboard/routers/chat.py. All per-tab endpoints (create, prompt, abort, permissions, stream) remain OpenCode-only. The approval round-trip (AC3) works at the Python level (PiRuntime.reply_permission -> PiRpcClient.reply_extension_ui) but is unreachable via the HTTP endpoint because the endpoint routes to OpencodeClient. S07 must add runtime dispatch to the affected router endpoints and add router-level tests."
}
```

---

## AC → Test Mapping (AC1..AC8)

| AC | Description | Test(s) |
|----|-------------|---------|
| AC1 | Mixed OpenCode + Pi tabs run independently | `tests/integration/test_chat_pi_mixed_tabs_independence.py` — 4 tests covering distinct subprocesses, stream independence, abort isolation, close isolation |
| AC2 | LF-only JSONL parsing handles Unicode line separators | `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` (fixed by S03 to use `ensure_ascii=False`) |
| AC3 | Approval modal works on Pi tabs | `tests/integration/test_chat_pi_approval_flow.py` — 3 tests (ask surfaces permission.asked, approve → value:true, deny → value:false). **PARTIALLY COVERED**: these tests exercise PiRuntime directly; the HTTP router path (`POST /api/chat/tabs/{id}/permissions/{rid}`) for Pi tabs is NOT tested and NOT wired |
| AC4 | LRU eviction at MAX_PI_TABS=6 | `tests/unit/chat/test_pi_runtime_lru_eviction.py` — 4 tests including `test_seventh_tab_evicts_lru`; `tests/integration/test_chat_pi_lifecycle.py::test_lru_eviction_when_creating_nth_tab` |
| AC5 | Idle reaper kills subprocess after 15 minutes | `tests/unit/chat/test_pi_runtime_idle_reaper.py` — 5 tests; `tests/integration/test_chat_pi_lifecycle.py::test_idle_reaper_terminates_then_reactivate_respawns` |
| AC6 | Event normalization — Pi events arrive in OpenCode shape | `tests/unit/chat/test_pi_event_normalization.py` — 21 tests covering every event type in §Scope mapping table |
| AC7 | Sync engine copies Pi extensions | `tests/unit/chat/test_sync_agents_extensions.py` — 7 tests covering copy, counter, idempotency, error handling, existing pi_agents_synced unchanged |
| AC8 | Runtime dropdown offers Pi; per-tab model dropdown is runtime-scoped | `tests/unit/chat/test_tab_service_allowlist.py::test_create_tab_accepts_runtime_pi` (allowlist); frontend behavior verified by manual smoke (S04 report) and S13 qv-browser |

---

## Invariant → Test Mapping (1..8)

| Invariant | Test | Status |
|-----------|------|--------|
| 1. No built-in line iterator in pi_jsonl_reader | `tests/unit/chat/test_pi_jsonl_reader.py::test_no_builtin_line_iterators_present` (AST walk) | PRESENT, PASSING |
| 2. Unicode separators in JSON strings do not split | `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` | PRESENT, PASSING (fixed by S03: ensure_ascii=False + self-verify asserts) |
| 3. PiRuntime implements ChatRuntime completely | `tests/unit/chat/test_pi_runtime_abc_compliance.py` — 3 tests | PRESENT, PASSING |
| 4. MAX_PI_TABS honoured by LRU eviction | `tests/unit/chat/test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru` | PRESENT, PASSING |
| 5. Idle reaper kills only idle subprocesses | `tests/unit/chat/test_pi_runtime_idle_reaper.py::test_reaper_does_not_kill_recently_active_client` | PRESENT, PASSING |
| 6. extension_ui_request → permission.asked translation | `tests/unit/chat/test_pi_event_normalization.py::test_extension_ui_request_with_iw_approvals_namespace_becomes_permission_asked` | PRESENT, PASSING |
| 7. Allowlist extension is one-line | `tests/unit/chat/test_tab_service_allowlist.py::test_create_tab_accepts_runtime_pi` | PRESENT, PASSING |
| 8. pi_extensions_synced counter increments | `tests/unit/chat/test_sync_agents_extensions.py::test_pi_extensions_synced_counter_increments` | PRESENT, PASSING |

All 8 invariants are covered. All tests pass.

---

## Round-Trip Trace: Approval Flow (AC3)

Each arrow traced against actual code files:

| Step | Code Location | Status |
|------|---------------|--------|
| TypeScript `ctx.ui.confirm({tool, args, question})` called | `agents/pi/extensions/iw-chat-approvals/index.ts:179` — `await ev.ctx.ui.confirm({ tool: ev.tool, args: ev.args, question })` | OK |
| Pi RPC emits `extension_ui_request` with id `iw-chat-approvals.<uuid>` | `tests/integration/stubs/_pi_stub.py:65-74` (stub emits `{"type":"extension_ui_request","id":"iw-chat-approvals.test-001",...}`) | OK (stub); production depends on Pi SDK behaviour documented as best-effort |
| `pi_rpc_client.events()` reads via LF-only reader | `orch/chat/pi/pi_rpc_client.py:257` — `async for raw in aiter_jsonl_lines(proc.stdout)` | OK |
| `event_normalizer.normalize_pi_event()` → `{"event":"permission.asked","data":{id,tool,args,question}}` | `orch/chat/pi/event_normalizer.py:115-127` — prefix check `request_id.startswith(_IW_APPROVALS_PREFIX)` → `permission.asked` | OK |
| `RelayManager` adds `"tab_id"` to envelope | NOT verified directly in this review (F-00086 feature — the normalizer correctly does NOT add tab_id; `orch/chat/pi/event_normalizer.py:7-9` confirms invariant) | OK (by invariant and test `test_normalizer_does_not_add_tab_id`) |
| SSE relay forwards to frontend | `dashboard/routers/chat.py:613-650` — stream_tab uses RelayManager; but this endpoint uses `tab.opencode_session_id` to get the relay, which fails for Pi tabs (no opencode_session_id) | BROKEN — stream_tab line 638 comment: "Tab has no opencode_session_id — cannot start relay" |
| Frontend modal renders showing tool + args | `dashboard/static/chat_assistant/chat.js:511,587-615` — handles `permission.asked` event, builds modal with tool and args | OK (frontend handles the event correctly) |
| User clicks Approve → `POST /api/chat/tabs/{tab_id}/permissions/{rid}` with `{"response":"approve"}` | `dashboard/static/chat_assistant/chat.js:638` — fetches the correct endpoint | OK (frontend call is correct) |
| Router calls `pi_runtime.reply_permission(...)` | `dashboard/routers/chat.py:722-747` — DOES NOT dispatch to PiRuntime; uses `tab.opencode_session_id` and `client.reply_permission()` (OpenCode) | BROKEN |
| `pi_rpc_client.reply_extension_ui(request_id, True)` | `orch/chat/pi/pi_runtime.py:184-201` — correctly calls `client.reply_extension_ui(request_id, value)` | OK (code path works if reached; not reached from router) |
| Stdin receives `{"type":"extension_ui_response","id":"iw-chat-approvals.<uuid>","value":true}\n` | `orch/chat/pi/pi_rpc_client.py:227-235` — `reply_extension_ui` builds the correct JSONL | OK |

Summary: The Python-layer round-trip (PiRuntime → PiRpcClient → normalizer → permission.asked → reply_permission → reply_extension_ui) is correct and tested. The HTTP-layer round-trip is broken because `stream_tab` and `reply_permission` both gate on `opencode_session_id` and dispatch to OpencodeClient, bypassing PiRuntime.

---

## Lint / Format / Typecheck / Test Output Summaries

```
make lint:        "All checks passed!"
make format-check: "807 files already formatted"
make type-check:  "Success: no issues found in 267 source files"

pytest (unit):
  66 tests in tests/unit/chat/test_pi_*.py + test_sync_agents_extensions.py + test_tab_service_allowlist.py
  All 66 PASSED in 5.37s (seed 3928736250)

pytest (integration):
  13 tests in tests/integration/test_chat_pi_*.py
  All 13 PASSED in 3.81s (seed 631799394)

Total: 79 tests, 0 failures, 0 errors.
```

---

## Notes on LOW / SUGGESTION Issues

1. **Docstring at `chat.py:265`**: says `"pi"` returns 400 (stale from F-00086). Must be updated as part of the router fix in S07.

2. **`client._last_activity` direct write (SLF001)**: carried from S02/S03 as intentional (LOW). The MEDIUM_SUGGESTION from S02 about `_touch_activity` being dead code when the client already updates its own activity timestamp is still valid but not blocking.

3. **Inline sqlalchemy import** (`noqa: PLC0415`) at `chat.py:834`: cosmetic, not blocking.

4. **Pi extension manifest best-effort warning**: README documents that the `package.json` shape is inferred from documentation. Non-blocking; acknowledged in S01 report as a known risk.

5. **Cross-chunk partial-record test**: S02 flagged this as MEDIUM_SUGGESTION for S05. S05 added `test_partial_record_buffered_across_reads` which covers this case (visible in the 66-test run output above). Resolved.

6. **proc.terminate() vs killpg docstring**: The docstring at `pi_rpc_client.py:17` still overstates the cleanup guarantee. Classified LOW — not blocking but should be corrected.
