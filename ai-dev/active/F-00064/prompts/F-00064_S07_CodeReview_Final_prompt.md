# F-00064_S07_CodeReview_Final_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

All reports from S01–S06 and all changed files:
- `ai-dev/active/F-00064/reports/F-00064_S01_Database_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S02_CodeReview_Database_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S03_Backend_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S04_CodeReview_Backend_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S05_Tests_report.md`
- `ai-dev/active/F-00064/reports/F-00064_S06_CodeReview_Tests_report.md`
- `orch/db/models.py`
- `orch/db/migrations/versions/<rev>_add_diagram_doc_type.py`
- `orch/diagram/render.py`
- `orch/diagram/install.py`
- `orch/rag/mapgen.py`
- `orch/rag/module_gen.py`
- `ai-core.sh`
- `tests/unit/rag/test_diagram_render.py`
- `tests/unit/rag/test_mapgen_mermaid.py`

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S07_CodeReview_Final_report.md`

## Final Review Checklist

### Cross-cutting: invariants from design doc
- [ ] `render_mermaid` and `render_d2` never raise in any code path
- [ ] Diagram failure in `module_gen.py` never propagates to caller
- [ ] `DocType.diagram` is present in both Python enum and migration DDL
- [ ] All `ProjectDoc` records with `doc_type=DocType.diagram` store DSL, not SVG
- [ ] `check_diagram_tools()` always returns dict with exactly `"mermaid"` and `"d2"` keys

### Integration consistency
- [ ] The `DocService` calls in `mapgen.py` and `module_gen.py` use the same create/update pattern and handle the case where the doc already exists (upsert semantics)
- [ ] `slug` computation in `module_gen.py` for diagram `doc_id` is consistent with `_make_slug` result
- [ ] No circular imports introduced between `orch/diagram/` and `orch/rag/`

### DB schema
- [ ] Migration handles `ADD VALUE` transactional restriction correctly
- [ ] No other tables or migrations are broken

### Test completeness against design doc
- [ ] All boundary behavior rows from the design doc are covered by a test
- [ ] Invariants 1–5 from the design doc each map to a test

### Security
- [ ] Subprocess `mmdc` invocation does NOT use `shell=True`
- [ ] DSL passed as stdin bytes, not as a command-line argument (injection risk if arg)
- [ ] `--no-sandbox` only for mmdc (headless Chromium requirement), not for d2

### Open issues
List any CRITICAL or HIGH findings. If there are none, state "No CRITICAL or HIGH findings."

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}
  ],
  "approved": true,
  "notes": ""
}
```
