# I-00101 S03 — Frontend Report

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S03 — Frontend
**Agent**: frontend-impl
**Status**: complete

---

## What Was Done

Implemented the full UI layer for the scope-violation escalation feature:

1. **`status_badge.html`** — Added `scope_blocked` mapping in the badge color dictionary (amber style distinct from `needs_fix`).

2. **`items.py`** — Added `scope_violations: list[str] | None` field to `StepDetail` dataclass. In `_get_steps()`, bulk-fetches scope violations for all `needs_fix` steps via `latest_scope_violation()` (single loop over needs_fix IDs, N+1 safe). Attached to each `StepDetail`.

3. **`item_steps_table.html`** — Updated the status column (line 111) to render the amber `badge-scope-blocked` when `step.scope_violations` is truthy, with `title` and `aria-label` listing offending paths. Updated the actions column (line ~157) to show three buttons (✎ Amend scope → modal, ↩ Revert → hx-confirm POST, ⏭ Skip) when `step.scope_violations` is set, and the existing Restart + Skip otherwise.

4. **`scope_amend_modal.html`** (new file) — Fragment modal with backdrop + centered card. Title "Amend scope for {item.id} / {step.step_id}". Pre-checked checkboxes per offending path. Read-only current `allowed_paths` list. Two buttons: Cancel (inline JS close) and "Amend & restart" (submits form).

5. **`actions.py`** — Added three new endpoints after `restart_step` (line 379):
   - `GET /item/{item_id}/scope/amend-modal/{step_id}` — returns modal HTML fragment (uses `templates.TemplateResponse` directly since `_render_fragment` is in auto_merge_ui.py)
   - `POST /item/{item_id}/scope/amend-and-restart/{step_id}` — validates paths are in violation set, calls `amend_allowed_paths()`, emits `scope_amended_by_operator` event, creates new StepRun with pending status, flips step to pending, unblocks item if failed
   - `POST /item/{item_id}/scope/revert-and-restart/{step_id}` — calls `revert_paths_in_worktree()`, emits `scope_reverted_by_operator`, same DB restart mutations

6. **`running.py`** — Added `scope_violations: list[str] | None` to `FailedRow` dataclass. In `_query_failed_steps()`, added a bulk query loop after `last_error_map` to populate `scope_violations_map` keyed on `step.id` for `needs_fix` steps. Attached to each `FailedRow`.

7. **`pages/system/running.html`** — Updated the Failed/Needs Attention table: renders `badge-scope-blocked` amber badge when `row.scope_violations` is set; shows Amend + Revert + Skip buttons for scope-blocked rows (with `hx-confirm` on Revert), and the existing Restart + Skip + "↺ from here" otherwise.

8. **`static/styles.css`** — Appended `.badge-scope-blocked` plain CSS rule (amber background #fde68a, amber border #f59e0b, amber text #92400e) because `make css` reported "Nothing to be done" (Tailwind prebuilt cache missed the new `bg-amber-200` in templates but the templates also use plain CSS fallback classes, so the plain CSS covers both rendering paths).

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/status_badge.html` | Added `scope_blocked` key to badge color map |
| `dashboard/routers/items.py` | Added `scope_violations` field to `StepDetail`; bulk-fetch in `_get_steps()` |
| `dashboard/templates/fragments/item_steps_table.html` | Scope-blocked badge + Amend/Revert/Skip buttons |
| `dashboard/templates/components/scope_amend_modal.html` | **NEW** — modal fragment |
| `dashboard/routers/actions.py` | Three new endpoints (amend-modal GET, amend-and-restart POST, revert-and-restart POST) |
| `dashboard/routers/running.py` | `FailedRow.scope_violations` + bulk fetch in `_query_failed_steps()` |
| `dashboard/templates/pages/system/running.html` | Scope-blocked badge + Amend/Revert/Skip in Failed table |
| `dashboard/static/styles.css` | `.badge-scope-blocked` plain CSS fallback |

---

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | Fixed (ruff reformatted `actions.py`) |
| `make typecheck` | ok — 0 errors |
| `make lint` | ok — all checks passed |
| `make css` | "Nothing to be done" → appended plain CSS fallback to `styles.css` |

---

## Test Results

```
940 passed, 15 skipped, 25 deselected, 1 xfailed in 181.91s (0:03:01)
```

No regressions in the existing `tests/dashboard/` suite.

---

## TDD Evidence

`tdd_red_evidence: "n/a — Frontend wires up helpers + templates; S05 owns the dashboard/integration tests"`

---

## Notes

- The `write_button_attrs` macro was already imported in `item_steps_table.html` (it was already used for `restart_setup_button`), so the amend/revert buttons correctly use `{{ write_button_attrs(request) }}`.
- The running.html table uses `{{ write_button_attrs(request) }}` for the amend button and skip button (which also goes through `skip_button` macro that calls `write_button_attrs`).
- `make css` reported "Nothing to be done" because the Tailwind prebuild uses a cached purge that doesn't detect `bg-amber-200` / `text-amber-900` / `border-amber-400` as being used (the templates reference them but Tailwind JIT didn't pick them up). The plain CSS `.badge-scope-blocked` fallback in `styles.css` ensures the badge renders correctly.
- The modal close uses inline JS (`onclick="document.getElementById('scope-amend-modal').remove(); ..."`) to remove both the modal and the backdrop when Cancel is clicked — consistent with other modal patterns in the codebase (e.g., `prompt_text_modal.html`).
- The skip button in running.html for scope-blocked rows uses the same confirm-dialog path as the other skip buttons (`hx-get="/project/.../api/confirm/skip-step/..." hx-target="#confirm-dialog" hx-swap="innerHTML"`) rather than a direct POST, which is consistent with the existing skip button pattern.
