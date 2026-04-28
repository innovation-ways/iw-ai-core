# F-00066_S05_Tests_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `dashboard/routers/code_qa.py`
- `tests/dashboard/test_code_qa_sse_wire.py` (existing — read for test patterns)
- `tests/conftest.py`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S05_Tests_report.md`
- `tests/unit/dashboard/test_code_qa_diagram_intercept.py` (new)

## Context

Read `tests/CLAUDE.md`. Unit tests use `monkeypatch` and `pytest.mark.asyncio`. No live DB connections. Import `_find_new_diagram_blocks` and `_sse_generator` from `dashboard.routers.code_qa`.

## Requirements

### `tests/unit/dashboard/test_code_qa_diagram_intercept.py`

#### `test_find_new_blocks_detects_mermaid`
- Input text: `"```mermaid\ngraph TD\n  A --> B\n```"`
- `processed`: empty set
- Assert result is `[("mermaid", "graph TD\n  A --> B")]`

#### `test_find_new_blocks_ignores_partial_block`
- Input text: `"```mermaid\ngraph TD\n  A --> B\n"` (no closing ```)
- Assert result is `[]`

#### `test_find_new_blocks_deduplicates`
- Input text: complete mermaid block
- `processed`: contains `("mermaid", dsl)` for that block already
- Assert result is `[]`

#### `test_find_new_blocks_detects_d2`
- Input text: `"```d2\nA -> B: uses\n```"`
- `processed`: empty set
- Assert result is `[("d2", "A -> B: uses")]`

#### `test_find_new_blocks_detects_multiple`
- Input text: two separate mermaid blocks
- `processed`: empty set
- Assert result has length 2

#### `test_find_new_blocks_never_raises`
- Pass `None` as `text` (should not raise — returns `[]`)

#### `test_sse_generator_emits_image_event_when_render_succeeds`

Use monkeypatch to patch `dashboard.routers.code_qa.render_mermaid` to return `"<svg>test</svg>"` and `dashboard.routers.code_qa._DIAGRAM_RENDER_AVAILABLE` to `True`.

Mock a `QAEngine` whose `answer_stream_v2` yields a sequence of tokens that together form a complete mermaid block:
```python
tokens = ["```mermaid\n", "graph TD\n", "  A --> B\n", "```"]
```

Call `_sse_generator(...)` and collect all yielded SSE strings.

Assert:
- An `event: image` line appears in the collected output
- The data payload contains `"svg_b64"` whose base64-decoded value is `"<svg>test</svg>"`
- The data payload contains `"source_type": "mermaid"`
- The data payload contains `"block_index": 0`

#### `test_sse_generator_no_image_event_when_render_returns_none`

Same setup but monkeypatch `render_mermaid` to return `None`.

Assert no `event: image` line appears in the output.

#### `test_sse_generator_no_image_event_when_render_unavailable`

Monkeypatch `_DIAGRAM_RENDER_AVAILABLE` to `False`.

Assert no `event: image` line appears (block detection is gated by the flag).

### Test setup helpers

For `_sse_generator` tests: look at how `tests/dashboard/test_code_qa_sse_wire.py` sets up a `FakeEngine` and calls `_sse_generator` with a testcontainer DB session. Follow the same pattern:
- Import `_sse_generator` from `dashboard.routers.code_qa`
- Use `testcontainers.postgres.PostgresContainer` for the DB session
- Use `pytest.mark.asyncio` and `async def`

Collect all yielded SSE strings:
```python
lines = []
async for chunk in _sse_generator(...):
    lines.append(chunk)
full_output = "".join(lines)
```

Then assert `"event: image" in full_output` (or not).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — zero errors on touched files
3. `make lint`
4. `make test-unit` — all pass

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/dashboard/test_code_qa_diagram_intercept.py"
  ],
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
