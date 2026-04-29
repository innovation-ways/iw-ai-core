# F-00065 S13 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S13 of work item F-00065 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00065 S13 Browser Verification Report

**Step**: S13 (qv-browser)
**Work Item**: F-00065 — Diagram display in code view
**Base URL**: `http://localhost:9919`
**E2E Stack**: `iw-ai-core-e2e-f00065`

---

## Results Summary

| ID | Verification | Status | Screenshot | Notes |
|----|-------------|--------|------------|-------|
| V1 | Architecture diagram visible on code index page | **FAIL** | F-00065_v1_arch_diagram.png | `<pre data-lang="mermaid">` renders as raw DSL text, not SVG. `window.iwChat.upgradeAllMermaidBlocks` is undefined — `mermaid.js` (chat library) is not loaded on the code page |
| V2 | Module diagram visible in module detail view | **FAIL** | — | No module has `diagram-module-<slug>` seeded. Available modules are `orch-daemon` and `dashboard`; fixture only seeds `diagram-module-rag` |
| V3 | Empty state for module without diagram | **PASS** | F-00065_v3_empty_state.png | "No diagram yet" message displayed correctly for `orch-daemon` which has no diagram doc |
| V4 | Mermaid blocks in architecture text render correctly | **SKIP** | — | Architecture map content has no ` ```mermaid ``` ` fenced block (F-00064 generated plain text only) |
| V5 | No regressions | **PASS** | F-00065_v5_no_regressions.png | Existing module doc, chat panel, and module navigation all intact |

---

## Screenshots Captured

- `ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png` — Architecture diagram (raw text, NOT rendered)
- `ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png` — Empty state for module without diagram
- `ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png` — No regressions check

---

## Root Cause Analysis (V1 Failure)

The architecture diagram fragment at `dashboard/templates/fragments/code_architecture_diagram.html:6` renders:
```html
<pre data-lang="mermaid"><code>{{ arch_diagram_dsl | e }}</code></pre>
```

The page template `project_code.html` includes `components/libs/mermaid.html` which loads the generic Mermaid library (`/static/vendor/mermaid/mermaid.min.js`) and initialises it with `startOnLoad: false`. The library does NOT define `window.iwChat.upgradeAllMermaidBlocks` — that function is defined in `dashboard/static/chat/mermaid.js` (the chat-panel-specific library).

The inline script in `code_architecture_diagram.html:11-18` calls `window.iwChat.upgradeAllMermaidBlocks(container)` but this is never executed because:
1. `chat/mermaid.js` is only loaded when the chat panel JS bundle initialises (triggered by the `<script type="module">` at `project_code.html:134`)
2. The chat module bundle (`render.js`, `actions.js`, etc.) may not have finished loading when the diagram fragment script runs
3. Even if the script runs, `window.iwChat.upgradeAllMermaidBlocks` is undefined because the mermaid.js file served at `/static/chat/mermaid.js` is the chat library, not the vendor library

**Actual loaded scripts on the code page:**
- `/static/vendor/mermaid/mermaid.min.js` (generic, no `iwChat`)
- `/static/chat/mermaid.js` → undefined (404 or not loaded yet)

The ` ```mermaid ``` ` → `<pre data-lang="mermaid"><code>` conversion in `_preprocess_mermaid()` (code_ui.py:61-63) is correct, but no JS upgrades these blocks to SVG.

---

## Environment Data (V2)

The fixture `ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py` seeds:
- `diagram-architecture` (architecture-level diagram — correct)
- `diagram-module-rag` (module-level diagram for "rag" module)

The seeded modules from `scripts/e2e_seed.py` are only `orch-daemon` and `dashboard`. Neither matches `rag`, so V2 has no module to test.

---

## No Regressions

Tested V5 by navigating the full page:
- Module detail loads correctly with doc content and "No diagram yet" empty state
- Chat panel shows correct context label "Chat — orch/daemon/ (Orchestration Daemon)"
- Architecture map renders with all components listed
- No new console errors on any page

---

## Code References

| File | Line | Issue |
|------|------|-------|
| `dashboard/templates/fragments/code_architecture_diagram.html` | 6 | Renders raw `<pre data-lang="mermaid">` but calls non-existent `window.iwChat.upgradeAllMermaidBlocks` |
| `dashboard/templates/components/libs/mermaid.html` | 1 | Only loads generic Mermaid, not the `iwChat`-extended version |
| `project_code.html` | 134-149 | Chat JS bundle (including `chat/mermaid.js`) loads asynchronously and may not be ready when diagram fragment scripts execute |
| `dashboard/static/chat/mermaid.js` | 243-248 | Defines `upgradeAllMermaidBlocks` but it is never invoked for architecture diagrams |

---

## Console Errors Observed

```
[ERROR] Failed to load resource: the server responded with a status of 404 (Not Found) @ http://localhost:9919/favicon.ico:0
```
(Only favicon 404 — no JS errors on the code page itself)

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
