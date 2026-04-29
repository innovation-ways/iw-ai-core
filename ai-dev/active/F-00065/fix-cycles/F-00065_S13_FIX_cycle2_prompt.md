# F-00065 S13 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S13 of work item F-00065 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00065 S13 Browser Verification Report

**Step**: S13 (qv-browser)
**Work Item**: F-00065 — Diagram display in code view
**Base URL**: http://localhost:9919

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Architecture diagram visible | **FAIL** | F-00065_v1_arch_diagram.png | `code-arch-diagram` div present but Mermaid not rendered to SVG — raw DSL shown as `<code>` element. DB missing `diagram-architecture` ProjectDoc row. |
| V2 | Module diagram visible | **FAIL** | F-00065_v2_module_diagram.png | Cannot test — no module link reached because architecture section did not navigate to module detail |
| V3 | Empty state for no diagram | **FAIL** | F-00065_v3_empty_state.png | Cannot test |
| V4 | Mermaid blocks render correctly | **FAIL** | F-00065_v4_mermaid_render.png | Cannot test |
| V5 | No regressions | **PASS** | F-00065_v5_no_regressions.png | Pages V1–V4 visited show clean 200, no console errors |

## Issue Summary

**ENV_DATA_MISSING**: The E2E database is missing the `diagram-architecture` and `diagram-module-rag` `ProjectDoc` rows required for V1 and V2.

The fixture file `ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py` exists and exports the correct `seed(db: Session) -> None` function. However, the E2E stack's database was not seeded with these rows before this verification step ran.

### Evidence

- The `/project/iw-ai-core/code` page loads with HTTP 200
- The "Architecture Diagram" heading (`<h3>Architecture Diagram</h3>`) is present in the DOM (line 116 of snapshot), confirming the template branch fires
- The `#code-arch-diagram` div contains `<pre data-lang="mermaid"><code>--- config: layout: elk --- graph TD ...</code></pre>` — the Mermaid initialization script runs but the diagram block inside the `<pre>` is not processed (no `.mermaid` class, no SVG output)
- This is **not** a code defect — the rendering pipeline is intact (`iwRenderMermaid` function exists at `components/libs/mermaid.html:6`). The issue is purely data missing from the DB.

## Root Cause

The `scripts/e2e_seed.py` seed script was not re-run after the fixture file was added to `ai-dev/active/F-00065/e2e_fixtures/`. The E2E stack's DB still has the baseline seed state (no `diagram-architecture` or `diagram-module-rag` rows).

## Screenshots Captured

- `ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png` — Architecture section with unrendered DSL
- `ai-dev/active/F-00065/evidences/post/F-00065_v2_module_diagram.png` — (not captured — V2 not reached)
- `ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png` — (not captured — V3 not reached)
- `ai-dev/active/F-00065/evidences/post/F-00065_v4_mermaid_render.png` — (not captured — V4 not reached)
- `ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png` — Code page loaded cleanly

## Adjacent Flows (V5 — No Regressions)

The code index page loaded cleanly (HTTP 200) with:
- Architecture map text rendered correctly (Components list, Data Flow paragraph)
- Module list loaded via htmx (`/api/projects/iw-ai-core/code/modules`)
- Chat panel visible and interactive
- No console errors on any visited page

## Required Fix

Re-run the e2e seed against the E2E stack DB to inject the fixture rows:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard \
  uv run python scripts/e2e_seed.py
```

Then re-execute S13.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: V1/V2 require diagram ProjectDoc rows — add ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py to e2e seed

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/F-00065/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00065/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00065/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
