# I-00101_S03_Frontend_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S03
**Agent**: Frontend

---

## ⛔ Docker is off-limits

Standard policy (see `docs/IW_AI_Core_Agent_Constraints.md`). Read-only `docker ps/inspect/logs` allowed; everything else forbidden.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00101/reports/I-00101_S01_Backend_report.md` — S01 report (helpers available)
- `orch/daemon/scope_amendment.py` — pure helpers from S01 (you import these)
- `dashboard/routers/actions.py` — existing `restart_step` (around line 323) and event-emit helper `_emit`
- `dashboard/routers/items.py` — existing item-detail render path that supplies the step list to the template
- `dashboard/routers/running.py` — existing `_query_failed_steps` (line 133)
- `dashboard/templates/components/status_badge.html` — existing status-badge mapping
- `dashboard/templates/fragments/item_steps_table.html` — existing steps table (action buttons around line 157)

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S03_Frontend_report.md` — Step report
- `dashboard/templates/components/scope_amend_modal.html` — NEW modal fragment

## Context

You are implementing the **Frontend** step of **I-00101**. S01 has produced the pure helpers in `orch/daemon/scope_amendment.py`. Your job is to surface scope-blocked steps in the UI and add the amend / revert actions.

Read the design doc's `## Affected Components`, `## Acceptance Criteria` (AC1, AC2, AC3), and `## Regression Prevention` (items 4 and 5) before opening any file.

## Requirements

### 1. `scope_blocked` badge variant

In `dashboard/templates/components/status_badge.html`, extend the status-to-class mapping with a `scope_blocked` key. Use Tailwind utilities consistent with the existing variants (the existing `needs_fix` row at line 14 uses `bg-warning text-warning-foreground`); the new variant should differentiate visually — e.g. an amber background with a slightly different glyph or border to read as "needs operator scope decision" not "needs fix". Add an icon if the existing variants use icons; otherwise rely on the label text.

The badge label is `Scope blocked` (two words, space-separated).

If `make css` reports "Nothing to be done" or the Tailwind CLI fails in the worktree (per CLAUDE.md I-00067 mitigation), append plain CSS rules directly to `dashboard/static/styles.css` — that file is served as-is and does not require Tailwind recompile.

### 2. Pass scope-violation data to the items table

In `dashboard/routers/items.py`, find the route that renders the item-detail page (which calls into `item_steps_table.html` via include/macro). For every step in status `needs_fix`, call `orch.daemon.scope_amendment.latest_scope_violation(db, step.id)` and attach the result onto the step object (or pass via a parallel dict keyed by `step.id`). The template should be able to read `step.scope_violations: list[str] | None` (or equivalent context name).

Choose the data-passing approach that fits the existing render path (look at how `last_error_map` is built in `running.py:_query_failed_steps` for one valid pattern). Avoid N+1 queries — build a single query keyed on all needs_fix step IDs.

### 3. Update `item_steps_table.html`

At lines ~157-167 (the action-buttons block for `failed | needs_fix` steps):

- When the step has `scope_violations` (i.e., it's scope-blocked), render the new `scope_blocked` badge in the status column instead of the default `status_badge` call. Use a `{% if step.scope_violations %}` branch.
- Add `title="Out-of-scope paths: …"` and `aria-label` attributes on the badge listing the offending paths so the operator sees them on hover and screen-readers announce them.
- In the actions column, when the step is scope-blocked, render **three** buttons (in this order): "Amend scope & restart" → opens modal via htmx (`hx-get="/project/{{ item.project_id }}/actions/item/{{ item.id }}/scope/amend-modal/{{ step.step_id }}"`); "Revert & restart" → a confirm-before-post button (`hx-post="/project/{{ item.project_id }}/actions/item/{{ item.id }}/scope/revert-and-restart/{{ step.step_id }}"` with `hx-confirm`); and the existing **Skip** button (in case the operator decides this isn't worth resolving). Hide the existing **Restart** button on scope-blocked rows — it would loop.
- When the step is in `needs_fix` but is **not** scope-blocked, render the existing Restart + Skip buttons unchanged.

The modal trigger uses `hx-target="body"` (or a dedicated `#modal-root` div if one already exists in the dashboard's base layout — check `dashboard/templates/base.html` for an existing modal mount point) and `hx-swap="beforeend"` so the modal HTML is appended to the page.

### 4. New `scope_amend_modal.html` partial

Create `dashboard/templates/components/scope_amend_modal.html`. It is a **fragment** — it MUST NOT extend `base.html` (per `dashboard/CLAUDE.md`).

Contents:

- Backdrop + centered modal card.
- Title: "Amend scope for {{ item.id }} / {{ step.step_id }}".
- A sentence explaining what will happen: "The selected paths will be added to this work item's `scope.allowed_paths` in both the worktree's manifest and the parent design-time copy. The step will then be re-queued."
- A `<form hx-post="/project/{{ item.project_id }}/actions/item/{{ item.id }}/scope/amend-and-restart/{{ step.step_id }}">` containing:
  - One checkbox per offending path (pre-checked), each `<input type="checkbox" name="paths" value="{{ path }}">`.
  - A read-only `<ul>` showing the current `scope.allowed_paths` list (passed from the GET endpoint).
  - Two buttons: "Cancel" (closes the modal via htmx target+swap clearing the modal container) and "Amend & restart" (submits the form).
- Use the project's existing CSS utility classes for modals if any exist (grep for `modal` in `dashboard/templates/`); fall back to plain CSS in `styles.css` otherwise.

### 5. Three new endpoints in `dashboard/routers/actions.py`

After the existing `restart_step` endpoint (line ~323), add three new endpoints. Use the same `@router.post(...)` decorator style and `_get_step`/`_get_item`/`_get_last_run`/`_emit`/`_action_response` helpers already in the file.

**GET `/item/{item_id}/scope/amend-modal/{step_id}`**

```python
@router.get(
    "/item/{item_id}/scope/amend-modal/{step_id}",
    response_class=HTMLResponse,
)
def scope_amend_modal(
    project_id: str,
    item_id: str,
    step_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    step = _get_step(db, project_id, item_id, step_id)
    violations = latest_scope_violation(db, step.id)
    if not violations:
        raise HTTPException(status_code=422, detail="Step is not scope-blocked")
    item = _get_item(db, project_id, item_id)
    # Resolve the worktree via the latest StepRun (WorkItem has no worktree_path column).
    last_run = _get_last_run(db, step.id)
    current_allowed = _load_current_allowed_paths(last_run, item_id) if last_run else []
    # _load_current_allowed_paths reads <worktree>/ai-dev/active/<id>/workflow-manifest.json
    # and returns scope.allowed_paths (list[str]); see helper definition below.
    return _render_fragment("components/scope_amend_modal.html", {
        "item": item,
        "step": step,
        "violations": violations,
        "current_allowed_paths": current_allowed,
    })
```

**POST `/item/{item_id}/scope/amend-and-restart/{step_id}`**

```python
@router.post(
    "/item/{item_id}/scope/amend-and-restart/{step_id}",
    response_class=Response,
)
def scope_amend_and_restart(
    project_id: str,
    item_id: str,
    step_id: str,
    paths: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    step = _get_step(db, project_id, item_id, step_id)
    violations = latest_scope_violation(db, step.id)
    if not violations:
        raise HTTPException(status_code=422, detail="Step is not scope-blocked; amend-scope is not applicable.")
    # Validate every submitted path was actually a violation
    bad = [p for p in paths if p not in violations]
    if bad:
        raise HTTPException(status_code=422, detail=f"Paths not in violation set: {bad}")

    item = _get_item(db, project_id, item_id)
    # `WorkItem` has NO `worktree_path` column. The worktree path lives on the
    # latest `StepRun.worktree_path` (see orch/db/models.py:807). Resolve it
    # via `_get_last_run(db, step.id)` — the same helper used by `restart_step`.
    last_run = _get_last_run(db, step.id)
    if last_run is None or not last_run.worktree_path:
        raise HTTPException(status_code=422, detail="No worktree path recorded for this step")
    worktree = Path(last_run.worktree_path)
    result = amend_allowed_paths(worktree, item_id, paths)

    _emit(db, "scope_amended_by_operator", project_id, item_id, "work_item",
          f"Amended scope.allowed_paths for {step_id}: added {result.paths_added}",
          {"step_id": step_id, "added_paths": result.paths_added,
           "manifests_updated": [str(p) for p in result.manifests_updated]})

    # Same DB mutations as restart_step (actions.py:323):
    last_run = _get_last_run(db, step.id)
    new_run = StepRun(
        step_id=step.id,
        run_number=(last_run.run_number + 1) if last_run else 1,
        status=RunStatus.pending,
        command=last_run.command if last_run else None,
        worktree_path=last_run.worktree_path if last_run else None,
        cli_tool=last_run.cli_tool if last_run else None,
        timeout_secs=last_run.timeout_secs if last_run else None,
    )
    db.add(new_run)
    step.status = StepStatus.pending
    step.started_at = None
    step.completed_at = None
    if item.status == WorkItemStatus.failed:
        item.status = WorkItemStatus.in_progress
    db.commit()

    return _action_response(f"Step {step_id} scope amended ({len(result.paths_added)} path(s)) and queued for restart.", toast_type="success")
```

**POST `/item/{item_id}/scope/revert-and-restart/{step_id}`** — same shape, but call `revert_paths_in_worktree` with the full `violations` list (operator confirmed via `hx-confirm`), emit `scope_reverted_by_operator` with `{step_id, reverted_paths, failed_paths}`, do NOT amend any manifest, do the same restart mutation.

**Important**: the existing `restart_step` at line 323 only allows `failed | skipped`. The new endpoints must work on `needs_fix` (which is what scope-blocked steps are in). Do NOT widen `restart_step` itself — write the new endpoints standalone.

### 6. Surface the badge in the global needs-attention table

In `dashboard/routers/running.py::_query_failed_steps`, after the existing `last_error_map` build (lines ~157-178), build a parallel `scope_violations_map: dict[int, list[str]]` keyed on `step.id` by calling `latest_scope_violation(db, step.id)` for each row (or a bulk-query equivalent for performance). Attach to the `FailedRow` and surface in the corresponding template (find the template that renders `FailedRow`; grep `_query_failed_steps` callers if unsure).

### 7. CSS class assertions reminder

Any inline UI test you happen to write (you shouldn't — S05 owns tests) MUST use the attribute-scoped form `class="badge-scope-blocked"`, not bare-substring `"badge-scope-blocked"` (per CLAUDE.md I-00067). The dashboard tests in S05 will follow this rule.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`:

- Routers are thin — business logic stays in `orch/`. The amend/revert composition here is the smallest reasonable router work; the file/git helpers live in `orch/daemon/scope_amendment.py`.
- Fragment templates do NOT extend `base.html`.
- htmx forms post HTML, not JSON — use `Form(...)` parameters in FastAPI.
- Tailwind classes — prefer existing utility classes from the rendered base; fall back to plain CSS in `styles.css` per the I-00067 mitigation if `make css` fails.

## TDD Requirement

Behavioural tests for the endpoints + badge are in S05. This step adds no behavioural test of its own — `tdd_red_evidence: "n/a — Frontend wires up helpers + templates; S05 owns the dashboard/integration tests"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck` (zero errors on touched Python files)
3. `make lint` (this also runs the template linter — Jinja2 `format`-filter rule + node check on dashboard JS)
4. `make css` if any new Tailwind classes were added. If `make css` reports "Nothing to be done" or fails, append plain CSS to `dashboard/static/styles.css` (per CLAUDE.md mitigation).

## Test Verification (NON-NEGOTIABLE)

Targeted run only — the new dashboard test does not exist yet (S05 writes it), so this is a sanity-check that nothing else under `tests/dashboard/` regresses:

```bash
uv run pytest tests/dashboard/ -v --no-cov
```

Do NOT run `make test-unit` or `make test-integration`. Those are S12/S13.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "I-00101",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/actions.py",
    "dashboard/routers/items.py",
    "dashboard/routers/running.py",
    "dashboard/templates/components/status_badge.html",
    "dashboard/templates/components/scope_amend_modal.html",
    "dashboard/templates/fragments/item_steps_table.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (existing tests/dashboard/ suite)",
  "tdd_red_evidence": "n/a — Frontend wires up helpers + templates; S05 owns the dashboard/integration tests",
  "blockers": [],
  "notes": ""
}
```
