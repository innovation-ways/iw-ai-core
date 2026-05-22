# CR-00078_S09_CodeReview_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S09
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work in this step.

## Scope of Review

Per-agent review of S08's frontend changes.

1. **`hx-target="closest .iw-modal-file-row"`** — verify this exact target string. A global selector would remove every row.
2. **Master button gated** — `{% if sections %}` guard surrounds the `<footer>`. The 404/empty branch from CR-00077 still does NOT render the master button.
3. **`batch_id` in template context** — the `{{ batch_id }}` interpolation in the new template fragments resolves to a value (verify S08 added it to the GET endpoint's context dict in `batches.py`). If missing, the resulting `hx-post` URL has `/batch//overlap/...` — broken.
4. **CSS prefix** — all new classes use `iw-modal-*` (no collision with existing).
5. **No conflict with CR-00077 CSS rules** — the new `.iw-modal-file-row` flex layout doesn't fight with the existing `.iw-modal-file-list li` rule. If both apply to the same elements, the merged style must produce the intended layout (flex + space-between). Inspect the actual rendered cascade by visual reading, or note that S19 browser_verification will catch a misrendered button.
6. **No `<form>` element** — `hx-post` directly on the `<button>`; no enclosing `<form>` introduced.
7. **`hx-confirm` text is meaningful** — `Ignore every remaining overlap for X in this batch and let it start?` — verify the held_item_id interpolates correctly.
8. **No `str.format`-style `format` filter** — verify with `scripts/check_templates.py` (covered by `make lint`).
9. **No Tailwind classes** added that need recompile — all utility classes are pre-existing or plain CSS.

## Severity Guide

- CRITICAL: `hx-target` global selector; missing `batch_id` in context (URL broken); master button rendered on empty path.
- HIGH: CSS cascade collision producing misrendered button; missing `{% if sections %}` guard.
- MEDIUM: `hx-confirm` text is vague; missing focus-visible style.
- LOW: spacing, comments.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-impl",
  "work_item": "CR-00078",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
