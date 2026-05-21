# CR-00071 S02 Code Review Report

**Step**: S02 — Code Review
**Agent**: code-review-impl
**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Completion Status**: pass
**Date**: 2026-05-21

---

## What Was Reviewed

S01 implemented the Pi context-window injection for `get_tab()` (`dashboard/routers/chat.py`), added a pure `normalize_pi_messages()` helper (`orch/chat/context_usage.py`), and wrote TDD unit + integration tests.

---

## Pre-Review Gate

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ All checks passed |

---

## Files Changed

| File | Lines Added | Purpose |
|------|-------------|---------|
| `dashboard/routers/chat.py` | +24 | Pi branch of `get_tab()` now computes and injects `context_pct` |
| `orch/chat/context_usage.py` | +64 | Added `normalize_pi_messages()` pure helper; updated docstrings |
| `tests/unit/test_context_usage.py` | +91 | Added `TestNormalizePiMessages` class (7 test cases) |
| `tests/dashboard/test_chat_router_pi_context_pct.py` | — | New file: 4 integration tests covering AC1–AC4 |

---

## Review Checklist

### 1. `get_tab` Pi branch (`dashboard/routers/chat.py`) ✅

- Pi branch computes `context_pct` via DB lookup + normalizer before `return`.
- Computation is wrapped in `contextlib.suppress(Exception)` — non-fatal; HTTP error impossible.
- `context_pct` is injected **only** when `session` is a dict and a numeric value was computed; otherwise absent.
- Return shape stays `{tab, session, messages}` — `context_pct` lives inside `session`.
- Pi context-window lookup queries `agent_runtime_options.context_window_tokens` for `(cli_tool="pi", model=<model>)`, resolving model from `tab.model` (`"pi/<model>"`).
- DB query lives in the **router** — `context_usage.py` has no DB access.
- Router stays thin: arithmetic/token normalisation is delegated to `context_usage.normalize_pi_messages()` + `context_usage.compute_context_pct()`.

### 2. `orch/chat/context_usage.py` ✅

- `normalize_pi_messages()` is **pure** — no DB, no HTTP, no I/O.
- All token sub-fields default safely — no `KeyError`/`TypeError` on partial/malformed Pi messages.
- Existing `compute_context_pct` / `lookup_context_window` / `resolve_model_from_tab` unchanged.
- The S01 report correctly identified that Pi token keys differ from OpenCode; the normalizer was necessary and is minimal.

### 3. No-regression for OpenCode ✅

- The OpenCode branch of `get_tab` is **byte-for-byte unchanged** (confirmed by `git diff main`).
- `_providers_cache` / `_get_providers_cached` and the OpenCode `context_pct` block untouched.
- `test_opencode_tab_context_pct_unchanged` integration test passes.

### 4. Graceful Degradation ✅

- AC2: no token data in Pi messages → `context_pct` omitted.
- AC3: model has `context_window_tokens = NULL` → `context_pct` omitted.
- No `0%` placeholder produced for a "no data" case.

### 5. Performance ✅

- No new uncached HTTP round-trip added to `get_tab`.
- Pi context-window read is a single indexed DB query on `agent_runtime_options` (PK on `(cli_tool, model)`).
- No N+1; no per-message query.

### 6. Tests ✅

- `tests/dashboard/test_chat_router_pi_context_pct.py` (new file) covers AC1 (numeric `context_pct` with token data + `context_window_tokens` row), AC2 (omitted, no token data), AC3 (omitted, NULL context window), AC4 (OpenCode regression).
- Tests seed `agent_runtime_options` in a testcontainer — no live-DB connection.
- `tests/unit/test_context_usage.py` covers `normalize_pi_messages` with 7 test cases including `test_combined_with_compute_context_pct` (end-to-end round-trip).
- RED output recorded: `ImportError` at test collection (expected TDD failure before implementation).
- All 43 tests pass.

### 7. Scope Check ✅

Changed files are a subset of the design's **Impacted Paths**:
- `dashboard/routers/chat.py` ✅
- `orch/chat/context_usage.py` ✅
- `tests/unit/test_context_usage.py` ✅ (modified)
- `tests/dashboard/test_chat_router_pi_context_pct.py` ✅ (new)
- No DB schema change, no migration, no frontend file change.

---

## Test Results

```
$ uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py \
  tests/unit/test_context_usage.py -v --no-cov -q

43 passed in 7.00s

$ uv run pytest tests/integration/test_chat_tabs_api.py -v -q -k "context_pct"
3 passed
```

---

## Findings

| Severity | Finding | Description |
|----------|---------|-------------|
| — | none | No CRITICAL, HIGH, or MEDIUM_FIXABLE findings. |

**Observations (no action required):**
- `tests/dashboard/test_chat_router_pi_context_pct.py` is an **untracked new file** (not in `git diff main`) — the agent correctly created it under the worktree. The `git diff main --stat` shows only 3 files; the new integration test file is `??` in git status. This is correct behavior — the worktree contains new files that have not been committed.
- `normalize_pi_messages` iterates all messages but does O(n) work with O(1) field access — no performance concern for typical chat message counts.

---

## Verdict

**pass** — S01 is ready to advance to S03.

All acceptance criteria verified. No regressions. No scope violations. Lint/format gates clean. TDD red output recorded.