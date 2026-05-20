# F-00087 S13 Browser Verification Fix Cycle 2/5

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

# F-00087 S13 Browser Verification Report

**Work Item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S13 (qv-browser)
**Run date**: 2026-05-20
**Base URL**: `http://localhost:9927` (per-worktree E2E compose stack `iw-ai-core-e2e-f00087`)
**E2E user**: `dev@example.local`

## Environment

- Base URL used: http://localhost:9927
- E2E user: dev@example.local
- Compose project: iw-ai-core-e2e-f00087
- Stack status at run time: healthy (e2e-db, e2e-dashboard, e2e-ollama, e2e-daemon-stub all Up)

## Pi Binary Check

```
docker compose -p iw-ai-core-e2e-f00087 exec e2e-dashboard which pi
# → "pi not found in e2e-dashboard"
docker compose -p iw-ai-core-e2e-f00087 exec e2e-dashboard pi --version
# → OCI runtime exec failed: exec: "pi": executable file not found in $PATH
```

The `pi` binary is **not installed** in the E2E stack. This is the root cause of V2 503 and the reason V3..V7 are `n/a`.

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/F-00087_v0_preflight_project_page.png | `/project/iw-ai-core/` renders HTTP 200. No dangling DOM refs. No load-time JS errors. |
| V1 | Runtime dropdown shows OpenCode + Pi | pass | null | evidences/post/F-00087_v1_runtime_dropdown_two_options.png | Create-tab modal Runtime combobox has exactly two options: "OpenCode" (default selected) and "Pi". CR-00062 seed rows are in place. |
| V2 | Model list per runtime — dropdown UX | pass | null | evidences/post/F-00087_v2_model_list_per_runtime.png | Selecting "Pi" repopulates Model dropdown with `pi/minimax/MiniMax-M2.7` (selected) and `pi/openai/gpt-5.3-codex`. Switching back to OpenCode re-fetches the full OpenCode model list. No cross-runtime model leakage observed. |
| V2b | Pi tab creation POST returns 503 | fail | env_data_missing | evidences/post/F-00087_v2_pi_503_runtime_unavailable.png | ENV_DATA_MISSING: POST /api/chat/tabs with Pi runtime returns 503; UI shows alert "Runtime unavailable; try again later." The `pi` binary is absent from the E2E stack container (`which pi` → not found). This is a stack configuration gap, not a code defect. |
| V3 | Mixed tabs created | n/a | env_data_missing | — | ENV_DATA_MISSING: pi binary not present in E2E stack; Pi tab creation returns 503. Cannot create Pi tabs to populate mixed tab strip. |
| V4 | Three independent streams | n/a | env_data_missing | — | ENV_DATA_MISSING: pi binary not present in E2E stack; Pi tab creation returns 503. Cannot exercise Pi streaming. |
| V5 | Pi abort isolation | n/a | env_data_missing | — | ENV_DATA_MISSING: pi binary not present in E2E stack; Pi tab never enters streaming state. |
| V6 | Pi approval modal | n/a | env_data_missing | — | ENV_DATA_MISSING: pi binary not present in E2E stack; extension_ui_request path requires Pi runtime pipeline. Permitted as n/a per spec — S05 integration tests cover the approval flow via stub. |
| V7 | Reload persistence + Pi respawn | n/a | env_data_missing | — | ENV_DATA_MISSING: pi binary not present in E2E stack; Pi session cannot be established to test respawn. |
| V8 | No regressions (OpenCode tab creation) | pass | null | evidences/post/F-00087_v8_opencode_tab_created_no_regression.png | OpenCode tab creation succeeds (HTTP 200). New tab appears in tab strip with correct model badge (anthropic/claude-opus-4-7). F-00086 multi-tab UI is intact. Ctrl+/ toggle works. No console errors on page load. |

**Overall status**: FAIL  
**Overall failure class**: ENV_DATA_MISSING

## Console / Network Errors

- `[ERROR] Failed to load resource: the server responded with a status of 503 (Service Unavailable) @ http://localhost:9927/api/chat/tabs:0` — logged when Pi tab creation was attempted (V2b). This is the expected/classified ENV_DATA_MISSING error, not a code defect.
- No errors observed on page load or during V0, V1, V2 (dropdown UX), V8.

## No Regressions

- `/project/iw-ai-core/` renders cleanly (HTTP 200, no console errors on load).
- AI Assistant panel expands/collapses via the "Expand AI Assistant panel (Ctrl+/)" button.
- The tab strip (F-00086 feature) is intact — seeded "Tab O" present, new OpenCode tab created successfully.
- Create-tab modal opens, renders Project/Runtime/Model/Title fields correctly.
- OpenCode tab creation (POST /api/chat/tabs) succeeds and the new tab appears selected.
- Per-tab model badge above composer updates correctly to reflect the active tab's model.

## Screenshots captured

- `ai-dev/active/F-00087/evidences/post/F-00087_v0_preflight_project_page.png`
- `ai-dev/active/F-00087/evidences/post/F-00087_v1_runtime_dropdown_two_options.png`
- `ai-dev/active/F-00087/evidences/post/F-00087_v2_model_list_per_runtime.png`
- `ai-dev/active/F-00087/evidences/post/F-00087_v2_pi_503_runtime_unavailable.png`
- `ai-dev/active/F-00087/evidences/post/F-00087_v8_opencode_tab_created_no_regression.png`

## Root cause

The `pi` binary is not installed in the E2E stack's `e2e-dashboard` container. The tab service's `PiRuntime.start()` calls `subprocess.Popen(["pi", ...])` (or equivalent), which fails with a missing executable and propagates as a 503 "Runtime unavailable" response to the client. All Pi-dependent verifications (V3..V7) cannot be exercised until the `pi` binary is present in the container image.

**What passed**: The frontend correctly shows both runtimes in the dropdown (V1), correctly re-fetches model lists per runtime (V2), and correctly displays the 503 error message as "Runtime unavailable; try again later." in the modal. OpenCode tab creation is unaffected (V8).

**Operator action required**: Install the `pi` binary in the E2E stack container image (or add it to the Dockerfile/compose service definition) and re-run S13 browser verification. The S05 integration tests use `tests/integration/stubs/_pi_stub.py` to exercise the runtime pipeline in isolation, so the stub covers the code paths that cannot be reached via the browser without the binary.


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: pi binary not present in E2E stack; Pi tab creation returns 503 'Runtime unavailable'. V1/V8 pass via UI evidence + CR-00062 seeded options; V3..V7 cannot be exercised without pi runtime; V6 already permitted as n/a per spec. S05 integration tests cover the runtime behaviors.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/F-00087/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

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
