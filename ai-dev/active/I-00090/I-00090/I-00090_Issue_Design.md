# I-00090: `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (operator) — observed on http://iw-dev-01:9900/system/running
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This item touches a dashboard SQL query helper and a test file under `tests/dashboard/`. No docker commands are needed. Testcontainer fixtures used by the tests are exempt per policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds, modifies, or deletes NO Alembic migrations.** It is a query-layer-only fix. `migration-check` is therefore not included in the gate set.

## Description

The system-wide "Running Tasks" page at `/system/running` (and its per-project sibling `/project/{id}/running`) currently shows step rows from work items that are no longer active. As of `2026-05-17` the "Failed / Needs Attention" table contains four rows belonging to CRs that the operator has long since closed or cancelled (CR-00023, CR-00049 — `cancelled`; CR-00052, CR-00054 — `completed`), and the "Recently Completed (last hour)" table is similarly unfiltered. The page is intended as the operator's live triage board for what needs attention right now; stale rows that can never be acted on dilute the signal and waste operator attention.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `dashboard/CLAUDE.md` for dashboard router/template/htmx conventions. The relevant SQLAlchemy 2.0 ORM style guide and append-only audit-table contract live in `orch/CLAUDE.md`.

## Browser Evidence

Pre-fix evidence captured against production at http://iw-dev-01:9900/system/running on 2026-05-17:

- `ai-dev/active/I-00090/evidences/pre/I-00090-bug-evidence.png` — viewport screenshot showing all four stale rows (CR-00023 S01 Database, CR-00049 S01 Backend, CR-00052 S12 SelfAssess, CR-00054 S19 SelfAssess) in the Failed table.
- `ai-dev/active/I-00090/evidences/pre/I-00090-bug-evidence-snapshot.yml` — accessibility-tree snapshot of the same page, including the surrounding "Running Now" and "Recently Completed" tables for context.

Item-status confirmation (collected via `uv run iw item-status` on 2026-05-17):

| Item | Status | Phase | Why it shouldn't surface |
|------|--------|-------|--------------------------|
| CR-00023 | `cancelled` | active | `status == cancelled` |
| CR-00049 | `cancelled` | active | `status == cancelled` |
| CR-00052 | `completed` | done | `status == completed` |
| CR-00054 | `completed` | done | `status == completed` |

## Steps to Reproduce

1. Have at least one `WorkflowStep` whose `status` is `failed` or `needs_fix` and whose parent `WorkItem.status` is `completed` or `cancelled` (or whose parent `WorkItem.archived_at IS NOT NULL`). The four CRs listed above all satisfy this on the production DB today.
2. Open http://iw-dev-01:9900/system/running in a browser.
3. Scroll to the "Failed / Needs Attention" section.
4. Repeat at `http://iw-dev-01:9900/project/iw-ai-core/running` — same rows appear, scoped to the project.
5. Scroll to "Recently Completed (last hour)" — any `step_run` with `completed_at >= now-1h` whose parent item is also non-active appears here too (this is the same bug; not always visible because the time window keeps the list short).

**Expected**: Both tables show ONLY step rows whose parent `WorkItem` is currently active — i.e. `WorkItem.archived_at IS NULL` AND `WorkItem.status NOT IN (completed, cancelled)`. With current production data, the Failed table should be empty.

**Actual**: Both tables include rows from items in `completed` / `cancelled` status and from archived items, polluting the operator's triage view forever (a failed step from an item closed weeks ago is still listed today).

## Browser Verification Script

Reproduction is straightforward and uses only the public route. The post-fix verification will be performed by the qv-browser step against the worktree's isolated E2E stack at `$IW_BROWSER_BASE_URL` (NOT the production URL above).

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/system/running"
playwright-cli snapshot
# Visually confirm the "Failed / Needs Attention" table contains ONLY rows
# whose parent items are currently active (archived_at IS NULL AND status NOT
# IN (completed, cancelled)). With the seeded E2E DB (pg_dump of prod), this
# should match expectations once the fix is applied.
playwright-cli screenshot
cp .playwright-cli/page-*.png ai-dev/active/I-00090/evidences/post/I-00090_v1_system_running_failed_table.png
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/running"
playwright-cli snapshot
playwright-cli screenshot
cp .playwright-cli/page-*.png ai-dev/active/I-00090/evidences/post/I-00090_v2_project_running_failed_table.png
```

## Root Cause Analysis

The page is rendered by `dashboard/routers/running.py:240` (`running_tasks()` for `/system/running`) and `dashboard/routers/running.py:277` (`project_running_tasks()` for `/project/{id}/running`). Both delegate to two private query helpers:

- `_query_failed_steps(db, project_id=None)` at `dashboard/routers/running.py:132-190` — selects `WorkflowStep` rows with `status IN (StepStatus.failed, StepStatus.needs_fix)`, joined to `WorkItem` and `Project`. The `WHERE` clause never filters by `WorkItem.archived_at` or `WorkItem.status`.
- `_query_recent_completions(db, project_id=None)` at `dashboard/routers/running.py:193-226` — selects `StepRun` rows with `status = RunStatus.completed` and `completed_at >= now-1h`, joined to `WorkflowStep` and `WorkItem`. Same omission.

Because `step_runs` and `workflow_steps` are append-only / audit-style (see `orch/CLAUDE.md` "append-only" list), closing or archiving a `WorkItem` never rewrites the historical step rows — and intentionally so, to preserve the audit trail. The bug is therefore not in the state machine but purely in these two read queries: they must filter by the parent `WorkItem`'s current lifecycle state, not assume the step's own status reflects "still needs attention".

The `_query_running_now()` helper at `dashboard/routers/running.py:89-129` has the same shape but, in production today, no `step_runs` with `status=running` exist whose parent items are inactive (the daemon's normal lifecycle keeps these in sync). This item explicitly leaves that helper unchanged — see **Out of Scope** below — because adding a silent filter there could mask a real daemon defect (an orphaned process whose parent item was archived out from under it). If a future incident demonstrates that case, it should be handled with both a filter AND a `daemon_event` WARNING, not silently.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/routers/running.py::_query_failed_steps` | Returns rows from completed/cancelled/archived items, polluting `/system/running` and `/project/{id}/running` "Failed / Needs Attention" tables |
| `dashboard/routers/running.py::_query_recent_completions` | Returns rows from completed/cancelled/archived items in the 1h Recently Completed table |
| `GET /system/running` (`running_tasks` handler) | Renders polluted tables to operator |
| `GET /project/{project_id}/running` (`project_running_tasks` handler) | Same, scoped to one project |

The `GET /system/running-fragment` htmx fragment endpoint only renders Running Now (not Failed / Completed), and `get_running_count()` only counts running rows for the sidebar badge — neither is affected by this fix.

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend (`backend-impl`) | Add `WorkItem.archived_at.is_(None)` + `WorkItem.status.notin_([completed, cancelled])` to `_query_failed_steps()` AND `_query_recent_completions()` in `dashboard/routers/running.py`. Import `WorkItemStatus` if not already imported. | — |
| S02 | CodeReview_Backend (`code-review-impl`) | Review S01: predicate placement, enum-list correctness, SQLAlchemy 2.0 idiom (`is_(None)` not `== None`), scope adherence, no template change | — |
| S03 | Tests (`tests-impl`) | Write `tests/dashboard/test_running_router_active_filter.py` — helper-level tests for all status branches (in_progress, completed, cancelled, archived, failed, paused) for BOTH `_query_failed_steps()` and `_query_recent_completions()`, plus route-level smoke tests for `GET /system/running` and `GET /project/{id}/running` confirming the active item ID appears and the inactive item IDs do NOT appear in the rendered HTML | — |
| S04 | CodeReview_Tests (`code-review-impl`) | Review S03: semantic-correctness assertions (specific item IDs / specific absence), all six branches covered for each helper, no shape-only assertions | — |
| S05 | CodeReview_Final (`code-review-final-impl`) | Global review of S01–S04: cross-file consistency, AC traceability, scope adherence | — |
| S06 | qv-gate `lint` | `make lint` | — |
| S07 | qv-gate `format` | `make format-check` | — |
| S08 | qv-gate `typecheck` | `make typecheck` | — |
| S09 | qv-gate `arch-check` | `make arch-check` | — |
| S10 | qv-gate `security-sast` | `make security-sast` | — |
| S11 | qv-gate `unit-tests` | `make test-unit` | — |
| S12 | qv-gate `integration-tests` | `make allure-integration` (timeout 1800s) | — |
| S13 | qv-browser | Browser verification on `/system/running` and `/project/{id}/running` against the worktree's isolated stack | — |
| S14 | SelfAssess (`self-assess-impl`) | Soft-step item retrospective via the `iw-item-analyze` skill (project has `self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No Alembic migration is generated or modified. `migration-check` gate intentionally omitted.

### Code Changes

- **Files to modify**: `dashboard/routers/running.py`
- **Nature of change**: Add two `.where(...)` predicates to each of `_query_failed_steps()` and `_query_recent_completions()`:
  ```python
  from orch.db.models import WorkItemStatus  # add to imports if not present
  ...
  .where(WorkItem.archived_at.is_(None))
  .where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))
  ```
  The existing `WorkItem` join is reused; no schema, template, or htmx changes are required.

## File Manifest

All files for this work item live under `ai-dev/active/I-00090/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00090_Issue_Design.md` | Design | This document |
| `I-00090_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `evidences/pre/I-00090-bug-evidence.png` | Evidence | Pre-fix screenshot of `/system/running` |
| `evidences/pre/I-00090-bug-evidence-snapshot.yml` | Evidence | Pre-fix a11y snapshot of `/system/running` |
| `prompts/I-00090_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00090_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00090_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00090_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00090_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00090_S13_BrowserVerification_prompt.md` | Prompt | S13 qv-browser verification |
| `prompts/I-00090_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

Reports are created during execution in `ai-dev/active/I-00090/reports/`.

## Test to Reproduce

Tests will be added under `tests/dashboard/` (the affected file is exercised via the dashboard `client` fixture, which is registered only in `tests/dashboard/conftest.py`; placing the test under `tests/integration/` would fail with `fixture 'client' not found`, see I-00067).

```python
# tests/dashboard/test_running_router_active_filter.py
"""I-00090 — Failed/Recently Completed tables must hide steps belonging to
completed / cancelled / archived WorkItems."""

from datetime import UTC, datetime, timedelta

from dashboard.routers.running import _query_failed_steps, _query_recent_completions
from orch.db.models import (
    Project, RunStatus, StepRun, StepStatus, WorkflowStep, WorkItem,
    WorkItemPhase, WorkItemStatus, WorkItemType,
)


def test_query_failed_steps_excludes_completed_item(db_session):
    """A failed step whose parent WorkItem.status == completed must NOT
    appear. RED until the .where(WorkItem.status.notin_([...])) predicate
    is added."""
    project = _make_project(db_session, "p1")
    item = _make_item(db_session, project.id, "CR-DEAD", status=WorkItemStatus.completed)
    step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)

    rows = _query_failed_steps(db_session)

    assert all(r.item_id != "CR-DEAD" for r in rows), (
        f"completed item should not surface in Failed table; got items: "
        f"{[r.item_id for r in rows]}"
    )
```

(Plus mirror tests for `cancelled`, `archived_at IS NOT NULL`, `in_progress` (must appear), `paused` (must appear), `failed` (must appear) — and the same six branches for `_query_recent_completions`. See the **TDD Approach** section below for the full list.)

## Acceptance Criteria

### AC1: Bug is fixed — Failed table excludes inactive items

```
Given a WorkflowStep with status = failed and parent WorkItem.status IN (completed, cancelled) OR WorkItem.archived_at IS NOT NULL,
When an operator loads GET /system/running OR GET /project/{id}/running,
Then the row for that step does NOT appear in the "Failed / Needs Attention" table.
```

### AC2: Active items still surface

```
Given a WorkflowStep with status = failed and parent WorkItem.archived_at IS NULL and WorkItem.status IN (draft, approved, in_progress, paused, failed),
When an operator loads GET /system/running OR GET /project/{id}/running,
Then the row for that step DOES appear in the "Failed / Needs Attention" table.
```

Note: item-level `failed` is intentionally treated as still-active because it represents an unresolved problem that needs operator attention.

### AC3: Recently Completed table is filtered the same way

```
Given a StepRun completed within the last hour whose parent WorkItem.status IN (completed, cancelled) OR archived_at IS NOT NULL,
When an operator loads GET /system/running OR GET /project/{id}/running,
Then the row for that step_run does NOT appear in the "Recently Completed (last hour)" table.
```

### AC4: Regression test exists

```
Given the fix is applied,
When the test suite runs (make test-unit + make allure-integration),
Then all tests in tests/dashboard/test_running_router_active_filter.py pass.
```

### AC5: Production sanity (qv-browser)

```
Given the worktree's isolated E2E stack is up and seeded from production data,
When the qv-browser step loads /system/running and /project/iw-ai-core/running,
Then no rows for CR-00023, CR-00049, CR-00052, or CR-00054 appear in the Failed table.
```

## Regression Prevention

- Add helper-level tests for all six WorkItem-status branches AND the archived branch for BOTH `_query_failed_steps()` and `_query_recent_completions()` — anyone adding a new "needs attention NOW" query in this router must reproduce the same filter pattern or the analogous tests will fail.
- Document the active-item predicate as a module-level docstring or comment in `dashboard/routers/running.py` so future "show me all X across all projects" helpers have a copy-pasteable reference.
- The route-level smoke tests assert on specific item IDs (not just response shape), preventing the I-00041/I003-style "tests pass but bug remains" regression.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/routers/running.py`
- `tests/dashboard/test_running_router_active_filter.py`

## TDD Approach

### Reproducing test (must FAIL on `main`, PASS after S01)

`tests/dashboard/test_running_router_active_filter.py::test_query_failed_steps_excludes_completed_item`

Run against `main` (pre-S01) it should fail with an `AssertionError: completed item should not surface in Failed table; got items: ['CR-DEAD', ...]`. After S01 applies the `.where(...)` predicates it should pass. The Backend step's `tdd_red_evidence` field MUST record this run (the new behavioural test added/restructured by the implementation step; if the Tests step adds the file then the Backend step's RED-evidence may be `"n/a — query-only fix; behavioural test added in S03"`, which is acceptable for a query-helper fix where the fail-first proof is owned by the Tests step).

### Unit tests

The router file is exercised via the dashboard `client` fixture (registered only in `tests/dashboard/conftest.py`), so all tests live there. Helper-level tests call `_query_failed_steps()` / `_query_recent_completions()` directly with a controlled `db_session`; route-level tests use the dashboard `TestClient`.

`tests/dashboard/test_running_router_active_filter.py` (single new file, must include all of):

For `_query_failed_steps`:
1. `test_query_failed_steps_includes_in_progress_item` — active item, status=in_progress, archived_at=None → row appears
2. `test_query_failed_steps_excludes_completed_item` — status=completed → row absent
3. `test_query_failed_steps_excludes_cancelled_item` — status=cancelled → row absent
4. `test_query_failed_steps_excludes_archived_item` — archived_at=now, status=in_progress (i.e. archived item with any status) → row absent
5. `test_query_failed_steps_includes_failed_item` — status=failed, archived_at=None → row appears (item-level failed is unresolved)
6. `test_query_failed_steps_includes_paused_item` — status=paused, archived_at=None → row appears
7. `test_query_failed_steps_includes_needs_fix_status` — step.status=needs_fix on an in_progress item → row appears (regression guard for the OR in `status.in_([failed, needs_fix])`)
8. `test_query_failed_steps_respects_project_filter` — when `project_id` is passed, rows from other projects are excluded (regression guard for the existing project filter)

For `_query_recent_completions` — mirror tests 1–6 above (no needs_fix mirror — that's only relevant to failed steps):
9. `test_query_recent_completions_includes_in_progress_item`
10. `test_query_recent_completions_excludes_completed_item`
11. `test_query_recent_completions_excludes_cancelled_item`
12. `test_query_recent_completions_excludes_archived_item`
13. `test_query_recent_completions_includes_failed_item`
14. `test_query_recent_completions_includes_paused_item`

Route-level smoke tests:
15. `test_system_running_route_renders_active_item_only` — seed two failed steps (one on an in_progress item `I-ALIVE`, one on a completed item `I-DEAD`), `GET /system/running`, assert `200 OK`, assert `"I-ALIVE"` IS in body, assert `"I-DEAD"` is NOT in body.
16. `test_project_running_route_renders_active_item_only` — same shape, `GET /project/{id}/running`, assert project-scoped filter still applies.

### Integration tests

The helper-level tests above use the testcontainer Postgres via the standard `db_session` fixture, so they run as part of `make allure-integration` if placed under `tests/integration/`. However, because the dashboard `client` fixture lives in `tests/dashboard/conftest.py`, tests 15–16 MUST live under `tests/dashboard/`. The other tests CAN live there too for cohesion — a single test file under `tests/dashboard/` is the simplest layout and matches the precedent set by `tests/dashboard/test_docs_running_jobs.py`.

**Assertion-strength rule** (see `skills/iw-ai-core-testing/SKILL.md`): every test MUST assert on a specific item ID or specific absence (`assert "CR-DEAD" not in [r.item_id for r in rows]`). NEVER use `assert len(rows) == N` alone — that's brittle and can pass for the wrong reason. NEVER use `assert "failed" in body` — that's shape-only and would pass even with the bug present.

**Assertion scoping for CSS class names** — when a regression test asserts that a CSS class name is present in rendered HTML, the bare-substring form `assert "my-class" in html` can false-positive because the same token may appear inside an inline `<script>` tag's JSON, a `data-*` attribute value, an HTML comment, or a CSS source map comment — even when the production element carrying that class is absent. Use the attribute-scoped form instead, e.g. `assert 'class="my-class"' in html` or a regex that anchors on `class\s*=\s*"[^"]*my-class[^"]*"` (I-00067). For this incident the route-level tests assert on item IDs (which are unique tokens), so this rule is informational only.

## Notes

- **Optional defence-in-depth (NOT required for acceptance)**: The implementer may choose to apply the same `archived_at IS NULL AND status NOT IN (completed, cancelled)` filter to `_query_running_now()` and `get_running_count()`. If they do, they MUST also emit a `daemon_event` at WARNING severity when a running step is filtered out — silently hiding an orphaned-process row would mask a real daemon defect. The recommended path for this item is to **leave the running-now helpers untouched** and file a follow-up incident only if an orphaned-running case is observed in production. This keeps the fix surgical.
- **Why item-level `failed` still surfaces**: an item whose status is `failed` represents an unresolved problem that the operator should still see. Only `completed` (success) and `cancelled` (operator decided not to pursue) are truly terminal-for-attention. Archived items are excluded regardless of status because the operator has explicitly removed them from active view.
- **Template untouched**: `dashboard/templates/pages/system/running.html` does not need to change. Empty tables already render correctly (the existing `{% for row in failed_rows %}` block degrades to an empty `<tbody>`).
- **Why `arch-check` and `security-sast` are included** when I-00088 did not: the user-presented plan included them and they are cheap; running them as a baseline avoids drift on this router. If either is unhealthy on `main`, the gate will fail and the fix-cycle agent will deal with it.
