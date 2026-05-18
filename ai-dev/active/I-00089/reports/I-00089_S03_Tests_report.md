# I-00089_S03_Tests_report

## Step Summary

**Work Item**: I-00089 — AI Assistant panel in-header collapse button unusable in both states
**Step**: S03 — Tests Implementation
**Agent**: tests-impl

## What Was Done

Created `tests/dashboard/test_chat_assistant_header.py` with two reproduction tests covering both bugs from the Issue_Design:

1. **`test_i00089_bug_a_collapse_button_hidden_when_collapsed`** (AC1 / Bug A)
   - Asserts the inline `<style>` block in the rendered HTML contains the selector chain `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn` in its `display: none` group.
   - Uses attribute-scoped regex (`re.DOTALL`) — not bare substring — to avoid false-positives from JS source or comments (per CLAUDE.md I-00067 guidance).

2. **`test_i00089_bug_b_collapse_button_has_discoverable_affordance`** (AC2 / Bug B)
   - Asserts the collapse button element carries a `title="Collapse panel"` attribute (word-boundary-anchored regex, not bare `"title" in button_tag`).
   - Asserts the button carries the custom class marker `chat-assistant-collapse-btn-distinct` — S01's Variant A choice (per S01 report `notes` field: "Chose the `chat-assistant-collapse-btn-distinct` custom class marker over the Tailwind `border-l` path").
   - Variant B (Tailwind border utility) is NOT asserted — the test targets exactly the variant S01 implemented.

Both tests use the canonical inline `client` fixture (from `test_chat_panel_default_collapsed.py:25-42`), which overrides `get_db` to use the test `db_session`. This matches the project convention for dashboard test files.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_chat_assistant_header.py` | New — 2 regression tests for Bug A + Bug B |

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | Fixed — added trailing newline |
| `make typecheck` | ok — no errors (255 source files checked) |
| `make lint` | ok — all checks passed after auto-fix |

## Test Results

```
tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_b_collapse_button_has_discoverable_affordance PASSED [ 50%]
tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_a_collapse_button_hidden_when_collapsed PASSED [100%]
2 passed in 6.93s
```

Both tests pass GREEN — S01's fix has already landed, so these assertions confirm the expected post-fix state.

## TDD / RED Evidence

`tests-impl` is a coverage step that executes AFTER S01 (fix) and S02 (review). Per the step contract, `tdd_red_evidence` is `n/a` — this is not a RED-first TDD step. RED evidence for this incident is established at incident intake via playwright-cli (see `ai-dev/active/I-00089/evidences/pre/`).

## Semantic Correctness Notes

- Bug A: regex `re.compile(r'#chat-assistant-panel\[data-collapsed="true"\][^{]*#chat-assistant-collapse-btn', re.DOTALL)` matches the exact selector chain S01 added, scoped to the `<style>` block context.
- Bug B `title`: `re.search(r'\btitle="[^"]+"', button_tag)` uses word-boundary anchoring to avoid matching `"title"` inside `aria-label="Collapse AI Assistant panel (Ctrl+/)"`.
- Bug B class: `assert "chat-assistant-collapse-btn-distinct" in button_tag` — semantic, targets the exact custom class S01 added as Variant A. Does NOT accept `border-l` (Variant B).

## Blockers

None.

## Notes

- S01 chose Variant A (custom `chat-assistant-collapse-btn-distinct` class over Tailwind `border-l`).
- Bug B assertions are tight — they accept only Variant A, not an any-of-several check. If S01 had chosen Variant B, the class assertion would need to be `re.search(r'\bclass="[^"]*\bborder(-l)?\b[^"]*"', button_tag)`.
- No JS changes were needed; the click handler in `chat.js:953-956` is already correct once the button visibility is properly controlled by CSS.