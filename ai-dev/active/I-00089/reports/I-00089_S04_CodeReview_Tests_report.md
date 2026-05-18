# I-00089 S04 CodeReview Tests — Report

## Summary

**pass** — No critical or high findings. The test file correctly implements regression coverage for both Bug A and Bug B with semantically precise assertions.

## Findings

| Severity | Area | Finding | File:line | Required Fix |
|----------|------|---------|-----------|--------------|
| none | — | — | — | — |

### Detailed Review

**Test placement** ✅
- File is at `tests/dashboard/test_chat_assistant_header.py` (correct subdirectory — not `tests/unit/` or `tests/integration/`).
- Inline `client` fixture (lines 26–45) mirrors the canonical pattern from `test_chat_panel_default_collapsed.py:25-42` — no project-wide `client` fixture exists in `tests/dashboard/conftest.py`, so each file must define its own.

**Bug A — semantic correctness** ✅
- The test (`test_i00089_bug_a_collapse_button_hidden_when_collapsed`) uses:
  ```python
  style_block_pattern = re.compile(
      r"#chat-assistant-panel\[data-collapsed=\"true\"\][^{]*"
      r"#chat-assistant-collapse-btn",
      re.DOTALL,
  )
  assert style_block_pattern.search(html)
  ```
- This is attribute-scoped to the `<style>` block (via `re.DOTALL` across the full HTML) and targets the exact selector chain S01 added: `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn { display: none; }` (panel.html line 12).
- **Pre-fix state**: Before S01's fix, `panel.html` did not contain `#chat-assistant-collapse-btn` in the display:none group — the selector would not match, test would fail. ✅
- **Post-fix state**: S01 added the rule at panel.html line 12; test passes. ✅
- A bare `"chat-assistant-collapse-btn" in html` substring check would have matched the button's own tag and passed even pre-fix, but that form is not used — the regex explicitly requires the CSS selector chain context.

**Bug B title assertion** ✅
- Uses `\btitle="[^"]+"` with word-boundary anchoring — does NOT match `title` appearing inside `aria-label="…title…"` or inside any other attribute name.
- **Pre-fix state**: Pre-fix HTML has no `title=` on the collapse button (only `aria-label`), so the regex fails → test fails. ✅
- **Post-fix state**: S01 added `title="Collapse panel"` (panel.html line 69); test passes. ✅

**Bug B class-marker assertion** ✅
- Asserts exactly `chat-assistant-collapse-btn-distinct` in `button_tag` (line 120) — the custom class Variant A that S01 chose (per S01 report notes: "Chose the `chat-assistant-collapse-btn-distinct` custom class marker over the Tailwind `border-l` path").
- **Pre-fix state**: Pre-fix HTML has no such class on the button → assertion fails. ✅
- **Post-fix state**: S01 added `chat-assistant-collapse-btn-distinct` to the button's class list (panel.html line 67); test passes. ✅
- The test does NOT accept `border-l` (Variant B) — which is correct because S01 chose Variant A.

**Element-scoped match** ✅
- Uses `re.search(r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>', html)` to extract only the button's opening tag before asserting on its attributes — not a bare substring across the full page HTML. Prevents false positives from `chat.js` source or other occurrences.

**Test isolation and stability** ✅
- No `time.sleep`, no network calls.
- `IW_CORE_EXPECTED_INSTANCE_ID` env var is popped/restored in the `client` fixture teardown (lines 32, 43-44).
- No reliance on Tailwind class names (the custom class marker is part of the fix's explicit contract).

**Test results** ✅
- S03 report shows `2 passed, 0 failed` (8.77s).
- Targeted run with `uv run pytest tests/dashboard/test_chat_assistant_header.py -v --no-cov` confirms: `2 passed`.

**RED reasoning** ✅
- S03 is a `tests-impl` coverage step that runs after S01 (fix). Per the step contract and the testing skill's guidance, `tests-impl` is exempt from the runtime-RED requirement. RED evidence for this incident was established at intake via playwright-cli (evidences/pre/).

## Acceptance Criteria Traceability

| AC | Covered by | Status |
|----|------------|--------|
| AC1: Bug A — collapsed-state stray button gone | `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_a_collapse_button_hidden_when_collapsed` — asserts CSS selector chain in `<style>` block | pass |
| AC2: Bug B — expanded-state collapse button discoverable | `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_b_collapse_button_has_discoverable_affordance` — asserts `title=` attribute and `chat-assistant-collapse-btn-distinct` class on button tag | pass |
| AC3: Regression test exists and passes | Both tests above | pass |

## Decision

`complete` — No CRITICAL or HIGH findings. All assertions are semantically correct and would fail against the pre-fix HTML. Test placement, fixture pattern, and isolation are all correct.