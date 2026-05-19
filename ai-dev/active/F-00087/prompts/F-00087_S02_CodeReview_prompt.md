# F-00087_S02_CodeReview_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration in this Feature.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00087 --json`.
- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document (read §Scope, §Acceptance Criteria, §Invariants, §Boundary Behavior, §TDD Approach in full)
- `ai-dev/active/F-00087/reports/F-00087_S01_Backend_report.md` — S01 implementation report
- All files listed in S01's `files_changed`
- `docs/research/R-00072-pi-dashboard-embedding.md` §2 (JSONL framing) — the basis for invariant #1 and #2

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_S02_CodeReview_report.md`

## Context

You are reviewing the Pi backend layer: Python `orch/chat/pi/` subpackage, the TypeScript Pi extension, sync-engine extension, API branch, lifespan wiring, and the one-line allowlist extension. The single highest-risk piece is `pi_jsonl_reader.py` — verify its correctness against R-00072 §2 first.

## Read the Design Document FIRST

- Read §Acceptance Criteria (AC1..AC8).
- Read §Invariants (1..8) — each maps to a test you must verify exists.
- Read §TDD Approach and note every test file the design names by path. Cross-check against S01's `files_changed`. Tests S01 deferred to S05 (most of them) are fine; tests S01 was supposed to write as RED evidence and didn't are CRITICAL findings.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in S01-changed files is a CRITICAL finding with `"category":"conventions"`.

## Review Checklist

### 1. LF-only JSONL reader correctness (highest priority)

- **Invariant #1**: grep `orch/chat/pi/pi_jsonl_reader.py` for `readline`, `for line in`, `splitlines`, `iter(.*readline`. ANY match (outside docstrings) is a CRITICAL finding. The reader MUST split bytes on `b'\\n'` only.
- **Invariant #2**: verify a test exists that feeds the reader a JSON string containing a Unicode line separator (` ` / `\\u2028` etc.) and asserts the record survives intact. If S01 deferred this to S05, flag MEDIUM — it should have been the RED test.
- Partial-record buffering: a record that arrives across two `stream.read(N)` calls is assembled correctly.
- Trailing `\\r` (CRLF endings) stripped to LF-only semantics.
- EOF behaviour: if the buffer is non-empty at stream close, the final record is yielded (or documented as dropped — match what the test asserts).

### 2. PiRpcClient correctness

- Subprocess started with `start_new_session=True` (so SIGTERM to the group cleans up children).
- `send_command` writes JSON-encoded + `\\n`-terminated to stdin; flushes (or relies on `await proc.stdin.drain()`).
- `events()` consumes the reader, json.loads, dispatches. Background pump task started in `start()`, cancelled in `close()`.
- `request_response` correlates command → response correctly (Pi's protocol echoes `{type:"response", ok:bool}` after each command per R-00072 §2; correlation by send-order is acceptable for v1 — flag MEDIUM if the implementation tries something more elaborate without a documented reason).
- `reply_extension_ui` writes the EXACT shape `{"type":"extension_ui_response","id":<id>,"value":<value>}` to stdin.
- `close()` is idempotent (calling twice doesn't crash).
- `last_activity` updated on BOTH send AND receive.

### 3. PiRuntime lifecycle and pool semantics

- **Invariant #3**: `PiRuntime.__abstractmethods__` is empty (constructible). If a test in `tests/unit/chat/test_pi_runtime_abc_compliance.py` doesn't exist yet (S05 owns it), flag MEDIUM with note that S05 must add it; check that every `ChatRuntime` abstract method has a concrete implementation here.
- **Invariant #4**: MAX_PI_TABS cap honoured by LRU eviction. Verify the eviction path: when `_get_or_spawn_client` would push active count > cap, the LRU client's `close()` is awaited BEFORE the new client is spawned. If the implementation rejects the call instead of evicting (HTTP 429 anywhere), that violates the design and is HIGH.
- **Invariant #5**: Idle reaper only kills idle subprocesses. Trace `_reaper_loop`: it checks `now - last_activity > IDLE_TIMEOUT_SECONDS`; if `last_activity` is updated on every event (not just user prompts), then a tab streaming a long response is NOT killed mid-stream. Verify both halves.
- Lazy spawn: `create_session()` reserves the slot but does NOT spawn the subprocess; first `prompt()`/`subscribe()` triggers the spawn. Flag HIGH if subprocesses are spawned at `create_session` time (defeats the lazy-on-restart UX from the design).
- Configurability: `IW_CORE_MAX_PI_TABS` and `IW_CORE_PI_IDLE_TIMEOUT` env-var overrides present and respected.
- Reaper task cancelled cleanly in PiRuntime shutdown (`close_all_clients` or equivalent).

### 4. Event normalizer completeness

- **Invariant #6**: every Pi event type listed in design §Scope's mapping table has a corresponding case in `normalize_pi_event`. Build the table from the design and check each row against the code. Missing rows are HIGH (incomplete coverage).
- `extension_ui_request` with id starting `"iw-chat-approvals."` translates to `permission.asked` with the enriched `{id, tool, args, question}` payload. Other id namespaces pass through.
- Unknown event types pass through (frontend ignores unknown — verify that's the contract by reading the existing chat.js event dispatch).
- The normalizer does NOT add `tab_id` — that's RelayManager's job (F-00086 invariant #2). Flag if `tab_id` shows up in the normalizer.

### 5. TypeScript Pi extension correctness

- `index.ts` reads `.opencode/opencode.json` ONCE per session (cached); refetch on mtime change is best-effort, OK to skip in v1 if S01 documents it.
- Policy parsing: `permission.bash[<pattern>]` glob match; first-match wins.
- Fail-safe behaviour:
  - Missing file → all "allow" (matches today's iw-ai-core "all allow" behaviour; not a regression).
  - Malformed JSON → all "ask" (fails toward user prompts, not silent execution).
- `ctx.ui.confirm` id is auto-prefixed with `"iw-chat-approvals."` so the normalizer can route it.
- On denial, throws — this is the documented way to block tool execution in Pi extensions per R-00072 §4.
- `package.json` has the minimal Pi extension manifest. If the exact manifest shape is uncertain (R-00072 may not pin it precisely), flag LOW with a note that S05's integration test will catch shape mismatches.

### 6. Allowlist extension is one-line

- **Invariant #7**: `git diff orch/chat/tab_service.py` should show only the literal `{"opencode"}` → `{"opencode", "pi"}` change. Any surrounding refactor is out of scope for this Feature and is a MEDIUM finding ("scope creep").

### 7. API branch (get_config) correctness

- The Pi branch reads from `agent_runtime_options WHERE cli_tool='pi' AND enabled=true ORDER BY sort_order`.
- The `ai_assistant.models` per-project allowlist intersection is applied with the same logic as the OpenCode branch (don't duplicate the function; factor a helper if the two branches diverge).
- Response shape is unchanged from F-00086.
- `default_model` resolves correctly: if a Pi row has `is_default=true`, that wins; else first row; else "".
- Empty Pi catalogue case: returns `{"models": [], "default_model": "", ...}` cleanly (no 500).

### 8. Lifespan wiring (dashboard/app.py)

- `PiRuntime` instantiated in lifespan and stored on `app.state.pi_runtime`.
- Shutdown cleanly closes all Pi subprocesses.
- `get_runtime_for_tab(tab, app_state)` helper raises `ValueError` on unknown runtime (defensive guard).
- F-00086's OpenCode runtime is NOT regressed — both runtimes coexist in lifespan.

### 9. Sync engine extension copy

- **Invariant #8**: `pi_extensions_synced` field on `AgentSyncResult` defaults to 0; increments on each successful copy.
- `shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy2)` preserves mtimes (`copy2` does, plain `copy` doesn't).
- Broken symlinks inside extension directories caught and logged; sync continues with other extensions.
- The existing `pi_agents_synced` behaviour (from CR-00062) is NOT regressed.
- CLI human/JSON output reflects the new counter; total file count updated.

### 10. TDD RED evidence

- S01's report `tdd_red_evidence` cites `test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` (or `test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru`) with a plausible failure snippet (`ImportError`, `AttributeError`, or `AssertionError` — NOT `SyntaxError` or collection error).
- Would the named test fail against pre-change code? Pre-change: no `orch/chat/pi/` directory → `ImportError` is correct RED shape.

## Test Verification (NON-NEGOTIABLE)

Run targeted tests on the F-00087 surface only (S11/S12 own full-suite execution):

```bash
uv run pytest tests/unit/chat/test_pi_jsonl_reader.py -v
uv run pytest tests/unit/chat/test_pi_runtime_lru_eviction.py -v
make lint
make typecheck
```

Report results. Any failure is a CRITICAL finding (downstream QV gates catch broader regressions).

## Severity Levels

Per template — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00087",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
