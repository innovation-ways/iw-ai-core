# I-00105_S06_CodeReview_report

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S06
**Agent**: code-review-impl (code-review-impl)
**Step Reviewed**: S05 (frontend-impl — dashboard context gauge)
**Review Date**: 2026-05-23

---

## Verdict

**FAIL** — AC2 of the review checklist is not met. The chat-assistant gauge
still computes against the raw window in both code paths (OpenCode and Pi), not
the effective budget. The per-step gauge is correctly wired. S05 cannot pass
review until the chat gauge is fixed.

---

## Findings

### 1. Per-step gauge — ✅ PASS

**Severity**: —

The diff shows `items.py` now:
- extends the `AgentRuntimeOption` query to also select `max_output_tokens`
- builds `runtime_opt_data[id] → (context_window, max_output_tokens)` map
- resolves both values per step and calls `compute_effective_context_pct(ctx_peak, ctx_win, max_out)`
- passes the result as `StepDetail.context_effective_pct`

`item_steps_table.html` reads `step.context_effective_pct` instead of computing
`ctx_peak / ctx_window * 100` inline. The bar width is clamped via `[ctx_pct, 100] | min`
so it never overflows visually, while the label reads the unrounded integer
directly (≥100% unblocked).

No `ctx_peak / ctx_window` raw-window division remains in the template. ✅

### 2. Chat gauge consistency — ❌ FAIL

**Severity**: CRITICAL (AC not met)

`dashboard/routers/chat.py` still uses `compute_context_pct` (raw window) in
both branches:

- **Pi path** (`get_tab`, ~line 795):
  ```python
  pct = context_usage.compute_context_pct(
      normalized_msgs, row.context_window_tokens
  )
  ```
  Looks up `context_window_tokens` only; no `max_output_tokens`.

- **OpenCode path** (`get_tab`, ~line 821):
  ```python
  pct = context_usage.compute_context_pct(messages, context_window)
  ```
  Same — raw window, no output reservation.

`dashboard/static/chat_assistant/chat.js` calls `_applyContextPct(session.context_pct)`
(JS side, line 1892), which is the value the router injects. The JS is fine; the
backend is not.

The S05 report itself documents this as an open AC2 deferral, but the review
checklist requires it to be resolved before S06 can pass. This is a **CRITICAL**
finding because AC2 states the two gauges must not diverge.

**Required fix**: `chat.py`'s Pi path should also look up `max_output_tokens` from
`AgentRuntimeOption` and call `compute_effective_context_pct`. The OpenCode path
additionally needs `lookup_max_output_tokens(providers_raw, pid, mid)` — the
providers raw data is already fetched and cached (`providers_raw` is in scope
at line ~818). The change is localized to `get_tab()` in `chat.py`; no JS changes
are needed.

### 3. NULL fallback — ✅ PASS

**Severity**: —

`compute_effective_context_pct` is called with `max_out=None` when the DB lookup
returns NULL. S03's function falls back to raw-window division (no crash, no
special template case). The template's fallback expression:
```
{{ ctx_eff_pct | round(0) | int if ctx_eff_pct is not none else ((ctx_peak / ctx_window * 100) | round(0) | int) }}
```
is syntactically correct but never fires in normal operation (S03 always returns
a float for NULL max_output), and is harmless if it does. ✅

### 4. Tests — ✅ PASS

**Severity**: MEDIUM (minor coverage observation)

`tests/dashboard/test_item_steps_effective_context.py` has four tests:

| Test | Assertion |
|------|-----------|
| `test_minimax_at_ceiling_reads_over_100_pct` | `pct_value >= 100` — specific semantic value |
| `test_minimax_bar_width_clamps_to_100` | `bar_width_pct == 100` — exact value |
| `test_null_max_output_falls_back_to_raw_window` | `pct_value == 50` — exact value |
| `test_green_threshold_for_low_usage` | `"ctx-bar-green" in bar_fill.get("class")` — color logic |

All assert specific values, not just shape. The `db_session` fixture is used
correctly. All 4 tests pass (4 passed in 37 s, confirmed from run output).

**Minor note**: The coverage failure in the full suite (`make test-unit`) is
pre-existing and unrelated to S05 (overall coverage 4.42%, well below the 50%
threshold). S05's own test run uses `--no-cov` and returns 4 passed cleanly.

### 5. Jinja2 / lint — ✅ PASS

**Severity**: —

`make lint` output:
```
uv run python scripts/check_templates.py
uv run ruff check .
All checks passed!
```

No `str.format`-style `format` filter calls; `%`-style (`"%d%%"|format(n)`) is
used throughout. ✅

### 6. Scope — ✅ PASS

**Severity**: —

Modified files:
- `dashboard/routers/items.py` — in scope (`dashboard/routers/`)
- `dashboard/templates/fragments/item_steps_table.html` — in scope (`dashboard/templates/`)
- `orch/db/models.py` — in scope (`orch/db/`)
- `orch/chat/context_usage.py` — in scope (`orch/chat/`)
- `tests/unit/test_context_usage.py` — in scope (`tests/`)
- `tests/dashboard/test_item_steps_effective_context.py` — in scope (`tests/dashboard/`)
- `orch/db/migrations/versions/2be8dc12874f_i_00105_add_max_output_tokens_to_agent_.py` — in scope

No files outside `scope.allowed_paths`. ✅

---

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S05",
  "completion_status": "complete",
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "dashboard/routers/chat.py",
      "detail": "Chat-assistant gauge uses compute_context_pct (raw window) in both Pi and OpenCode paths (lines ~795, ~821). max_output_tokens is never read. The two gauges are inconsistent — AC2 not met. Fix: look up max_output_tokens from AgentRuntimeOption (Pi) or lookup_max_output_tokens via providers_raw (OpenCode), then call compute_effective_context_pct instead. No JS change needed."
    },
    {
      "severity": "MEDIUM",
      "file": "tests/dashboard/test_item_steps_effective_context.py",
      "detail": "Tests are correctly written (specific values, not shape). Full test-unit suite coverage failure (4.42% vs 50% threshold) is pre-existing and unrelated to S05."
    }
  ],
  "notes": "Per-step gauge (items.py + item_steps_table.html) is correctly wired to compute_effective_context_pct. No raw-window division remains in the template. make lint is green. Chat gauge fix is localized to get_tab() in chat.py."
}
```

---

## Recommendation

S05 must be re-opened for a minor patch that fixes `dashboard/routers/chat.py`'s
`get_tab()` endpoint. The fix is:

1. **Pi path**: extend the existing `AgentRuntimeOption` lookup (already fetches
   `context_window_tokens`) to also fetch `max_output_tokens`. Switch the
   `compute_context_pct` call to `compute_effective_context_pct`.

2. **OpenCode path**: `providers_raw` is already in scope at line ~818; call
   `context_usage.lookup_max_output_tokens(providers_raw, pid, mid)` alongside
   the existing `lookup_context_window` call, then call
   `compute_effective_context_pct` instead of `compute_context_pct`.

Both paths already use `contextlib.suppress(Exception)` around the percentage
computation, so any None return from the effective-budget function degrades
gracefully. No test changes are needed beyond adding a dashboard test for the
chat gauge's effective-budget behaviour (mirroring the per-step test).