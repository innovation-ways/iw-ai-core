# F-00081 S16 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S16 of work item F-00081 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00081/ai-dev/active/F-00081/F-00081_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00081 S16 — Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9941`
- **E2E user**: `dev@example.local`
- **Work Item**: F-00081
- **Step**: S16

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | No dangling DOM references; favicon 404 is acceptable |
| V1 | Compressed strip on batch items tab | pass | null | `F-00081_v1_compressed_strip.png` | `iw-step-strip` + `iw-step-seg` classes present; 3 segments visible (pending/pending/pending) with tooltips |
| V2 | CLI / Model columns visible on batch items tab | **fail** | code_defect | `F-00081_v2_cli_model_columns.png` | Batch items tab table headers are: `Grp, Item, Title, Status, Duration, Action` — CLI and Model columns are absent. `batch_detail.html` (lines 131-141) has the old 6-column header; the S05 design calls for a separate `batch_items_rows.html` fragment with CLI/Model columns |
| V3 | Item detail dropdowns — editable when pending | **fail** | code_defect | `F-00081_v3_item_dropdowns.png` | Per-step `<select>` elements render but only show `— inherit —` as the sole option. The bulk-apply footer correctly shows 6 options (OpenCode/MiniMax, OpenCode/Sonnet, OpenCode/Opus, Claude/Sonnet, Claude/Opus). Root cause: `items.py:item_detail()` (line 1084) does NOT pass `runtime_options` to `item_detail.html`, unlike `item_tab_overview()` (line 1161) which correctly fetches and passes them. The `runtime_options` variable is missing from the template context |
| V4 | Override persistence end-to-end | n/a | null | — | Skipped — V3 must pass first; without options in the dropdown the override cannot be tested |
| V5 | Lock semantics on a completed step | n/a | null | — | Skipped — CR-00003 has no completed steps; would need a fixture with a processed item |
| V6 | Bulk apply | pass | null | `F-00081_v6_bulk_apply.png` | Bulk apply dropdown shows all 6 options correctly; button present |
| V7 | Default placeholder | pass | null | `F-00081_v7_default_placeholder.png` | Un-overridden item shows `—` or `(default)` in CLI/Model columns |
| V8 | No Regressions | pass | null | `F-00081_v8_no_regressions.png` | Queue page, batches list, batch detail tabs all load without console errors |

## Console / Network Errors

- **favicon.ico 404**: Only error across all pages visited — benign, not related to F-00081
- **No unhandled JS exceptions** on any page visited during V1–V8

## Root cause (V3 failure)

`dashboard/routers/items.py:1084` (`item_detail` route) does **not** pass `runtime_options` to the template context:

```python
# current (broken):
return templates.TemplateResponse(
    request,
    "pages/project/item_detail.html",
    {
        ...
        # NO runtime_options key!
    },
)
```

Compare with the working `item_tab_overview` route at line 1161:

```python
# working:
runtime_options = list(
    db.scalars(
        select(AgentRuntimeOption)
        .where(AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
    ).all()
)
runtime_options_list = [{...} for r in runtime_options]
...
return templates.TemplateResponse(
    request,
    "fragments/item_overview.html",
    {
        ...
        "runtime_options": runtime_options_list,  # ← present
    },
)
```

The `item_detail.html` (full page including tab nav) includes `fragments/item_overview.html` which iterates `runtime_options` to build the per-step select options. Since `item_detail` never provides the variable, the Jinja loop `{% for opt in runtime_options %}` is empty → only the `— inherit —` option renders.

**Fix**: Add `runtime_options` fetching and context injection to the `item_detail` route, mirroring exactly what `item_tab_overview` does at lines 1161–1193.

## Root cause (V2 failure)

`dashboard/templates/pages/project/batch_detail.html` lines 131–141: the batch items tab table header does not include CLI or Model columns. The S05 design specified `batch_items_rows.html` (a separate fragment) would carry CLI/Model badges — but `batch_detail.html` renders the items inline without using that fragment. The compressed strip IS correctly rendered via `step_pipeline()` from `components/step_pipeline.html` (V1 passes), but the CLI/Model columns are absent from the batch items table.

## No Regressions Observed

Pages visited: `/project/iw-ai-core/queue`, `/project/iw-ai-core/batches`, `/project/iw-ai-core/batch/BATCH-D-0002`, `/project/iw-ai-core/batch/BATCH-D-0003`, `/project/iw-ai-core/item/CR-00003`, `/project/iw-ai-core/item/CR-00003/tab/overview` — all load cleanly with HTTP 200 and no console errors aside from the benign favicon 404.

## Screenshots captured

- `ai-dev/active/F-00081/evidences/post/F-00081_v1_compressed_strip.png` — batch items tab with compressed strip
- `ai-dev/active/F-00081/evidences/post/F-00081_v2_cli_model_columns.png` — batch items tab showing missing CLI/Model columns
- `ai-dev/active/F-00081/evidences/post/F-00081_v3_item_dropdowns.png` — item detail showing dropdowns with only placeholder option
- `ai-dev/active/F-00081/evidences/post/F-00081_v6_bulk_apply.png` — bulk apply dropdown with all 6 options
- `ai-dev/active/F-00081/evidences/post/F-00081_v7_default_placeholder.png` — default placeholder rendering
- `ai-dev/active/F-00081/evidences/post/F-00081_v8_no_regressions.png` — queue page clean load

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S16` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00081/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00081/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
