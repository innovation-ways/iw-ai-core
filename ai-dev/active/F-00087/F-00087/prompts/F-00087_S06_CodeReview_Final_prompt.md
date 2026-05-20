# F-00087_S06_CodeReview_Final_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Review Step**: S06 (Final Review)
**Implementation Steps Reviewed**: S01..S05

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00087 --json`.
- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document
- All implementation step reports: `ai-dev/active/F-00087/reports/F-00087_S0[1,4,5]_*_report.md`
- Per-agent code review report: `ai-dev/active/F-00087/reports/F-00087_S02_CodeReview_report.md`
- Fix reports: `ai-dev/active/F-00087/reports/F-00087_S03_CodeReview_FIX_report.md` (if present)
- All files listed across every implementation report's `files_changed`

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_S06_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of F-00087. Per-agent reviews caught individual-step issues; your job is integration: does the Python `PiRuntime` line up with the TypeScript extension's payload shape, the event normalizer's mapping table, the API branch's response, and the frontend's dropdown contract?

## Read the Design Document FIRST

- Read §Acceptance Criteria (AC1..AC8) in full.
- Read §Invariants (1..8) in full.
- Read §TDD Approach and note every test file the design names. Cross-check against `files_changed` across all steps; any named test file missing is a CRITICAL finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in S01..S05 changed files is a CRITICAL finding with `"category":"conventions"`.

## Review Checklist

### 1. Completeness vs Design

- Every Pi event type listed in design §Scope's mapping table is normalized in `orch/chat/pi/event_normalizer.py` AND has a unit test in `tests/unit/chat/test_pi_event_normalization.py`?
- Every endpoint behaviour listed in §API Changes works? `GET /api/chat/config?runtime=pi` returns Pi catalogue rows; `POST /api/chat/tabs` with `runtime="pi"` accepts a Pi model and rejects an OpenCode-only model with HTTP 400?
- The TypeScript extension exists at `agents/pi/extensions/iw-chat-approvals/` with `index.ts`, `package.json`, `README.md`?
- The sync engine copies the extension (verify by reading the test fixture in `tests/unit/chat/test_sync_agents_extensions.py` and tracing the code path it exercises)?
- The frontend runtime dropdown has BOTH options ("OpenCode" and "Pi")?
- **No TODO/placeholder code.** Grep S01..S05 changed files for `TODO`, `FIXME`, `XXX`, `pass  #`, `raise NotImplementedError` outside abstract methods.

### 2. Cross-layer payload alignment

Trace one round-trip end-to-end — the **approval flow** (AC3):

- TypeScript extension `index.ts` calls `ctx.ui.confirm({tool, args, question})`.
- Pi's RPC layer emits `extension_ui_request` with id `iw-chat-approvals.<uuid>` and payload `{tool, args, question}`.
- `pi_rpc_client.events()` reads the event via the LF-only reader.
- `event_normalizer.normalize_pi_event()` translates it to `{"event":"permission.asked", "data":{"id":..., "tool":..., "args":..., "question":...}}`.
- `RelayManager` adds `"tab_id": <tab.id>` to the event envelope.
- SSE relay forwards to the frontend.
- Frontend modal renders showing tool name + args.
- User clicks Approve → `POST /api/chat/tabs/{tab_id}/permissions/{request_id}` with `{"response":"approve"}`.
- Router calls `pi_runtime.reply_permission(...)` → `pi_rpc_client.reply_extension_ui(request_id, True)`.
- Stdin receives `{"type":"extension_ui_response", "id":"iw-chat-approvals.<uuid>", "value":true}\n`.
- Pi resumes; tool executes.

**Each arrow is a potential mismatch.** Trace each one against the actual code. Any divergence in id format, field names, value types is a HIGH or CRITICAL finding.

### 3. Invariants enforced by tests

For each invariant 1..8, locate the test that proves it. Missing is CRITICAL.

| Invariant | Expected test |
|-----------|---------------|
| 1. No built-in line iterators in pi_jsonl_reader | `tests/unit/chat/test_pi_jsonl_reader.py::test_no_builtin_line_iterators_present` |
| 2. Unicode separators in JSON strings do not split | `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` |
| 3. PiRuntime implements ChatRuntime completely | `tests/unit/chat/test_pi_runtime_abc_compliance.py` |
| 4. MAX_PI_TABS honoured by LRU eviction | `tests/unit/chat/test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru` |
| 5. Idle reaper kills only idle subprocesses | `tests/unit/chat/test_pi_runtime_idle_reaper.py::test_reaper_does_not_kill_recently_active_client` |
| 6. extension_ui_request → permission.asked translation | `tests/unit/chat/test_pi_event_normalization.py::test_extension_ui_request_with_iw_approvals_namespace_becomes_permission_asked` |
| 7. Allowlist extension is one-line | `tests/unit/chat/test_tab_service_allowlist.py::test_create_tab_accepts_runtime_pi` (extending F-00086's file) |
| 8. pi_extensions_synced counter | `tests/unit/chat/test_sync_agents_extensions.py::test_pi_extensions_synced_counter_increments` |

### 4. Cross-agent consistency

- The id prefix `"iw-chat-approvals."` is used consistently across the TypeScript extension (sets it) and the Python normalizer (matches on it). String literal drift here is HIGH (silent UX failure: modal never appears).
- The `agent_runtime_options` model-string format `<cli_tool>/<model>` is consistent between F-00086's existing OpenCode handling and F-00087's Pi handling — frontend doesn't have to special-case the runtime.
- The `tab_service.ALLOWED_RUNTIMES` constant is the ONLY place enforcing the allowlist (no duplicate check in the router or normalizer).
- The Pi `agents/pi/extensions/iw-chat-approvals/` directory does NOT collide with the existing 30 `agents/pi/*.md` agent files (CR-00062). Verify sync_agents handles both paths correctly and `pi_agents_synced` is NOT decremented or affected by the new `pi_extensions_synced` logic.

### 5. Integration points

- `dashboard/app.py` lifespan instantiates BOTH `OpencodeRuntime` AND `PiRuntime` and stores both on app.state. Shutdown closes both cleanly. No order-of-operations bug.
- `get_runtime_for_tab(tab, app_state)` is called wherever the router needs the per-tab runtime. Grep `dashboard/routers/chat.py` for `app.state.opencode_runtime` and `app.state.pi_runtime` — direct access bypassing the helper is a MEDIUM finding (defensive guard escaped).
- The `subscribe` AsyncIterator chain (PiRuntime → RelayManager → SSE) preserves `tab_id` on every event. F-00086 invariant #2 must hold for Pi events too.

### 6. Test coverage holism

- Every acceptance criterion AC1..AC8 has at least one test (unit or integration) covering it. Map AC → test explicitly in your report.
- The integration tests exercise the stub `pi` binary on PATH (not a real Pi runtime). If S05 accidentally requires the real `pi` binary, that's a test isolation failure and a CRITICAL finding.

### 7. Security (cross-cutting)

- No hardcoded API keys, model credentials, or auth tokens in any new file (Python or TypeScript).
- The TypeScript extension reads `.opencode/opencode.json` from the project root only — no path traversal vulnerability (e.g., extension shouldn't try to read `~/.opencode/...` or arbitrary paths).
- Subprocess command construction: `pi`, `--mode`, `rpc`, `--session-dir`, `<dir>` — no user-controlled shell strings. If S01 used `shell=True` anywhere, that's a CRITICAL finding (shell injection vector).

## Test Verification (NON-NEGOTIABLE)

Run targeted tests over the F-00087 surface (S11/S12 own full-suite execution):

```bash
uv run pytest tests/unit/chat/test_pi_*.py tests/unit/chat/test_sync_agents_extensions.py tests/unit/chat/test_tab_service_allowlist.py -v
uv run pytest tests/integration/test_chat_pi_*.py -v
make lint
make typecheck
```

Report results. Any failure here is a CRITICAL finding (downstream QV gates catch broader regressions).

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "F-00087",
  "steps_reviewed": ["S01", "S04", "S05"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": "",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "targeted: X tests/unit/chat/test_pi_* passed, Y tests/integration/test_chat_pi_* passed",
  "missing_requirements": [],
  "notes": ""
}
```
