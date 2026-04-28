# F-00066_S01_Backend_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`
- `orch/diagram/render.py` (F-00064 output — must exist before running this step)

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S01_Backend_report.md`
- `dashboard/routers/code_qa.py` (modified)
- `orch/rag/qa.py` (modified)

## Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md`.

F-00066 adds server-side diagram rendering to the QA SSE stream. When the LLM emits a ` ```mermaid ` or ` ```d2 ` fenced block, the backend detects the complete block, renders it via `orch.diagram.render`, and emits an `image` SSE event.

**Pre-flight check**: Confirm `orch/diagram/render.py` exists with `render_mermaid` and `render_d2` functions (F-00064 dependency). If the file does not exist, raise a blocker.

## Requirements

### 1. `dashboard/routers/code_qa.py`

#### 1a. Add module-level constant and helper

```python
_FENCED_BLOCK_RE = re.compile(r"```(mermaid|d2)\n(.*?)```", re.DOTALL)


def _find_new_diagram_blocks(
    text: str,
    processed: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return (lang, dsl) pairs for newly completed fenced mermaid/d2 blocks.

    Never raises — returns empty list on any error.
    """
    try:
        results = []
        for m in _FENCED_BLOCK_RE.finditer(text):
            lang = m.group(1)
            dsl = m.group(2).strip()
            key = (lang, dsl)
            if key not in processed:
                results.append((lang, dsl))
        return results
    except Exception:
        return []
```

#### 1b. Import `render_mermaid` and `render_d2`

At the top of the file (inside a `try/except ImportError` guard so the module loads even if F-00064 hasn't landed yet):

```python
try:
    from orch.diagram.render import render_d2, render_mermaid
    _DIAGRAM_RENDER_AVAILABLE = True
except ImportError:
    _DIAGRAM_RENDER_AVAILABLE = False
    def render_mermaid(dsl: str) -> str | None:  # type: ignore[misc]
        return None
    def render_d2(dsl: str) -> str | None:  # type: ignore[misc]
        return None
```

#### 1c. Update `_sse_generator` to intercept fenced blocks

In `_sse_generator`, add these variables at the top of the function:

```python
accumulated_text = ""
processed_diagram_blocks: set[tuple[str, str]] = set()
block_emit_index = 0
```

After the existing `yield f"event: token\ndata: ..."` line (not the error path), add the block detection:

```python
accumulated_text += token_text
if _DIAGRAM_RENDER_AVAILABLE:
    new_blocks = _find_new_diagram_blocks(accumulated_text, processed_diagram_blocks)
    for lang, dsl in new_blocks:
        processed_diagram_blocks.add((lang, dsl))
        render_func = render_mermaid if lang == "mermaid" else render_d2
        svg = await loop.run_in_executor(None, render_func, dsl)
        if svg:
            import base64 as _base64
            svg_b64 = _base64.b64encode(svg.encode("utf-8")).decode("ascii")
            img_payload = json.dumps({
                "svg_b64": svg_b64,
                "alt": "Diagram",
                "source_type": lang,
                "block_index": block_emit_index,
            })
            yield f"event: image\ndata: {img_payload}\n\n"
        block_emit_index += 1
```

**Important**: the `base64` module is already imported at the top of `code_qa.py`. Use the existing import, not a local re-import.

**Important**: `loop` in `_sse_generator` is `asyncio.get_event_loop()`. Use `loop.run_in_executor(None, render_func, dsl)` — this runs the synchronous render function in the default ThreadPoolExecutor.

The block detection MUST happen ONLY for token events (not phase/citation/error events). Place the detection code in the `kind == "token"` branch, after the existing token yield.

Also detect blocks for the branch that handles raw `str` events (the fallback `else` branch at the bottom of the event loop). Accumulate those tokens too.

### 2. `orch/rag/qa.py`

Update `RENDERING_CAPABILITIES_BLOCK` to:
1. Add a D2 bullet after the Mermaid bullet
2. Add a note encouraging proactive use

```python
RENDERING_CAPABILITIES_BLOCK: str = (
    "## Rendering Capabilities\n\n"
    "The chat UI renders your markdown response inline. Use these features "
    "directly when they help — never tell the user to paste code into an "
    "external editor or live-preview site:\n"
    "- Mermaid diagrams — emit a fenced ```mermaid block. The UI renders it "
    "as an interactive SVG with expand and retry controls. Supported types: "
    "flowchart, sequenceDiagram, classDiagram, erDiagram, stateDiagram-v2, gantt.\n"
    "- D2 diagrams — emit a fenced ```d2 block. D2 excels at architecture, "
    "network topology, and multi-container system diagrams (rendered server-side "
    "as SVG; falls back to source if the d2 binary is absent).\n"
    "- Tables — use GitHub-flavored markdown tables when comparing multiple "
    "items side by side.\n"
    "- Code — use fenced blocks with a language tag (```python, ```typescript, "
    "etc.) so syntax highlighting applies.\n\n"
    "Do not preface answers with disclaimers about being a text-based AI; "
    "emit diagrams and code directly in the response. If a diagram would make "
    "an architectural relationship clearer than prose, include it proactively.\n\n"
)
```

**Do NOT change `DIAGRAM_DIRECTIVE_BLOCK`** — it is for the explicit `/diagram` context chip.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — zero errors on touched files
3. `make lint`
4. `make test-unit` — all pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code_qa.py",
    "orch/rag/qa.py"
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
