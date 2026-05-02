# F-00076_S07_Frontend_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S07
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Same constraints as the design document.)

## Input Files

- `uv run iw item-status F-00076 --json`
- `ai-dev/active/F-00076/F-00076_Feature_Design.md` (sections: AC6, Frontend Changes, File Manifest)
- `ai-dev/active/F-00076/evidences/pre/` — pre-feature screenshots (item-detail, batch-detail, worktrees)
- `ai-dev/active/F-00076/reports/F-00076_S03_Backend_report.md` (column wiring details)
- `ai-dev/active/F-00076/reports/F-00076_S04_Pipeline_report.md` (event payload shape)
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/batch_items.html`
- `dashboard/templates/system/worktrees_table.html` (or the actual worktrees table fragment — verify path)
- `dashboard/routers/items.py:949-997` (item overview tab)
- `dashboard/routers/batches.py:362-420` (batches/items fragments)
- `dashboard/routers/worktrees.py:555-590` (worktrees table fragment)
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S07_Frontend_report.md`
- Modified templates listed above
- Modified routers (data pass-through only — no new endpoints)

## Context

Display `WorkItem.impacted_paths` and the held-state reason on three pages:

1. **Item detail (overview tab)** — collapsible "Impacted Paths" panel listing globs with a small "declared" or "auto" badge from `config["scope_extraction"]["source"]`.
2. **Worktrees table** — column or tooltip showing the in-flight item's globs (read from `WorkItem.impacted_paths` joined to the worktree's BatchItem).
3. **Batch detail items fragment** — for items with status=`pending` AND a recent `item_held_for_scope` event in the last 5 minutes, render "Held: overlaps with I-NNNNN on `<glob>`" inline.

Read `dashboard/CLAUDE.md` for htmx + Jinja2 + Tailwind patterns. Match existing fragment style (reference `dashboard/templates/fragments/item_overview.html` for badge/panel idiom).

## Requirements

### 1. Item overview "Impacted Paths" panel

In `dashboard/templates/fragments/item_overview.html`, add a collapsible section after the existing dependency block. Use a `<details>` element to keep it native. Render:

- Heading: "Impacted Paths" + small badge:
  - Green `declared` if `item.config.scope_extraction.source == "declared"`.
  - Amber `auto` (with tooltip "regex fallback — please verify in design doc") if `regex_fallback`.
  - Grey `none` if `none`.
- List of globs as monospace `<code>` chips, one per line.
- Empty state: "No paths declared — item bypasses cross-batch conflict gate".

In `dashboard/routers/items.py:tab_overview()` (around line 949-997), ensure the `item` object passed to the template carries `impacted_paths` and `config` — the existing serialization should already include them once S01/S03 land, but verify in your test pass.

### 2. Worktrees table — in-flight scope tooltip

In the worktrees table fragment (find via `grep -rn 'worktrees-table\|worktree-row' dashboard/templates/`), add a column or tooltip showing the currently-running item's `impacted_paths`. Tooltip rendered via title attribute or a Tailwind tooltip pattern already in use. Keep it under 5 globs visible; "+N more" if longer.

In `dashboard/routers/worktrees.py:570` (worktrees_table fragment), pass `impacted_paths` for each row by joining `BatchItem` → `WorkItem`.

### 3. Batch detail — held-state row indicator

In `dashboard/templates/fragments/batch_items.html`, for each item row:

- If `item.status == "pending"` AND there is a `daemon_event` of type `item_held_for_scope` for this work_item_id within the last 5 minutes: render a row indicator like `🔒 Held: overlaps with {{ blocking_id }} on {{ glob_summary }}`.
- The data feed comes from a new helper in `dashboard/routers/batches.py` that queries `DaemonEvent` filtered to `event_type='item_held_for_scope'` and `entity_id IN (item ids in this batch)`, ordered by `created_at DESC`, taking only the most recent per item. Inject into the items context as `held_reasons: dict[item_id -> {blocking_id, conflicting_globs}]`.

`glob_summary` = first 2 conflicting globs joined by `, ` plus "+N" if more.

### 4. Style and accessibility

- Use existing Tailwind classes — don't introduce new utility names.
- Tooltips must be readable in dark mode (project supports dark mode — verify).
- The held-indicator must be screen-reader friendly (`aria-label` summarizing the conflict).
- The collapsible "Impacted Paths" panel default state: collapsed if list >= 6 globs, expanded otherwise.

### 5. Browser verification (preview locally)

Before reporting done, run the dashboard locally and verify the three pages render correctly:

```bash
./ai-core.sh status   # confirm running
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/<project>/item/<some-item>"
playwright-cli screenshot
# repeat for /batch/<batch-id> and /system/worktrees
```

The post-evidence screenshots are S21's job; you only need to spot-check renders work. Note any layout regressions in your report.

## Project Conventions

`dashboard/CLAUDE.md` — Jinja2 + htmx fragments, Tailwind utilities, no inline `<script>`, dark mode requires `dark:` variants.

## TDD Requirement

Frontend changes are template-heavy; write a small set of route-level integration tests in `tests/dashboard/`:

- `tests/dashboard/test_item_overview_impacted_paths.py` — render fragment with a fixture work item, assert globs appear, assert badge text.
- `tests/dashboard/test_batch_held_indicator.py` — seed a `DaemonEvent` of type `item_held_for_scope`, assert the held-indicator HTML appears on the batch fragment.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` — runs `node --check` over `dashboard/static/**/*.js`. If you add new JS, ensure it parses cleanly.

## Test Verification

1. `make test-frontend`
2. `make test-unit` (route tests included)
3. Do NOT report `tests_passed: true` unless all pass.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/item_overview.html",
    "dashboard/templates/fragments/batch_items.html",
    "dashboard/templates/system/worktrees_table.html",
    "dashboard/routers/items.py",
    "dashboard/routers/batches.py",
    "dashboard/routers/worktrees.py",
    "tests/dashboard/test_item_overview_impacted_paths.py",
    "tests/dashboard/test_batch_held_indicator.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Verify the actual worktrees table fragment path — it may not be `worktrees_table.html` exactly"
}
```
