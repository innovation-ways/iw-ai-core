# F-00068_S04_CodeReview_Frontend_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step Being Reviewed**: S02 (Frontend — chat styles + callout parser)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — §Canonical Callout Spec, §Invariants
- `ai-dev/active/F-00068/reports/F-00068_S02_Frontend_report.md`
- `dashboard/static/chat.css`
- `dashboard/static/chat/render.js`

## Output Files

- `ai-dev/active/F-00068/reports/F-00068_S04_CodeReview_Frontend_report.md`

---

## Review Checklist

### 1. Callout color values (CRITICAL cross-feature check)
- Verify CSS hex values in `chat.css` exactly match the F-00067 canonical palette:
  - note: `#3B82F6` / `#EFF6FF` / `#1D4ED8`
  - tip: `#10B981` / `#ECFDF5` / `#065F46`
  - warning: `#F59E0B` / `#FFFBEB` / `#92400E`
  - danger: `#EF4444` / `#FEF2F2` / `#991B1B`
  - important: `#8B5CF6` / `#F5F3FF` / `#4C1D95`
- Any mismatch with the canonical palette is CRITICAL.

### 2. CSS scope
- Verify all new prose and callout styles are scoped to `.chat-message-body` — no global rule leakage. Missing scope is HIGH.

### 3. Chat panel heading sizes
- Verify H2 is `1rem` (not the larger `1.2rem` used in `prose-doc`).
- Verify H3 is `0.9rem` or smaller with muted color.

### 4. JS callout parser correctness
- Verify `iwProcessChatCallouts(container)` handles multi-line callout bodies (children beyond first `<p>`).
- Verify unknown callout types (e.g., `[!CUSTOM]`) fall through to plain blockquote — no crash.
- Verify empty callout body (`> [!TIP]` with no following text) does not crash.
- Verify `iwProcessChatCallouts` is called AFTER `iwRenderMermaid()` to avoid interference.

### 5. DOMPurify
- Verify S02 report confirms `class` is in the DOMPurify `ALLOWED_ATTR` list.
- Verify callout div classes (`callout`, `callout-warning`, etc.) survive `sanitizeHTML()`.

### 6. Re-render path
- Verify `iwProcessChatCallouts` is called in both the initial render path AND the re-render path in `render.js`.

### 7. No regressions
- Verify existing chat functionality (mermaid rendering, code copy buttons, table CSV export) is not broken by changes to `render.js`.

## Test Verification

Run `make test-unit`. Report results.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00068",
  "step_reviewed": "S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
