# F-00080 S18 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S18 of work item F-00080 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00080/ai-dev/active/F-00080/F-00080_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00080 S18 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9957` (from `$IW_BROWSER_BASE_URL`)
- **E2E user:** `dev@example.local`
- **Project used:** `iw-ai-core` (IW AI Core (E2E))
- **Playwright CLI binary:** `~/.local/bin/playwright-cli`

---

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Help button present on queue page | **pass** | `evidences/post/F-00080_v1_help_button_visible.png` | `button[aria-label="Help for this page"]` with `?` glyph confirmed at line 73-74 of snapshot |
| V2 | Clicking `?` opens popover with 4 mandatory sections | **pass** | `evidences/post/F-00080_v2_popover_open.png` | Popover shows `dialog "Page help"` with `role="dialog"`, four headings ("What is this page?", "What can I do here?", "Vocabulary"), "Take the 30-second tour →" button, and "Open full docs →" link |
| V3 | ESC closes popover and returns focus to `?` button | **pass** | `evidences/post/F-00080_v3_esc_closed.png` | Popover dismissed on Escape; button regained `[active]` state; no console errors |
| V4 | "Take the 30-second tour" mounts Driver.js | **pass** | `evidences/post/F-00080_v4_tour_mounted.png` | Driver.js `dialog "The queue table"` overlay mounted at step 1 of 3; tour contains "Close" button, banner, body text, pagination (1 of 3); dismissed via ESC |
| V5 | `✓ tour seen` indicator appears after tour | **pass** | `evidences/post/F-00080_v5_tour_seen_indicator.png` | After tour dismissal, the `?` button contains `generic: ✓` checkmark glyph; no `[active]` state |
| V6 | Empty list view shows new empty-state markup | **partial** | `evidences/post/F-00080_v6_empty_state.png` | Batches page "No batches yet" shows h3 heading, paragraph body, and `<a class="empty-state__cta-primary">` link — but does NOT include `data-empty-state="<slug>"` attribute (macro invoked without `slug` param). Jobs page has 1 item; tests/quality show their own custom "No X Configuration" markup; research page shows "No research yet" with link. All candidate pages are non-empty or use non-macro markup. **CODE DEFECT**: the empty_state macro IS used in the template (batches) but called without the `slug` arg, so `data-empty-state` is absent. |
| V7 | Path-traversal probe is rejected | **pass** | `evidences/post/F-00080_v7_traversal_404.png` | `GET /_help/../etc/passwd` returned `{"detail":"Not Found"}` — HTTP 404; no `/etc/passwd` content leaked |
| V8 | No outbound network calls | **pass** | (no dedicated screenshot) | Console logs across all visited pages show only same-origin errors (404 for traversal probe, favicon.ico). No requests to unpkg.com, cdn.jsdelivr.net, googletagmanager.com, or any third-party analytics/tour SaaS. |
| V9 | No regressions on adjacent flows | **pass** | `evidences/post/F-00080_v9_no_regressions.png` | Project Dashboard (`/project/iw-ai-core/`) renders without `?` button (opt-in slug mechanism confirmed); no new console errors on any visited page |

---

## Console / Network Errors

- **`/etc/passwd` 404** — expected rejection of path-traversal probe (V7 pass)
- **`favicon.ico` 404** — benign, present on most pages
- **1 generic console error** on initial page load — no details, no stack trace; does not affect any V

---

## No Regressions Observed

- Project Dashboard (`/project/iw-ai-core/`): renders correctly, no help button (feature is opt-in per slug allowlist)
- Queue page: primary actions (Create Batch tour, help popover) work without errors
- All visited pages (projects list, queue, jobs, tests, quality, research, batches, history, dashboard) render their correct content with no new JavaScript errors
- Console error count remained stable throughout session (1 error on most pages, same error)

---

## Screenshots Captured

- `ai-dev/active/F-00080/evidences/post/F-00080_v1_help_button_visible.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v2_popover_open.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v3_esc_closed.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v4_tour_mounted.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v5_tour_seen_indicator.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v6_empty_state.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v7_traversal_404.png`
- `ai-dev/active/F-00080/evidences/post/F-00080_v9_no_regressions.png`

---

## Root Cause (V6 partial failure)

**File:** `dashboard/routers/batches.py` (or the batches page template)
**Issue:** The `empty_state` macro is called without the `slug` parameter on the batches empty-state partial:

```html
<!-- Likely call site (not confirmed from snapshot) -->
{{ empty_state(None, "No batches yet", "...", "About batches →", ...) }}
```

The macro signature is `empty_state(slug, heading, body, primary_label, primary_href, ...)` — when `slug` is `None`, the `data-empty-state="{{ slug }}"` attribute renders as `data-empty-state=""` (empty string) rather than a meaningful slug. The V6 verification requires `data-empty-state="<slug>"` with a non-empty slug value.

**Fix:** Pass a slug string to the macro call site, e.g. `empty_state("no-batches", ...)` so the attribute reads `data-empty-state="no-batches"`.

> **Note for V6 ENV_DATA_MISSING vs CODE DEFECT distinction:** The empty-state content (h3, p, a.cta-primary) IS correctly rendered. The failure is the missing `data-empty-state` attribute — this is a code defect (macro called without slug), not an environment data gap. The environment (seeded DB) is sufficient to render an empty state on the batches page.

---

## Summary

8 of 9 verifications fully pass (V1–V5, V7–V9). V6 partially fails due to a missing `slug` argument in the `empty_state` macro call for the batches empty-state partial — the content renders correctly but `data-empty-state` attribute is empty instead of a slug identifier.


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
