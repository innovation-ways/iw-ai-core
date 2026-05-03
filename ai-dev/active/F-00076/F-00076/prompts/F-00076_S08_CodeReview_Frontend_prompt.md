# F-00076_S08_CodeReview_Frontend_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S08
**Agent**: code-review-impl
**Reviewing**: S07 (frontend-impl)

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/reports/F-00076_S07_Frontend_report.md`
- All files listed in S07's `files_changed`

## Review Scope

1. **Item overview panel** (`dashboard/templates/fragments/item_overview.html`):
   - Renders `impacted_paths` as monospace chips.
   - Badge color/text matches `config.scope_extraction.source`.
   - Empty-state copy is exact.
   - `<details>` default state matches design (collapsed if >=6 globs).

2. **Worktrees table tooltip** (`dashboard/templates/system/worktrees_table.html` or actual path):
   - Tooltip readable in light AND dark mode.
   - Row passes `impacted_paths` from joined `BatchItem` → `WorkItem` query.
   - "+N more" rendered when more than 5 globs.

3. **Batch held indicator** (`dashboard/templates/fragments/batch_items.html`):
   - Triggers only on `pending` status + `item_held_for_scope` event within 5 min.
   - `held_reasons` context dict keyed by `item_id`.
   - `glob_summary` correctly truncates to first 2 + "+N".
   - `aria-label` present and informative.

4. **Routers** (`dashboard/routers/items.py`, `batches.py`, `worktrees.py`):
   - No new endpoints (data pass-through only — design says so).
   - DaemonEvent query in `batches.py` is bounded (LIMIT N per item, time filter).
   - No N+1 on the held-events query.

5. **Tests**: route-level integration tests cover both panels.

6. **Conventions**: `dashboard/CLAUDE.md` — Jinja2 + htmx + Tailwind, no inline scripts.

## Severity Levels

(Same as S02.)

## Output

`ai-dev/active/F-00076/reports/F-00076_S08_CodeReview_Frontend_report.md`. Re-run `make test-frontend` and `make test-unit`.

## Subagent Result Contract

(Same shape as S02.)
