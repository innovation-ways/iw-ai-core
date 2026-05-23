# I-00105_S05_Frontend_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state.
Testcontainers via pytest fixtures are the only exception; read-only docker
introspection and `./ai-core.sh` / `make` targets are allowed. STOP and raise a
blocker if your task seems to need a prohibited command. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migration** and no schema change. If your work appears to
need one, STOP and raise a blocker.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design document.
- `ai-dev/work/I-00105/reports/I-00105_S03_Backend_report.md` — S03 report: the new effective-budget meter function and its signature.
- `orch/chat/context_usage.py` — the meter (S03 added the effective-budget function).
- `dashboard/routers/items.py` — computes `context_pct` for the per-step table.
- `dashboard/templates/fragments/item_steps_table.html` — renders the per-step context gauge (this is the gauge that read "64%").
- `dashboard/routers/chat.py` and `dashboard/static/chat_assistant/chat.js` — the chat-assistant context gauge (shares the same meter).

## Output Files

- `dashboard/routers/items.py`, `dashboard/templates/fragments/item_steps_table.html` (modified)
- `dashboard/routers/chat.py`, `dashboard/static/chat_assistant/chat.js` (modified — only if they compute the percentage; see Requirement 2)
- `tests/dashboard/...` — gauge rendering tests
- `ai-dev/work/I-00105/reports/I-00105_S05_Frontend_report.md` — step report.

## Context

You are wiring the dashboard context gauges to the **effective-budget meter**
from S03 so they show usable-budget usage, not raw-window usage. This is the
user-facing half of AC1.

## Requirements

### 1. Per-step context gauge (the one that read 64%)

**Locate the current calculation correctly.** The per-step gauge's raw-window
percentage is **computed in the template, not in the router**.
`dashboard/templates/fragments/item_steps_table.html` does its own division
(`ctx_pct = ctx_peak / ctx_window * 100`, then clamps the result to 100) — this
is the raw-window calculation to replace. `dashboard/routers/items.py` does
**not** compute a percentage today; it only resolves `context_window_tokens`
per step via the existing `runtime_opt_tokens` lookup that selects
`AgentRuntimeOption.id, AgentRuntimeOption.context_window_tokens` (around lines
401–410) and passes `context_tokens_peak` / `context_window_tokens` to the
template.

To switch the per-step gauge to the effective budget:

- Extend the `items.py` `runtime_opt_tokens` lookup to also select
  `max_output_tokens` from `AgentRuntimeOption`, and resolve it per step
  alongside `context_window_tokens`.
- Compute the effective-budget percentage in `items.py` via S03's meter
  (`compute_effective_context_pct`) so the template renders a precomputed
  value; pass that value through to the template.
- Update `item_steps_table.html` to render the precomputed effective-budget
  percentage instead of doing its own `ctx_peak / ctx_window` division. The bar
  *width* may stay clamped to 100% to avoid visual overflow, but the displayed
  *number* must be allowed to read ≥100% for a near-ceiling step (AC1) — do not
  clamp the label to 100.

The displayed percentage for a near-ceiling step must now read near/over 100%,
not ~64%.

### 2. Chat-assistant gauge

`dashboard/routers/chat.py` / `chat.js` render a context gauge for the chat
assistant from the same meter. If they call the raw-window `compute_context_pct`
directly, switch them to the effective-budget function so the two gauges are
consistent. If they already delegate to a shared helper that S03 fixed, no
change is needed — verify and note it.

### 3. No behaviour change when `max_output_tokens` is NULL

A runtime with no recorded output reservation must render exactly as today
(meter falls back to the raw window — S03 guarantees this). Do not special-case
it in the template.

### 4. Tests

Add/extend tests under `tests/dashboard/` (the `client` fixture lives in
`tests/dashboard/conftest.py` — see `CLAUDE.md` gotcha). Assert the **specific
rendered percentage**: a step on a MiniMax-M2.7-like runtime at ~131K input
renders ≥100%, and a runtime with NULL `max_output_tokens` renders the
raw-window percentage. Assert on values, not just "a gauge element exists".

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` — Jinja2 + htmx patterns. **MUST**
keep Jinja2 `format`-filter calls `%`-style (`"%d%%"|format(n)`), never
`str.format`-style — enforced by `make lint`. If `make css` reports nothing to
do, append plain CSS directly to `dashboard/static/styles.css`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete, run in order and fix anything reported:
1. `make format`  2. `make typecheck`  3. `make lint` (includes JS `node --check` + Jinja2 template check)

## Test Verification (NON-NEGOTIABLE)

Run only your own new/affected tests — NOT the full suite:
```bash
uv run pytest tests/dashboard/<your test files> -v
```
Do not report `tests_passed: true` unless they pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/... — <RED line>  (or 'n/a — wiring only' if no new behavioural test logic)",
  "blockers": [],
  "notes": "Which gauges changed; whether chat.py/chat.js needed edits or already delegated to the shared meter."
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S05`
On success: write the report, then
`uv run iw step-done I-00105 --step S05 --report ai-dev/work/I-00105/reports/I-00105_S05_Frontend_report.md`
On failure: `uv run iw step-fail I-00105 --step S05 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
