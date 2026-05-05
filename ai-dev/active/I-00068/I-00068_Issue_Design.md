# I-00068: Recent Activity batch link from "archived" event routes to /item/ instead of /batch/

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-05
**Reported By**: sergio (operator)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies — see `docs/IW_AI_Core_Agent_Constraints.md`. This incident does not require any container operations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This incident does NOT add or modify any Alembic migrations — it is a Python + Jinja2 template change with no schema impact.

---

## Description

Clicking the `BATCH-00076` link on a "Batch X archived successfully" row in the project dashboard's "Recent Activity" card navigates to `/project/iw-ai-core/item/BATCH-00076` and returns `{"detail":"Work item 'BATCH-00076' not found"}`. The same batch ID rendered from earlier events (e.g., "Batch X archiving started", "Batch X completed — all items merged") links correctly to `/project/iw-ai-core/batch/BATCH-00076`. The asymmetry is jarring: a single batch's history contains both working and broken links.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Critical context for this incident:

- `dashboard/CLAUDE.md` — Jinja2 templates + htmx + prebuilt Tailwind.
- `orch/CLAUDE.md` — `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves `metadata`); `daemon_events` is append-only.
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL.

## Steps to Reproduce

1. Open `http://iw-dev-01:9900/project/iw-ai-core/`.
2. In the "Recent Activity" card, find a row whose message starts with `Batch BATCH-00076 archived successfully`.
3. Click the `BATCH-00076` badge on that row.

**Expected**: Browser navigates to `/project/iw-ai-core/batch/BATCH-00076` and the batch detail page loads (HTTP 200).

**Actual**: Browser navigates to `/project/iw-ai-core/item/BATCH-00076` and the dashboard returns `{"detail":"Work item 'BATCH-00076' not found"}` (HTTP 404 from the work-item route).

## Browser Evidence

- Pre-fix screenshot: `ai-dev/active/I-00068/evidences/pre/I-00068-batch-link-page.png`
- Pre-fix accessibility snapshot: `ai-dev/active/I-00068/evidences/pre/I-00068-snapshot.yml`

The snapshot at lines 132-134 shows `BATCH-00076 → /url: /project/iw-ai-core/item/BATCH-00076` for the "archived successfully" event, and at lines 138-140 shows `BATCH-00076 → /url: /project/iw-ai-core/batch/BATCH-00076` (correct) for the earlier "archiving started" event — concrete proof of the asymmetric routing.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "http://iw-dev-01:9900/project/iw-ai-core/"
playwright-cli snapshot
# In the snapshot, locate two rows for the same batch:
#  - "Batch BATCH-XXXXX archiving started" → href ends with /batch/BATCH-XXXXX  ← correct
#  - "Batch BATCH-XXXXX archived successfully" → href ends with /item/BATCH-XXXXX  ← BUG
# Click the second one to reproduce the 404.
playwright-cli screenshot
cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/pre/I-00068-batch-link-page.png
```

## Root Cause Analysis

Two contributing defects, both must be fixed for full coverage.

**Defect 1 (root cause): missing `entity_type` in batch-archive event emission**

`orch/archive/batch_archiver.py:341-357` defines `_emit(...)` and constructs a `DaemonEvent` WITHOUT setting `entity_type`:

```python
def _emit(
    db: Any,
    event_type: str,
    project_id: str,
    batch_id: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=batch_id,    # set
        message=message,
        event_metadata=metadata or {},
        # entity_type is NOT set — defaults to None
    )
    db.add(event)
```

Compare with the correct pattern at `orch/cli/batch_commands.py:392` which DOES set `entity_type="batch"`, and `orch/daemon/batch_manager.py` which threads `entity_type` through its `_emit_event` helper. The archiver was written before the convention solidified and was never retrofitted.

**Defect 2 (template fallback is too permissive)**

`dashboard/templates/pages/project/dashboard.html:115-119`:

```jinja
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}"
     class="font-mono text-xs font-semibold text-primary hover:underline mr-1">
    {{ event.entity_id }}
  </a>
{% endif %}
```

When `entity_type` is `None`, the fallback unconditionally routes to `/item/`. For an `entity_id` that begins with `BATCH-`, this produces a known-broken URL because the work-item route refuses non-work-item IDs (returns 404). Hardening the fallback to detect the `BATCH-` prefix prevents the same class of bug from reappearing if any other emitter is added later that forgets `entity_type`.

The combination of Defect 1 + Defect 2 is what the user observed: the archiver produces an event with `entity_type=None`, and the template falls through to `/item/`. Fixing only Defect 1 fixes the user-visible symptom; fixing both makes the system robust against future regressions.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/archive/batch_archiver.py` | `_emit` does not propagate `entity_type` — events emitted by `archive_batch` (e.g., `batch_archived`, `batch_archive_failed`) carry `entity_type=None` instead of `"batch"`. |
| `dashboard/templates/pages/project/dashboard.html` | Fallback elif unconditionally routes to `/item/` for any `entity_id` when `entity_type` is `None`. Should detect the `BATCH-` prefix. |
| `tests/integration/test_dashboard_pages.py` | Existing test `test_recent_activity_unknown_entity_type_falls_back_to_item_route` uses a `BATCH-`-free ID so it still reflects the post-fix contract — but a new test must lock in the `BATCH-` prefix detection rule. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend (`backend-impl`) | In `orch/archive/batch_archiver.py`, add an `entity_type` parameter to `_emit` (default `None`) and update every call site within the file to pass `entity_type="batch"` for batch-scoped events. | — |
| S02 | CodeReview (`code-review-impl`) | Review S01: every batch event in the archiver carries `entity_type="batch"`; no signature breaking changes elsewhere; events appended remain consistent with `daemon_events` append-only contract. | — |
| S03 | Frontend (`frontend-impl`) | In `dashboard/templates/pages/project/dashboard.html`, harden the fallback (current lines 115-119): when `entity_type` is missing, detect the `BATCH-` prefix on `entity_id` and route to `/batch/`; otherwise keep the existing `/item/` fallback. Do NOT touch the explicit `entity_type == 'batch'`, `'doc_job'`, `'work_item'` branches. | — |
| S04 | CodeReview (`code-review-impl`) | Review S03: prefix check is correct, no other prefixes (e.g., `DOCJOB-`, `JOB-`) are unintentionally caught, no XSS introduced (the entity_id is autoescaped — confirm). | — |
| S05 | Tests (`tests-impl`) | Add `tests/integration/test_i00068_batch_link_routing.py`. (a) Backend unit/integration test asserting `batch_archiver._emit` writes a `DaemonEvent` row with `entity_type="batch"`. (b) Dashboard tests asserting `BATCH-` IDs route to `/batch/` regardless of `entity_type` value (including `None`, `"batch"`, and the legacy missing case). (c) The existing `test_recent_activity_unknown_entity_type_falls_back_to_item_route` is updated to use a non-`BATCH-` ID so it continues to test the generic fallback. Tests assert specific URL substrings, not shape. | — |
| S06 | CodeReview (`code-review-impl`) | Review S05: tests are falsifiable on `main`; specific-value assertions (`assert 'href="/project/.../batch/BATCH-...' in resp.text`); no shape-only checks; no flakiness. | — |
| S07 | CodeReview_Final (`code-review-final-impl`) | Cross-cutting review across S01 + S03 + S05; full unit + integration test pass. | — |
| S08 | self-assess-impl | Self-assessment via `iw-item-analyze`. | — |
| S09..S15 | qv-gate | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S16 | qv-browser | Browser verification: open dashboard, click a `BATCH-XXXXX` link from an "archived" event, confirm `/batch/` URL, confirm 200, confirm batch detail loads. | — |

Agent slugs: `backend-impl`, `code-review-impl`, `frontend-impl`, `tests-impl`, `code-review-final-impl`, `self-assess-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None — the `entity_type` column already exists on `daemon_events`; we are simply populating it correctly.
- **Migration notes**: None.

### Code Changes

- **Files to modify**: `orch/archive/batch_archiver.py`, `dashboard/templates/pages/project/dashboard.html`, `tests/integration/test_dashboard_pages.py` (the existing `test_recent_activity_unknown_entity_type_falls_back_to_item_route` test needs its entity_id changed from a `BATCH-`-free value to remain meaningful — but the existing test already uses `I-99999`, so confirm during S05 whether any change is needed).
- **Files to create**: `tests/integration/test_i00068_batch_link_routing.py`.
- **Nature of change**: Add `entity_type="batch"` to archive events; harden template fallback; add regression tests.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00068_Issue_Design.md` | Design | This document |
| `I-00068_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00068_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00068_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review |
| `prompts/I-00068_S03_Frontend_prompt.md` | Prompt | S03 frontend hardening |
| `prompts/I-00068_S04_CodeReview_Frontend_prompt.md` | Prompt | S04 review |
| `prompts/I-00068_S05_Tests_prompt.md` | Prompt | S05 tests |
| `prompts/I-00068_S06_CodeReview_Tests_prompt.md` | Prompt | S06 review |
| `prompts/I-00068_S07_CodeReview_Final_prompt.md` | Prompt | S07 global review |
| `prompts/I-00068_S08_SelfAssess_prompt.md` | Prompt | S08 self-assessment |
| `prompts/I-00068_S16_BrowserVerification_prompt.md` | Prompt | S16 browser verification |
| `evidences/pre/I-00068-batch-link-page.png` | Evidence | Pre-fix screenshot |
| `evidences/pre/I-00068-snapshot.yml` | Evidence | Pre-fix a11y snapshot showing both correct and buggy URLs |

Reports are created during execution in `ai-dev/active/I-00068/reports/`.

## Test to Reproduce

Two falsifying tests, one per defect:

```python
# tests/integration/test_i00068_batch_link_routing.py

def test_batch_archived_event_emits_entity_type_batch(db_session, ...):
    """Reproduction: would FAIL before S01 because batch_archiver._emit omits entity_type."""
    from orch.archive.batch_archiver import _emit
    _emit(
        db_session,
        event_type="batch_archived",
        project_id="test-proj",
        batch_id="BATCH-00099",
        message="Batch BATCH-00099 archived successfully",
    )
    db_session.commit()
    row = db_session.scalars(
        select(DaemonEvent).where(DaemonEvent.entity_id == "BATCH-00099")
    ).one()
    assert row.entity_type == "batch"     # FAILS pre-fix (was None)


def test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none(client, db_session):
    """Reproduction: would FAIL before S03 because the fallback elif routes to /item/."""
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="BATCH-00099",
        entity_type=None,            # simulate the legacy/buggy emission
        message="Batch BATCH-00099 archived successfully",
    )
    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/batch/BATCH-00099"' in resp.text  # FAILS pre-fix
    assert 'href="/project/test-proj/item/BATCH-00099"' not in resp.text
```

## Browser Verification Test

After the fix:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"
# 1. Find a Recent Activity row with "Batch BATCH-XXXXX archived successfully"
playwright-cli snapshot
# 2. Confirm the BATCH-XXXXX link href ends with /batch/BATCH-XXXXX (not /item/)
# 3. Click the link
playwright-cli click <batch-archived-link-ref>
playwright-cli snapshot
# 4. Confirm the URL is /project/{pid}/batch/BATCH-XXXXX and the batch detail page renders (no 404)
playwright-cli screenshot
```

## Acceptance Criteria

### AC1: Archive events carry entity_type="batch"

```
Given a batch is archived via orch.archive.batch_archiver
When a DaemonEvent row is written for that archive operation
Then row.entity_type equals "batch"
And row.entity_id equals the batch ID
```

### AC2: Dashboard routes BATCH- IDs to /batch/ even when entity_type is None

```
Given a DaemonEvent row with entity_id starting with "BATCH-" and entity_type is None
When the project dashboard renders
Then the rendered link href is /project/{pid}/batch/{entity_id}
And no /project/{pid}/item/{entity_id} link is generated for that row
```

### AC3: Existing entity_type routing is preserved

```
Given a DaemonEvent row with entity_type in {"batch", "doc_job", "work_item"}
When the project dashboard renders
Then the rendered link href matches the corresponding route exactly as it did before this incident
```

### AC4: Generic /item/ fallback still works for non-BATCH IDs

```
Given a DaemonEvent row with entity_id starting with "I-" or "CR-" or "F-" and entity_type is None
When the project dashboard renders
Then the rendered link href is /project/{pid}/item/{entity_id}
```

### AC5: Regression tests exist

```
Given the fix is applied
When the test suite runs
Then the regression tests in tests/integration/test_i00068_batch_link_routing.py pass
And they would fail when run against the pre-fix code
```

## Regression Prevention

- **Test the contract, not the symptom**: AC1 locks in the `entity_type` value at the emission boundary, AC2 locks in the URL routing rule by ID prefix. Both must pass for the regression to be impossible.
- **Defensive template**: even if a future emitter forgets to set `entity_type`, BATCH-prefixed IDs will still route correctly. This guards against repeating the same defect.
- **Browser verification**: end-to-end click-through in the isolated worktree stack confirms the bug is gone in the real environment.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/archive/batch_archiver.py`
- `dashboard/templates/pages/project/dashboard.html`
- `tests/integration/test_i00068_batch_link_routing.py`
- `tests/integration/test_dashboard_pages.py`

## TDD Approach

- Reproducing tests: see "Test to Reproduce" above. Both fail on `main` and pass after S01 + S03.
- Unit tests: `_emit` writes `entity_type="batch"`.
- Integration tests: dashboard rendering routes `BATCH-` IDs to `/batch/` for `entity_type` in `{None, "batch"}`.

## Notes

- We are NOT performing a full sweep of every `DaemonEvent(...)` site (per operator scoping decision). Only `orch/archive/batch_archiver.py` is fixed at the emitter level. The template hardening (S03) covers any other sites that may have the same omission today or in the future.
- The existing test `test_recent_activity_unknown_entity_type_falls_back_to_item_route` at `tests/integration/test_dashboard_pages.py:267` already uses entity_id `I-99999` (work-item-shaped), so it remains valid as the "generic fallback to `/item/`" assertion. S05 should NOT modify it; it should add new tests in a new file.
- Out of scope: redesigning event-emission helpers across all modules, adding a centralised `entity_type` enum, retroactively backfilling old `daemon_events` rows.
