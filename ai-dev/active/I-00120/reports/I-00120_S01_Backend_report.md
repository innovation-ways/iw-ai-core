# I-00120 S01 Backend Report

## Work Item
**I-00120** — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid

## Step
**S01 — backend-impl** (status discriminator in `orch/llm_usage.py`)

## What Was Done

Added a `status` discriminator to the Codex usage dict returned by `_codex_usage()` and
`_codex_usage_remote()`, enabling consumers to distinguish "0% genuine usage" from "auth
broken".

### Changes to `orch/llm_usage.py`

1. **Status constants** — four module-level strings:
   - `_CODEX_STATUS_OK = "ok"`
   - `_CODEX_STATUS_EXPIRED = "expired"`
   - `_CODEX_STATUS_UNAUTHENTICATED = "unauthenticated"`
   - `_CODEX_STATUS_ERROR = "error"`

2. **`_oauth_is_expired(entry)`** — reads `expires` (epoch milliseconds) from the OAuth
   entry; returns `True` when it is a number at or before now; returns `False` when
   missing or non-numeric (defensive — lets remote call decide).

3. **`_codex_zero(status)`** — helper replacing the old module-level `_CODEX_ZERO` dict.
   Returns the same zeroed shape (`block_pct: 0, week_pct: 0, *_reset: None, plan_type:
   None`) plus `"status": status`. The module-level `_CODEX_ZERO` is retained (kept
   for backward compatibility with external callers that may reference it).

4. **`_codex_usage_remote()`** — success return now includes `"status":
   _CODEX_STATUS_OK`.

5. **`_codex_usage()`** — structured error handling:
   - `entry is None` → `WARNING`, `_codex_zero(_CODEX_STATUS_UNAUTHENTICATED)`
   - `_oauth_is_expired(entry)` → `WARNING`, `_codex_zero(_CODEX_STATUS_EXPIRED)` (proactive,
     no network call)
   - `HTTPStatusError` with `status_code == 401` → `WARNING`, `_codex_zero(_CODEX_STATUS_EXPIRED)`
   - `HTTPStatusError` non-401 → `logger.exception()`, `_codex_zero(_CODEX_STATUS_ERROR)`
   - any other `Exception` → `logger.exception()`, `_codex_zero(_CODEX_STATUS_ERROR)`

6. **`get_llm_usage()`** outer fallback → `_codex_zero(_CODEX_STATUS_ERROR)`.

Token refresh was **not implemented** (explicitly out of scope per the design doc).

### Changes to `tests/unit/test_llm_usage.py`

1. **`_write_opencode_auth_oauth()`** fixture — updated `expires` value from `1_779_689_299_438`
   to `4_867_344_000_000` (far-future epoch-ms) so that tests targeting network/HTTP error
   paths are not short-circuited by the new proactive expiry check.

2. **`TestCodexStatusDiscriminator`** — new test class covering all four statuses:
   - `test_expired_token_proactive_yields_expired_status` — no network call made
   - `test_401_response_yields_expired_status` — HTTP 401 → expired
   - `test_unauthenticated_yields_unauthenticated_status` — no auth.json → unauthenticated
   - `test_non_401_http_error_yields_error_status` — HTTP 500 → error
   - `test_ok_response_yields_ok_status` — successful response → ok
   - `test_outer_fallback_in_get_llm_usage_yields_error_status` — outer try/except → error

3. **`TestCodexUsage.test_no_oauth_returns_zero_and_logs_warning`** — updated expected
   dict to include `"status": "unauthenticated"`.

4. **`TestCodexUsage.test_handles_http_error` → `test_handles_http_error_401_logs_warning`**
   — updated to expect `WARNING` log level (not `ERROR`) and `status == "expired"` for
   HTTP 401, matching the new contract.

## Test Results

### TDD RED evidence (initial failures before implementation)

```
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_expired_token_proactive_yields_expired_status
KeyError: 'status'  — _codex_usage() returned a dict with no 'status' key (pre-fix)

tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_401_response_yields_expired_status
AssertionError: expected 'expired', got None  — 401 was caught by the bare `except Exception`
```

### GREEN after implementation

```
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_expired_token_proactive_yields_expired_status PASSED
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_401_response_yields_expired_status PASSED
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_unauthenticated_yields_unauthenticated_status PASSED
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_non_401_http_error_yields_error_status PASSED
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_ok_response_yields_ok_status PASSED
tests/unit/test_llm_usage.py::TestCodexStatusDiscriminator::test_outer_fallback_in_get_llm_usage_yields_error_status PASSED
```

### Full codex suite

```
33 passed, 66 deselected in 0.32s
```

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 973 files already formatted |
| `make typecheck` | ✅ Success: no issues found in 287 source files |
| `make lint` | ✅ All checks passed |

## Notes / Observations

- The `_write_opencode_auth_oauth()` fixture had `expires: 1_779_689_299_438` — a real past timestamp.
  This caused `test_remote_success` to short-circuit through proactive expiry (returning `status=expired`
  instead of the live payload). Updated to a far-future value so existing network/HTTP tests are not
  affected by the new proactive check. Tests explicitly testing expiry set their own `expires` inline.
- The original `test_handles_http_error` expected `ERROR` level logging for HTTP 401. The design
  contract requires `WARNING` level for 401 (it's a known recoverable condition), so the test was
  updated accordingly.
- The module-level `_CODEX_ZERO` dict is retained for backward compatibility with any external
  callers; the `status` key is only added by `_codex_zero(status)`.
- Token refresh is explicitly out of scope per the design doc.