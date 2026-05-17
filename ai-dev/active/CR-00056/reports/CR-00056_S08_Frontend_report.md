# CR-00056 S08 — Frontend Report

## What Was Done

Implemented the visible half of CR-00056: a **Prompt** column in the steps table that opens an accessible modal with the prompt text and per-section copy buttons.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/item_steps_table.html` | Added Prompt column header (between Model and Status), prompt cell with `View` button + `hx-get` trigger, mount point `<div id="prompt-modal-mount">`, updated empty-state `colspan` from 8→9 |
| `dashboard/templates/fragments/prompt_text_modal.html` | Replaced placeholder with production modal: shared `.activity-modal*` CSS classes, header with step info + file path, per-section copy buttons, inline script calling `window.__promptModalInit` |
| `dashboard/static/styles.css` | Appended `.prompt-modal-section`, `.prompt-modal-section-header`, `.prompt-modal-pre` rules (Tailwind CLI reported "Nothing to be done") |
| `dashboard/static/prompt_modal.js` | New file: focus trap (Tab/Shift+Tab), Escape key dismiss, backdrop click dismiss, body scroll lock, copy-to-clipboard via `window.iwClipboard.copy(text, button)` |
| `dashboard/templates/base.html` | Added `<script defer src="/static/prompt_modal.js"></script>` after `clipboard.js` include |

## CSS Approach

Reused `.activity-modal*` class names in the template (backdrop, modal, inner, header, body) — no parallel CSS needed for the outer shell. Added new `.prompt-modal-section*` rules for the multi-section layout inside the body (section headers, pre blocks, copy buttons).

## Key Decisions

- **Reused activity-modal CSS** — the outer modal structure (backdrop, positioning, inner container, header) is identical; no need for parallel `.prompt-modal-*` outer rules.
- **`data-prompt-section-body` attribute** for copy target lookup — index-based, matches the copy button's `data-prompt-copy-section`.
- **`window.__promptModalInit` singleton** — guards against double-binding on subsequent htmx swaps; also hooked to `htmx:afterSwap` on `#prompt-modal-mount` as fallback.
- **`aria-hidden="false"` on both overlay and modal** at swap time — the modal is visible immediately when inserted; no separate "open" step needed.

## TDD Evidence

`n/a — frontend template + CSS + JS only; behavioural verification is the qv-browser step S22`

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ✅ ok |
| `make typecheck` | ✅ ok |
| `make lint` | ✅ ok |

## Test Results

```
tests/dashboard/test_prompt_modal_route.py::TestPromptModalRoute::test_returns_200_with_prompt_text PASSED
tests/dashboard/test_prompt_modal_route.py::TestPromptModalRoute::test_404_unknown_item PASSED
tests/dashboard/test_prompt_modal_route.py::TestPromptModalRoute::test_404_unknown_step PASSED
tests/dashboard/test_prompt_modal_route.py::TestPromptModalRoute::test_404_no_prompt_text PASSED
tests/dashboard/test_prompt_modal_route.py::TestPromptModalRoute::test_fix_prompt_text_sections PASSED
tests/dashboard/test_prompt_modal_route.py::TestStepDetailHasPrompt::test_synthetic_step_returns_404 PASSED
6 passed
```

Coverage failure is pre-existing (total 18% < fail-under 50%) — unrelated to these changes.

## Blockers

None.
