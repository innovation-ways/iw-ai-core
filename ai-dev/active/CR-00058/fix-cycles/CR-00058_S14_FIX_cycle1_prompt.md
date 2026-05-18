# CR-00058 S14 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S14 of work item CR-00058 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/daemon/scope_overlap.py
  orch/daemon/batch_manager.py
  orch/daemon/project_registry.py
  dashboard/routers/batches.py
  dashboard/templates/fragments/batch_items_rows.html
  dashboard/templates/_partials/help/batches.html
  dashboard/templates/_partials/help/queue.html
  dashboard/templates/_partials/help/batch_detail.html
  dashboard/static/styles.css
  tests/unit/daemon/test_scope_overlap.py
  tests/unit/daemon/test_project_registry_overlap_gate.py
  tests/integration/daemon/__init__.py
  tests/integration/daemon/test_overlap_gate_policy.py
  tests/integration/daemon/test_batch_manager_scope_gate.py
  tests/integration/test_f_00076_gate_performance.py
  tests/dashboard/test_batches_router.py
  docs/IW_AI_Core_Daemon_Design.md
  docs/IW_AI_Core_Architecture.md
  .iw-orch.json

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00058/ai-dev/active/CR-00058/CR-00058_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00058 S14 Browser Verification Report

## Environment
- Base URL used: http://localhost:9913
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | Project home, batches, queue, history pages have no dangling DOM refs and no console errors |
| V1 | Held-reason pill renders | pass | null | evidences/post/CR-00058_v1_v2_batch_detail.png | F-00055 shows "Held: overlaps with CR-00001 on `orch/daemon/batch_manager.py`" pill |
| V2 | Policy-allowed pill renders | pass | null | evidences/post/CR-00058_v1_v2_batch_detail.png | CR-00001 shows "policy allowed (tests/**, test/**, **/*conftest*+2 more)" pill |
| V3 | Held precedence | pass | null | evidences/post/CR-00058_v3_held_precedence.png | I-00001 with both events shows only held pill (policy_allowed suppressed) |
| V4 | Queue page surfaces pills | fail | code_defect | — | Queue page (`/project/iw-ai-core/queue`) does not render scope_status pills — grep confirms `scope_status` not used in queue template |
| V5 | Help partial mentions new pill | pass | null | evidences/post/CR-00058_v5_help_batches.png | Batches help panel contains "Items released by an allow-on-overlap rule show an info pill" |
| V6 | No regressions | pass | null | — | Adjacent UI (batch list filters, batch detail table, item links) render correctly |

## Console / Network Errors
None observed during any page navigation or reload.

## No Regressions
- Batch list page (batches): filter checkboxes, batch row with actions (Cancel, Pause) render correctly
- Batch detail page: table with 3 items (CR-00001, F-00055, I-00001) shows correct status badges, pills, and "View" links
- Item detail links from batch rows work (links to /project/iw-ai-core/item/{id})

## Root Cause (V4 failure)

**CODE_DEFECT: Queue page does not surface scope pills**

File: `dashboard/templates/pages/project/queue.html` (and related router `dashboard/routers/project_pages.py`)

The queue page template does not include any rendering of `scope_status` pills. The `batch_items_rows.html` fragment correctly implements both held and policy_allowed pills, but this fragment is only used on the batch detail page. The queue page renders items from the `work_items` table directly, not from `batch_items`, and does not join or query `DaemonEvent` for scope-gate status.

The design doc (AC6) states: "The batch detail and queue pages already surface `item_held_for_scope` reasons via `dashboard/routers/batches.py:74-149`." The implementation correctly extended `batches.py` with `ScopeStatus` dataclass and `_get_scope_statuses()` for batch context, but the queue page router (`project_pages.py`) was not updated to surface the same information for queue items.

To fix: `project_pages.py` should call `_get_scope_statuses()` for queue items (approved work items not yet in a batch), and `queue.html` should render the scope pill similar to `batch_items_rows.html`.

## Screenshots captured
- `ai-dev/active/CR-00058/evidences/post/CR-00058_v1_v2_batch_detail.png`
- `ai-dev/active/CR-00058/evidences/post/CR-00058_v3_held_precedence.png`
- `ai-dev/active/CR-00058/evidences/post/CR-00058_v5_help_batches.png`

## Fixture Notes
The initial fixture `ai-dev/active/CR-00058/e2e_fixtures/001_overlap_gate_events.py` was created but the SQLAlchemy model uses `event_metadata` (Python attr) → `metadata` (DB column). Passing `metadata=` kwarg to `DaemonEvent(...)` constructor does not work because SQLAlchemy maps `event_metadata` attribute to the DB column. The fixture metadata was inserted as `{}` due to this naming mismatch. The verification was completed by inserting events via raw SQL (`psql`) directly to ensure proper JSONB metadata.

## Fixture File Created
`ai-dev/active/CR-00058/e2e_fixtures/001_overlap_gate_events.py` — but note the `metadata` → `event_metadata` kwarg bug needs to be fixed for it to work via `e2e_seed.py`.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S14` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00058/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00058/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
