# CR-00057 S15 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S15 of work item CR-00057 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/daemon/project_registry.py
  dashboard/routers/chat.py
  dashboard/static/chat_assistant/chat.js
  projects.toml
  CLAUDE.md
  docs/IW_AI_Core_AI_Assistant_Models.md
  tests/unit/daemon/test_project_registry_ai_assistant.py
  tests/dashboard/test_chat_router.py
  tests/integration/test_project_registry_ai_assistant.py
  tests/integration/test_chat_config_allowlist_intersection.py
  tests/integration/test_chat_endpoint_session_lifecycle.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00057/ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00057 S15 Browser Verification Report

## Environment
- Base URL used: http://localhost:9936
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/CR-00057_v0_preflight_sanity.png | Checked routes: `/project/iw-ai-core/`, `/system/status`, `/project/iw-ai-core/code`, `/project/iw-ai-core/docs`, `/project/iw-ai-core/jobs`. No dangling DOM refs found. |
| V1 | Curated 5-model allowlist on iw-ai-core | fail | env_data_missing | evidences/post/CR-00057_v1_dropdown_filtered.png | Dropdown contains only `stub/echo` (selected), not the curated 5-model allowlist. |
| V2 | /api/chat/config returns curated list | fail | env_data_missing | evidences/post/CR-00057_v2_api_response.json | API returned `models=["stub/echo"]`, `default_model="stub/echo"`, plus `project_directory`; does not match expected curated response. |
| V3 | Fail-open on system page | fail | env_data_missing | evidences/post/CR-00057_v3_fail_open_system_page.png | System page dropdown also shows only `stub/echo` (not expanded fail-open set). |
| V4 | Project switch refreshes dropdown | n/a | null | evidences/post/CR-00057_v4_project_switch.png | ENV_DATA_MISSING: only one project (`iw-ai-core`) is present in seed, so no second project state exists to verify project-switch refresh behavior. |
| V5 | Prompt round-trip with default model | fail | env_data_missing | evidences/post/CR-00057_v5_prompt_roundtrip.png | Prompt round-trip succeeded, but only with `stub/echo`; expected curated default `anthropic/claude-opus-4-7` not available due missing allowlist seed/config sync. |
| V6 | No regressions across project tabs | pass | null | evidences/post/CR-00057_v6_no_regressions.png | Visited Code/Docs/Jobs tabs and confirmed AI Assistant panel remains mounted/expandable. |

## Console / Network Errors
None observed in `.playwright-cli/console-*.log` during visited-page checks.

## No Regressions
Visited `/project/iw-ai-core/code`, `/project/iw-ai-core/docs`, and `/project/iw-ai-core/jobs`. No unhandled JS/HTMX errors observed. Chat panel remained present and functional across tab navigation.

## Screenshots captured
- ai-dev/active/CR-00057/evidences/post/CR-00057_v0_preflight_sanity.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v1_dropdown_filtered.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v2_api_response.json
- ai-dev/active/CR-00057/evidences/post/CR-00057_v3_fail_open_system_page.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v4_project_switch.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v5_prompt_roundtrip.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v6_no_regressions.png

## Root cause (on failure only)
The E2E runtime is serving fallback chat config (`stub/echo`) instead of the per-project allowlist from `projects.toml`, so both project-scoped and system-page model lists cannot match the CR acceptance expectations. Attempted registry sync via `docker compose -p "$COMPOSE_PROJECT_NAME" exec app ...` failed because service `app` is not running in this stack context, preventing in-container sync remediation during this run.


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: chat config seed/sync missing curated ai_assistant allowlist for iw-ai-core (API and dropdown show stub/echo only)

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/CR-00057/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S15` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00057/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00057/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
