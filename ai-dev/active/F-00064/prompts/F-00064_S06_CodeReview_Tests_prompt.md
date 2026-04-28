# F-00064_S06_CodeReview_Tests_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`
- `ai-dev/active/F-00064/reports/F-00064_S05_Tests_report.md`
- `tests/unit/rag/test_diagram_render.py`
- `tests/unit/rag/test_mapgen_mermaid.py`
- `tests/conftest.py`

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S06_CodeReview_Tests_report.md`

## Review Checklist

### Coverage
- [ ] All 8 tests in `test_diagram_render.py` are present (binary missing, timeout, nonzero exit, success for mermaid; binary missing for d2; unknown type dispatcher; check_diagram_tools both absent and both present)
- [ ] All 3 tests in `test_mapgen_mermaid.py` are present (ELK injected, ELK not duplicated, fallback when no fenced block)

### Test quality
- [ ] No test connects to live DB (port 5433) or live Ollama
- [ ] All subprocess calls are monkeypatched — no real subprocess execution
- [ ] Each test has a single, clear assertion focus
- [ ] Invariant from design doc verified: `render_mermaid` and `render_d2` never raise (confirmed by test structure)
- [ ] Tests follow project conventions in `tests/CLAUDE.md` and match patterns in `tests/unit/`

### Correctness
- [ ] `test_render_mermaid_binary_missing` correctly handles both `shutil.which` returning None AND the `~/.local/bin/mmdc` fallback path not existing
- [ ] Timeout test correctly simulates `subprocess.TimeoutExpired`
- [ ] ELK deduplication test verifies exactly-one occurrence

## Subagent Result Contract

```json
{
  "step": "S06",
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
