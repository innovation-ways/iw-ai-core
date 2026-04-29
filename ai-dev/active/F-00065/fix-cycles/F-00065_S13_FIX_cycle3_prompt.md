# F-00065 S13 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S13 of work item F-00065 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00065 S13 Browser Verification Report

**Work Item**: F-00065 — Diagram display in code view
**Step**: S13
**Agent**: qv-browser
**Base URL**: `http://localhost:9919`
**E2E Credentials**: `dev@example.local` / `DevPass2026!`

## Summary

**Overall Status: FAIL**

The E2E stack was started from this worktree's source code and the dashboard UI loaded correctly. However, V1 and V2 both failed because the diagram `ProjectDoc` rows seeded by the fixture file were not present in the E2E database. V3, V4, and V5 passed.

## Environment Data Gap

The fixture file `ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py` exists and declares the correct `seed()` function. The root cause is that the per-item fixture discovery mechanism (documented in `scripts/e2e_seed.py`) was not triggered — the diagram rows were never inserted into the E2E DB.

This is classified as **ENV_DATA_MISSING** per the step instructions, not a code defect. The page renders cleanly with HTTP 200, the architecture diagram heading is visible, the empty state appears correctly for modules without diagrams, and no console errors were observed.

---

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Architecture diagram visible (AC2) | **FAIL** | `F-00065_v1_arch_diagram.png` | Heading "Architecture Diagram" rendered (HTTP 200). The `id="code-arch-diagram"` element is present. However, the Mermaid DSL is shown as raw escaped text inside a `<code>` element rather than rendered as an SVG. Root cause: `arch_diagram_dsl` from the DB is `None` because the fixture rows were never seeded. |
| V2 | Module diagram visible in detail view (AC1) | **FAIL** | `F-00065_v3_empty_state.png` | Clicked on `orch/daemon/` module. The module detail fragment loads with doc content and the "No diagram yet — run 'Generate Code Map' to create one." empty-state message is shown. The diagram slot renders the empty-state (class `code-diagram-empty`), confirming the feature works correctly — but `diagram-module-orch-daemon` row is absent from DB. |
| V3 | Empty state for module without diagram (AC3) | **PASS** | `F-00065_v3_empty_state.png` | The empty state message "No diagram yet — run 'Generate Code Map' to create one." appears correctly inside a `<div class="code-diagram-empty">`. No error toast, no broken fragment. |
| V4 | Mermaid blocks in architecture text render correctly (AC4) | **PASS** | `F-00065_v4_mermaid_render.png` | The architecture map content does NOT contain a ` ```mermaid ``` ` fenced block (F-00064's `generate_level1` output is plain markdown without a Mermaid block). So V4 is not applicable and is marked pass with note: "No Mermaid block present in architecture-map doc content — skipped." |
| V5 | No regressions | **PASS** | `F-00065_v5_no_regressions.png` | Project dashboard page loads correctly. All navigation links work. Module detail shows correct doc content, generating states, and Q&A panel intact. No console errors observed on any visited page. |

---

## Root Cause: ENV_DATA_MISSING

The fixture file `ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py` was correctly authored with an idempotent `seed()` function that inserts:
1. `ProjectDoc` with `doc_id="diagram-architecture"` (architecture diagram)
2. `ProjectDoc` with `doc_id="diagram-module-rag"` (module diagram for rag module)

However, the E2E stack's database was not seeded with these rows. The page renders correctly in all other respects — empty states work, the UI is not broken — but the diagram DSL is `None` for both the architecture panel and the module diagram slot.

The `code_ui.py:132-134` looks up:
```python
arch_diagram_doc = DocService(db).get_doc(project_id, "diagram-architecture")
if arch_diagram_doc:
    arch_diagram_dsl = arch_diagram_doc.content
```

Since the fixture was not applied, `arch_diagram_doc` is `None` → `arch_diagram_dsl` is `None` → the diagram panel still renders (due to the `{% if arch_diagram_dsl %}` guard in `code_architecture_view.html:43-45`) but with no content, showing only the raw text in the accessibility tree.

**Fix**: The per-item fixture script must be executed against the E2E DB before running S13. The fixture discovery mechanism is described in `scripts/e2e_seed.py` but apparently was not invoked for this worktree's E2E stack.

---

## Screenshots Captured

| File | Verification |
|------|-------------|
| `ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png` | V1 — Architecture diagram section on code index page |
| `ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png` | V2 + V3 — Module detail with empty diagram state |
| `ai-dev/active/F-00065/evidences/post/F-00065_v4_mermaid_render.png` | V4 — Code index page showing architecture map (no mermaid block present) |
| `ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png` | V5 — Project dashboard for no-regression check |

---

## Console Errors

None observed across all visited pages (code index, module detail, project dashboard).

---

## Adjacent Flows Tested (V5 — No Regressions)

- Project dashboard (`/project/iw-ai-core/`) loads with service health, active batches, git status sections intact
- Code index page (`/project/iw-ai-core/code`) loads with correct heading, job status banner, architecture map text, module cards, and chat panel
- Module detail fragment (clicking `orch/daemon/`) renders: breadcrumb, module heading, doc content, empty diagram slot, regeneration button — all intact
- Navigation sidebar remains functional throughout

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: V1/V2 require diagram ProjectDoc rows — add ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py and ensure per-item fixture is executed in E2E stack

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


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
