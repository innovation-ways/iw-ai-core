# F-00066 S13 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S13 of work item F-00066 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00066 S13 Browser Verification Report

## Environment

- **Base URL Used**: `http://localhost:9943`
- **mmdc availability**: ABSENT (MMDC_ABSENT)
- **E2E Project**: `iw-ai-core` (IW AI Core (E2E))
- **User**: `dev@example.local`

## mmdc Status

`mmdc` is not installed on this system. Server-side Mermaid rendering via `render_mermaid()` is not available. The client-side fallback path (via `upgradeAllMermaidBlocks`) is the only rendering option, but it requires properly formatted mermaid fenced code blocks (`<pre data-lang="mermaid">`) to be present in the response.

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Mermaid diagram inline | FAIL | F-00066_v1_mermaid_inline.png | E2E stub returns mermaid DSL as plain text in `<code>` element, not as `<pre data-lang="mermaid">`. No `image` SSE event fired. Server-side rendering (mmdc) unavailable; client-side fallback cannot find block to upgrade. |
| V2 | Download SVG link | FAIL | — | Skipped — no server-rendered figure was produced (V1 failed) |
| V3 | Client-side fallback | FAIL | — | E2E stub does not emit `<pre data-lang="mermaid">` blocks; `upgradeAllMermaidBlocks` has nothing to upgrade. |
| V4 | No regressions | PASS | F-00066_v4_no_regressions.png | Module detail page loads correctly; chat streams text responses; no console errors observed. |

## Root Cause Analysis

The E2E daemon stub (`e2e-daemon-stub`) returns a deterministic stub response for QA questions. When asked about diagrams, the stub returns the mermaid DSL as plain text embedded in a `<code>` element:

```
code [ref=e197]: "flowchart TD A[Question] --> B{Decision} B -->|Yes| C[Step 1] B -->|No| D[Step 2] C --> E[Result] D --> E"
```

For proper diagram rendering, the response should either:
1. **Server-side (mmdc)**: Emit an `image` SSE event containing base64-encoded SVG, which `onImage` handler uses to insert a `<figure class="chat-diagram-figure">` with `<img data:image/svg+xml;base64,...>` and a "Download SVG" link
2. **Client-side fallback**: Emit a `<pre data-lang="mermaid">` block that `upgradeAllMermaidBlocks` can detect and render via the browser's mermaid.js

The stub does neither — it returns raw DSL text without proper formatting, so:
- Server-side rendering cannot find `<pre data-lang="mermaid">` to replace
- Client-side fallback cannot find `<pre data-lang="mermaid">` to upgrade

This is an **E2E stub limitation**, not a code defect. When a real LLM (Ollama) is connected and returns properly formatted mermaid fenced code blocks, both rendering paths should work assuming mmdc is installed for server-side rendering.

## Screenshots

1. `F-00066_v1_mermaid_inline.png` — Shows stub response with raw mermaid DSL visible as text in chat
2. `F-00066_v4_no_regressions.png` — Shows module detail page loading correctly after stub response

## Console Errors

No console errors were observed during V1–V4 verification.

## Recommendation

To complete V1–V3 verification:
1. Install `mmdc` for server-side rendering: `npm install -g @mermaid-js/mermaid-cli` (or appropriate package)
2. OR update the E2E daemon stub to emit properly formatted mermaid fenced code blocks (`<pre data-lang="mermaid">`) so client-side fallback can render them

The V4 (no regressions) check passes, confirming the feature doesn't break existing functionality.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: mmdc absent AND E2E stub returns mermaid DSL as plain text instead of fenced code blocks — server-side rendering and client-side fallback both unavailable. V4 (no regressions) passes.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/F-00066/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00066/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00066/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
