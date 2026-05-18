# I-00101_S04_CodeReview_Frontend_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step Being Reviewed**: S03 (Frontend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations in S03.

## Input Files

- `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00101/reports/I-00101_S03_Frontend_report.md` — S03 report
- All files in S03's `files_changed`

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S04_CodeReview_Frontend_report.md` — Review report

## Context

Reviewing the Frontend wiring (badge, modal, endpoints, global table). The design doc's AC1, AC2, AC3 are S03's responsibility.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint    # includes scripts/check_templates.py — catches %-style format-filter rule (I-00075)
make format  # ruff format --check
make css     # confirm Tailwind output is up-to-date OR plain CSS is in styles.css per I-00067 mitigation
```

NEW violations against `main` → CRITICAL findings.

## Review Checklist

### 1. Badge variant correctness

- `dashboard/templates/components/status_badge.html` has a `scope_blocked` key in the mapping AND the existing mappings for real StepStatus values (`needs_fix`, `failed`, `completed`, etc.) are unchanged. Any change to existing keys is **CRITICAL** (would break unrelated rendering).
- The Tailwind classes (or plain CSS rule names) used are differentiable from `needs_fix` — same amber tone is OK but there must be visible distinction (icon, border, or label).

### 2. Items.py wiring

- `dashboard/routers/items.py` calls `latest_scope_violation` for each `needs_fix` step. Verify no N+1 query — a bulk fetch is acceptable; per-row is **MEDIUM_FIXABLE** (perf).
- The context variable passed to the template is named consistently (e.g., `step.scope_violations`); the template branch in `item_steps_table.html` matches that name.

### 3. Template branch correctness

- `item_steps_table.html` uses `{% if step.scope_violations %}` to switch into the scope-blocked rendering. Empty list `[]` correctly falls through to the standard branch (per S01's `latest_scope_violation` returning `None` not `[]` for empty).
- On scope-blocked rows, the existing **Restart** button is **hidden** (rendering it would let the operator re-trigger the loop) — **HIGH** if Restart still renders.
- The **Skip** button is still rendered on scope-blocked rows.
- The new "Amend scope & restart" button uses `hx-get` to the modal endpoint with the correct URL pattern (`/project/{project_id}/actions/item/{item_id}/scope/amend-modal/{step_id}`) — verify segment order matches the existing endpoints in `actions.py`.
- The new "Revert & restart" button uses `hx-post` with `hx-confirm` to the revert endpoint.
- `title` / `aria-label` attributes on the badge list the offending paths.

### 4. Modal partial

- `dashboard/templates/components/scope_amend_modal.html` does NOT extend `base.html`. **CRITICAL** if it does (per `dashboard/CLAUDE.md`).
- Form posts to the correct endpoint with the same URL pattern as the GET.
- Each checkbox is `<input type="checkbox" name="paths" value="…">` — FastAPI's `paths: list[str] = Form(...)` only collects from `name="paths"`.
- All violation paths are pre-checked.
- The current `allowed_paths` list is rendered read-only (no checkboxes, no inputs).
- Clipboard buttons (if any) use the `window.iwClipboard.copy(text, button)` shared helper, NOT direct `navigator.clipboard.writeText()` (per `dashboard/CLAUDE.md`).

### 5. Endpoint correctness

- **GET amend-modal** validates `latest_scope_violation IS NOT None` and returns 422 otherwise. Missing guard = **HIGH**.
- **POST amend-and-restart** validates the same AND rejects paths not in the violation set (HTTP 422 with explicit message). Missing rejection of off-list paths = **HIGH** (otherwise the operator could append arbitrary paths).
- **POST amend-and-restart** emits `scope_amended_by_operator` event with metadata `{step_id, added_paths, manifests_updated}`. Event name mismatch is **HIGH** (the tests in S05 assert this exact name).
- **POST amend-and-restart** performs the same DB mutations as the existing `restart_step` at `dashboard/routers/actions.py:323-371`: new `StepRun` with incremented run_number, step.status flipped to pending, started_at/completed_at cleared, item.status fixed if it was `failed`, single `db.commit()`. Any divergence in mutation set is **HIGH**.
- **POST revert-and-restart** invokes `revert_paths_in_worktree(worktree, list(violations))` (the full violation set, since the modal doesn't surface partial revert), emits `scope_reverted_by_operator` event with `{step_id, reverted_paths, failed_paths}`, then does the same restart mutation. Does NOT amend any manifest.
- Both POSTs handle the `needs_fix` status correctly. **CRITICAL** if they reject `needs_fix` like the existing `restart_step` does.
- No new `restart_step` was widened — the existing endpoint remains `failed | skipped` only. **MEDIUM_FIXABLE** if `restart_step` was modified without a reason in the report.

### 6. Global needs-attention table

- `running.py::_query_failed_steps` builds a `scope_violations_map` keyed on `step.id` and attaches the violations to the row. Missing = **HIGH** (AC1 requires the badge in the global table too).
- The template rendering `FailedRow` rows also gates the scope_blocked badge on the violations list.

### 7. CSS / styles

- If `make css` reports drift or failure and `dashboard/static/styles.css` was hand-edited, the changes are scoped to the new badge variant and modal — no unrelated rules were touched. **HIGH** on unrelated edits.

### 8. Template linter

- `make lint` passes the `scripts/check_templates.py` step. The Jinja2 `format`-filter rule (`"%dm%02ds"|format(m, s)`, never `str.format`-style) applies — if the new modal renders any duration or numeric formatting, verify `%`-style is used (per CLAUDE.md I-00075).

### 9. Scope discipline

- Files changed are ONLY those listed in design's File Manifest under `S03 Frontend`. Any other file is **CRITICAL** scope creep.

### 10. TDD RED Evidence

S03 legitimately adds no behavioural test — `tdd_red_evidence: "n/a — Frontend wires up…"` is correct. Missing field = **HIGH**.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/ -v --no-cov
```

Confirm no dashboard test regressed.

## Review Result Contract

Standard JSON contract (see template). `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE; `fail` otherwise.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00101",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
