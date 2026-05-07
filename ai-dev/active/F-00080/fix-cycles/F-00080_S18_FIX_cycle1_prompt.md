# F-00080 S18 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S18 of work item F-00080 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00080/ai-dev/active/F-00080/F-00080_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00080 S18 Browser Verification Report

## Environment
- Base URL used: http://localhost:9957
- E2E user: dev@example.local
- Project used: iw-ai-core (IW AI Core (E2E))

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | help button visible | pass | evidences/post/F-00080_v1_help_button_visible.png | `?` button with `aria-label="Help for this page"` confirmed at ref=e59 on queue page |
| V2 | popover opens with 4 sections | pass | evidences/post/F-00080_v2_popover_open.png | Popover has `role="dialog"` / `aria-modal="true"`, contains all 4 section headings: "What is this page?", "What can I do here?", "Vocabulary", "Take the 30-second tour →" button and "Open full docs →" link |
| V3 | ESC closes popover and restores focus | pass | evidences/post/F-00080_v3_esc_closed.png | Pressing Escape closes dialog; help button retains `[active]` flag indicating focus restored |
| V4 | tour mounts Driver.js | **fail** | evidences/post/F-00080_v4_tour_mounted.png | Clicking "Take the 30-second tour →" produced a disabled "Tour unavailable" button (ref=e145). Driver.js overlay was NOT mounted — no `driver-active-element` class appeared in snapshot |
| V5 | tour seen indicator | **fail** | evidences/post/F-00080_v5_tour_seen_indicator.png | After V4 interaction, reloading the queue page shows no `data-tour-seen="true"` attribute on the help button; button label remained plain "?" with no checkmark |
| V6 | empty state rendering | pass | evidences/post/F-00080_v6_empty_state.png | Research page rendered `data-empty-state="research"` empty state: heading "No research yet" (h3), body paragraph, and `<a class="empty-state__cta-primary">` link to `/docs/implementation/00_INDEX.md` |
| V7 | traversal 404 | pass | evidences/post/F-00080_v7_traversal_404.png | `/_help/../etc/passwd` returned HTTP 404 with JSON `{"detail":"Not Found"}`; no content from `/etc/passwd` |
| V8 | no outbound network | pass | (combined) | All navigation was same-origin to `http://localhost:9957`; no requests to `unpkg.com`, `cdn.jsdelivr.net`, or any analytics SaaS |
| V9 | no regressions | pass | evidences/post/F-00080_v9_no_regressions.png | Project dashboard (`/project/iw-ai-core/`) renders correctly with no `?` button; queue page continues to render empty-state correctly |

## Console / Network Errors

- V7 probe: `Failed to load resource: 404 (Not Found)` for `/etc/passwd` — expected, confirms rejection
- All other pages: 0 console errors observed during normal navigation
- No outbound/multi-origin requests detected in any session

## Root Cause (V4 + V5 failures)

**V4 — `dashboard/static/help/tours.js`:**
When the tour button is clicked, `tourRegistry.startTour(slug)` is called. The tour for `queue` is registered in `tours.js` but `tour.steps` is empty (`[]`), causing Driver.js to show "Tour unavailable" (the disabled button at ref=e145) rather than mounting an overlay. The popover correctly closes but no Driver.js instance is created.

**V5 — `dashboard/static/help/help.js`:**
The `data-tour-seen` attribute is set via `localStorage.setItem('tour-seen:${slug}', 'true')` only after a Driver.js tour completes (on `driver.on('destroyed')`). Since V4 fails to mount Driver.js, the 'destroyed' event never fires, and `data-tour-seen` is never written. A page reload after the failed tour attempt shows no indicator.

**Fix required:** Ensure `queue` tour in `tours.js` has at least one step definition so Driver.js can mount, and that the `destroyed` callback path is exercised.

## Screenshots captured
- `ai-dev/active/F-00080/evidences/post/F-00080_v1_help_button_visible.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v2_popover_open.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v3_esc_closed.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v4_tour_mounted.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v5_tour_seen_indicator.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v6_empty_state.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v7_traversal_404.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v9_no_regressions.png`


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S18` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00080/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00080/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
