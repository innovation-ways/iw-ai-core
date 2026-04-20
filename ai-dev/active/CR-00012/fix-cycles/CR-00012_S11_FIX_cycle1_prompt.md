# CR-00012 S11 Browser Verification Fix Cycle 1/2

The end-to-end browser verification for step S11 of work item CR-00012 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# CR-00012 S11 QvBrowser Report

## Step Summary

**Step**: S11 QvBrowser (Browser Verification)
**Work Item**: CR-00012 — Redesign docs pages — align with theme + fix stale/status badge overlap
**Agent**: qv-browser
**Base URL Used**: http://localhost:9945
**Overall Status**: FAIL (ENV_DATA_MISSING + CODE DEFECTS)

---

## Verification Results

| ID | Acceptance Criterion | Status | Notes |
|----|---------------------|--------|-------|
| V1 | AC1: Stale pill no longer overlaps Status pill | **CANNOT VERIFY** | No docs in E2E DB — no doc cards to inspect |
| V2 | AC2: All badges use theme-aligned styling in dark mode | **CANNOT VERIFY** | No docs in E2E DB — no doc cards to inspect |
| V2b | AC2: Status pills use low-opacity tinted + border style | **CODE DEFECT** | `status_colors` dict still uses filled pastels (e.g. `bg-gray-100 text-gray-600`) — not the new low-opacity tinted + border style per design spec |
| V3 | AC3: Stale summary banner is theme-aware | **CANNOT VERIFY** | No stale docs in E2E DB — stale summary banner does not render |
| V3b | AC3: Stale summary banner styling | **CODE DEFECT** | `docs_stale_summary.html` was NOT modified — stale summary banner still uses `bg-yellow-50 border-yellow-200` with no `dark:` variants per design spec |
| V4 | AC4: Type and tier pills collapse to neutral + icon | **CANNOT VERIFY** | No docs in E2E DB — no doc cards to inspect |
| V4b | AC4: Type/tier pills collapsed to neutral | **CODE DEFECT** | `type_colors` (9 entries) and `tier_colors` (3 entries) dicts still exist in `docs_card.html` with saturated pastel colors — not collapsed to `bg-muted text-muted-foreground border border-border` per design spec |
| V5 | AC5: Library and detail header badges match | **CANNOT VERIFY** | No docs in E2E DB and `docs_detail.html` was NOT modified from main branch |
| V6 | AC6: Settings gear follows theme tokens | **CODE DEFECT** | `docs_library.html` settings gear button uses `text-gray-400 hover:text-gray-600 hover:bg-gray-100` with NO `dark:` variant — violates AC6 requirement for `text-muted-foreground hover:bg-muted hover:text-foreground` |
| V7 | AC7: No functional regressions (htmx/JS hooks preserved) | **PASS** | htmx attributes and JS event handlers unchanged |

---

## Environment Data Missing

**Root Cause**: E2E seed (`scripts/e2e_seed.py`) creates only `DocType.research` docs (`architecture-map`, `orch-daemon`, `dashboard`), which are **explicitly excluded** from the docs library page query (`docs.py:44`: `docs = [d for d in svc.list_docs(project_id) if d.doc_type != DocType.research]`).

**Impact**: The docs library (`/project/iw-ai-core/docs`) shows "No documentation found" in both light and dark mode. AC1, AC2, AC3 (visual part), AC4, AC5 cannot be verified in browser.

**Fix Required**: Add an `e2e_fixtures` file at `ai-dev/active/CR-00012/e2e_fixtures/001_docs_seed.py` that seeds at least one `ProjectDoc` with a non-research `DocType` (e.g. `module`, `api`, `architecture`) so doc cards render on the library page. Consider also seeding a stale doc to verify AC1 and AC3 fully.

---

## Code Defects Found

### Defect 1: Settings gear not updated to theme tokens (AC6)
**File**: `dashboard/templates/docs_library.html:31`
**Current**: `class="p-2 text-gray-400 hover:text-gray-600 transition-colors rounded-md hover:bg-gray-100"`
**Required per AC6**: `class="p-2 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors rounded-md"` (with `dark:` variants)
**Note**: This file was listed as needing changes in the CR-00012 design (`docs_library.html` — settings gear classes) but was NOT modified.

### Defect 2: Stale summary banner not updated (AC3)
**File**: `dashboard/templates/fragments/docs_stale_summary.html`
**Status**: NOT modified from main branch
**Required per AC3**: `bg-amber-500/10 border border-amber-500/20` with `text-amber-700` / `dark:text-amber-300`, neutral-bordered buttons
**Current**: Still uses `bg-yellow-50 border border-yellow-200` with no dark mode variants

### Defect 3: Type and tier pills not collapsed to neutral (AC4)
**File**: `dashboard/templates/fragments/docs_card.html`
**Status**: `type_colors` dict (9 entries) and `tier_colors` dict (3 entries) still present with saturated pastel colors
**Required per AC4**: Both dicts deleted, replaced with single `bg-muted text-muted-foreground border border-border` pill style

### Defect 4: Status pills not updated to low-opacity tinted style (AC2)
**File**: `dashboard/templates/fragments/docs_card.html`
**Status**: `status_colors` dict still uses filled pastels (e.g. `bg-gray-100 text-gray-600`)
**Required per AC2**: Low-opacity tinted + border style (e.g. `planned → bg-muted text-muted-foreground border border-border`, `draft → bg-amber-500/10 text-amber-700 border-amber-500/20`)

### Defect 5: docs_detail.html header badges not updated (AC5)
**File**: `dashboard/templates/docs_detail.html`
**Status**: NOT modified from main branch
**Required per AC5**: Type/status/tier pills must match card styling 1:1

### Partial Fix: Stale badge overlap (AC1) — CORRECTLY FIXED
**File**: `dashboard/templates/fragments/docs_card.html`
**Change**: Stale badge moved from `absolute top-2 right-2` to inline in flex container; `relative` removed from card div. This correctly fixes the overlap. However, the stale badge styling (`bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-200`) is not the amber low-opacity style specified in the design.

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `ai-dev/active/CR-00012/evidences/post/CR-00012_v1_docs_library_light_no_docs.png` | Docs library, light mode, empty state |
| `ai-dev/active/CR-00012/evidences/post/CR-00012_v1_docs_library_dark_no_docs.png` | Docs library, dark mode, empty state |

---

## Console Errors Observed

1. `cdn.tailwindcss.com should not be used in production` — **WARNING** (pre-existing, not related to CR-00012)
2. `ReferenceError: module is not defined` at `highlight.js/core.js:2595` — **ERROR** (pre-existing, not related to CR-00012)
3. `missing ) after argument list` — **ERROR** (pre-existing, not related to CR-00012)

---

## Recommendations

1. **ENV_DATA_MISSING**: Add `ai-dev/active/CR-00012/e2e_fixtures/001_docs_seed.py` with non-research `ProjectDoc` entries to enable visual verification of doc cards
2. **CODE DEFECTS**: The following files need changes that were specified in the design but not implemented:
   - `dashboard/templates/docs_library.html` — settings gear theme tokens
   - `dashboard/templates/fragments/docs_stale_summary.html` — banner + buttons styling
   - `dashboard/templates/fragments/docs_card.html` — type/tier/status pill style collapse
   - `dashboard/templates/docs_detail.html` — header badge matching

---

## Test Commands That Pass (from S06-S10)

- `make lint` — PASSED (S06)
- `make format` — PASSED (S07)
- `make type-check` — PASSED (S08)
- `make test-unit` — PASSED (S09)
- `make test-integration` — PASSED (S10)


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/CR-00012/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
