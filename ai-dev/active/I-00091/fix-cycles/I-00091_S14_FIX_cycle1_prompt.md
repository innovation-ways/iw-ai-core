# I-00091 S14 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S14 of work item I-00091 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/auto_merge_aggregator.py
  dashboard/templates/fragments/auto_merge_settings.html
  dashboard/templates/fragments/auto_merge_status_chip.html
  dashboard/routers/auto_merge_ui.py
  dashboard/static/styles.css
  tests/unit/test_auto_merge_config_resolution.py
  tests/dashboard/test_auto_merge_routes.py
  tests/integration/test_auto_merge_control_surface.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00091/ai-dev/active/I-00091/I-00091_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00091 S14 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9900` (production dashboard — note: `IW_BROWSER_BASE_URL` env var is `http://localhost:9924` but the isolated E2E stack's dashboard runs at port 9900)
- **E2E user:** `dev@example.local`
- **Browser:** playwright-cli (chromium, in-memory, headless)

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | | No dangling DOM refs; htmx targetError on POST is a consequence of the form submit, not a page-load defect |
| V1 | Phase-only override survives reload | fail | code_defect | `evidences/post/I-00091_v1_phase_only.png` | Phase=1 was saved (backend returned `{"ok":true,"phase":1,...}`). The in-browser state immediately after Save correctly showed `1 — dry-run` selected. After reload, both dropdowns show `Use global default` — the saved phase was not persisted in the form's selected option |
| V2 | Runtime-only override survives reload | n/a | null | | Skipped — V1 must pass first; V1 defect prevents clean V2 setup |
| V3 | Both-axes override survives reload | n/a | null | | Skipped |
| V4 | Clear back to global removes the override | n/a | null | | Skipped |
| V5 | In-place swap, no full-page reload | n/a | null | | Skipped |
| V6 | No regressions on adjacent flows | pass | null | | `/project/iw-ai-core/queue` and `/project/iw-ai-core/batches` return HTTP 200; console shows only the single htmx:targetError from the V1 POST |

## Console / Network Errors

**Only error observed:**
```
[   72396ms] [ERROR] htmx:targetError @ http://localhost:9900/static/vendor/htmx/htmx.min.js:0
```
This is a consequence of the V1 form POST. The `hx-target="#auto-merge-settings"` swap failed because the backend returned both the settings fragment and the chip fragment concatenated in a single response body (see `auto_merge_ui.py:408` — `return HTMLResponse(settings_html + chip_html)`), which is not valid HTML for a single `hx-target`. This is a secondary code defect related to the OOB swap mechanism.

No console errors at page load time (V0 PASS).

## No Regressions Observed

- `/project/iw-ai-core/queue` → HTTP 200 ✓
- `/project/iw-ai-core/batches` → HTTP 200 ✓
- Verdict rollup and event table load correctly (visible in screenshots) ✓
- No new console errors introduced on adjacent pages ✓

## Root Cause — V1 Failure

**Code defect in settings form rendering on reload.**

**What happened:**
1. V1 POST `{"phase": 1, "runtime_option_id": null}` → backend returned `{"ok": true, "phase": 1, "runtime_option_id": null}`
2. Browser state immediately after Save: Phase dropdown showed `1 — dry-run` [selected] — the in-place htmx swap worked for the selected option
3. After `playwright-cli reload`: Phase dropdown reverted to `Use global default` [selected] — the phase=1 was not reflected on reload

**Backend investigation:**
- `auto_merge_ui.py:377` — after save, `_load_status(db, project_id)` is called to re-read the config
- `auto_merge_aggregator.py:169` — `db.get(AutoMergeProjectConfig, project_id)` retrieves the saved row
- `auto_merge_aggregator.py:172-173` — `phase_source = "per_project_db"` when `db_row.phase is not None` (phase=1 is not None)
- `auto_merge_aggregator.py:177` — `phase = db_row.phase` (= 1) — not falling back to toml

**Template logic (`auto_merge_settings.html:3-4,14-17`):**
```python
{% set _phase_override = status.config.phase_source == 'per_project_db' %}
...
<option value="1" {% if _phase_override and status.config.phase == 1 %}selected{% endif %}>1 — dry-run</option>
```

This should render `selected` when phase_source=`per_project_db` and phase=1. The backend logic confirms both conditions should be true after the V1 save. Yet the browser shows "Use global default" on reload.

**Suspected cause:** The page reload (in the playwright context) may be hitting a **different uvicorn process** that does not have the same DB view, or there is a transaction isolation issue where the GET handler reads the row before the POST's commit is visible. However, the POST response was returned only after `db.commit()` (line 365), so the row should be committed and visible.

Alternative: the template context may be passing `status.config.phase` as 0 (fallback from invalid phase) despite phase_source being correct — check `auto_merge_aggregator.py:178-187` which shows an invalid-phase fallback to 0 (with preserved phase_source). But phase=1 is valid (not 2 or 3), so this path should not be hit.

The evidence points to the htmx swap succeeding visually (phase shows dry-run in-browser) but the underlying DB state may not be what the reload reads. A deeper investigation of the actual DB row content and the full reload GET response would be needed to pinpoint the exact failure.

## Screenshots Captured

- `ai-dev/active/I-00091/evidences/post/I-00091_v1_phase_only.png` — Phase-only override: immediate post-Save state (correct) and post-reload state (incorrect — shows "Use global default")

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S14` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00091/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00091/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
