# F-00064_S04_CodeReview_Backend_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`
- `ai-dev/active/F-00064/reports/F-00064_S03_Backend_report.md`
- `orch/diagram/render.py`
- `orch/diagram/install.py`
- `orch/rag/mapgen.py`
- `orch/rag/module_gen.py`
- `ai-core.sh`

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S04_CodeReview_Backend_report.md`

## Review Checklist

### `orch/diagram/render.py`
- [ ] `render_mermaid` and `render_d2` never raise — all paths return `str | None`
- [ ] Binary discovery uses `shutil.which` + `~/.local/bin` fallback for mmdc
- [ ] Subprocess invocation passes DSL via stdin (not a temp file)
- [ ] `--no-sandbox` flag included in mmdc puppeteer config (WSL/headless Linux requirement)
- [ ] Timeout of 10 seconds enforced; `TimeoutExpired` caught and returns `None`
- [ ] Nonzero returncode caught; WARNING logged with stderr; returns `None`
- [ ] Public `render(dsl, dsl_type)` dispatcher exists and handles unknown type gracefully
- [ ] No third-party imports (stdlib only)

### `orch/rag/mapgen.py`
- [ ] `_build_mermaid` prompt requires ELK frontmatter and max 15 nodes
- [ ] Defensive ELK frontmatter injection present after LLM response parsing
- [ ] Architecture diagram stored as `ProjectDoc` with `doc_id="diagram-architecture"` and `doc_type=DocType.diagram`
- [ ] `DocService.create_doc` / `update_doc` called correctly (check signature match)
- [ ] Diagram storage failure does NOT propagate to `generate_level1` — wrapped in try/except or structured to not raise

### `orch/rag/module_gen.py`
- [ ] Diagram generation wrapped in `try/except Exception` that logs WARNING and does not re-raise
- [ ] Re-uses already-retrieved LanceDB nodes — does NOT re-embed
- [ ] Module diagram stored as `ProjectDoc` with `doc_id=f"diagram-module-{slug}"` and `doc_type=DocType.diagram`
- [ ] ELK frontmatter enforced in output (defensive check)
- [ ] Fallback DSL used when LLM returns no fenced block

### `ai-core.sh`
- [ ] Binary check does not affect exit code
- [ ] Warning messages are yellow (ANSI escape) and informational
- [ ] Check placed after `uv sync` in install section

### General
- [ ] Preflight gates passed per S03 report
- [ ] No SVG stored in `content` — DSL only

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}
  ],
  "approved": true,
  "notes": ""
}
```
