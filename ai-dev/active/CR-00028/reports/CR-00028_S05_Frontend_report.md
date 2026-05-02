# CR-00028 S05 Frontend Implementation Report

**Step**: S05 — Frontend dashboard UI for recoverable merge statuses
**Work Item**: CR-00028 — Don't cascade merge-time failures to dependent items
**Date**: 2026-05-02
**Agent**: frontend-impl

---

## Summary

Implemented the dashboard UI components for the three new operator-recoverable `BatchItemStatus` values introduced in CR-00028:
- `merge_failed` (new)
- `migration_invalid` (pre-existing)
- `migration_rebase_failed` (pre-existing)

All three now share the same `bg-warning` visual treatment (amber/yellow — distinct from the red `bg-destructive` used for plain `failed`), and the `abandon-merge` action button is wired into the item overview page alongside the existing `restart-merge` button.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/status_badge.html` | Added `merge_failed`, `migration_invalid`, `migration_rebase_failed` entries using `bg-warning text-warning-foreground` (same token as `timeout`, `stalled`, `needs_fix`) |
| `dashboard/routers/items.py` | Extended `_merge_status()` with a `recoverable_merge_statuses` set; maps all three recoverable statuses to display value `"merge_failed"` |
| `dashboard/templates/components/action_button.html` | Added `abandon_merge_button` macro (danger styling, `hx-get` to `/project/{id}/api/confirm-item/abandon-merge/{item_id}`) |
| `dashboard/templates/fragments/item_overview.html` | Extended MERGE-step button condition to `step.status in ('failed', 'merge_failed')`; renders both `restart_merge_button` and `abandon_merge_button` (latter only for `merge_failed`) |

---

## Decisions & Rationale

### Status badge color — `bg-warning` reused (no `make css` needed)

The prompt suggested `bg-warning` (already used by `timeout`, `stalled`, `needs_fix`) for the recoverable badge. This avoids introducing a new Tailwind utility class, so `make css` was **not** run. All three statuses (`merge_failed`, `migration_invalid`, `migration_rebase_failed`) share this token.

> **Note for reviewers**: `migration_invalid` and `migration_rebase_failed` were not explicitly mentioned in the prompt's Step 1, but they pre-date CR-00028 and already fell through to the `bg-muted text-muted-foreground` fallback. Giving them the same `bg-warning` treatment as `merge_failed` makes them visually consistent and is an intentional change flagged here. If a different hue (e.g. amber) is preferred for the recoverable-merge group vs. general warnings, that would require adding new Tailwind tokens and running `make css` — flag this in the review.

### `_merge_status` returns literal `"merge_failed"`

Returning the literal string `"merge_failed"` (rather than a distinct string per status) is intentional — it makes the badge lookup (Step 1) and the button condition in `item_overview.html` trip on the same value. The operator can still distinguish the underlying DB status by looking at the item detail page if needed.

### Abandon button only shown for `merge_failed` (not `failed`)

The condition `{% if step.status == 'merge_failed' %}` on the abandon button ensures it only appears for the new non-cascading statuses. Legacy `failed` rows (e.g. notes starting with "Merge failed") still get only Retry — operators can drop a row to legacy-cascade behavior by NOT retrying. This matches the design intent in the prompt.

### No inline buttons added to batch detail page

Per prompt Step 5, inline Retry/Abandon buttons were not added to `batch_detail.html`. The badge color change is sufficient for that surface, and operators can click through to the item overview for the full button set.

---

## Quality Gates

| Check | Result |
|-------|--------|
| `make format` | `dashboard/routers/items.py` — already formatted; HTML templates are Jinja2 (not ruff-checkable) |
| `make typecheck` | ✅ Success — no issues in 212 source files |
| `make lint` | ✅ Only pre-existing errors in `actions.py:1170` (N806 in test fixture) and `test_batch_manager.py:191` (line too long) — unrelated to this CR |
| `make test-unit` | ✅ 2291 passed, 2 skipped, 5 xfailed, 1 xpassed |

---

## Smoke Check

- `playwright-cli open http://localhost:9900/project/iw-ai-core/batches` — page loads without errors
- Screenshot saved to `.playwright-cli/page-2026-05-02T13-54-55-010Z.png`
- No `merge_failed` rows exist in the live DB yet (DB enum won't exist until migration applies post-merge); deep E2E verification deferred to S15

---

## Blockers

None.
