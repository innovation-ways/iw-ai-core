# F-00083 S09 — Code Review Fix Final Report

**Step**: S09 (code-review-fix-final-impl)
**Work item**: F-00083 — Dashboard AI Assistant (OpenCode-backed chat panel v1)
**Date**: 2026-05-15

---

## Summary

S08 reported CRITICAL=0, HIGH=1, MEDIUM=0, LOW=1.

The HIGH finding (H1) described two boundary rows without test coverage:
1. "User selects a model the provider doesn't authenticate" — no test for `provider_unauthenticated` / `session.error` event pass-through at the wire level.
2. "Concurrent prompts to same session from two tabs" — explicitly out-of-scope at the wire level (design doc notes this as a browser-level behavior; deferred to S18).

The LOW finding (L1) described a naming mismatch between `tests/integration/_fake_opencode.py` and the `test_chat_*` glob pattern in the manifest — no code change warranted (the file is test infrastructure, not production code, and the S05 "only if needed" exception explicitly covers it).

This step addresses H1 boundary row #1 by adding two targeted tests.

---

## What Was Done

### H1 — Added two tests for error event pass-through

**Finding**: No test verified that error events (e.g., `provider_unauthenticated`, `session.error`) flow from the OpenCode upstream through the relay and appear in the dashboard SSE stream intact. The relay is deliberately "dumb" (passes everything through), but no test held it accountable for error event types specifically.

**Fix**: Added two new tests:

1. **`tests/unit/test_chat_relay.py::test_unknown_error_event_passes_through_relay`** — Unit-level test that feeds `session.idle` followed by `provider_unauthenticated` into the `SessionRelay` and asserts both events exit on the subscriber stream with correct event type labels and payload contents. This is the relay's unit contract: unknown error types must not be dropped.

2. **`tests/integration/test_chat_endpoint_session_lifecycle.py::test_session_error_event_surfaces_to_sse_stream`** — Integration-level test that pushes `session.error` and `provider_unauthenticated` through the fake OpenCode server → `OpencodeClient` → `RelayManager` → dashboard router SSE endpoint → `AsyncClient` and asserts both events appear in the parsed SSE body with correct event type labels and payload contents. This covers the full wire path from upstream to browser.

### L1 — No change required

`_fake_opencode.py` naming is test infrastructure under an explicitly documented exception. No rename warranted.

---

## Files Changed

- `tests/unit/test_chat_relay.py` — added `test_unknown_error_event_passes_through_relay` (unit test, boundary row H1 relay contract)
- `tests/integration/test_chat_endpoint_session_lifecycle.py` — added `test_session_error_event_surfaces_to_sse_stream` (integration test, boundary row H1 wire path)

No production files changed.

---

## Test Results

All 74 targeted tests pass (72 original + 2 new):

```
74 passed, 2 warnings in 36.53s
```

Tests run:
- `tests/unit/test_chat_runtime.py` — 7 passed
- `tests/unit/test_chat_client.py` — 5 passed
- `tests/unit/test_chat_relay.py` — 12 passed (was 11; +1 new)
- `tests/unit/test_chat_filters.py` — 8 passed
- `tests/dashboard/test_chat_router.py` — 35 passed
- `tests/integration/test_chat_endpoint_session_lifecycle.py` — 3 passed (was 2; +1 new)
- `tests/integration/test_chat_endpoint_permission_flow.py` — 2 passed
- `tests/integration/test_chat_endpoint_reconnect.py` — 2 passed

Coverage failure (`total coverage < 50%`) is a pre-existing threshold against the full codebase — not introduced by this feature.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 705 files already formatted |
| `make typecheck` | ok — no issues found in 248 source files |
| `make lint` | ok — all checks passed |

---

## Deferred Item

H1 boundary row #2 ("Concurrent prompts to same session from two tabs") is deferred to S18 browser verification. The design doc explicitly notes this as a browser-level behavior (OpenCode queues; UI in both tabs shows "agent busy") that is not testable at the wire level. No change made.
