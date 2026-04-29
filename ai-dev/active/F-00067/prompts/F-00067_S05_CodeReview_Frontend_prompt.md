# F-00067_S05_CodeReview_Frontend_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step Being Reviewed**: S02 (Frontend — templates)
**Review Step**: S05

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (§Callout Rendering Spec)
- `ai-dev/active/F-00067/reports/F-00067_S02_Frontend_report.md` — S02 implementation report
- `dashboard/templates/docs_detail.html`
- `dashboard/templates/fragments/code_architecture_diagram.html`
- `dashboard/templates/fragments/code_module_diagram.html`
- `dashboard/routers/code_ui.py`
- `dashboard/routers/code.py`
- All test files listed in S02 report

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S05_CodeReview_Frontend_report.md`

---

## Context

Review the dashboard template changes implemented in S02. Focus on: callout CSS correctness, JS parser safety, TOC anchor generation, purpose paragraph extraction, and absence of regressions.

## Review Checklist

### 1. Callout CSS values
- Verify CSS border/background/text colors **exactly match** the canonical palette from the design doc. Any mismatch is HIGH.
- Verify `callout-header` has `text-transform: uppercase` and `letter-spacing` for visual distinction.
- Verify `.callout-body` text color is readable against the tinted background.

### 2. Callout implementation approach
- **CRITICAL**: Verify callout detection is implemented server-side in `dashboard/utils/markdown.py` (`render_markdown_with_callouts()`) — NOT only in JavaScript. The FastAPI test can only verify server-rendered HTML.
- Verify the Python post-processor handles multi-line blockquote bodies (not just single-line).
- Verify unknown types (`[!CUSTOM]`) fall back to plain blockquote — no crash, no empty div.
- Verify the parser is case-insensitive for the type string.
- Check for XSS risk: the content extracted from blockquotes must be re-inserted from the existing DOM nodes, not from raw string concatenation with untrusted input.
- If a JS `iwProcessCallouts()` function also exists: verify it is optional progressive enhancement only, not the primary rendering path.

### 3. Typographic hierarchy
- Verify H1/H2/H3 CSS includes both weight AND color changes (not just size).
- Verify `max-width: 72ch` on body paragraphs.

### 4. TOC
- Verify heading IDs are generated safely (no special characters in anchor IDs).
- Verify the TOC is only rendered when ≥3 headings exist.
- Verify the TOC is hidden on narrow viewports (`@media max-width: 1279px`).

### 5. Purpose paragraph extraction
- Verify `re.search(r'<!-- purpose: (.*?) -->', content)` is used in the Python router.
- Verify a missing purpose marker does not cause a template error (None-safe check).

### 6. Regression check
- Verify the `view-html` and `view-pdf` tabs still work (not broken by template changes).
- Verify existing `blockquote` styling (non-callout) is preserved.
- Verify Mermaid rendering still triggers correctly in the diagram fragments.

## Test Verification

Run `make test-unit` and report results.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview",
  "work_item": "F-00067",
  "step_reviewed": "S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
