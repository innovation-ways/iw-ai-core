# F-00064 S04 Code Review — Backend

## What was done

Reviewed S03 backend implementation against the full checklist. All files verified against checklist items.

## Files Reviewed

- `orch/diagram/render.py`
- `orch/diagram/install.py`
- `orch/rag/mapgen.py`
- `orch/rag/module_gen.py`
- `ai-core.sh`

## Findings

All checklist items pass:

| Item | Result |
|------|--------|
| `render_mermaid` / `render_d2` never raise — all paths return `str \| None` | ✓ Lines 56–96, 99–129 |
| Binary discovery: `shutil.which` + `~/.local/bin` fallback | ✓ Lines 26–36 |
| DSL via stdin (not temp file) | ✓ `input=dsl.encode()` |
| `--no-sandbox` in puppeteer config | ✓ Line 74 |
| 10s timeout enforced, `TimeoutExpired` caught | ✓ Lines 78, 81–83 |
| Nonzero returncode caught, WARNING logged | ✓ Lines 91–94 |
| Public `render(dsl, dsl_type)` dispatcher | ✓ Line 132–137 |
| No third-party imports (stdlib only) | ✓ |
| `_build_mermaid` requires ELK frontmatter + max 15 nodes | ✓ Lines 277–287 |
| Defensive ELK frontmatter injection | ✓ Lines 295–297 |
| Architecture diagram stored as `ProjectDoc` with `doc_id="diagram-architecture"` | ✓ Lines 186, 198 |
| `DocService.create_doc` / `update_doc` signature correct | ✓ `create_doc` passes all fields; `update_doc` uses only mutable fields |
| Diagram storage failure does NOT propagate | ✓ Lines 208–213 wrapped in try/except |
| Module diagram wrapped in try/except | ✓ Lines 181–195 |
| Re-uses `last_context_chunks` — no re-embed | ✓ Lines 143, 156, 241 |
| Module diagram doc_id = `f"diagram-module-{slug}"` | ✓ Line 273 |
| ELK frontmatter enforced in module diagram | ✓ Lines 268–270 |
| Fallback DSL when LLM returns no fenced block | ✓ Line 266 |
| `ai-core.sh`: binary check non-blocking, no exit code effect, yellow warnings | ✓ Lines 651–665 |
| `ai-core.sh`: check after `uv sync` in install | ✓ Line 651 |
| No SVG stored in content — DSL only | ✓ All `content=` fields store raw DSL |

## Test Results

```
make lint — All checks passed!
```

## Issues / Observations

None. S03 implementation is complete and correct per design spec.