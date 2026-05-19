# F-00087_S05_Tests_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainers via pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00087 --json`.
- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document (read §Acceptance Criteria, §Invariants, §Boundary Behavior, §TDD Approach in full)
- All implementation reports from S01/S04 (and fix reports from S03/S07 if present)
- All files listed in those reports' `files_changed`
- Existing test suite: `tests/unit/chat/test_pi_jsonl_reader.py` (S01 wrote a partial RED file), `tests/unit/chat/test_pi_runtime_lru_eviction.py` (S01 wrote a partial RED file)
- CR-00062 reference: `tests/integration/test_pi_dispatch_end_to_end.py` (if present) — pattern for stub `pi` binary on PATH

## Output Files

Unit:
- `tests/unit/chat/test_pi_jsonl_reader.py` — extend S01's RED-skeleton
- `tests/unit/chat/test_pi_rpc_client.py` — new
- `tests/unit/chat/test_pi_runtime_lru_eviction.py` — extend S01's RED-skeleton
- `tests/unit/chat/test_pi_runtime_idle_reaper.py` — new
- `tests/unit/chat/test_pi_runtime_abc_compliance.py` — new
- `tests/unit/chat/test_pi_event_normalization.py` — new
- `tests/unit/chat/test_sync_agents_extensions.py` — new
- `tests/unit/chat/test_tab_service_allowlist.py` — extend (file from F-00086; add `runtime="pi"` case)

Integration:
- `tests/integration/test_chat_pi_mixed_tabs_independence.py` — new
- `tests/integration/test_chat_pi_approval_flow.py` — new
- `tests/integration/test_chat_pi_lifecycle.py` — new

Stub binary:
- `tests/integration/stubs/pi` — 3-line bash script (chmod +x)

Report:
- `ai-dev/active/F-00087/reports/F-00087_S05_Tests_report.md`

## Context

You are writing the dedicated test coverage for F-00087. The design's §Invariants section is your acceptance contract — every invariant maps to exactly one named test.

## Requirements

### 1. Unit tests

**`tests/unit/chat/test_pi_jsonl_reader.py`** (extend the RED-skeleton from S01)
- `test_unicode_separators_in_json_string_do_not_split` (invariant #2) — already exists from S01; verify it passes GREEN.
- `test_no_builtin_line_iterators_present` (invariant #1) — read the module source and assert no `readline`, `for line in`, `splitlines`, `iter(.*readline` matches (outside docstrings).
- `test_partial_record_buffered_across_reads` — feed `b'{"a":1`, then `b'}\n'`; assert exactly one record yielded after the second read.
- `test_crlf_line_endings_normalized` — feed `b'{"a":1}\r\n{"b":2}\r\n'`; assert two records yielded with no `\r` in either.
- `test_empty_stream_yields_nothing` — feed `b''`; assert no records.
- `test_trailing_partial_at_eof` — feed `b'{"a":1}\n{"b":2'` then close; document whether the trailing partial is yielded or dropped (match the implementation; test the contract either way).

**`tests/unit/chat/test_pi_rpc_client.py`**
- `test_send_command_writes_json_with_lf_terminator` — mock the subprocess; assert `send_command({"type":"prompt","message":"hi"})` writes `b'{"type":"prompt","message":"hi"}\n'` to stdin.
- `test_events_iterates_jsonl_from_stdout` — feed mock stdout `b'{"type":"agent_start"}\n{"type":"agent_end"}\n'`; assert two events.
- `test_request_response_correlates_by_send_order` — send two commands; mock stdout emits two `{"type":"response","ok":true}` events; assert the right call gets the right response.
- `test_reply_extension_ui_writes_correct_shape` — `reply_extension_ui("iw-chat-approvals.abc", True)` writes `b'{"type":"extension_ui_response","id":"iw-chat-approvals.abc","value":true}\n'`.
- `test_close_is_idempotent` — calling close() twice does not raise.
- `test_close_escalates_sigterm_to_sigkill` — simulate a subprocess that ignores SIGTERM; assert SIGKILL is sent after 5s timeout. Use a fast-forward time fixture.
- `test_last_activity_updates_on_send_and_receive` — initial value; after a send, value increased; after a receive, value increased again.

**`tests/unit/chat/test_pi_runtime_lru_eviction.py`** (extend S01's RED)
- `test_seventh_tab_evicts_lru` (invariant #4) — already exists from S01; verify GREEN. Create 7 mock clients; assert the LRU client's `close()` was awaited.
- `test_evicted_tab_persists_session_metadata` — after eviction, the tab's `pi_session_path` (or equivalent) is preserved on the runtime's metadata dict, so respawn-on-activate via `pi --session <path>` can resume.
- `test_max_pi_tabs_env_var_override` — set `IW_CORE_MAX_PI_TABS=3`; create 4 tabs; assert eviction fires at the 4th.

**`tests/unit/chat/test_pi_runtime_idle_reaper.py`** (invariant #5)
- `test_reaper_kills_client_idle_past_threshold` — mock time; create a client; advance time by `IDLE_TIMEOUT_SECONDS + 1`; run one reaper tick; assert client closed.
- `test_reaper_does_not_kill_recently_active_client` — create a client; advance time but `touch_last_activity` within the threshold; assert NOT closed.
- `test_idle_timeout_env_var_override` — set `IW_CORE_PI_IDLE_TIMEOUT=1`; advance time by 2s; assert reaper culls.
- `test_reaper_task_cancelled_cleanly_on_runtime_shutdown` — start runtime; close it; assert reaper task is cancelled and the program does not hang.

**`tests/unit/chat/test_pi_runtime_abc_compliance.py`** (invariant #3)
- `test_pi_runtime_is_constructible` — `PiRuntime.__abstractmethods__` is `frozenset()`; `PiRuntime()` instantiates without raising.
- `test_every_chat_runtime_abstract_method_is_implemented` — discover via `ChatRuntime.__abstractmethods__`; for each, assert `PiRuntime` declares a method with `inspect.iscoroutinefunction()` True (where applicable) and a compatible signature.

**`tests/unit/chat/test_pi_event_normalization.py`** (invariant #6)
- One test per row in design §Scope's event-mapping table. Use `pytest.mark.parametrize` if convenient.
- `test_message_update_text_delta_becomes_message_part_added`.
- `test_tool_execution_start_passthrough`, `test_tool_execution_update_passthrough`, `test_tool_execution_end_passthrough`.
- `test_agent_start_becomes_session_start`, `test_agent_end_becomes_session_idle`.
- `test_extension_ui_request_with_iw_approvals_namespace_becomes_permission_asked`.
- `test_extension_ui_request_with_other_namespace_passes_through`.
- `test_extension_error_becomes_session_error`.
- `test_unknown_event_type_passes_through`.
- `test_normalizer_does_not_add_tab_id` — verify the returned envelope has no top-level `"tab_id"` key (RelayManager owns that).

**`tests/unit/chat/test_sync_agents_extensions.py`** (invariant #8, AC7)
- `test_sync_copies_pi_extensions_subdirs_into_dot_pi_extensions` — fixture with `agents/pi/extensions/foo/index.ts`; assert `<project>/.pi/extensions/foo/index.ts` exists byte-identical.
- `test_pi_extensions_synced_counter_increments` — assert `result.pi_extensions_synced == 1` after sync of one extension.
- `test_sync_is_idempotent` — run twice; counter same, file content unchanged, mtimes preserved.
- `test_broken_symlink_in_extension_dir_does_not_break_sync` — create a dangling symlink inside the fixture extension; assert sync logs a warning and counter for OTHER extensions still increments.
- `test_existing_pi_agents_still_synced` — verify CR-00062's `pi_agents_synced` counter still works alongside the new `pi_extensions_synced`.

**`tests/unit/chat/test_tab_service_allowlist.py`** (extend; invariant #7)
- Add `test_create_tab_accepts_runtime_pi` — `tab_service.create_tab(db, project_id="X", runtime="pi", model="pi/minimax/MiniMax-M2.7")` succeeds; row persisted with `runtime="pi"`.
- Keep all existing F-00086 tests intact (the OpenCode allowlist case still passes).

### 2. Integration tests

All use the testcontainer fixture from `tests/integration/conftest.py`. After `Base.metadata.create_all()`, apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (per `tests/CLAUDE.md`).

**Stub `pi` binary** (`tests/integration/stubs/pi`):
```bash
#!/usr/bin/env bash
# Stub pi binary for F-00087 integration tests. Emits canned JSONL events
# in response to commands on stdin. Pattern lifted from CR-00062 S05.
exec python3 "$(dirname "$0")/_pi_stub.py" "$@"
```

(A pure-Python stub is easier to make deterministic than a bash one for event streams. The bash wrapper picks the Python stub so `which pi` resolves to a single bash file but the logic is in the Python sibling. Both files live under `tests/integration/stubs/`.)

Write `_pi_stub.py` to:
- Parse `--mode rpc --session-dir <dir>` args.
- Read JSONL commands on stdin.
- For each `{"type":"prompt"}`: emit `agent_start`, `message_update` (text_delta), `agent_end`, `response ok` events on stdout.
- For `{"type":"abort"}`: emit `agent_end` with abort marker; respond ok.
- For test-specific scenarios (extension_ui_request flow): emit an `extension_ui_request` event when prompted with a "trigger-approval" marker; wait for `extension_ui_response` on stdin; emit `tool_execution_*` events based on the response value.

Test fixture prepends `tests/integration/stubs/` to PATH for the duration of the test (`monkeypatch.setenv("PATH", f"{stub_dir}:{old_path}")`).

**`tests/integration/test_chat_pi_mixed_tabs_independence.py`** (AC1)
- `test_one_opencode_and_two_pi_tabs_stream_independently`: stub `pi` on PATH; stub OpenCode runtime (existing test pattern); create three tabs; send a prompt in each; subscribe to each tab's SSE; assert events for each tab carry the correct `tab_id` and that aborting one Pi tab does not affect the OpenCode tab or the other Pi tab.
- `test_two_pi_tabs_with_different_models_use_distinct_subprocesses`: assert each Pi tab has its own subprocess (mock the subprocess factory to count spawns).

**`tests/integration/test_chat_pi_approval_flow.py`** (AC3)
- `test_ask_pattern_surfaces_approval_modal_and_round_trips_response`: stub `pi` configured to emit an `extension_ui_request` with id `"iw-chat-approvals.test-001"`; create a Pi tab; send a "trigger-approval" prompt; subscribe to SSE; assert one `permission.asked` event arrives with `{id, tool, args, question}`; POST `/api/chat/tabs/{id}/permissions/iw-chat-approvals.test-001` with `{"response":"approve"}`; assert the stub's stdin received `{"type":"extension_ui_response","id":"iw-chat-approvals.test-001","value":true}\n`; assert a `tool.execution.end` event follows.
- `test_deny_response_sends_value_false`: same flow with `{"response":"deny"}` → stdin receives `value:false`.
- `test_policy_file_missing_defaults_to_allow`: fixture project with no `.opencode/opencode.json`; assert no `permission.asked` event surfaces for tools the stub emits.

**`tests/integration/test_chat_pi_lifecycle.py`**
- `test_first_prompt_spawns_subprocess_lazily`: create a Pi tab; assert no subprocess spawned; send first prompt; assert exactly one subprocess spawned.
- `test_idle_reaper_terminates_then_reactivate_respawns`: set `IW_CORE_PI_IDLE_TIMEOUT=1`; create + prompt a Pi tab; sleep 2s + run one reaper tick; assert subprocess closed; send another prompt; assert a new subprocess spawned with `--session <pi_session_path>` argv.
- `test_lru_eviction_when_creating_seventh_tab`: set `IW_CORE_MAX_PI_TABS=3`; create + prompt 4 Pi tabs; assert the LRU subprocess was terminated; assert the evicted tab's row still has its `pi_session_path` preserved.
- `test_pi_binary_missing_returns_503`: prepend an EMPTY directory to PATH (no pi binary anywhere); attempt to send a prompt in a Pi tab; assert HTTP 503 with the documented error message.

### 3. Test isolation rules

- NEVER mock the database in these tests; use the testcontainer fixture.
- NEVER connect tests to the live DB (port 5433).
- NEVER call `importlib.reload(orch.config)`; use `monkeypatch.delenv()`.
- Use `monkeypatch.setenv` for `IW_CORE_MAX_PI_TABS` and `IW_CORE_PI_IDLE_TIMEOUT` overrides.
- The stub `pi` binary is a TEST asset under `tests/integration/stubs/`; it is NOT installed system-wide.

## Project Conventions

Read `tests/CLAUDE.md` (fixture rules, FTS trigger requirement, live-DB write guard). Read `skills/iw-ai-core-testing/SKILL.md` for assertion-strength rules and the test red-flag checklist.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `uv run pytest tests/unit/chat/test_pi_*.py tests/unit/chat/test_sync_agents_extensions.py tests/unit/chat/test_tab_service_allowlist.py -v` — your new unit tests must pass
5. `uv run pytest tests/integration/test_chat_pi_*.py -v` — your new integration tests must pass

Do NOT run `make test-unit` or `make test-integration` — S11/S12 own those.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/chat/test_pi_jsonl_reader.py",
    "tests/unit/chat/test_pi_rpc_client.py",
    "tests/unit/chat/test_pi_runtime_lru_eviction.py",
    "tests/unit/chat/test_pi_runtime_idle_reaper.py",
    "tests/unit/chat/test_pi_runtime_abc_compliance.py",
    "tests/unit/chat/test_pi_event_normalization.py",
    "tests/unit/chat/test_sync_agents_extensions.py",
    "tests/unit/chat/test_tab_service_allowlist.py",
    "tests/integration/test_chat_pi_mixed_tabs_independence.py",
    "tests/integration/test_chat_pi_approval_flow.py",
    "tests/integration/test_chat_pi_lifecycle.py",
    "tests/integration/stubs/pi",
    "tests/integration/stubs/_pi_stub.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/chat/test_pi_*: X passed; tests/integration/test_chat_pi_*: Y passed",
  "tdd_red_evidence": "n/a — dedicated test-coverage step (per template TDD RED Evidence rules; tests-impl is exempt)",
  "blockers": [],
  "notes": ""
}
```
