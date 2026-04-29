# F-00068_S07_CodeReview_Final_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01–S05

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md`
- All reports: `F-00068_S01_*` through `F-00068_S06_*`
- `orch/rag/qa.py`, `dashboard/static/chat.css`, `dashboard/static/chat/render.js`
- All test files

## Output Files

- `ai-dev/active/F-00068/reports/F-00068_S07_CodeReview_Final_report.md`

---

## Final Review Checklist

### 1. Cross-feature color palette consistency (CRITICAL)
- Verify callout hex values in `chat.css` match the F-00067 canonical palette exactly:
  - note `#3B82F6`/`#EFF6FF`, tip `#10B981`/`#ECFDF5`, warning `#F59E0B`/`#FFFBEB`, danger `#EF4444`/`#FEF2F2`, important `#8B5CF6`/`#F5F3FF`
- Any mismatch creates visual inconsistency between chat and docs. CRITICAL.

### 2. System prompt content integrity
- Verify `RENDERING_CAPABILITIES_BLOCK` still contains all original content (Mermaid, D2, tables, code) PLUS the new callout + structure sections.
- Verify no accidental truncation of the block.

### 3. JS parser call order
- Verify `iwProcessChatCallouts()` is called after `iwRenderMermaid()` in both render paths.

### 4. CSS scope — no global leakage
- Verify ALL new CSS rules in `chat.css` are nested under `.chat-message-body`. Run a quick grep: `grep -n "^\.callout\|^h1\|^h2\|^h3\|^p \|^ul\|^ol\|^code\|^pre\|^blockquote" dashboard/static/chat.css` — any unscoped rule is HIGH.

### 5. AC coverage
- AC2: callout rendering — verified by S04 review + browser test
- AC3: heading hierarchy — verified by S04 review
- AC4: code blocks styled — verified by CSS inspection
- AC5: DOMPurify passthrough — verified in S02 report

### 6. Dependency on F-00067
- Verify F-00068 does NOT import from F-00067's callout CSS (each feature is independent).
- Verify F-00068 can be deployed before or after F-00067 without breaking either.

## Test Verification

Run `make test-unit` and `make test-integration`. Report results.

## Final Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "F-00068",
  "steps_reviewed": ["S01", "S02", "S05"],
  "verdict": "pass|fail",
  "cross_layer_findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
