# I-00120 S02 Code Review Report

## Work Item
**I-00120** — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid

## Step Reviewed
**S01 — backend-impl**

## Reviewer
CodeReview

---

## Verdict: ✅ PASS

All seven checklist items pass with zero CRITICAL/HIGH/MEDIUM_FIXABLE findings. Lint, format, and
typecheck are clean. All 99 unit tests pass; the 33 codex-specific tests pass without a single failure.

---

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 973 files already formatted |

No new violations in changed files.

---

## Checklist Findings

### 1. Contract correctness — `status` key in every branch ✅

Every branch in `_codex_usage()` returns a dict via `_codex_zero(status)`:

| Branch | Status | Lines |
|--------|--------|-------|
| `entry is None` | `"unauthenticated"` | 419–422 |
| `_oauth_is_expired(entry)` | `"expired"` | 423–428 |
| `HTTPStatusError` 401 | `"expired"` | 434–437 |
| `HTTPStatusError` non-401 | `"error"` | 438–440 |
| All other `Exception` | `"error"` | 440–441 |
| `_codex_usage_remote()` success | `"ok"` | 393–397 |

Zeroed shape (`block_pct: 0`, `week_pct: 0`, `*_reset: None`, `plan_type: None`) is preserved
alongside the new `status` key. The module-level `_CODEX_ZERO` dict (line 308) is defined but never
referenced in the updated code — only `_codex_zero(status)` is used — confirming backward compat is
preserved without a status key on the bare constant.

### 2. Proactive expiry — epoch milliseconds, defensive for missing/non-numeric ✅

```python
raw = entry.get("expires")
if not isinstance(raw, (int, float)):
    return False
return raw <= datetime.now(UTC).timestamp() * 1000
```

- `expires` compared as epoch milliseconds (multiplied ×1000 against `datetime.now(UTC).timestamp()`)
- Non-numeric or missing `expires` → `False` (does NOT misclassify unknown as expired)
- Boundary: `raw <= now_ms` → expired (token valid up to and including the expiry instant)

### 3. 401 vs other errors — specific catch before generic ✅

```python
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        return _codex_zero(_CODEX_STATUS_EXPIRED)
    logger.exception("Codex usage fetch failed")
    return _codex_zero(_CODEX_STATUS_ERROR)
except Exception:
    logger.exception("Codex usage fetch failed")
    return _codex_zero(_CODEX_STATUS_ERROR)
```

- `HTTPStatusError` caught first (line 432), generic `Exception` on line 440
- `exc.response.status_code` accessed inside the `HTTPStatusError` branch only (no risk of
  `AttributeError` on a bare `Exception`)
- 401 → `"expired"`; non-401 HTTP → `"error"`; all other exceptions → `"error"`

### 4. Never raises ✅

All three entry points into `_codex_usage()` are guarded:
- `_load_openai_oauth()` → `None` → unauthenticated branch (no network call)
- Proactive `_oauth_is_expired()` → False on non-numeric, False on future → network call with
  live token
- `try: _codex_usage_remote(...)` → `except HTTPStatusError` + `except Exception` catch all
  error paths; the outer `get_llm_usage()` has an additional `try/except Exception` as a last-
  resort outer fallback returning `_codex_zero(_CODEX_STATUS_ERROR)`

### 5. No token refresh ✅

Zero occurrences of `refresh`, `token_endpoint`, `post`, `write`, or any auth-file mutation in
`orch/llm_usage.py`. Out-of-scope commitment honoured.

### 6. No collateral changes ✅

- Claude `_claude_usage()` unchanged (no `status` key — correct, design covers only Codex)
- MiniMax `_minimax_usage()` unchanged (no `status` key — correct, design covers only Codex)
- 60s cache in `get_llm_usage()` unchanged
- `get_llm_usage()` outer fallback for codex path uses `_codex_zero(_CODEX_STATUS_ERROR)` — correct
  `status: error` for a raise-out scenario

### 7. TDD RED evidence ✅

S01 report documents two pre-fix test failures:

```
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_expired_token_proactive_yields_expired_status
KeyError: 'status' — _codex_usage() returned a dict with no 'status' key (pre-fix)
```

This is a genuine `KeyError` from the missing `status` key, not an import/collection error.
The test asserts `result["status"] == "expired"`, which would raise `KeyError` before the fix because
the returned dict had no `status` key at all. Valid RED evidence.

```
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_401_response_yields_expired_status
AssertionError: expected 'expired', got None — 401 was caught by the bare `except Exception`
```

This is a genuine `AssertionError` from `assert result.get("status") == "expired"`. Before the fix,
the 401 path fell through to the bare `except Exception` which returned `_CODEX_ZERO` (no `status` key),
so `.get("status")` returned `None`. Valid RED evidence.

---

## Test Results

```
tests/unit/test_llm_usage.py -k codex: 33 passed, 66 deselected
Full suite: 99 passed
```

### Full codex suite (33 tests)

- `TestCodexStatusDiscriminator` (6 tests) — all pass
- `TestCodexUsage` (6 tests) — all pass
- `TestCodexUsageRemote` (10 tests) — all pass
- `TestCodexWindowExtractors` (11 tests) — all pass
- `TestGetLlmUsageCodexIntegration` (2 tests) — all pass

---

## Findings Summary

| Category | Count | Severity |
|----------|-------|----------|
| Conventions (lint/format) | 0 | — |
| Contract correctness | 0 | — |
| Proactive expiry | 0 | — |
| 401 vs other errors | 0 | — |
| Never raises | 0 | — |
| No token refresh | 0 | — |
| No collateral changes | 0 | — |
| TDD RED evidence | 0 | — |

**mandatory_fix_count: 0**

---

## Notes

1. **`_CODEX_ZERO` module-level constant is unused after the fix** — it is defined on line 308 but
   only `_codex_zero(status)` is called in production code. This is benign (no harm) but the constant
   is technically dead code. Suggestion (not a block): remove it in S03 or add a `namedtuple`/`@dataclass`
   if external callers need it. Not a finding since it doesn't break anything.

2. **S01 test suite (`TestCodexStatusDiscriminator`) is well-structured** — covers proactive expiry
   (no network call), 401 response, unauthenticated, non-401 HTTP error, ok, and the outer fallback
   path. The `test_ok_response_yields_ok_status` test correctly sets a future `expires` inline rather
   than relying on the fixture's fixed value.

3. **S01 correctly updated `TestCodexUsage.test_handles_http_error` → `test_handles_http_error_401_logs_warning`**
   — the old test expected `ERROR` log for HTTP 401; the design contract requires `WARNING` (recoverable
   auth condition), and the new test validates `status == "expired"` as required.

4. **`_write_opencode_auth_oauth()` fixture expiry fix** — S01 updated the fixture's `expires` from
   `1_779_689_299_438` (past) to `4_867_344_000_000` (far future), preventing unintended proactive expiry
   short-circuits in network/HTTP tests that don't explicitly set `expires`.

---

## JSON Result

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00120",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "33 passed, 0 failed (codex suite)",
  "notes": "Zero findings. Contract correct, proactive expiry defensive, 401 correctly distinguished, never raises, no token refresh, no collateral changes, TDD RED evidence valid. _CODEX_ZERO constant is unused but harmless."
}
```