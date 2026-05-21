# CR-00071 S04 Code Review Final Report

**Step**: S04 — Final Cross-Step Review
**Agent**: code-review-final-impl
**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Completion Status**: pass
**Date**: 2026-05-21

---

## Pre-Review Gate

| Gate | Result |
|------|--------|
| `make lint` (`uv run ruff check .`) | ✅ All checks passed |
| `make format-check` (`uv run ruff format --check .`) | ✅ All checks passed |

---

## What Was Reviewed

S01 (backend-impl) implemented the Pi context-window injection for `get_tab()`. S02
(code-review-impl) returned **pass** with zero mandatory findings. S03
(code-review-fix-impl) confirmed no changes were needed. This S04 performs a global,
cross-step final review verifying the complete CR-00071 change satisfies every
acceptance criterion and design constraint.

---

## Changed Files

| File | Lines | Purpose |
|------|-------|---------|
| `dashboard/routers/chat.py` | +24 | Pi branch of `get_tab()` computes + injects `context_pct` before return |
| `orch/chat/context_usage.py` | +64 | Added `normalize_pi_messages()` pure helper; updated docstrings |
| `tests/unit/test_context_usage.py` | +91 | Added `TestNormalizePiMessages` class (7 test cases) |
| `tests/dashboard/test_chat_router_pi_context_pct.py` | new | 4 integration tests covering AC1–AC4 |

---

## Final Review Checklist

### ✅ Acceptance Criteria AC1–AC5

| AC | Criterion | Verified |
|----|-----------|----------|
| AC1 | Pi tab with token-bearing messages + `context_window_tokens` row → `session.context_pct` numeric `[0, 100]` | ✅ `test_pi_tab_injects_context_pct_when_token_data_and_context_window_present` passes; percentage = used/context_window*100 (8700/100000=8.7) |
| AC2 | Pi tab with no token usage → `context_pct` absent | ✅ `test_pi_tab_omits_context_pct_when_no_token_usage` passes |
| AC3 | Pi tab with `context_window_tokens = NULL` → `context_pct` absent | ✅ `test_pi_tab_omits_context_pct_when_context_window_tokens_null` passes |
| AC4 | OpenCode tabs byte-for-byte unchanged | ✅ `test_opencode_tab_context_pct_unchanged` passes; OpenCode branch untouched in `git diff` |
| AC5 | Indicator renders end-to-end for a Pi tab | ✅ Frontend `chat.js` reads `session.context_pct` — no change needed (CR-00067 already wired generically) |

### ✅ End-to-End Contract

The field the Pi branch injects is `session["context_pct"]`. The CR-00067 frontend
(`chat.js` `_applyContextPct()`) reads `data.session.context_pct`. Both use the
same field name at the same nesting level. Zero frontend change required.

### ✅ OpenCode Unchanged (AC4)

`git diff HEAD` on `dashboard/routers/chat.py` shows the diff is entirely within
the Pi branch (lines 773–800). The OpenCode path from line 802 onward is
byte-for-byte identical to the pre-CR state. `get_tab`, `_providers_cache`,
`_get_providers_cached`, and all existing `context_usage.py` public functions are
unchanged.

### ✅ Pi Context-Window Source

The lookup at lines 785–792 queries `agent_runtime_options` for
`(cli_tool="pi", model=model_part)` and reads `row.context_window_tokens`.
- No-row → `scalar_one_or_none()` returns `None` → block skipped → `context_pct` absent.
- NULL → `row.context_window_tokens is not None` fails → block skipped → `context_pct` absent.
- Both cases degrade gracefully; no exception propagates.

### ✅ Layer Boundary

The DB query lives in `dashboard/routers/chat.py` (the router). `normalize_pi_messages()`
and `compute_context_pct()` in `orch/chat/context_usage.py` are pure — no DB, no HTTP,
no I/O. This is confirmed by the module docstring: *"No I/O, no DB, no HTTP —
fully unit-testable without mocks or testcontainers."*

### ✅ Graceful Degradation

The Pi branch injection is wrapped in `contextlib.suppress(Exception)`. When any
computation step fails (no model row, NULL tokens, malformed messages, division
error), `context_pct` is simply absent from `session`. The endpoint always
returns `{"tab": ..., "session": ..., "messages": ...}` with HTTP 200. No `0%`
placeholder. Worst case = pre-CR behavior.

### ✅ Performance

No uncached HTTP round-trip added. The Pi context-window read is a single indexed
SQLAlchemy query on `agent_runtime_options` (PK on `(cli_tool, model)`). The
existing 5-second `get_tab` poll interval is unchanged.

### ✅ Pi Token-Shape Decision (Outcome #2)

S01 report confirms: Pi `get_messages()` returns `usage: {"input", "output",
"cacheRead", "cacheWrite"}` — keys **differ** from OpenCode's
`{"input", "output", "reasoning", "cache": {"read", "write"}}`. Therefore a
normalizer was necessary and was implemented. The normalizer is present precisely
because keys differ. Code matches the S01 decision.

### ✅ Scope

Every changed file is within the design's **Impacted Paths**:
- `dashboard/routers/chat.py` ✅
- `orch/chat/context_usage.py` ✅
- `tests/unit/test_context_usage.py` ✅ (modified)
- `tests/dashboard/test_chat_router_pi_context_pct.py` ✅ (new, within impacted paths)

No DB schema change. No migration. No new endpoints. No frontend file change.

### ✅ Conventions

`dashboard/CLAUDE.md` and `orch/CLAUDE.md` honoured:
- Router stays thin — DB query for context-window lookup is in the router; pure
  token normalization and arithmetic are delegated to `context_usage.py`.
- `context_usage.py` is pure by design (no DB, no I/O).
- Docstrings added to `normalize_pi_messages` explaining the translation.

---

## Test Results

```
$ uv run pytest tests/unit/test_context_usage.py -v --no-cov -q
39 passed in 0.24s

$ uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py -v --no-cov -q
4 passed in 7.18s

$ uv run pytest tests/integration/test_chat_tabs_api.py -q -k "context_pct" --no-cov
3 passed
```

All tests pass. S01's TDD red output (ImportError at collection) is recorded in
the new integration test file. All 46 relevant tests pass across all layers.

---

## Findings

| Severity | Finding | Description |
|----------|---------|-------------|
| — | none | No CRITICAL, HIGH, or MEDIUM_FIXABLE findings. |

**Observations (no action required):**
- `tests/dashboard/test_chat_router_pi_context_pct.py` is an untracked new file
  (not committed to the branch yet) — correct worktree behavior.
- `normalize_pi_messages` iterates messages in O(n) with O(1) field access —
  no performance concern for typical chat message counts (< 1000 messages).
- The `AgentRuntimeOption` import at line 77 of `chat.py` was already present
  before this CR (used for the Pi model catalogue at lines 263–268); the new
  query at lines 787–792 reuses the existing import without adding new ones.

---

## Subagent Result

```json
{
  "step": "S04",
  "agent": "code-review-final-impl",
  "work_item": "CR-00071",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed; 39 unit + 4 dashboard + 3 integration tests passed",
  "notes": "Cross-step review confirms AC1–AC5 satisfied, OpenCode path unchanged, Pi token-shape decision (outcome #2) correctly implemented, layer boundary respected, graceful degradation maintained, performance unchanged, scope clean."
}
```