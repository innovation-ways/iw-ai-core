# I-00056_S04_CodeReview_Frontend_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step Being Reviewed**: S03 (Frontend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00056 --json`
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `ai-dev/active/I-00056/reports/I-00056_S03_Frontend_report.md`
- All files in S03's `files_changed`
- `dashboard/templates/fragments/code_module_cards.html` (reference for parity)

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S04_CodeReview_report.md`

## Pre-Review Gate

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL.

## Review Checklist

### 1. DOM order: chips slot precedes prose

Open the rendered output of the Code page (manually or via test client). The element `id="code-component-chips-slot"` MUST appear in source order before `class="prose-doc`. If the chip strip arrives via htmx, the slot itself must still precede the prose body.

### 2. Chip click parity with cards

For every module, the chip's `hx-get` URL, `hx-target`, and `hx-swap` must EXACTLY match the cards template — both surfaces load the same module detail into the same `#code-detail-panel`. Diff the htmx attributes between `code_module_chips.html` and `code_module_cards.html` to verify.

### 3. Tailwind hygiene

- No dynamic class construction (`class="text-{{ color }}"` etc.). Tailwind's JIT requires statically-knowable class names.
- New classes appear in `dashboard/static/styles.css` — confirm `make css` was run and the regenerated file is staged.
- No inline `style=` attributes.

### 4. Accessibility

- Each chip has a discoverable accessible name (either visible text covers both name + path, or an `aria-label` does).
- The chip strip wrapper has an `aria-label` describing the region (e.g. "Code components").
- Tab order is sensible — chips should be focusable in document order.

### 5. Empty state

Verify the chips template renders nothing (or a tiny muted hint at most) when `modules` is empty. The chip strip must not produce a 0-height wrapper that nonetheless adds visual padding.

### 6. No regressions on the cards section

`#code-components-section` (the cards htmx slot) is unchanged. Cards still load below the prose. Confirm by reading the diff of `code_architecture_view.html`.

### 7. No scope creep

Out-of-scope (must not appear):

- Changes to `code_module_cards.html`.
- Changes to chat panel templates (I-00057's territory).
- Changes to the diagram-architecture rendering (I-00055).
- Style changes to `.prose-doc` itself.

## Test Verification

```bash
make test-unit
```

## Severity Levels

| CRITICAL | DOM order wrong; htmx target mismatch; dynamic Tailwind class | Must fix |
| HIGH | Missing accessibility name; `make css` not run | Must fix |
| MEDIUM (fixable) | Convention drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00056",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
