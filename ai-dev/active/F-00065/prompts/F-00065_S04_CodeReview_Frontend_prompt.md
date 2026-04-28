# F-00065_S04_CodeReview_Frontend_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `ai-dev/active/F-00065/reports/F-00065_S03_Frontend_report.md`
- All changed files from S03

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S04_CodeReview_Frontend_report.md`

## Review Checklist

### `_preprocess_mermaid` fix
- [ ] Output is now `<pre data-lang="mermaid"><code>...</code></pre>` (not `<div class="mermaid">`)
- [ ] Other callers of `_preprocess_mermaid` (if any) are not broken
- [ ] DSL content is escaped in templates using `| e` filter, not `| safe`

### Fragment templates
- [ ] Neither `code_module_diagram.html` nor `code_architecture_diagram.html` extends `base.html`
- [ ] Both call `upgradeAllMermaidBlocks(container)` in an inline script after render
- [ ] Empty state in `code_module_diagram.html` shows a helpful message, not an error
- [ ] `code_module_detail.html` adds diagram slot inside the `doc_html` branch only (not shown when generating or error state)
- [ ] Architecture diagram panel is included in `code_architecture_view.html` conditionally on `arch_diagram_dsl`

### Security
- [ ] `diagram_dsl` and `arch_diagram_dsl` are HTML-escaped in templates (never `| safe`)
- [ ] Inline `<script>` in fragments is safe (no user-controlled values interpolated into JS)

### CSS
- [ ] `make css` was run and `dashboard/static/styles.css` is updated
- [ ] Old `.prose-doc .mermaid` CSS removed from `code_architecture_view.html` (obsolete)

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
