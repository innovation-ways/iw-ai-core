# F-00087 — S03 CodeReviewFix Report

**Work item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S03 (CodeReviewFix, fix cycle 1 of 5)
**Agent**: code-review-fix-impl
**Review addressed**: S02 (`F-00087_S02_CodeReview_report.md`)
**Status**: complete

---

## Summary

Applied all four mandatory findings (1 CRITICAL, 1 HIGH, 2 MEDIUM_FIXABLE) from the
S02 review.  No unrelated refactors; the MEDIUM_SUGGESTION and LOW findings are left
for the noted owners (S05 for cross-chunk buffering test; `proc.terminate()` →
`killpg` is out-of-scope per the design's "Out of Scope" item *Crash-recovery reaper
for orphaned subprocesses*).

Quality gates all green; targeted F-00087 unit suite (8 tests) all pass.

## Findings Addressed

### CRITICAL — Unicode-separator regression test does not exercise the regression

* **File**: `tests/unit/chat/test_pi_jsonl_reader.py:62`
* **Change**: `json.dumps(..., ensure_ascii=False).encode()` (both records) so raw
  3-byte UTF-8 sequences for U+2028 / U+2029 land in the stream.  Added two
  self-verification asserts:

  ```python
  assert b"\xe2\x80\xa8" in record1, "test bug: U+2028 not encoded as raw bytes"
  assert b"\xe2\x80\xa9" in record1, "test bug: U+2029 not encoded as raw bytes"
  ```

  If `ensure_ascii=False` is ever dropped (the Python default), the self-verify
  asserts fire before the JSONL-reader behaviour is even checked — the test
  refuses to silently pass on a non-regression input.  Invariant #2's safety net
  now actually exercises the regression case from R-00072 §2.

### HIGH — `directory` argument never reaches Pi subprocess

* **Files**: `orch/chat/pi/pi_rpc_client.py` (`PiRpcClient.__init__` adds `cwd=`
  parameter; `start()` passes `cwd=str(self._cwd) if self._cwd else None` to
  `asyncio.create_subprocess_exec`), `orch/chat/pi/pi_runtime.py`
  (`_get_or_spawn_client` reads `meta.get("directory")` and passes it as
  `cwd=directory` to `PiRpcClient`).
* **Why this matters**: The Pi extension reads `.opencode/opencode.json` via
  `process.cwd()` (`agents/pi/extensions/iw-chat-approvals/index.ts:140`).
  Without `cwd`, the subprocess inherited the dashboard's working directory and
  loaded the wrong policy file — AC3 (approval modal on Pi tabs) was implicitly
  broken.  Pi tabs now spawn with `cwd=<project repo root>`.

### MEDIUM_FIXABLE — `default_agent` missing in Pi-branch response

* **File**: `dashboard/routers/chat.py`
* **Change**: `_apply_ai_assistant_allowlist` now always emits `default_agent`
  (default `""`), and the two Pi-branch result dicts that bypass the helper
  (no `ai_assistant` config / no project_key) explicitly set
  `default_agent: ""`.  The endpoint docstring's documented shape
  `{models, default_model, default_agent, project_directory}` is now honoured
  for both runtimes and across every code path.

### MEDIUM_FIXABLE — Extension `session_start` triple-step

* **File**: `agents/pi/extensions/iw-chat-approvals/index.ts:138-145`
* **Change**: Reduced `_loadPolicy(repoRoot); _policyCache.delete(repoRoot);
  _sessionPolicy = _loadPolicy(repoRoot);` to the single intent-bearing pair
  `_policyCache.delete(repoRoot); _sessionPolicy = _loadPolicy(repoRoot);`.
  The cache is now invalidated *before* the load so each new session forces a
  fresh read from disk (the original intent inferable from the leftover).

## Findings Skipped

| Finding | Severity | Reason |
|---------|----------|--------|
| `proc.terminate()` does not killpg the subprocess group | MEDIUM_SUGGESTION | Out of scope: F-00087 design §Out of Scope explicitly defers "Crash-recovery reaper for orphaned subprocesses" to a follow-up; the docstring's overclaim was a minor wording issue, not a code defect. |
| Cross-chunk partial-record buffering test missing | MEDIUM_SUGGESTION | Owned by S05 per the design's TDD Approach split; review report explicitly flagged for S05. |
| Six of eight invariant tests deferred | MEDIUM_SUGGESTION | Owned by S05; consistent with the S01 prompt that scoped only the two RED-evidence tests to S01. |
| `MAX_PI_TABS` / `IDLE_TIMEOUT_SECONDS` read at module import time | LOW | Production behaviour is correct (daemon inherits env at start); test isolation is fine because the LRU test uses `MAX_PI_TABS == 6` (the default).  Not blocking. |
| Inline `from sqlalchemy import select` with `noqa: PLC0415` | LOW | Cosmetic; not blocking.  Touching top-level imports here would inflate the diff beyond what S03 should change. |
| `client._last_activity = now` direct write (SLF001) | LOW | Documented and intentional — keeps the runtime authoritative for meta refresh even when the client doesn't see the activity.  Not blocking. |
| TDD RED-evidence transcript not literally captured | LOW | Process-doc improvement for CLAUDE.md / iw-ai-core-testing skill; out of scope for S03. |

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/chat/test_pi_jsonl_reader.py` | `ensure_ascii=False` + raw-byte self-verify asserts in `test_unicode_separators_in_json_string_do_not_split` |
| `orch/chat/pi/pi_rpc_client.py` | `PiRpcClient(cwd=...)` parameter; `subprocess_exec(cwd=str(self._cwd) if self._cwd else None)` |
| `orch/chat/pi/pi_runtime.py` | `_get_or_spawn_client` reads `meta["directory"]` and passes it as `cwd=` to `PiRpcClient` |
| `dashboard/routers/chat.py` | `_apply_ai_assistant_allowlist` always emits `default_agent`; both Pi-branch result dicts set `default_agent: ""` |
| `agents/pi/extensions/iw-chat-approvals/index.ts` | Removed duplicated `_loadPolicy` call in `session_start` handler |

## Test Results

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | PASS (`All checks passed!`) |
| Format | `make format` (check) | PASS (`797 files already formatted`) |
| Typecheck | `make typecheck` | PASS (`Success: no issues found in 267 source files`) |
| Targeted unit | `uv run pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v --no-cov` | PASS (`8 passed in 0.19s`) |

## Fix Result (machine-readable)

```json
{
  "step": "S03",
  "agent": "code-review-fix-impl",
  "work_item": "F-00087",
  "fix_cycle": 1,
  "review_step": "S02",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL",
      "status": "fixed",
      "files_changed": ["tests/unit/chat/test_pi_jsonl_reader.py"],
      "description": "Pass ensure_ascii=False to json.dumps so raw U+2028/U+2029 UTF-8 bytes land in the stream; added self-verify asserts on the encoded bytes so the test refuses to silently pass on non-regression input."
    },
    {
      "finding_number": 2,
      "severity": "HIGH",
      "status": "fixed",
      "files_changed": ["orch/chat/pi/pi_rpc_client.py", "orch/chat/pi/pi_runtime.py"],
      "description": "PiRpcClient.__init__ accepts cwd=; start() passes it to asyncio.create_subprocess_exec. PiRuntime._get_or_spawn_client forwards meta['directory'] as cwd so the Pi extension reads .opencode/opencode.json from the project repo, not the dashboard's cwd."
    },
    {
      "finding_number": 3,
      "severity": "MEDIUM_FIXABLE",
      "status": "fixed",
      "files_changed": ["dashboard/routers/chat.py"],
      "description": "_apply_ai_assistant_allowlist always emits default_agent (default ''); both Pi-branch bypass paths set default_agent: '' so the documented {models, default_model, default_agent, project_directory} shape is preserved for Pi."
    },
    {
      "finding_number": 4,
      "severity": "MEDIUM_FIXABLE",
      "status": "fixed",
      "files_changed": ["agents/pi/extensions/iw-chat-approvals/index.ts"],
      "description": "Reduced session_start handler from load→delete→load to delete→load so each new session forces a fresh read; removed the no-op first load."
    }
  ],
  "findings_skipped": [
    {"finding_id": "MEDIUM_SUGGESTION-proc.terminate-not-killpg", "reason": "Out of scope per design §Out of Scope (crash-recovery reaper deferred)."},
    {"finding_id": "MEDIUM_SUGGESTION-cross-chunk-buffering-test", "reason": "Owned by S05 (tests-impl) per the design's TDD Approach."},
    {"finding_id": "MEDIUM_SUGGESTION-six-deferred-invariant-tests", "reason": "Owned by S05; consistent with the S01 prompt scope."},
    {"finding_id": "LOW-env-vars-at-import-time", "reason": "Production behaviour correct; not blocking."},
    {"finding_id": "LOW-inline-sqlalchemy-import", "reason": "Cosmetic; not in S03 scope."},
    {"finding_id": "LOW-touch-activity-direct-write", "reason": "Documented and intentional; not blocking."},
    {"finding_id": "LOW-tdd-red-evidence-not-literally-captured", "reason": "Process-doc improvement; out of scope for S03."}
  ],
  "tests_passed": true,
  "test_summary": "make lint, make format (check), make typecheck all green; uv run pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v --no-cov → 8 passed in 0.19s.",
  "notes": "All four mandatory findings fixed with the minimum surface change. Lazy spawn semantics preserved (directory plumbed through meta, applied only at first _get_or_spawn_client call). LF-only byte-level reader preserved verbatim — no built-in line iterator introduced. Full-suite execution belongs to S11/S12."
}
```
