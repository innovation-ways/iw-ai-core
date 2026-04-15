# F-00048_S06_CodeReview_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `ai-dev/work/F-00048/reports/F-00048_S05_Frontend_report.md` -- S05 implementation report
- All files listed in S05 report's `files_changed`:
  - `dashboard/templates/fragments/code_module_cards.html`
  - `dashboard/templates/fragments/code_module_detail.html`
  - `dashboard/templates/fragments/code_symbol_panel.html`
  - `dashboard/templates/fragments/code_module_spinner.html`
  - `dashboard/templates/fragments/code_architecture_view.html` (modified — added 3 containers below the Mermaid diagram; F-00047's content must remain intact)

## Output Files

- `ai-dev/work/F-00048/reports/F-00048_S06_CodeReview_report.md` -- Review report

## Context

You are reviewing the frontend implementation done in S05 for **F-00048: Code Understanding: Module + Symbol Views**.

Read the design document to understand the intended UI. Read the S05 report to understand what was done. Then review all changed template files.

## Review Checklist

### 1. Template Architecture Compliance

- Do all fragment templates (`code_module_cards.html`, `code_module_detail.html`, `code_symbol_panel.html`, `code_module_spinner.html`) NOT extend `base.html`? This is a hard rule.
- Are htmx attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`, `hx-indicator`) used correctly throughout?
- Are API endpoint URLs correct and matching S03's implementation (`/api/projects/{project_id}/code/...`)?
- Are Tailwind classes applied statically (no dynamic class construction)?

### 2. Three-Level Navigation

- **Level 1 (Module Cards)**:
  - Do module cards load via `hx-get` triggered on page load (not on user action)?
  - Does each card show: module path, name, description, and a "View details" button?
  - Does the "View details" button target `#code-detail-panel` with `hx-swap="innerHTML"`?

- **Level 2 (Module Detail)**:
  - Is the breadcrumb present showing "Architecture > {module.path}"?
  - Does the breadcrumb "Architecture" link navigate back to the module cards view?
  - Is the "Regenerate" button wired to `hx-post` to the `/generate` endpoint?
  - Is there a polling/spinner state for when `generating: true` is returned?
  - Is the cached/fresh indicator shown?

- **Level 3 (Symbol Panel)**:
  - Are [explain] buttons present on file rows?
  - Do they use `hx-swap="afterend"` to insert the panel inline below the file row?
  - Does the close button remove the panel from the DOM?
  - Is the panel visually distinct from the Level 2 content (border, background)?

### 3. Loading States

- Is the htmx loading indicator (`hx-indicator`) referenced correctly?
- Does the spinner show during Level 2 generation?
- Is the polling state (`hx-trigger="load delay:2s"`) correct for the generating case?
- Do panels avoid content flash (do not show empty state before content loads)?

### 4. Code Quality and Maintainability

- Is Jinja2 template syntax correct (`{% %}`, `{{ }}`, `{# #}`)?
- Are template variables accessed correctly (dict access: `module.name` or `module["name"]`)?
- Is the `| safe` filter only applied to context vars that are already server-rendered HTML (`doc_html`, `explanation_html`), NEVER to raw markdown or user-supplied strings?
- Is the `| urlencode` filter applied to user-supplied values in URL query strings?
- Are there any hardcoded project IDs, slugs, or URLs?
- Does the modified `code_architecture_view.html` preserve all of F-00047's existing content (Mermaid container, existing headings, empty states)?

### 5. Accessibility

- Are interactive elements using semantic HTML (`<button>` not `<div onclick>`)?
- Are `[explain]` and `[close]` buttons keyboard-accessible?
- Does the module cards grid have appropriate heading structure?
- Are loading states communicated with `aria-live` or similar if applicable?
- Are breadcrumb links accessible (not just styled divs)?

### 6. Security

- Is user-supplied content (`doc.content`, `explanation`) properly escaped or explicitly sanitized before `| safe`?
- Are `file_path` values URL-encoded when used in query strings (`| urlencode`)?
- Are there any XSS vectors in template output?

### 7. UI/UX Correctness vs Design

Compare against the design document's wireframes:
- Module cards section appears below Mermaid diagram?
- Level 2 view shows: breadcrumb, module name, cached/fresh indicator, regenerate button, content?
- Level 3 panel shows: symbol name, explanation, close button?

### 8. Integration with Existing Templates

- Does the Code tab modification integrate cleanly with the existing page structure?
- Are the new `#code-components-section` and `#code-detail-panel` IDs unique on the page?
- Does the htmx indicator placement not interfere with other page elements?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `uv run pytest tests/unit/ -v` -- no regressions
2. Run `uv run pytest tests/integration/ -v` -- no regressions
3. If possible: start dashboard and use playwright-cli to verify the module cards render:
   ```bash
   playwright-cli kill-all
   playwright-cli open http://localhost:9900
   playwright-cli snapshot
   ```
4. Report test and verification results accurately in the result contract

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Broken navigation, XSS vulnerability, fragment extends base.html | Must fix before merge |
| **HIGH** | Missing navigation level, broken htmx wiring, missing accessibility | Must fix before merge |
| **MEDIUM (fixable)** | Incorrect Tailwind, missing loading state, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better UX pattern available | Optional, author decides |
| **LOW** | Nitpick, minor style | Informational only |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "F-00048",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/template.html",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
