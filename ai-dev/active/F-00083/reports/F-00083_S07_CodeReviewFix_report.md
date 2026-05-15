# F-00083 S07 Code Review Fix Report

## Summary

- CRITICAL findings fixed: 0 (none existed)
- HIGH findings fixed: 1 of 1 (H1 — Last-Event-ID query-param/header mismatch)
- MEDIUM findings addressed: 0 (M1 is process-only, no code change needed; M2 deferred to S08 per design)
- LOW findings addressed: 0 (deferred, low-risk)
- Pre-flight gates: format=ok, typecheck=ok, lint=ok
- Tests: 72 passed (66 unit/dashboard + 6 integration), 0 failed
- Regression guard: PASS (zero diff on `dashboard/templates/chat/` and `dashboard/static/chat/`)

---

## HIGH Findings Fixed

### H1 — `Last-Event-ID` query-param/header mismatch (FIXED)

**File**: `dashboard/routers/chat.py` line 235

**Root cause**: The `stream_session` endpoint read `Last-Event-ID` from the HTTP request header only. When `_connectStream()` is called manually from JS (tab navigation, session switch, `newSession()`), a fresh `EventSource` is constructed. The browser has no previous `Last-Event-ID` state for a new `EventSource`, so it sends no header — only the JS-appended query parameter `?last_event_id=...`. The router never read the query param, so AC6 (tab-refresh reconnect replay) did not work for manually-triggered reconnects.

**Fix applied**: Added query-param fallback in `dashboard/routers/chat.py`:

```python
# Before:
last_event_id = request.headers.get("Last-Event-ID")

# After:
last_event_id = request.headers.get("Last-Event-ID") or request.query_params.get(
    "last_event_id"
)
```

This is a minimal, targeted fix: the header is checked first (used by the browser's native EventSource auto-reconnect), and the query param is used as a fallback (used by the manual JS reconnect path). The existing integration tests that send the header directly still pass; the fix also covers the JS-initiated path.

---

## MEDIUM Findings (Deferred)

### M1 — TDD RED evidence convention (deferred — no code change)

Process observation only. The review notes that S02/S03 RED evidence used ImportError/ModuleNotFoundError rather than AttributeError/AssertionError. No production code change is needed. Applied as a process note for future backend/API steps: write tests that import a stub skeleton first (so collection succeeds) and fail with AttributeError at the unimplemented method call.

### M2 — `permission.reply` wire-field name unverified (deferred to S08)

The design explicitly carries this to S08 for live validation against `opencode serve`. No code change in S07. Noted for S08: run a spike against `opencode serve` to verify whether the field is `reply` or `response`, then update `OpencodeClient.reply_permission` if needed.

---

## LOW Findings (Deferred)

### L1 — `_chipDismissed` reset on page navigation (deferred)

LOW risk. The chip is re-injected on every page load via `setContext`, so the flag resetting is acceptable in practice. No change in S07. Could be addressed post-v1 by storing the flag in `sessionStorage`.

### L2 — `IW_CORE_REPO_ROOT` not documented in `.env.example` (deferred)

LOW risk. The default `parents[3]` calculation is correct for the standard layout. The env var is only needed for non-standard deployments. No change in S07.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 705 files already formatted |
| `make typecheck` | ok — Success: no issues found in 248 source files |
| `make lint` | ok — All checks passed |

---

## Test Results

### Unit + Dashboard Tests

```
uv run pytest tests/unit/test_chat_client.py tests/unit/test_chat_filters.py \
  tests/unit/test_chat_relay.py tests/unit/test_chat_runtime.py \
  tests/dashboard/test_chat_router.py -v
```

Result: **66 passed** in 27.67s

### Integration Tests

```
uv run pytest tests/integration/test_chat_endpoint_permission_flow.py \
  tests/integration/test_chat_endpoint_reconnect.py \
  tests/integration/test_chat_endpoint_session_lifecycle.py -v
```

Result: **6 passed** in 24.03s

**Total: 72 passed, 0 failed**

Note: Both runs report a coverage failure (`total coverage < 50%`) but this is a pre-existing global threshold issue across the entire codebase — not introduced by this fix. All individual chat tests pass.

---

## Regression Guard

```
git diff --stat dashboard/templates/chat/ dashboard/static/chat/
```

Result: **(empty output)** — PASS. Zero changes to the existing Code Q&A chat paths.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/chat.py` | Line 235: added `or request.query_params.get("last_event_id")` fallback to `last_event_id` assignment in `stream_session` endpoint |
| `ai-dev/active/F-00083/reports/F-00083_S07_CodeReviewFix_report.md` | This report |
