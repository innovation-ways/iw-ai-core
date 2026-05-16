# CR-00056_S06_API_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S06
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations in this step.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `AC4–AC9`
- `dashboard/routers/items.py` — read the existing routes (especially `_get_steps()` at ~line 350, `StepDetail` at ~lines 54-76, and an existing fragment route like `step-runs/{step_id}` at ~line 1250 for the pattern)
- `dashboard/templates/fragments/activity_text_modal.html` — reference pattern for the fragment template (S08 will build the actual fragment; you build the route that returns it)
- `dashboard/CLAUDE.md` — fragment templates must NOT extend `base.html`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S06_API_report.md`

## Context

You are adding a new dashboard route and extending the `StepDetail` data container. The route returns an HTML fragment (the modal). The S08 (frontend) step builds the actual template; your job is the route plumbing + dataclass change. You may create a **placeholder** template (`dashboard/templates/fragments/prompt_text_modal.html`) so the route doesn't 500 in tests — S08 will replace its contents.

Read `dashboard/CLAUDE.md` and `orch/CLAUDE.md` first.

## Requirements

### 1. Extend the `StepDetail` dataclass

In `dashboard/routers/items.py` around lines 54-76, add a new field:

```python
has_prompt: bool = False  # True if any StepRun for this step has prompt_text or fix_prompt_text set
```

In `_get_steps()` (around line 350-492), populate `has_prompt` per step by checking whether any of the step's StepRuns has `prompt_text is not None` OR `fix_prompt_text is not None`. The simplest approach: a single subquery or aggregation alongside the existing run-counts query. If a query change is too invasive, a Python-side check over already-loaded StepRuns is acceptable — but avoid the N+1 trap (loading runs per step). Document your approach in the report.

For synthetic steps (`is_synthetic=True`, e.g., S00/MERGE), set `has_prompt=False` always — those have no agent prompt.

### 2. Add the prompt-modal route

In `dashboard/routers/items.py`, add a new route:

```python
@router.get("/item/{item_id}/step/{step_id}/prompt-modal", response_class=HTMLResponse)
def get_prompt_modal(
    request: Request,
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ...
```

Semantics:

- 404 if `WorkItem` with `(project_id, item_id)` does not exist.
- 404 if `WorkflowStep` with the given `step_id` is not part of that item.
- Query the WorkflowStep + all its StepRuns ordered by `run_number ASC`.
- Build a list of **sections** for the template:
  - The first StepRun's `prompt_text` (if non-NULL) becomes the "Initial Prompt" section.
  - For each subsequent StepRun where `fix_prompt_text` is non-NULL, add a "Fix Prompt (cycle N)" section with that StepRun's `fix_prompt_text` (use `run_number - 1` as cycle N, or look up the matching FixCycle row — whichever matches the daemon's numbering).
  - If NO sections result (no run has prompt_text or fix_prompt_text), return 404.
- The route returns the rendered `dashboard/templates/fragments/prompt_text_modal.html` fragment with context:
  ```python
  {
      "request": request,
      "item": work_item,        # for the header
      "step": workflow_step,    # for step_id, agent_label
      "prompt_file_display": workflow_step.prompt_file or "",
      "sections": [
          {"label": "Initial Prompt", "text": "..."},
          {"label": "Fix Prompt (cycle 1)", "text": "..."},
          ...
      ],
  }
  ```

Use `templates.TemplateResponse(...)` exactly as sibling fragment routes do — match the patterns in `_get_steps()`-adjacent routes.

### 3. Create a placeholder fragment template

Create `dashboard/templates/fragments/prompt_text_modal.html` with a minimal valid HTML stub:

```jinja
{# Placeholder — full implementation in S08 (frontend) #}
<div class="prompt-modal-backdrop" role="presentation"></div>
<div class="prompt-modal" role="dialog" aria-modal="true" aria-labelledby="prompt-modal-title">
  <h3 id="prompt-modal-title">Step {{ step.step_id }} prompt</h3>
  {% for section in sections %}
    <section>
      <h4>{{ section.label }}</h4>
      <pre>{{ section.text }}</pre>
    </section>
  {% endfor %}
</div>
```

This is enough for the dashboard tests in S11 to assert the route returns 200 with the right structure. S08 will replace this stub with the full styled, accessible modal + JS.

The template MUST NOT extend `base.html` (it's a fragment).

### 4. Authorization scope

`project_id` is validated by the FastAPI route signature (it's part of the prefix `/project/{project_id}`). Inside the handler:

- Load `WorkItem.where(project_id=project_id, id=item_id)`. If `None`, return 404 (use `HTTPException(status_code=404)`).
- Load `WorkflowStep.where(project_id=project_id, work_item_id=item_id, step_id=step_id)`. If `None`, return 404.
- Mismatched project_id → 404 (not 403, not 500). This matches sibling routes in `items.py`.

### 5. Do NOT touch unrelated routes

Only add the one new route and the `has_prompt` field. Do not refactor `_get_steps()` beyond the minimal additions. Do not rename anything.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Routers are thin — business logic stays in `orch/`. The aggregation here is small enough to live in the route, but if it grows, factor a helper.
- Fragment templates MUST NOT extend `base.html`.
- htmx endpoints return HTML fragments that swap in via `hx-target`.

## TDD Requirement

This is an API step. Follow RED → GREEN.

1. **RED**: Write `tests/dashboard/test_prompt_modal_route.py` with at least one test (e.g., `test_returns_200_with_prompt_text`). Run targeted: `uv run pytest tests/dashboard/test_prompt_modal_route.py::test_returns_200_with_prompt_text -v`. Confirm it fails with a 404 or AssertionError because the route does not exist yet. Capture the failure for `tdd_red_evidence`.
2. **GREEN**: Implement the route + placeholder template. Re-run; it passes.

The full coverage matrix (404 cases, sections, ARIA) lives in S11.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
uv run pytest tests/dashboard/test_items_router.py -v   # only if that file exists; otherwise skip
```

Do NOT run the full integration suite.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "api-impl",
  "work_item": "CR-00056",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/items.py",
    "dashboard/templates/fragments/prompt_text_modal.html",
    "tests/dashboard/test_prompt_modal_route.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "tests/dashboard/test_prompt_modal_route.py::test_returns_200_with_prompt_text — 404 Not Found (route undefined)",
  "blockers": [],
  "notes": "has_prompt populated via <chosen approach>; placeholder fragment for S08 to flesh out."
}
```
