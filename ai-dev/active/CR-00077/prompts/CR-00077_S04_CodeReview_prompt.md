# CR-00077_S04_CodeReview_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S03_Frontend_report.md`
- The S03 diff (templates + CSS).

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S04_CodeReview_report.md` — findings with severities.

## Scope of Review

Per-agent review of S03's template + CSS changes:

1. **Single source of truth** — `batch_overlap_modal.html` is the only template that renders the modal. The `batch_items_rows.html` trigger calls the endpoint; the modal markup is not duplicated anywhere. If any duplicated modal markup exists, flag as CRITICAL.

2. **Reuse of pill markup** — the trigger button preserves the original `title`, `aria-label`, SVG icon, and visible text. If any of those four are missing or altered, flag as MAJOR (this is the no-regression contract).

3. **Esc handler scope** — the Esc listener is `document.addEventListener('keydown', onKey)` AND there is a matching `document.removeEventListener('keydown', onKey)` inside `close()`. If the removeListener is missing, flag as MAJOR (handler leak across multiple opens).

4. **Modal root** — exactly one `<div id="overlap-modal-root"></div>` in `batch_detail.html`, placed outside the polled items fragment. Duplicate IDs in the rendered HTML are a CRITICAL accessibility / DOM bug. Confirm `queue.html` was NOT modified (out of scope).

5. **CSS append-only** — the new rules are *appended* to `dashboard/static/styles.css`; no existing rules deleted; all class names use the `iw-modal-*` / `iw-overlap-pill-*` prefixes (no collisions with existing classes like `.modal`, `.dialog`, `.overlay`).

6. **Tailwind discipline** — no edits to `dashboard/static/styles.tailwind.css` or `tailwind.config.js`. No new Tailwind classes that need JIT recompile (the plain-CSS-fallback rule from root `CLAUDE.md`).

7. **No read-only contract violations** — no `<form>`, no `<input>`, no `hx-post`, no `hx-delete` in the modal partial. If any are present, flag as CRITICAL (CR-00078 owns those).

8. **Jinja `%`-format-filter rule** (root `CLAUDE.md`) — no `"{} ..."|format(...)` style usage. If found, flag as CRITICAL.

9. **404 path** — the modal partial's `{% if empty %}` branch renders correctly without any `sections` variable being passed (the route only passes `held_item_id` in that case).

10. **Read-only — script tag review** — the inline `<script>` block only manipulates the modal's own DOM via `document.getElementById('overlap-modal-root')`. It does not fetch, post, or write to any state.

11. **Trigger URL survives live refresh** — the trigger button's `hx-get` embeds `{{ batch.id }}`. Confirm `batch` is resolvable in BOTH render paths of `batch_items_rows.html`: the `batch_detail.html` page load AND the `batch_items_fragment` htmx endpoint (S01 added `batch` to the latter's context). If the polled fragment cannot resolve `batch.id`, the modal trigger silently breaks after the first Items-tab refresh — flag as **HIGH**.

## Severity Guide

- CRITICAL: duplicate modal templates, duplicate DOM IDs, form/POST in modal, `str.format`-style filter call.
- HIGH: Esc handler leak, missing aria attributes, broken trigger semantics.
- MEDIUM: CSS naming collision, Tailwind input edit, missing focus-visible style.
- LOW: documentation, file ordering.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00077",
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
