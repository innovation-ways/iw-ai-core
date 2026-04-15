# F-00047 S11 — QV Browser Verification

## Mission

Execute browser verification for the Code Understanding dashboard tab using `playwright-cli` in the headless WSL/Linux environment. This is the final QV gate — it verifies that the feature is observably correct in a real browser after all prior gates (lint/format/typecheck/unit/integration) have passed.

## Scope

Verify the following golden paths against a running dashboard (`http://localhost:9900`). All checks must pass with visible evidence (snapshot + screenshot) captured for the worktree report.

Use a seeded project that has:
- At least one project registered in the dashboard
- A completed `CodeIndexJob` with a valid `doc_id` pointing to a `ProjectDoc` whose `content` contains a ` ```mermaid ` fenced block (for the architecture-view path)
- A second project with **no** completed job (for the empty-state path)

If the test data is missing, pick any existing project and document its seed state in the report — do not invent fake projects.

## Required Reading

1. `CLAUDE.md` — `playwright-cli` rules (MANDATORY: `playwright-cli kill-all` before starting; NEVER run `npx playwright install`; NEVER touch `.playwright/cli.config.json`)
2. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — wireframes and Acceptance Criteria
3. `dashboard/templates/project_code.html` — to map what you expect on screen

## Pre-flight

```bash
playwright-cli kill-all
make dashboard-start   # if not already running; otherwise skip
curl -sS -o /dev/null -w "%{http_code}" http://localhost:9900/ || { echo "dashboard not reachable"; exit 1; }
```

## Checks

### Check 1 — Code nav link appears (AC1)

```bash
playwright-cli open http://localhost:9900/project/{seed-project-id}/
playwright-cli snapshot
```

Verify in the snapshot:
- A "Code" entry is present in the sub-nav after "Research".
- The link target is `/project/{seed-project-id}/code`.

### Check 2 — Empty state renders (AC2)

```bash
playwright-cli open http://localhost:9900/project/{project-without-index}/code
playwright-cli snapshot
playwright-cli screenshot
```

Verify:
- HTTP 200 (no error page).
- Heading "No code map generated yet." is present.
- A "Generate Code Map" button is present.
- No `<div class="mermaid">` nodes are present.

### Check 3 — Architecture view + Mermaid SVG (AC3)

```bash
playwright-cli open http://localhost:9900/project/{project-with-index}/code
playwright-cli snapshot
playwright-cli screenshot
```

Verify:
- Heading "Architecture" is present.
- At least one `svg` inside a `.mermaid` container (Mermaid has rendered the fenced block).
- Raw ` ```mermaid ` markdown is NOT visible on the page (it was pre-processed).

### Check 4 — Dropdown open/close (AC5)

```bash
playwright-cli click "button:has-text('Generate Code Map')"
playwright-cli snapshot   # dropdown open
playwright-cli click "body"
playwright-cli snapshot   # dropdown closed
```

Verify the `#code-dropdown-menu` div toggles the `hidden` class and that outside-click closes it.

### Check 5 — Running job SSE update (AC4)

Seed (or trigger via the dashboard) a running `CodeIndexJob` for a test project:

```bash
playwright-cli open http://localhost:9900/project/{project-id}/code
playwright-cli snapshot
```

Verify:
- The job status fragment is rendered (`#code-job-status-panel` present).
- The progress bar element exists with `role="progressbar"`.
- After ~5 seconds the progress counters have been updated by the EventSource (compare two snapshots).

Note: if a fake progress runner is not available in the environment, document this as "manual trigger not possible in CI" and skip to Check 6 — but flag the skip clearly in the report.

### Check 6 — Cancel path (AC7)

With a running job in place (from Check 5):

```bash
playwright-cli click "button:has-text('Cancel')"
# playwright-cli will surface the hx-confirm dialog — accept it
playwright-cli snapshot
```

Verify:
- After the click the cancel DELETE request is issued and the status panel swaps (still present, labeled "Cancelling..." or equivalent).
- Within a few seconds the SSE terminal event fires and both `#code-status-panel` and `#code-architecture-panel` are refreshed.

### Check 7 — Regression: existing pages still load

```bash
playwright-cli open http://localhost:9900/project/{seed-project-id}/docs
playwright-cli snapshot
playwright-cli open http://localhost:9900/project/{seed-project-id}/research
playwright-cli snapshot
```

Verify:
- Docs and Research pages still render without errors.
- `base.html` Mermaid script additions have not broken any existing page.

## Teardown

```bash
playwright-cli kill-all
```

## Output

Produce a report section listing each check, PASS/FAIL/SKIP, the evidence captured (snapshot/screenshot filenames), and any observed issues. A single FAIL in Checks 1–4 or 7 blocks merge. A SKIP in Check 5 or 6 is acceptable only with a written justification (e.g., "no fake runner available in QV environment; manual smoke-test performed on developer workstation").

## Pass/Fail

- **PASS**: all checks PASS or have accepted SKIP justifications
- **FAIL**: any check FAIL, or a SKIP without justification — block the merge and flag to frontend-impl / api-impl
