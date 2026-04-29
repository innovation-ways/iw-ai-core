# F-00066 S01 Backend Report

## What was done

Implemented server-side proactive diagram rendering for the QA SSE stream.

### `dashboard/routers/code_qa.py`

1. **Added `_FENCED_BLOCK_RE`** — regex to match fenced ` ```mermaid\n...``` ` and ` ```d2\n...``` ` blocks
2. **Added `_find_new_diagram_blocks()`** — helper that scans accumulated text for newly completed diagram blocks and returns `(lang, dsl)` pairs not yet processed
3. **Added import guard** for `render_mermaid`/`render_d2` from `orch.diagram.render` — allows module to load gracefully if F-00064 hasn't landed yet
4. **Updated `_sse_generator`**:
   - Added `accumulated_text`, `processed_diagram_blocks`, and `emit_counts` state variables
   - In the `kind == "token"` branch: after yielding the token, detects new diagram blocks and emits `event: image` SSE events with base64-encoded SVG
   - In the fallback `else` (raw `str` events) branch: same accumulation + detection logic
   - `emit_counts[lang]` increments regardless of render success/failure to give stable per-language indices to the frontend

### `orch/rag/qa.py`

Updated `RENDERING_CAPABILITIES_BLOCK` to:
- Add a D2 bullet describing server-side D2 rendering
- Add a note encouraging proactive diagram use when it clarifies architecture

## Files changed

- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`

## Pre-flight results

| Gate | Result |
|------|--------|
| `make format` | ok (ruff format applied) |
| `make typecheck` | ok (mypy passed) |
| `make lint` | ok (ruff passed) |
| `make test-unit` | 1971 passed, 2 failed, 2 skipped |

## Test failures

The 2 failing tests (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) are pre-existing — they test that migration guards raise in agent context and are unrelated to diagram rendering.

## Blockers

None. `orch/diagram/render.py` exists with required functions confirmed.
