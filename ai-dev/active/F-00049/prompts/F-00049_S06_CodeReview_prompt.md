# F-00049_S06_CodeReview_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Design document
- `ai-dev/work/F-00049/reports/F-00049_S05_Frontend_report.md` — S05 implementation report
- All files listed in the S05 report's `files_changed`:
  - `dashboard/templates/fragments/code_qa_panel.html`
  - `dashboard/templates/project_code.html`

## Output Files

- `ai-dev/work/F-00049/reports/F-00049_S06_CodeReview_report.md` — Review report

---

## Context

You are reviewing the frontend implementation done in S05 by the frontend-impl agent for **F-00049: Code Understanding Q&A Panel**. Your focus is on HTML correctness, JavaScript correctness, SSE streaming via fetch, security (XSS), and integration with the existing project_code.html template.

Read the design document and S05 report before reviewing the files.

---

## Review Checklist

### 1. Template Structure

- Does `code_qa_panel.html` NOT contain `{% extends "base.html" %}`?
- Does the panel have `id="qa-panel"` at the root element?
- Is there a collapsible body element with `id="qa-panel-body"`?
- Is there a conversation area with `id="qa-conversation"`?
- Is there a context label with `id="qa-context-label"`?
- Is there an input with `id="qa-input"` and a submit button with `id="qa-submit-btn"`?
- Does `project_code.html` include the fragment via `{% include "fragments/code_qa_panel.html" %}`?

### 2. data-context-level Integration

- Does `project_code.html` have an element with `id="code-content-root"` containing:
  - `data-context-level="architecture"` (default)?
  - `data-context-doc-id="{{ index_status.level1_doc_id | default('') }}"`?
  - `data-module-path=""`?
- Does `qaUpdateContextLabel()` read from `document.getElementById('code-content-root').dataset`?
- Is `qaUpdateContextLabel()` called on page load AND on `htmx:afterSwap`?

### 3. Panel Collapse/Expand

- Does `qaTogglePanel()` correctly toggle visibility of `#qa-panel-body`?
- Does it swap the icon between ▼ and ▶?
- Does it update the label between "collapse" and "expand"?
- Is the function called on header click (not just button click)?

### 4. SSE Streaming via Fetch

- Is the endpoint URL correct: `'/api/projects/' + QA_PROJECT_ID + '/code/qa'`?
- Is the POST made with `Content-Type: application/json`?
- Is the request body a JSON string (not FormData or URLSearchParams)?
- Is the response body consumed via `response.body.getReader()` (ReadableStream)?
- Are SSE lines parsed by splitting on `\n` and checking for `data: ` prefix?
- Is the buffer correctly maintained for incomplete lines between chunks?

### 5. Token Handling

- Are tokens appended to the assistant bubble using `.textContent +=` (not `+=` on `innerHTML`)?
- Does `qaScrollBottom()` fire after each token to keep conversation scrolled?
- Is the full response accumulated in a string for the `done` event?

### 6. Done and Error Events

- On `data.event === 'done'`: Is the full response pushed to `qaHistory` as assistant turn?
- On `data.event === 'done'`: Is the user question pushed to `qaHistory` as user turn (before assistant)?
- Is history trimmed to `QA_MAX_HISTORY` (10 entries) after each turn?
- On `data.event === 'error'`: Is the assistant bubble replaced (or updated) with an error bubble?
- Does the error bubble display the message from the SSE event?

### 7. Conversation History

- Is `qaHistory` a JS array (`var qaHistory = []`) scoped correctly (not a global `window.` property that could conflict)?
- Is it populated with `{role: "user", content: question}` and `{role: "assistant", content: full_response}` after each complete turn?
- Is the trim logic `qaHistory.length > QA_MAX_HISTORY` with `.slice()` to keep the most recent entries?
- Is the full `qaHistory` array sent with each POST request?

### 8. Loading State

- Is the input `#qa-input` disabled while streaming?
- Is the submit button `#qa-submit-btn` disabled while streaming?
- Does the button text change to indicate loading?
- Are both re-enabled after `done`, `error`, or fetch failure?

### 9. Enter Key Support

- Is there a `keydown` (or `keypress`) listener on `#qa-input` that calls `qaSubmit()` on Enter?
- Does it check that the input is not disabled before submitting?

### 10. Security

- Is user question text added via `.textContent` (not `.innerHTML`)?
- Are streamed tokens added via `.textContent +=` (not string concatenation into `innerHTML`)?
- Is there no `eval()` or `document.write()` anywhere in the script?

### 11. Tailwind Classes

- Are all Tailwind classes static strings (no dynamic concatenation like `"bg-" + color`)?
- Are the classes plausible for a dark/light dashboard (using semantic tokens like `bg-card`, `border-border`, `text-muted-foreground` that match the existing design system)?

### 12. `QA_PROJECT_ID` Injection

- Is `QA_PROJECT_ID` set via `"{{ current_project.id }}"` (Jinja2 template variable)?
- Is this on the JS side (not hardcoded)?

### 13. Design Compliance

Verify each UI acceptance criterion:
- AC9: Collapse/expand toggles panel body, icon, and label text
- AC10: Context label reads from `data-context-level` on `#code-content-root`

---

## Browser Verification (Required)

Before submitting your review, run browser verification using `playwright-cli`:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900
# Navigate to a project Code tab
playwright-cli snapshot
# Check: "Ask about this codebase" panel visible
playwright-cli click "#qa-panel-header"
playwright-cli snapshot
# Check: panel is collapsed (body hidden, icon shows ▶)
```

Report what you observed in your review findings.

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | XSS risk, broken streaming, panel not rendering | Must fix before merge |
| **HIGH** | Missing feature, broken collapse, wrong endpoint URL | Must fix before merge |
| **MEDIUM (fixable)** | Missing loading state, enter key not handled, context label wrong | Should fix in fix cycle |
| **MEDIUM (suggestion)** | UX improvement, better error message | Optional, author decides |
| **LOW** | Nitpick, minor style issue | Informational only |

---

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00049",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "security|architecture|code_quality|conventions|ux",
      "file": "path/to/file.html",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "Existing tests pass; browser verification confirmed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL, HIGH, or MEDIUM (fixable) findings. `fail` otherwise.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
