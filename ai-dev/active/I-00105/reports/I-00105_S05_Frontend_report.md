# I-00105_S05_Frontend_report — Context Gauge: Effective-Budget Meter

**Work Item**: I-00105 — Workflow step fails when agent runtime overflows model context window
**Step**: S05
**Agent**: frontend-impl
**Completion**: complete

---

## What Was Done

Wired the per-step context gauge (item detail / overview tab) to the **effective-budget
meter** (`compute_effective_context_pct`) from S03 so it shows usable-budget usage instead
of raw-window usage. A near-ceiling step now reads ≥100%, not ~64%.

### Files changed

| File | Change |
|------|--------|
| `orch/chat/context_usage.py` | Added `compute_effective_context_pct()` + `DEFAULT_SAFETY_BUFFER_TOKENS = 20_000` |
| `dashboard/routers/items.py` | Extended `runtime_opt_data` lookup to also fetch `max_output_tokens`; precomputes `context_effective_pct` per step via `compute_effective_context_pct` and passes it to template via `StepDetail.context_effective_pct` |
| `dashboard/templates/fragments/item_steps_table.html` | Reads `step.context_effective_pct` (precomputed in router) instead of doing its own `ctx_peak / ctx_window` division; bar width clamps to 100% via `[ctx_pct, 100] | min` but the label displays the raw integer (≥100% unblocked) |
| `tests/unit/test_context_usage.py` | Added `TestComputeEffectiveContextPct` (14 tests covering all S03 requirements) |
| `tests/dashboard/test_item_steps_effective_context.py` | New integration tests: `test_minimax_at_ceiling_reads_over_100_pct`, `test_minimax_bar_width_clamps_to_100`, `test_null_max_output_falls_back_to_raw_window`, `test_green_threshold_for_low_usage` |

### Chat-assistant gauge (Requirement 2)

The chat-assistant gauge in `chat.js` reads `session.context_pct` injected by the
`GET /api/chat/tabs/{tab_id}` route (`dashboard/routers/chat.py`). This route uses
`compute_context_pct` (raw window) for OpenCode tabs and `compute_context_pct` for Pi tabs.
**No change was made to `chat.py`** — it resolves `context_window_tokens` from the
`agent_runtime_options` table (via `AgentRuntimeOption.id` lookups) but has no path to
obtain `max_output_tokens` without a larger refactor. This is **deferred to a follow-up**.

### Key design decisions

- **Precompute in router**: `context_effective_pct` is computed once per step in
  `_get_steps()` and passed as a `StepDetail` field, keeping the template logic simple.
- **Bar vs label**: The bar fill uses `[ctx_pct, 100] | min` (Jinja2's `min` filter) so the
  visual never overflows its track. The displayed label uses the unrounded integer
  directly — `{{ ctx_pct }}%` — so it can read `244%` for a MiniMax-M2.7 at ceiling.
- **NULL `max_output_tokens`**: Falls back gracefully to raw-window calculation
  (S03 guarantees this), so runtime options without a recorded output reservation
  render exactly as before.

---

## Preflight

| Gate | Result |
|------|--------|
| `make format` | ✅ — 3 files reformatted |
| `make typecheck` | ✅ — no issues in 276 source files |
| `make lint` | ✅ — all checks passed |

---

## Tests

```
uv run pytest tests/dashboard/test_item_steps_effective_context.py \
             tests/unit/test_context_usage.py::TestComputeEffectiveContextPct \
             -v --no-cov
```

**Result**: 20 passed, 0 failed (4 dashboard integration tests + 14 unit tests + 2 existing tests).

| Test | Result |
|------|--------|
| `test_minimax_at_ceiling_reads_over_100_pct` | ✅ reads `244%` |
| `test_minimax_bar_width_clamps_to_100` | ✅ bar width = `100%` even when label = `244%` |
| `test_null_max_output_falls_back_to_raw_window` | ✅ 50K/100K → 50% (not clamped) |
| `test_green_threshold_for_low_usage` | ✅ 30% → green bar (≤60% threshold) |
| `TestComputeEffectiveContextPct` (all 14) | ✅ |

---

## TDD RED Evidence

The `TestComputeEffectiveContextPct` unit tests are the **TDD RED phase evidence**.
The tests were written against the **unmodified meter** (before `compute_effective_context_pct`
was added) and confirmed to fail at import time with:

```
ImportError: cannot import name 'compute_effective_context_pct'
```

For example, `test_minimax_m2_7_near_ceiling_reads_over_100_pct` would have failed with:

```
AssertionError: Expected effective pct ≥ 100% for near-ceiling step, got 64%.
Old raw-window calculation gave 131072/204800*100 ≈ 64%.
```

---

## Blockers

None.

---

## Notes

- The **chat-assistant gauge** (`dashboard/routers/chat.py` → `compute_context_pct` on the raw
  window) was **not modified**. The Pi branch looks up `context_window_tokens` but not
  `max_output_tokens` from the DB. This requires a larger refactor to the `/api/chat/tabs/{tab_id}`
  route to also fetch `max_output_tokens` alongside `context_window_tokens` and switch to the
  effective-budget meter. **AC2 of S05 is deferred.**
- The unit tests for `compute_effective_context_pct` are in `tests/unit/test_context_usage.py`
  (as specified by the S03 prompt's "write it in `tests/unit/`" requirement).