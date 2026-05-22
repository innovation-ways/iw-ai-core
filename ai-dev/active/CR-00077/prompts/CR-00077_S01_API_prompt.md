# CR-00077_S01_API_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network management commands. Testcontainer fixtures spun up by pytest are the only exception. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no** alembic migration and **no** schema change. If you find yourself wanting to add a new column or table, STOP and raise a blocker — the data needed by this endpoint already exists in `daemon_events`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00077 --json` is the authoritative source.
- `ai-dev/active/CR-00077/CR-00077_CR_Design.md` — design document.

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S01_API_report.md` — step report.
- Code: see Requirements below.

## Context

You are implementing the new htmx endpoint for **CR-00077 — Overlap details popup (read-only)**. Read the design document first. Then read `dashboard/CLAUDE.md` for FastAPI / Jinja / htmx conventions, `orch/CLAUDE.md` for the `DaemonEvent.event_metadata` reserved-name gotcha, and the root `CLAUDE.md` for testing rules.

## Requirements

### 1. Add the grouping helper

Add to `dashboard/routers/batches.py`, near `_get_scope_statuses` (lines ~147-200), a pure function:

```python
def group_overlap_events(
    events: list[DaemonEvent],
) -> list[tuple[str, list[str]]]:
    """Return ordered (blocking_item_id, conflicting_globs) tuples.

    Most-recent-wins on duplicate blocking_item_ids (events arrive newest first).
    Events whose `event_metadata` lacks the required keys are silently skipped.
    Insertion order across distinct blocking_item_ids is preserved.
    """
```

Rules:
- Pure function. No DB access. No I/O. Importable from `tests/unit/`.
- Each input `DaemonEvent` is expected to have `event_metadata` with keys `blocking_item_id: str` and `conflicting_globs: list[str]`. Skip rows that lack either key (use `dict.get`, defensive).
- Order: preserve the order of first appearance of each `blocking_item_id` in the input list. When a `blocking_item_id` appears twice, keep the first occurrence's payload (the caller passes events ordered newest first).

### 2. Add the endpoint

Add to `dashboard/routers/batches.py`:

```
GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}
```

Behaviour:
1. Resolve the project (existing pattern in this router).
2. Verify the batch exists; 404 otherwise.
3. Query `DaemonEvent` rows where:
   - `project_id == <resolved project_id>`
   - `event_type == "item_held_for_scope"`
   - `entity_id == held_item_id`
   - `entity_type == "work_item"`
   - `created_at >= now() - 300s` (same window as `_get_scope_statuses`; reuse the cutoff helper or factor it out — do not duplicate magic number)
   - ordered by `created_at DESC`
4. If the result set is empty, render `dashboard/templates/fragments/batch_overlap_modal.html` with `{"empty": True, "held_item_id": held_item_id}` and return HTTP **404** (the fragment renders a short "No overlap details available — the item may have been released since this page rendered." message). Use `status_code=404` on `templates.TemplateResponse` so htmx can swap-on-404 if needed; many existing routers in this repo do this.
5. Otherwise, call `group_overlap_events(events)`. For each `blocking_item_id`, fetch the blocking item's title via `db.get(WorkItem, (project_id, blocking_item_id))` — if the item is missing (rare), use `blocking_item_id` as the title fallback.
6. Render `dashboard/templates/fragments/batch_overlap_modal.html` with context:
   ```python
   {
       "held_item_id": held_item_id,
       "project_id": project_id,
       "sections": [
           {"blocking_item_id": "<id>", "blocking_item_title": "<title>", "globs": ["...", "..."]},
           ...
       ],
       "empty": False,
   }
   ```
   Return HTTP 200.

### 3. Wire the route

Mount the route on the existing `batches` router. Match the URL pattern style used elsewhere in `dashboard/routers/batches.py` (kebab-case slug + ID). Do NOT introduce a new router file.

### 4. Patch the items-fragment template context

`dashboard/templates/fragments/batch_items_rows.html` is re-rendered on every htmx
live refresh by the existing `batch_items_fragment` handler
(`GET /batch/{batch_id}/fragment/items`, ~line 651 of `batches.py`). That handler
currently passes only `{"current_project": project, "items": items}` to the
template — it does **not** pass `batch`. S03's new trigger button embeds
`{{ batch.id }}` in its `hx-get` URL, so without `batch` in the context the URL
collapses to `/project/{slug}/batch//overlap/{id}` (empty `batch_id`) after the
first `batch-items-refresh` SSE swap — exactly while items are still held.

Fix it in this step: in `batch_items_fragment`, keep the return value of
`_get_batch_or_404(...)` (it is currently discarded on ~line 660 — mirror the
pattern already used by `batch_detail_header_fragment` on ~line 691) and add
`"batch": batch` to the `TemplateResponse` context dict. This is the **only**
change to an existing endpoint — do not alter its URL, status code, or response
shape.

### 5. Do NOT touch the modal template

Step S03 (`frontend-impl`) owns the new modal template, the trigger HTML, and the CSS. Your job is the endpoint + helper only. If the template does not yet exist when you test, you may add an empty stub `dashboard/templates/fragments/batch_overlap_modal.html` containing only `{# CR-00077 S01 stub — S03 fills this in #}` so the endpoint can be imported and instantiated. Mark this stub explicitly in your report's `notes`.

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Routers are thin — keep the helper pure; keep the route 15-25 lines.
- htmx GETs return fragments — the fragment template MUST NOT extend `base.html`.
- Use the `get_db()` dependency from `dashboard/dependencies.py`.

## TDD Requirement

Follow TDD for the helper (the route's behaviour is covered by S05 dashboard tests; you don't write its tests here):

1. **RED**: In a scratch test file (or paste into `tests/unit/test_batch_overlap_grouping.py` if you prefer, but S05 owns that file long-term), write a failing test for `group_overlap_events`: empty list → `[]`; single event → `[(id, globs)]`; two events same blocking item → only first; events to two different blocking items → both, original order. Run the targeted test and capture `tdd_red_evidence` (the `AssertionError` or `ImportError: cannot import name 'group_overlap_events'`).
2. **GREEN**: Implement the helper.
3. **REFACTOR**: tighten typing.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix formatting drift.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

Run only your targeted tests. Do **NOT** run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "CR-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/batches.py",
    "dashboard/templates/fragments/batch_overlap_modal.html"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed, 0 failed",
  "tdd_red_evidence": "tests/unit/...::test_group_overlap_events_empty — ImportError: cannot import name 'group_overlap_events' from dashboard.routers.batches",
  "blockers": [],
  "notes": "If you created the modal template stub, list it here so S03 knows to overwrite it."
}
```
