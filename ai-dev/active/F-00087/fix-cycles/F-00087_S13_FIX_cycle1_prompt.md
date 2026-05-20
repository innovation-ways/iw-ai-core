# F-00087 S13 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S13 of work item F-00087 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/chat/__init__.py
  orch/chat/pi/**
  orch/chat/tab_service.py
  orch/skills/sync_agents.py
  orch/cli/skills_commands.py
  dashboard/routers/chat.py
  dashboard/app.py
  dashboard/templates/chat_assistant/create_tab_modal.html
  dashboard/static/chat_assistant/chat.js
  dashboard/static/chat_assistant/chat.css
  dashboard/static/styles.css
  agents/pi/extensions/**
  tests/unit/chat/test_pi_*.py
  tests/unit/chat/test_sync_agents_extensions.py
  tests/unit/chat/test_tab_service_allowlist.py
  tests/integration/test_chat_pi_*.py
  tests/integration/stubs/**
  ai-dev/active/F-00087/**
  ai-dev/archive/F-00087/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00087/ai-dev/active/F-00087/F-00087_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00087 S13 — qv-browser (lifecycle summary)

**Status**: FAIL — code_defect
**Base URL**: `http://localhost:9927` (per-worktree e2e stack)

## Summary

- V0..V3 PASS — runtime dropdown shows OpenCode + Pi, model list switches per runtime, 1 OpenCode + 2 Pi tabs created with correct per-tab models.
- **V4 FAIL** — Pi prompts are accepted (HTTP 204) and Pi stub subprocesses run in the dashboard container, but no streaming agent response is delivered to the UI. User echo appears (frontend-optimistic), then `Session idle.`; no `message.part.added` payload reaches the transcript.
- V5/V6/V7 blocked by V4.
- V8 partial — no regressions observed in adjacent UI flows; OpenCode end-to-end streaming was not exercised in this session due to time focused on the Pi defect.

## Defect classification

`code_defect` in the Pi end-to-end event pipeline (JSONL reader → normalizer → broker → SSE → frontend). Spec is correct, environment is correct (pi binary + stub running, ports open, 204/200 responses), but normalized Pi events are not surfacing in the UI. S05 integration tests pass because they bypass the dashboard SSE stack.

## Files / evidence

- Detailed report: `ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md`
- Pre screenshot: `ai-dev/active/F-00087/evidences/pre/F-00087-create-tab-modal-with-pi.png`
- Post screenshots:
  - `ai-dev/active/F-00087/evidences/post/F-00087_v1_runtime_dropdown_two_options.png`
  - `ai-dev/active/F-00087/evidences/post/F-00087_v2_model_list_per_runtime.png`
  - `ai-dev/active/F-00087/evidences/post/F-00087_v3_mixed_tabs_created.png`
  - `ai-dev/active/F-00087/evidences/post/F-00087_v4_pi_no_stream_response.png`

## Likely-implicated files

- `orch/chat/pi/pi_jsonl_reader.py`
- `orch/chat/pi/event_normalizer.py`
- `orch/chat/pi/pi_runtime.py`
- `dashboard/routers/chat.py`
- `dashboard/static/chat_assistant/chat.js`


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S13` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00087/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00087/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
