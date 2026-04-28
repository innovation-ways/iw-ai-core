# F-00065_S06_CodeReview_Tests_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `ai-dev/active/F-00065/reports/F-00065_S05_Tests_report.md`
- `tests/unit/dashboard/test_preprocess_mermaid.py`
- `tests/dashboard/test_code_diagram_endpoint.py`

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S06_CodeReview_Tests_report.md`

## Review Checklist

- [ ] All 3 `_preprocess_mermaid` tests present; each asserts the `<pre data-lang="mermaid">` format
- [ ] All 3 endpoint tests present; 200+fragment, 200+empty-state, 404
- [ ] No live DB connections in unit or dashboard tests
- [ ] Tests match project conventions (`tests/CLAUDE.md`)
- [ ] Boundary behavior rows from design doc are covered

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
