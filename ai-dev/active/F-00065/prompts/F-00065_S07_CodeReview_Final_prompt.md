# F-00065_S07_CodeReview_Final_prompt

**Work Item**: F-00065 — Diagram display in code view
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

All S01–S06 reports and all changed files. Refer to the File Manifest in the design doc.

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S07_CodeReview_Final_report.md`

## Final Review Checklist

### Invariants from design doc
- [ ] No fragment extends `base.html`
- [ ] `diagram_dsl` and `arch_diagram_dsl` always HTML-escaped (`| e`), never `| safe`
- [ ] `upgradeAllMermaidBlocks` called after each fragment renders
- [ ] `_preprocess_mermaid` outputs `<pre data-lang="mermaid">` (Invariant 3)
- [ ] New endpoint returns 404 for unknown project (never 200 with error body)

### Integration consistency
- [ ] `arch_diagram_dsl` passed through both the initial page load and any htmx refresh handler for the architecture view
- [ ] Module diagram slot only appears when `doc_html` is present (not during generating/error state)
- [ ] `make css` output (`styles.css`) committed

### Security
- [ ] No XSS vector: DSL content from DB is HTML-escaped before embedding in HTML
- [ ] Inline `<script>` in fragments does not interpolate any DB values into JS string literals

### Open issues (CRITICAL/HIGH only)
State: "No CRITICAL or HIGH findings" if none.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
