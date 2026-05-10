# I-00074 S13 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S13 of work item I-00074 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00074/ai-dev/active/I-00074/I-00074_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00074 S13 Browser Verification Report

## Environment
- Base URL used: http://localhost:9937
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/I-00074-S13-doc-page.png | Doc detail page loaded cleanly; no console errors at load |
| V1 | PDF download | FAIL | env_data_missing | evidences/post/I-00074-S13-pdf-download.png | Endpoint returns 503 with JSON `{"error":"PDF generation unavailable","detail":"Chromium binary not found — check _PLAYWRIGHT_CHROME path"}` — Chromium is not installed in the isolated E2E container, not a code defect |
| V2 | No regressions | PASS | null | evidences/post/I-00074-S13-no-regressions.png | Doc detail page renders correctly; Mermaid diagrams visible in HTML view |

## Console / Network Errors
- V1 PDF route: `Failed to load resource: the server responded with a status of 503 (Service Unavailable)` — expected behavior when Chromium binary is absent
- No other console errors observed during navigation

## Root Cause

**V1 — ENV_DATA_MISSING (Chromium binary not present in E2E container):**

The `_PLAYWRIGHT_CHROME` constant in `dashboard/utils/markdown.py:34-36` resolves to:
```python
PLAYWRIGHT_CHROME = Path.home() / ".cache" / "ms-playwright" / "chromium-1217" / "chrome-linux64" / "chrome"
```

Inside the isolated E2E container, `Path.home()` resolves to `/app`, but Chromium was only installed on the **host** machine at `/home/sergiog/.cache/ms-playwright/`. The container's `/app/.cache/ms-playwright/` directory does not exist.

When `render_pdf_chromium()` is called, `_PLAYWRIGHT_CHROME.exists()` returns `False`, the function logs a warning and returns `None`, and the PDF route at `dashboard/routers/docs.py:216-223` returns a clean 503 JSON response — the correct graceful degradation behavior.

**Verification:**
- The Python function works correctly on the host: `uv run python -c "from dashboard.utils.markdown import render_pdf_chromium; print(len(render_pdf_chromium('<h1>Test</h1>')))"` → `14145` PDF bytes with valid `\x25\x50\x44\x46` header
- The code path from route → `render_pdf_chromium()` → 503 response is intact
- The only issue is that the E2E container lacks the Chromium binary as a runtime dependency

**Fix required:** The E2E container image must have Chromium installed at the expected path, or `_PLAYWRIGHT_CHROME` must be configurable via environment variable so the container can specify a path that exists within its own filesystem.

V2 passes because the HTML view renders from pre-rendered content without requiring Chromium.

## No Regressions
- Projects page → project home → docs catalog → doc detail: all navigation paths load correctly
- HTML tab on doc detail page shows the architecture document with Mermaid diagrams visible
- Download PDF link present and correctly targets the `/pdf` route
- Tab list (Markdown / HTML / PDF / IDE) all present and clickable

## Screenshots captured
- ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
- ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
- ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: Chromium binary not present in E2E container at expected path ~/.cache/ms-playwright/chromium-1217/ — container has /app/.cache/ms-playwright/ which is empty; code path is correct (render_pdf_chromium returns None gracefully, route returns clean 503); fix requires Chromium to be installed in the E2E container or _PLAYWRIGHT_CHROME to be environment-configurable

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00074/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S13` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00074/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00074/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
