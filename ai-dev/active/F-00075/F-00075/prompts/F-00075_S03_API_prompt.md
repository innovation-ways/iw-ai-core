# F-00075_S03_API_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S03
**Agent**: api-impl

---

## ⛔ Docker is off-limits

(Same policy as in S01. Full policy: docs/IW_AI_Core_Agent_Constraints.md)

## ⛔ Migrations: agents generate, daemon applies

This work item touches no migrations.

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- `ai-dev/active/F-00075/reports/F-00075_S01_Backend_report.md`
- `dashboard/routers/usage.py` — the file to modify (24-line file; the function `llm_usage_fragment` lives at lines 23–40).
- Reference: `dashboard/CLAUDE.md` — router conventions.

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S03_API_report.md`

## Context

S01 changed `_minimax_usage()` to return additional fields (`block_reset`, `used`, `total`). The router `dashboard/routers/usage.py` currently extracts only `block_pct` for MiniMax. Your job is to forward the new fields into the template context so the frontend (S04) can render the reset countdown and an optional tooltip.

The Claude branch already passes `claude_reset` — mirror that pattern for MiniMax.

## Requirements

### 1. Add the new template variables

In `dashboard/routers/usage.py`, inside `llm_usage_fragment`, extend the template context dict to include three new keys, mirroring the Claude pattern:

```python
"minimax_5h_pct": minimax["block_pct"],
"minimax_5h_color": _bar_color(minimax["block_pct"]),
"minimax_reset": minimax.get("block_reset"),       # NEW — None when call failed or no key
"minimax_5h_used": minimax.get("used"),             # NEW — int or None
"minimax_5h_total": minimax.get("total"),           # NEW — int or None
```

Use `.get()` not `[]`. The MiniMax dict only contains `used`/`total` when the remote call succeeded; on failure it's just `{"block_pct": 0, "block_reset": None}`. Both keys must default cleanly to `None` for the template.

### 2. No other changes

- The router prefix and path stay `/api/usage/llm/fragment`.
- `_bar_color()` is unchanged.
- The response type stays `HTMLResponse`.
- No new imports unless strictly required (none should be).

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Routers are thin — no business logic.
- Fragment templates do **not** extend `base.html`.
- `request.app.state.templates.TemplateResponse(...)` is the rendering pattern in use.

## TDD Requirement

If a unit test for `llm_usage_fragment` already exists, extend it to assert the new context keys are present. Otherwise rely on S07 to add coverage; in that case at minimum smoke-test the route locally with a stubbed `get_llm_usage` and confirm no `KeyError`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

`make test-unit` must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/usage.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
