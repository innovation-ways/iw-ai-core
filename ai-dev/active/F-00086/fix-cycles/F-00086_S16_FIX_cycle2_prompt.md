# F-00086 S16 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S16 of work item F-00086 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/chat/__init__.py
  orch/chat/runtime_base.py
  orch/chat/opencode/**
  orch/chat/tab_service.py
  orch/chat/migration_helpers.py
  orch/db/models.py
  orch/db/migrations/versions/**
  dashboard/routers/chat.py
  dashboard/app.py
  dashboard/templates/chat_assistant/**
  dashboard/static/chat_assistant/**
  dashboard/static/styles.css
  tests/unit/chat/**
  tests/dashboard/test_chat_*.py
  tests/integration/test_chat_*.py
  ai-dev/active/F-00086/**
  ai-dev/archive/F-00086/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00086/ai-dev/active/F-00086/F-00086_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00086 S16 Browser Verification Report

## Environment
- Base URL used: http://localhost:9931
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/F-00086_v0_preflight_sanity.png | Checked `/project/iw-ai-core/`, `/project/iw-ai-core/queue`, `/project/iw-ai-core/code` for dangling fragment refs; none found. |
| V1 | Tab strip renders and "+" opens create-tab modal | pass | null | evidences/post/F-00086_v1_create_tab_modal.png | Tab strip present, + button present, empty-state shown, modal includes Project/Runtime/Model/Title fields. |
| V2 | Create two tabs with different models and verify per-tab independence | fail | code_defect | evidences/post/F-00086_v2_two_tabs_independent.png | Two tabs created and model badges differ per-tab, but Tab A prompt did not show streaming/assistant output within the required 10s window. |
| V3 | Tab persistence across page reload | pass | null | evidences/post/F-00086_v3_tabs_persist_after_reload.png | Used `playwright-cli reload` (state-safe). Tab A/Tab B and prior prompts persisted after reload. |
| V4 | Close a tab and reopen from recent-closed menu | pass | null | evidences/post/F-00086_v4_reopen_from_recent_closed.png | Closed Tab A, reopened from Recently Closed, tab and history restored. |
| V5 | Per-tab abort | fail | code_defect | evidences/post/F-00086_v5_per_tab_abort.png | No visible per-tab Abort control/aborted indicator during test flow; could not verify tab-scoped abort semantics. |
| V6 | Runtime dropdown stub — only OpenCode | pass | null | evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png | Runtime selector showed only `OpenCode` option. |
| V7 | No regressions | pass | null | evidences/post/F-00086_v7_no_regressions.png | Dashboard, Queue, and Code routes render; assistant panel collapse/expand still works. |

## Console / Network Errors
None observed (no `.playwright-cli/console-*.log` emitted during run).

## No Regressions
- `/project/iw-ai-core/` rendered (HTTP 200 UI path).
- `/project/iw-ai-core/queue` rendered.
- `/project/iw-ai-core/code` rendered.
- AI Assistant panel toggle (collapse/expand) remained functional.

## Screenshots captured
- ai-dev/active/F-00086/evidences/post/F-00086_v0_preflight_sanity.png
- ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png
- ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png
- ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png
- ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png
- ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png
- ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png
- ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png

## Root cause (on failure only)
`dashboard` AI assistant multi-tab behavior appears partially non-functional under this E2E runtime: in V2, Tab A did not produce streaming output in the required window despite successful prompt submission, and in V5 no tab-scoped abort control/aborted-state indicator was available to execute the specified abort validation. This is classified as **CODE_DEFECT** because required UI/runtime behavior was missing during clean page renders.


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S16` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00086/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00086/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
