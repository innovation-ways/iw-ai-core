# F-00091 S19 Browser Verification Fix Cycle 3/5

The end-to-end browser verification for step S19 of work item F-00091 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/templates/chat_assistant/panel.html
  dashboard/templates/chat_assistant/composer.html
  dashboard/static/chat_assistant/chat.js
  dashboard/static/chat_assistant/chat.css
  dashboard/static/styles.css
  dashboard/routers/chat.py
  dashboard/routers/projects.py
  orch/chat/context_usage.py
  orch/db/migrations/versions/**
  tests/dashboard/**
  tests/integration/**
  tests/unit/**

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00091/**
  ai-dev/archive/F-00091/**
  ai-dev/work/F-00091/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/ai-dev/active/F-00091/F-00091_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00091 S19 Browser Verification Report

- Base URL: `http://localhost:9949`
- Work item: `F-00091`
- Step: `S19`

## Verification Results

| Check | Status | Summary |
|---|---|---|
| V0 | PASS | Referenced pages loaded; no dangling ref/ID failures observed during navigation checks. |
| V1 | PASS | Assistant panel shows project selector with populated options; selected project on `/` matches alphabetical first from `GET /api/chat/projects` (`innoforge`). |
| V2 | PASS | Switching selector to `iw-ai-core` changed tab strip content (from single `B-Only-Tab` to `A-*` tabs) and selector value updated. |
| V3 | PASS | Navigating URL to project page (`/project/innoforge/`) and then `/system/status` did not change assistant project selection (`iw-ai-core`) or its tab strip. |
| V4 | PASS | Active tab `A-Unknown-Context` restored after switching projects and remained active after reload. |
| V5 | PASS (unknown branch) | Context usage bar stayed visible with `—%` and unknown tooltip text (`Context window usage unknown...`). Known branch not exercisable from seed. |
| V6 | FAIL | Regression found: clicking `+ New chat tab` triggered console error and did not create tab (`400` on `/api/chat/tabs`). |

## Issues Found

1. **CODE_DEFECT**: `+ New chat tab` action caused backend 400 and console error.
   - Evidence: `.playwright-cli/console-2026-05-28T00-57-03-457Z.log:1`
   - Message: `Failed to load resource: the server responded with a status of 400 (Bad Request) @ http://localhost:9949/api/chat/tabs:0`

## Screenshots

- `ai-dev/active/F-00091/evidences/post/F-00091_v1_selector_visible.png`
- `ai-dev/active/F-00091/evidences/post/F-00091_v2_after_dropdown_switch.png`
- `ai-dev/active/F-00091/evidences/post/F-00091_v3_url_navigation_no_swap.png`
- `ai-dev/active/F-00091/evidences/post/F-00091_v4_tab_restored_after_reload.png`
- `ai-dev/active/F-00091/evidences/post/F-00091_v5_progress_bar.png`
- `ai-dev/active/F-00091/evidences/post/F-00091_v6_no_regressions.png`

## No regressions observed

- Tab settings panel opens and shows Title/Runtime/Model controls.
- Composer still shows Clear / Abort / Send controls.
- Skills tray opens and lists skills/commands.

## Regressions observed

- `+ New chat tab` failed (400), so V6 overall fails.
- Console error present during V6 interaction.


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S19` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00091/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00091/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
