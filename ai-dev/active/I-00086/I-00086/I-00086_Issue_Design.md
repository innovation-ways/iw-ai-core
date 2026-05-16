# I-00086: Runtime override controls give no UI feedback — "Apply" appears to do nothing

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-15
**Reported By**: User report (sergio)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This item does NOT modify any docker-compose file.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged — no schema changes are required.

## Description

On the item-detail page (Overview tab → steps table), changing a step's runtime/model via either the per-step CLI `<select>` or the bulk "Apply to remaining steps" button silently succeeds: no confirmation toast appears, and the read-only **Model** column stays stale until the user manually refreshes the page. The DB IS updated, but every UI signal a user would use to confirm the action is missing — the fix is functional but invisible. Users repeatedly click the controls thinking they didn't work.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Specifically:

- `dashboard/CLAUDE.md` — htmx fragment patterns, toast component contract, "routers are thin" rule, prebuilt CSS rule.
- `tests/CLAUDE.md` — test fixture rules, the `client` fixture lives in `tests/dashboard/conftest.py`, no live DB in tests.

## Steps to Reproduce

1. Approve any work item that has pending steps and run the daemon long enough that at least one step is `pending`, or use the historical case where an item has a `failed` step that hasn't been restarted. (Any item-detail page with at least one editable step suffices.)
2. Open the dashboard at `http://localhost:9900/project/iw-ai-core/item/<ID>`.
3. In the **Overview** tab, locate the steps table. Each editable step (status `pending` or `failed`) shows a CLI `<select>` in its row. The footer of the table shows the **"Apply to remaining steps:"** selector + **Apply** button.
4. Pick a runtime option in the per-step `<select>`. → Browser shows no feedback. The adjacent read-only **Model** column still shows the previous value (often `—` or `inherit`).
5. Pick a runtime option in the bulk selector, click **Apply**. → Same: no toast, no visible row update.
6. Hard-refresh the page. → The Model column now shows the new value(s).

**Expected**:

- A success toast appears (e.g. `Model updated for N step(s)` for bulk, `Model updated` for per-step).
- The steps table re-renders in place so each affected row's **Model** column reflects the new option.
- No manual refresh is required to see the updated values.
- The bulk-apply "0 editable steps" branch shows an `info`/`warning` toast (`No editable steps to update`) rather than silently doing nothing.

**Actual**: Both endpoints return `204 No Content`. With `hx-swap="none"` on both controls, htmx swaps nothing and no client-visible event is emitted. The user sees no change.

## Browser Evidence

Deferred — the bug is well-described and reproducible. The `qv-browser` step at execution time will capture screenshots of:

1. The reproduction (post-action UI showing the stale Model column) — `evidences/post/I-00086_v1_per_step_after.png` and `_v2_bulk_after.png`.
2. The fixed behavior (Model column updated, toast visible) — `evidences/post/I-00086_v3_per_step_fix.png` and `_v4_bulk_fix.png`.

No pre-fix screenshot is mandated here; the bug is "absence of feedback" and is fully described by the inline HTML quoted in **Root Cause Analysis** below.

## Browser Verification Script

(Captured at execution time by the `qv-browser` step using the env-supplied `$IW_BROWSER_BASE_URL`. The verification spec lives in `prompts/I-00086_S14_BrowserVerification_prompt.md`. Reproduction flow: open the project's history list, open an item with editable steps, change the per-step `<select>`, then change the bulk selector and click Apply.)

## Root Cause Analysis

Two controls in `dashboard/templates/fragments/item_overview.html` mutate runtime overrides via PATCH but tell htmx not to swap anything and accept a body-less response — and the corresponding backend endpoints return `204 No Content`:

### Per-step `<select>` — `dashboard/templates/fragments/item_overview.html:83-93`

```html
<select
  class="text-xs border border-border rounded bg-background text-foreground px-1 py-0.5 cursor-pointer w-48"
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-swap="none"
  hx-disabled-elt="this"
  name="option_id">
  ...
</select>
```

### Bulk Apply button — `dashboard/templates/fragments/item_overview.html:192-198`

```html
<button
  class="text-xs bg-secondary text-secondary-foreground hover:bg-secondary/80 px-2 py-0.5 rounded border border-border transition-colors"
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/runtime-override/bulk"
  hx-vals="javascript:{option_id: document.getElementById('bulk-runtime-option').value}"
  hx-swap="none">
  Apply
</button>
```

### Endpoints — `dashboard/routers/runtime_overrides.py`

- `patch_step_runtime_override` (around line 200, single-step PATCH) → `return Response(status_code=204)`.
- `patch_bulk_runtime_override` (line 244-292) → `return Response(status_code=204)`.

Neither sets an `HX-Trigger` header, neither returns a body. The page already wires `htmx:beforeOnLoad` to `HX-Trigger.showToast` (`dashboard/templates/pages/project/item_detail.html:158-167`), so the toast hookup is already present — the endpoints just don't emit the trigger. The read-only **Model** column (`item_overview.html:103-111`) is computed from `step.runtime_option_id` and `runtime_options` and only refreshes when the steps fragment is re-rendered.

The existing comment at `item_overview.html:78-82` warns NOT to disable the per-step `<select>` in an onchange handler (htmx omits disabled controls from the request body and the override gets cleared instead of set). Any fix must preserve `hx-disabled-elt="this"`.

The bulk endpoint also silently skips non-editable steps — the count the user sees in the toast must be the **number actually updated**, not the number of rows currently in the table.

### Precedent for the fix

`dashboard/routers/staleness.py:132` already demonstrates the exact pattern this fix should adopt: a 204 (now: HTML fragment) response carrying `HX-Trigger: {"showToast": {"message": "...", "type": "success"}}`. The page-level JS hook in `pages/project/item_detail.html:158-167` consumes `trigger.showToast` and routes it to `showToast(...)` from `components/toast.html`.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/routers/runtime_overrides.py` | Both PATCH endpoints return 204 with no body and no `HX-Trigger` — frontend has nothing to render and no signal to display. |
| `dashboard/templates/fragments/item_overview.html` | Both controls use `hx-swap="none"` with no `hx-target` and no toast-trigger consumer wired specifically to these controls. |
| `dashboard/templates/pages/project/item_detail.html` | Already supports `HX-Trigger.showToast` and an optional `reload` flag — no change needed beyond confirmation. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | API | Update both PATCH endpoints in `runtime_overrides.py`: render the steps-table fragment as response body, emit `HX-Trigger: showToast` header, report the count actually updated for bulk (and `info`-style toast when 0 steps were eligible). Add small helper that renders the new `item_steps_table.html` fragment. | — |
| S02 | CodeReview_API | Review S01 | — |
| S03 | Frontend | Extract `dashboard/templates/fragments/item_steps_table.html` (steps table + bulk-apply footer); update `item_overview.html` to `{% include %}` it and add `hx-target="#item-steps-table"` / `hx-swap="outerHTML"` to both controls. Preserve `hx-disabled-elt="this"` and the existing CLI/Model-column rendering. | — |
| S04 | CodeReview_Frontend | Review S03 | — |
| S05 | Tests | Reproduction + regression tests: both endpoints now return HTML and set `HX-Trigger`; bulk reports actual updated count; bulk "0 editable steps" branch returns `info`-toast trigger; per-step toast fires on success. | — |
| S06 | CodeReview_Tests | Review S05 | — |
| S07 | CodeReview_Final | Cross-agent global review | — |
| S08 | QV: lint | `make lint` | — |
| S09 | QV: format | `make format-check` | — |
| S10 | QV: typecheck | `make type-check` | — |
| S11 | QV: security-sast | `make security-sast` | — |
| S12 | QV: unit-tests | `make test-unit` | — |
| S13 | QV: integration-tests | `make allure-integration` | — |
| S14 | QV: browser | qv-browser verification of both controls | — |
| S15 | SelfAssess | Self-assessment of execution (project has `self_assess = true`) | — |

Agent slugs: `api-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No schema changes. The runtime override is already persisted via `WorkflowStep.agent_runtime_option_id`; only the response contract changes.

### Code Changes

- **Files to modify**:
  - `dashboard/routers/runtime_overrides.py` — response shape: HTML fragment body + `HX-Trigger` header for both endpoints; bulk endpoint must report `count of editable steps actually changed`.
  - `dashboard/templates/fragments/item_overview.html` — wire `hx-target`/`hx-swap`; include the new sub-fragment.
- **Files to create**:
  - `dashboard/templates/fragments/item_steps_table.html` — extracted sub-fragment containing the `<table id="item-steps-table">` and the bulk-apply footer (the agent may pick a slightly different ID, but the ID must be quoted in the design's `hx-target`).
  - `tests/dashboard/test_runtime_override_response.py` — reproduction + regression coverage (test file path is illustrative; the agent may place it inside an existing `tests/dashboard/test_runtime_overrides*.py` if one exists).
- **Nature of change**: API response shape change (204 → 200 with fragment body + header) + template restructure to make the steps table independently swappable.

## File Manifest

All files for this work item live under `ai-dev/active/I-00086/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00086_Issue_Design.md` | Design | This document |
| `I-00086_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00086_S01_API_prompt.md` | Prompt | S01 fix implementation (router) |
| `prompts/I-00086_S02_CodeReview_API_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00086_S03_Frontend_prompt.md` | Prompt | S03 fix implementation (templates) |
| `prompts/I-00086_S04_CodeReview_Frontend_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00086_S05_Tests_prompt.md` | Prompt | S05 reproduction + regression tests |
| `prompts/I-00086_S06_CodeReview_Tests_prompt.md` | Prompt | S06 review of S05 |
| `prompts/I-00086_S07_CodeReview_Final_prompt.md` | Prompt | S07 global review |
| `prompts/I-00086_S14_BrowserVerification_prompt.md` | Prompt | S14 qv-browser spec |
| `prompts/I-00086_S15_SelfAssess_prompt.md` | Prompt | S15 self-assessment |

Reports are created during execution in `ai-dev/active/I-00086/reports/`.

## Test to Reproduce

The reproducing test lives under `tests/dashboard/` because it drives FastAPI routes via the dashboard `client` fixture (which is only registered in `tests/dashboard/conftest.py`).

```python
def test_i00086_bulk_apply_returns_fragment_and_toast_trigger(client, db_session, seeded_item):
    """Bulk PATCH must return the rendered steps-table fragment AND an HX-Trigger showToast header.

    FAILS before the fix (response is 204 with empty body and no HX-Trigger).
    PASSES after the fix.
    """
    # Arrange: item with at least 2 editable (pending) steps + a non-default runtime option.
    project_id, item_id, option_id, editable_step_count = seeded_item

    # Act
    resp = client.patch(
        f"/project/{project_id}/api/item/{item_id}/runtime-override/bulk",
        data={"option_id": option_id},
    )

    # Assert — semantic, not shape
    assert resp.status_code == 200, f"expected 200 with fragment, got {resp.status_code}"
    assert 'id="item-steps-table"' in resp.text, "response must include the steps-table fragment"

    import json
    trigger = json.loads(resp.headers["HX-Trigger"])
    assert "showToast" in trigger
    toast = trigger["showToast"]
    assert toast["type"] == "success"
    assert toast["message"] == f"Model updated for {editable_step_count} step(s)"
```

## Browser Verification Test

The qv-browser step at S14 must verify, against the isolated worktree E2E stack:

1. Open an item-detail page with at least one editable step.
2. Change the per-step CLI `<select>` to a non-default option.
3. Verify a success toast appears AND the **Model** column in the same row updates without a manual refresh.
4. Use the **"Apply to remaining steps:"** selector + Apply button to set a different non-default option.
5. Verify a success toast appears AND every editable row's **Model** column reflects the chosen option.
6. Verify no new console errors during any of the above.

Full Playwright CLI script lives in `prompts/I-00086_S14_BrowserVerification_prompt.md`.

## Acceptance Criteria

### AC1: Per-step model dropdown gives visible feedback

```
Given an item-detail page with at least one editable step
When the user selects a non-default runtime option in that step's CLI <select>
Then a success toast "Model updated" (or equivalent) appears
And the Model column in that row updates to show the new option label
And no manual page refresh is required
```

### AC2: Bulk Apply gives visible feedback and reports the correct count

```
Given an item-detail page with N >= 1 editable steps
When the user picks a non-default runtime option in the "Apply to remaining steps:" selector and clicks Apply
Then a success toast "Model updated for N step(s)" appears (N = number actually changed)
And the Model column in every editable row reflects the chosen option
And no manual page refresh is required
```

### AC3: Bulk Apply handles the zero-editable-steps case

```
Given an item-detail page with 0 editable steps (e.g. all steps are running, done, or merged)
When the user picks any option in the "Apply to remaining steps:" selector and clicks Apply
Then an info or warning toast "No editable steps to update" appears
And no row in the table changes
And the response does not error
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test for AC1/AC2/AC3 passes
And it would fail against pre-fix code
```

## Regression Prevention

- **Response-contract assertion**: the new tests assert specific values (`'id="item-steps-table"'` in body, `"HX-Trigger"` header with `showToast` payload of the correct `type` and exact `message`), not just status code. A future regression that returns 204 again will fail the test.
- **Sub-fragment isolation**: extracting `fragments/item_steps_table.html` makes "swap just the steps table" a first-class pattern; future controls in the same area can reuse the same `hx-target`/`hx-swap` shape without re-bundling the whole overview.
- **Toast trigger consistency**: by going through the existing `HX-Trigger.showToast` channel rather than inline JS, every future action button gets a tested feedback path for free.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/routers/runtime_overrides.py`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/item_steps_table.html`
- `tests/dashboard/**`
- `ai-dev/active/I-00086/**`
- `ai-dev/archive/I-00086/**`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_runtime_override_response.py::test_i00086_bulk_apply_returns_fragment_and_toast_trigger` — fails on `assert resp.status_code == 200` against pre-fix code (current behavior returns 204).
- **Unit / dashboard tests** (added in S05):
  - Bulk endpoint: success path with N editable steps → 200, fragment body, success toast with `N step(s)`.
  - Bulk endpoint: zero-editable-steps branch → 200, fragment body, `info` toast `No editable steps to update`, no DB writes (no `runtime_override_changed` DaemonEvent emitted).
  - Per-step endpoint: success → 200, fragment body, success toast.
  - Per-step endpoint: clearing override (option_id=None) → 200, fragment body, success toast.
  - Validation: invalid `option_id` (or unknown step/item) → 404, no toast trigger.
  - Fragment content assertion: the returned HTML includes the **updated** model label for every editable step.
- **Integration tests**: rely on the existing dashboard `client` fixture; no new testcontainer scenarios are required.

**Assertion scoping for CSS class names**: tests should assert on attribute-scoped HTML strings (`'id="item-steps-table"'`) rather than bare substrings, per `tests/CLAUDE.md`.

## Notes

- The current dropdown in `item_overview.html:84-93` uses `hx-disabled-elt="this"` deliberately — see the inline comment at line 78-82. Any change must preserve this; do NOT add an `onchange="this.disabled=true"` handler.
- The bulk-control bug is the user-reported symptom; the per-step bug has the same root cause and is included in this incident to avoid filing a second one.
- The page-level toast wiring in `item_detail.html:158-167` reads `trigger.showToast` and supports a `reload` flag (currently unused by this incident). We do NOT want to set `reload: true` — the whole point of the fix is to avoid a full reload.
- The bulk endpoint currently passes `option_id` as `Form(default=None)`. The new tests should keep posting via form-encoded body to preserve the existing wire contract — htmx serializes `hx-vals` as form data by default.
- Self-assess step (S15) is included because `projects.toml` declares `self_assess = true` for `iw-ai-core`.
