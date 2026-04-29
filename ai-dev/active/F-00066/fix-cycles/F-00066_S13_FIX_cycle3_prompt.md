# F-00066 S13 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S13 of work item F-00066 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00066 S13 Browser Verification Report

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S13
**Agent**: qv-browser
**Date**: 2026-04-29

## Environment

- **Base URL**: `http://localhost:9943`
- **mmdc availability**: ABSENT (MMDC_ABSENT)
- **E2E User**: `dev@example.local`
- **Project**: iw-ai-core (E2E)

## mmdc Status

`mmdc` binary is **not installed** on this system. Server-side Mermaid/D2 rendering is unavailable.

## LanceDB Index

LanceDB index **exists** for project `iw-ai-core` (confirmed by page showing "Last indexed: just now · 42 files · 100 chunks").

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Mermaid diagram inline | **FAIL** | F-00066_v1_mermaid_inline.png | Stub returns raw DSL text in `code` element, not `pre[data-lang="mermaid"]` block |
| V2 | Download SVG link | **SKIP** | F-00066_v2_download_link.png | mmdc absent — no server-rendered figure to check |
| V3 | Client-side fallback | **FAIL** | F-00066_v3_fallback.png | Stub does not emit proper mermaid fences; client-side renderer cannot process |
| V4 | No regressions | **PASS** | F-00066_v4_no_regressions.png | Module navigation works; chat panel loads correctly |

## Detailed Findings

### V1 & V3 Failure Analysis

The E2E stub (`stub:latest`) is **not configured to emit proper mermaid fences**. When asked questions that should trigger diagram responses:

1. First question: `"Show me a flowchart of how the QA pipeline works"`
   - Response: Raw text `flowchart TD A[Question] --> B{Decision}...` inside a `<code>` element
   - Expected: ` ```mermaid\nflowchart TD A[Question]...\n``` ` fences

2. Second question: `"Draw a class diagram of the project structure"`
   - Response: Raw text `classDiagram class QAEngine...` inside a `<code>` element
   - Expected: ` ```mermaid\nclassDiagram...\n``` ` fences

The stub returns deterministic placeholder text but does not use markdown code fences with `mermaid` language identifier. This prevents both:
- Server-side interception (AC1/AC2) — cannot detect blocks without proper fences
- Client-side fallback (AC3) — `upgradeAllMermaidBlocks` looks for `pre[data-lang="mermaid"]`, not bare `code` elements

### Code Implementation Review

The code implementation appears **correct** based on static analysis:

- `dashboard/routers/code_qa.py:36` — `_FENCED_BLOCK_RE` pattern correctly matches ` ```(mermaid|d2)\n(.*?)``` `
- `dashboard/routers/code_qa.py:39-57` — `_find_new_diagram_blocks()` helper detects completed blocks
- `dashboard/routers/code_qa.py:265-284` — emits `event: image` SSE when render succeeds
- `dashboard/static/chat/stream.js:60-72` — handles `event: image` and calls `onImage`
- `dashboard/static/chat/render.js:462-498` — `onImage` handler creates `<figure class="chat-diagram-figure">` with img and download link
- `dashboard/static/chat/render.js:511-513` — hides server-rendered `<pre>` elements with `data-iw-server-rendered`

## Screenshots

1. `F-00066_v1_mermaid_inline.png` — First question response showing stub code output
2. `F-00066_v2_download_link.png` — (same as V1 due to skip)
3. `F-00066_v3_fallback.png` — Second question showing same stub pattern
4. `F-00066_v4_no_regressions.png` — Module detail page loads correctly

## Conclusion

**Overall Status**: FAIL (ENV_DATA_MISSING)

The verification fails because the **E2E stub is not emitting proper mermaid fences**, not due to code defects. The actual implementation is correctly in place.

- **V1**: FAIL — Stub limitation (not a code defect)
- **V2**: SKIP — mmdc absent (expected)
- **V3**: FAIL — Stub limitation (not a code defect)
- **V4**: PASS — No regressions detected

### Classification

```
ENV_DATA_MISSING: E2E stub does not emit ```mermaid fences — server-side interception and client-side fallback cannot be verified with current stub configuration.
```

### Recommendation

The stub (`stub:latest`) needs to be updated to emit proper markdown mermaid fences when responding to diagram-related questions. The actual F-00066 code implementation appears correct and would work with a properly configured LLM or stub.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: E2E stub does not emit proper mermaid fences — V1 (mermaid inline) and V3 (client-side fallback) cannot be verified. mmdc absent (expected). Code implementation appears correct based on static analysis.

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


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
