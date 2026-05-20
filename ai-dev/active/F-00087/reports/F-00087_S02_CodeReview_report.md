# F-00087 — S02 CodeReview Report

**Work item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S02 (CodeReview, per-agent review of S01)
**Agent**: code-review-impl
**Status**: complete
**Verdict**: **fail** (1 CRITICAL, 1 HIGH, 2 MEDIUM_FIXABLE; S03 must address)

---

## Summary

The S01 backend layer is well-structured, all module-level invariants are present in the code, and pre-review quality gates (`make lint`, `make format`, `make typecheck`) plus the targeted unit tests (`tests/unit/chat/test_pi_jsonl_reader.py`, `tests/unit/chat/test_pi_runtime_lru_eviction.py`) all pass — 8 tests passed in 0.22s. The LF-only reader is correct (no `readline()` / `for line in stream` / `splitlines` / `iter(...readline...)` patterns in source code — all 3 grep hits are in docstrings/comments which is permitted). PiRuntime is fully concrete (`__abstractmethods__ == frozenset()`). The allowlist extension is a literal one-line change. The Pi extension manifest, sync engine extension copy, CLI extension, and lifespan wiring all match the design.

**However**, the single most important test in the package — `test_unicode_separators_in_json_string_do_not_split` — has a CRITICAL bug: it uses `json.dumps()` with the default `ensure_ascii=True`, which **escapes U+2028 / U+2029 to ASCII ` ` / ` ` sequences before encoding to bytes**. The stream bytes therefore contain NO raw 0xE2 0x80 0xA8 bytes — the regression case the test claims to cover is never actually exercised. A readline-based reader would pass this test identically. Invariant #2's safety net is non-functional.

In addition, the Pi branch of `get_config` omits the `default_agent` key promised by the endpoint docstring, the `PiRuntime.create_session(directory=...)` argument is stored but never forwarded to the Pi subprocess (Pi extension would read `.opencode/opencode.json` from the wrong directory), and a stray `_loadPolicy` double-call in the TypeScript extension's `session_start` handler is a leftover refactoring artefact.

S03 must address the CRITICAL Unicode-separator test bug and the HIGH `directory` argument plumbing. The MEDIUM_FIXABLE items (`default_agent` shape, extension double-load) should be fixed in the same pass.

## Test Results

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | PASS (`All checks passed!`) |
| Format | `make format` (check) | PASS (`797 files already formatted`) |
| Typecheck | `make typecheck` | PASS (`Success: no issues found in 267 source files`) |
| Targeted unit | `pytest test_pi_jsonl_reader.py test_pi_runtime_lru_eviction.py -v --no-cov` | PASS (`8 passed in 0.22s`) |

## Review Result (machine-readable)

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00087",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "testing",
      "file": "tests/unit/chat/test_pi_jsonl_reader.py",
      "line": 62,
      "description": "The headline Unicode-separator regression test does NOT actually exercise the regression. `json.dumps({'text': f'line1{line_sep}line2{para_sep}end'}).encode()` uses Python's default `ensure_ascii=True`, which escapes U+2028 and U+2029 to ASCII `\\u2028` / `\\u2029` sequences BEFORE encoding to bytes. Verified by `python -c \"import json; print(json.dumps({'x':'\\u2028'}).encode())\"` → `b'{\"x\": \"\\\\u2028\"}'` (no raw 0xE2 0x80 0xA8 bytes). A readline-based reader would pass this test identically because the encoded bytes contain only LF separators and ASCII content. Invariant #2's safety net is therefore non-functional — if S03/S05 or any future change broke the LF-only reader to use `readline()`, this test would still pass.",
      "suggestion": "Either pass `ensure_ascii=False` to `json.dumps(...)` so the U+2028/U+2029 bytes are written verbatim into the stream, OR construct the bytes manually: `record1 = b'{\"text\":\"line1\\xe2\\x80\\xa8line2\\xe2\\x80\\xa9end\"}'`. Assert `b'\\xe2\\x80\\xa8' in record1` before feeding the stream so the test self-verifies it is exercising the regression case. Re-run with a temporarily-broken reader (e.g., replace the byte scan with `await stream.readline()`) to confirm the test now fails."
    },
    {
      "severity": "HIGH",
      "category": "architecture",
      "file": "orch/chat/pi/pi_runtime.py",
      "line": 105,
      "description": "`PiRuntime.create_session(*, model, agent, directory)` stores `directory` in `_client_tab_meta[session_id]['directory']` but never forwards it to the Pi subprocess. `_get_or_spawn_client` builds `session_dir = self._base_session_dir / session_id` (i.e., `~/.pi/agent/sessions/<uuid>/`), and `PiRpcClient.start()` spawns `pi --mode rpc --session-dir <dir>` with no `cwd` override — so the subprocess inherits the dashboard's working directory, not the target project's repo root. The TypeScript Pi extension's `_loadPolicy(repoRoot)` then reads `.opencode/opencode.json` from the wrong directory (dashboard cwd instead of project repo). AC3 (approval modal works on Pi tabs) implicitly depends on the policy file being read from the project, not the dashboard.",
      "suggestion": "Either (a) pass `cwd=directory` to `asyncio.create_subprocess_exec` in `PiRpcClient.start()` when `directory` is provided, OR (b) pass `--cwd <directory>` to the `pi` CLI if Pi supports it, OR (c) include `directory` in a `session_start` envelope the Pi extension consumes. Update `PiRpcClient.__init__` to accept `cwd: Path | None = None` and `PiRuntime._get_or_spawn_client` to pass `cwd=meta.get('directory')`. Add a test that constructs PiRuntime, calls create_session(directory='/tmp/foo'), spawns the client (with stub binary), and asserts the subprocess was spawned with cwd='/tmp/foo'."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "dashboard/routers/chat.py",
      "line": 889,
      "description": "Pi branch of `get_config` returns a response missing the `default_agent` key. The OpenCode branch always sets `default_agent` (line 922 / 978: `raw.get('default_agent', '')`), and the endpoint docstring (line 818) promises `{models, default_model, default_agent, project_directory}`. `_apply_ai_assistant_allowlist` only adds `default_agent` when truthy (line 805-806), so the Pi branch's result dict has only `{models, default_model, project_directory}`. Although the current frontend does not appear to read `default_agent` (grep -r 'default_agent' dashboard/static dashboard/templates returns nothing), the documented response shape is violated and any future consumer relying on the key would break.",
      "suggestion": "In the Pi branch, always include `default_agent: \"\"` in `result`. Either (a) change `_apply_ai_assistant_allowlist` to always include `default_agent` (default \"\") and remove the `if default_agent:` guard, OR (b) add `result['default_agent'] = ''` after the dict construction in the Pi branch's three result paths."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "agents/pi/extensions/iw-chat-approvals/index.ts",
      "line": 141,
      "description": "`session_start` handler does a redundant triple-step: `_sessionPolicy = _loadPolicy(repoRoot); _policyCache.delete(repoRoot); _sessionPolicy = _loadPolicy(repoRoot);` — loads, invalidates cache, re-loads. The first load is overwritten by the second; the cache invalidation is pointless because nothing changed between the two loads. Looks like a leftover from a refactor.",
      "suggestion": "Reduce to a single load: `_policyCache.delete(repoRoot); _sessionPolicy = _loadPolicy(repoRoot);` (delete-then-load, so each new session forces a fresh read from disk and ignores any cross-session stale entry). The delete is the only meaningful step if the goal is per-session refresh."
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "code_quality",
      "file": "orch/chat/pi/pi_rpc_client.py",
      "line": 127,
      "description": "`PiRpcClient.close()` uses `proc.terminate()` (SIGTERM) and `proc.kill()` (SIGKILL) on the leader only. The subprocess is launched with `start_new_session=True`, which puts it in its own process group — but `proc.terminate()` sends SIGTERM only to the leader, not the whole group. If the Pi binary spawns child processes (likely for tool execution), those children may be orphaned when the Pi parent exits. The docstring on line 17 specifically claims `start_new_session=True` is set 'so SIGTERM to the process group cleans up any child processes Pi might have spawned' — but no `killpg` call is ever made, so this property is not actually achieved.",
      "suggestion": "Replace `proc.terminate()` with `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)` (and the SIGKILL fallback with `os.killpg(..., signal.SIGKILL)`), wrapped in `contextlib.suppress(ProcessLookupError)`. The whole-group kill is what `start_new_session=True` was meant to enable. Alternative: document that orphan-child cleanup is deferred to F-00087's stated out-of-scope item ('Crash-recovery reaper for orphaned subprocesses') and update the docstring to match what the code actually does."
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "testing",
      "file": "tests/unit/chat/test_pi_jsonl_reader.py",
      "line": 0,
      "description": "Partial-record buffering across MULTIPLE read calls is not covered. The test `test_partial_record_flushed_on_stream_close` covers EOF with a partial record, but does not cover the case the design specifically calls out: a record arriving across two `stream.read(N)` calls. The current implementation handles this correctly (the `bytearray` buffer survives across `await stream.read(_CHUNK_SIZE)` iterations), but there is no test asserting it. A future refactor could break cross-chunk buffering without test failure.",
      "suggestion": "Add a test that uses `asyncio.StreamReader.feed_data(part1); await asyncio.sleep(0); feed_data(part2); feed_eof()` to simulate split-chunk delivery and asserts the single full record is yielded. S05 (Tests step) is the natural owner per the design's TDD Approach section, but flagging here so it does not slip."
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "testing",
      "file": "tests/unit/chat/",
      "line": 0,
      "description": "Per design §Invariants, the following invariant tests should exist but are deferred to S05: `test_pi_runtime_abc_compliance.py` (#3), `test_pi_runtime_idle_reaper.py` (#5), `test_pi_event_normalization.py` (#6), `test_tab_service_allowlist.py` Pi extension (#7), `test_sync_agents_extensions.py` (#8), `test_pi_rpc_client.py`. The S01 prompt explicitly states most tests are S05's responsibility, and the two RED-evidence tests (Unicode separators + LRU eviction) are present. Not blocking, but worth confirming in S06 (Final Review) that S05 covers all eight invariants.",
      "suggestion": "S05 must add all six missing test files. S06 must verify each design §Invariant has a matching test before passing the work item."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "orch/chat/pi/pi_runtime.py",
      "line": 44,
      "description": "`MAX_PI_TABS` and `IDLE_TIMEOUT_SECONDS` are computed at module import time from environment variables. Setting `IW_CORE_MAX_PI_TABS` or `IW_CORE_PI_IDLE_TIMEOUT` AFTER the module is imported has no effect. Production behavior is fine because the daemon process inherits env at start, but tests using `monkeypatch.setenv` would need module reload to take effect. The design's invariant #4 test (`test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru`) hardcodes `assert MAX_PI_TABS == 6`, which works because no env var is set. The env-var override design promise (AC5: 'configurable via env var IW_CORE_PI_IDLE_TIMEOUT for ops-tuning') is technically met, but only at process start.",
      "suggestion": "Either read the env vars inside `__init__` (so each PiRuntime instance picks up current env), or document the import-time-fixed behaviour in the docstring. Reading inside __init__ is more flexible and aligns with how tests can pass `base_session_dir=...` to override defaults."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "dashboard/routers/chat.py",
      "line": 834,
      "description": "`from sqlalchemy import select` is imported inline inside `get_config` with `noqa: PLC0415`. The same module already imports from sqlalchemy at TYPE_CHECKING time (line 80). Moving the import to the top-level would be cleaner and remove the noqa.",
      "suggestion": "Add `from sqlalchemy import select` at the top of `dashboard/routers/chat.py` near the other sqlalchemy imports; remove the inline import. (PLC0415 is the suppression for 'import not at top-level' — the noqa is justifying a code-smell instead of fixing it.)"
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "orch/chat/pi/pi_runtime.py",
      "line": 319,
      "description": "`_touch_activity` reaches into `client._last_activity` (single-underscore private attribute, marked `noqa: SLF001`) to update it directly. This couples PiRuntime to PiRpcClient internals. The PiRpcClient already updates `_last_activity` on every send/receive, so this direct write is mostly redundant — except when the runtime knows about an event the client doesn't (none currently; touch is called only from prompt/abort/reply_permission/subscribe, all of which already trigger send_command which already updates the client's _last_activity).",
      "suggestion": "Remove the direct `client._last_activity = now` write — the client maintains its own activity timestamp via send_command / pump_events, so this is dead code at best and a confusing dual source of truth at worst. The meta-dict update is still needed for sessions with no active client (e.g., between eviction and respawn)."
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "ai-dev/active/F-00087/reports/F-00087_S01_Backend_report.md",
      "line": 64,
      "description": "S01's report acknowledges (`## TDD RED Evidence` section) that it did not capture the literal RED transcript — the agent wrote module and test together and re-ran to capture GREEN output. The expected RED shape (ModuleNotFoundError on the missing `orch.chat.pi` import) is plausible and the AST-based grep test (`test_no_builtin_line_iterators_present`) provides ongoing regression coverage. Per the step prompt's TDD section, RED evidence should be 'ImportError, AttributeError, or AssertionError — NOT SyntaxError or collection error', which the hypothetical shape satisfies. Not blocking but worth noting that future TDD steps should capture the literal RED output before writing the GREEN code.",
      "suggestion": "Document this in CLAUDE.md / iw-ai-core-testing skill if not already present: 'TDD RED evidence must be the literal pytest output captured BEFORE the implementation is written. Re-running tests after GREEN is achieved does not satisfy this — the agent must save the failing transcript from the first run.'"
    }
  ],
  "mandatory_fix_count": 4,
  "tests_passed": true,
  "test_summary": "make lint, make format (check), make typecheck all green; pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v --no-cov: 8 passed in 0.22s.",
  "notes": "Architecture is sound. The CRITICAL finding is in the test file, not the production code — the LF-only reader itself appears correct and the AST-based grep test (`test_no_builtin_line_iterators_present`) does provide a separate, working safety net against regression. Once S03 fixes the Unicode-separator test to actually exercise raw U+2028/U+2029 bytes (and fixes the directory-plumbing HIGH finding), this work item should pass S06 Final Review without further structural concerns. The deferred-to-S05 test list is large (6 of 8 invariant tests) but consistent with the design's TDD Approach split."
}
```

## Findings Detail

### CRITICAL — Unicode regression test does not exercise the regression

`tests/unit/chat/test_pi_jsonl_reader.py:62` — `json.dumps(..., ensure_ascii=True)` (the default) escapes U+2028 / U+2029 to ASCII ` ` / ` ` BEFORE encoding to bytes. Verified:

```
$ uv run python -c "import json; print(json.dumps({'x':' '}).encode())"
b'{"x": "\\u2028"}'
```

No raw 0xE2 0x80 0xA8 bytes ever reach the reader, so a `readline()`-based reader would pass this test identically — the safety net for Invariant #2 is broken. **Fix**: either `json.dumps(..., ensure_ascii=False).encode()` or construct bytes manually (`b'{"text":"line1\xe2\x80\xa8line2"}'`) and assert the raw bytes are present before feeding the stream.

### HIGH — `directory` argument never reaches Pi subprocess

`orch/chat/pi/pi_runtime.py:105-117` — `create_session(directory=...)` is stored in metadata but never forwarded; `PiRpcClient.start()` does not set `cwd`. The Pi extension reads `.opencode/opencode.json` from `process.cwd()` (extension index.ts:140), so policy is loaded from the dashboard's directory instead of the project's. AC3 (approval modal on Pi tabs) depends on the policy file being read from the right place. Fix by passing `cwd=directory` through `PiRpcClient.__init__` to `asyncio.create_subprocess_exec`.

### MEDIUM_FIXABLE — `default_agent` missing in Pi branch response

`dashboard/routers/chat.py:889+` — Pi branch result dict lacks `default_agent`; OpenCode branch always includes it. Endpoint docstring promises `{models, default_model, default_agent, project_directory}`. Fix in `_apply_ai_assistant_allowlist` or the three result-construction paths.

### MEDIUM_FIXABLE — Extension `session_start` triple-step

`agents/pi/extensions/iw-chat-approvals/index.ts:138-145` — `_loadPolicy` is called twice with a cache-delete in the middle; the second call overwrites the first. Reduce to `_policyCache.delete(repoRoot); _sessionPolicy = _loadPolicy(repoRoot);`.

### MEDIUM_SUGGESTION items

- `pi_rpc_client.py:127` — `proc.terminate()` doesn't kill the process group despite `start_new_session=True`; docstring overstates the cleanup guarantee.
- Cross-chunk partial-record buffering not tested.
- Six of eight invariant tests deferred to S05 (consistent with prompt, but S06 must verify).

### LOW items

- Env-var read at module import time (not per-instance).
- Inline sqlalchemy import with `noqa: PLC0415`.
- Cross-class private attribute write (`client._last_activity`) with SLF001 suppression.
- TDD RED evidence not literally captured (hypothetical transcript in S01 report).

## Files Reviewed

All files listed in S01's `files_changed`:

**New (Python)** — `orch/chat/pi/__init__.py`, `pi_jsonl_reader.py`, `pi_rpc_client.py`, `pi_runtime.py`, `event_normalizer.py`.
**Modified (Python)** — `orch/chat/__init__.py`, `orch/chat/tab_service.py`, `dashboard/routers/chat.py`, `dashboard/app.py`, `orch/skills/sync_agents.py`, `orch/cli/skills_commands.py`.
**New (TypeScript)** — `agents/pi/extensions/iw-chat-approvals/index.ts`, `package.json`, `README.md`.
**New (Tests)** — `tests/unit/chat/test_pi_jsonl_reader.py`, `tests/unit/chat/test_pi_runtime_lru_eviction.py`.

## Notes

S03 (CodeReviewFix) must apply: the CRITICAL test fix, the HIGH directory-plumbing fix, and the two MEDIUM_FIXABLE items (`default_agent` shape, extension double-load). The MEDIUM_SUGGESTION and LOW items are recommended but not blocking. Once S03 lands, S04 (Frontend) and S05 (Tests) can proceed; S06 should verify every design §Invariant maps to a passing test before passing the item.
