# I-00076: Per-step CLI/runtime override `<select>` silently clears the override instead of setting it

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-10
**Reported By**: User (manual operator action on I-00075/S13 — chose "Claude Code + Opus 4.7", step launched on opencode/minimax anyway)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident touches a single Jinja2 template (and one test file). It does not touch any docker container, volume, or network state.

## ⛔ Migrations: agents generate, daemon applies

This incident leaves migrations unchanged. No alembic revision is generated; no schema changes are required. Existing tables only (`workflow_steps.agent_runtime_option_id`, `agent_runtime_options`).

## Description

In the dashboard's item-detail **Overview** tab, the per-step CLI/runtime override `<select>` — rendered for steps in `pending` or `failed` status — silently *clears* the step's runtime override instead of *setting* it to the chosen option. An operator who picks e.g. "Claude Code + Opus 4.7" for a step and then restarts it sees the step launched on the project default (`opencode` + `minimax/MiniMax-M2.7`) regardless. The override is never persisted, so the resolver's cascade falls straight through to the project default.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Particularly relevant: F-00081's runtime-option cascade (`orch/agent_runtime/resolver.py` — step override → item override → `projects.toml` lookup → catalogue default), the htmx patterns in `dashboard/CLAUDE.md`, and the prebuilt-Tailwind / plain-CSS rule (no new CSS classes are needed here).

## Browser Evidence

**Pre-fix evidence**: deferred — by the time the bug was diagnosed, a working-tree mitigation had already been applied to `dashboard/templates/fragments/item_overview.html` on the design host, so the broken on-screen state cannot be re-screenshotted. The bug is instead proven by the orchestration DB audit trail (`daemon_events`):

- Every `runtime_override_changed` event emitted for I-00075/S13 by the dashboard recorded `metadata->>'new_option_id' = null` — two events per operator action, ~90 ms apart (the redundant `htmx.trigger(this,'change')` double-fire). Three separate operator attempts (2026-05-10 06:42, 07:29, 08:20 UTC) all show `new_option_id: null`.
- `workflow_steps.agent_runtime_option_id` for I-00075/S13 stayed `NULL` across all of those attempts; every `step_runs` row for the step shows `cli_tool = opencode`, `agent_runtime_option_id = 1`, command `opencode run … --model minimax/MiniMax-M2.7`.
- After the working-tree mitigation, the same UI action recorded `new_option_id: 5` (a *single* event), `workflow_steps.agent_runtime_option_id = 5`, and the daemon launched the step with `claude -p … --model claude-opus-4-7` — confirming the diagnosis.

This audit excerpt is the canonical proof the bug existed. The S13 (qv-browser) verification below re-confirms correct behaviour end-to-end.

## Steps to Reproduce

1. Open the dashboard, navigate to any work item that has a step in `pending` or `failed` status (item-detail page → **Overview** tab).
2. In that step's row, open the **CLI** column `<select>` and pick a non-default option (e.g. "Claude Code + Opus 4.7").
3. Restart the step (↻ button → confirm), or wait for the daemon to relaunch it.
4. Inspect the new `step_runs` row (or the step's CLI badge once it is running).

**Expected**: the step's `agent_runtime_option_id` is set to the chosen option; the next launch uses that option's `cli_tool` / `model` (e.g. `claude --model claude-opus-4-7`). A single `runtime_override_changed` event is emitted with `new_option_id` = the chosen id.

**Actual**: the PATCH to `…/step/{step_id}/runtime-override` arrives with **no `option_id` form field**, so `patch_step_runtime_override` treats it as `None` and writes `workflow_steps.agent_runtime_option_id = NULL`. The resolver cascade then falls through to the `projects.toml` default (`opencode` + `minimax/MiniMax-M2.7`). Two `runtime_override_changed` events are emitted, both with `new_option_id: null`.

## Browser Verification Script

The post-fix verification is run by the qv-browser agent inside the isolated worktree compose stack (env-driven base URL / credentials — no hardcoded ports). It must, against the worktree's source:

1. Open an item that has a `failed`/`pending` step, snapshot the step row's CLI `<select>`, select a non-default option, and assert the corresponding `PATCH …/runtime-override` returned `204` and that exactly **one** `runtime_override_changed` row landed with the chosen `new_option_id` (verified via the item's logs/events tab or a DB query inside the e2e stack), and that `workflow_steps.agent_runtime_option_id` equals the chosen id.
2. Confirm the rendered `<select>` markup carries `hx-disabled-elt="this"` and **no** `onchange="…disabled…"` / `htmx.trigger(` attribute.
3. Confirm adjacent overview-tab flows (step pipeline strip, restart/skip buttons, the "Apply to remaining steps" bulk control) still render and function, with no new console errors.

The exact commands live in `prompts/I-00076_S13_BrowserVerification_prompt.md`.

## Root Cause Analysis

`dashboard/templates/fragments/item_overview.html` — the editable-step CLI `<select>` (≈ lines 78–88 at current `main` HEAD):

```html
<select
  class="… w-24"
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-swap="none"
  name="option_id"
  onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');">
```

Two defects in the `onchange` handler:

1. **`this.disabled = true` runs before htmx serializes the request.** htmx's `shouldInclude()` returns `false` for any element with the `disabled` attribute (vendored `dashboard/static/vendor/htmx/htmx.min.js`, htmx 2.0.3: `if (t.name === "" || t.name == null || t.disabled || …) return false`). So the `<select>`'s own `name="option_id"` value is excluded from the PATCH body. `dashboard/routers/runtime_overrides.py::patch_step_runtime_override` declares `option_id: int | None = Form(default=None)`, sees `None`, runs `_validate_option_id(db, None) → None`, and writes `step.agent_runtime_option_id = None`. The override is *cleared*, never *set*.
2. **`htmx.trigger(this, 'change')` is redundant and double-fires the request.** A `<select>` already triggers htmx on `change` by default, so the explicit re-dispatch causes a second PATCH (hence the two `runtime_override_changed` events per action).

Downstream, `orch/agent_runtime/resolver.py::resolve_runtime` does exactly what it should: step override `NULL` → item override `NULL` → `projects.toml` lookup for `iw-ai-core` (`cli_tool=opencode`, `model=minimax/MiniMax-M2.7`) → `agent_runtime_options` row id 1. The launch in `orch/daemon/batch_manager.py::_launch_step` (and `orch/daemon/fix_cycle.py::_launch_fix_agent`) then runs `opencode … --model minimax/MiniMax-M2.7`. No backend change is needed — the bug is entirely in the template's client-side handler.

The intent of the original `onchange` was UX feedback (grey-out / lock the control while the PATCH is in flight). htmx provides `hx-disabled-elt` for exactly this: it adds `disabled` to the element **after** the request parameters are computed and re-enables it on completion, so the element's value is still serialized.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/item_overview.html` (modify) | The editable-step CLI `<select>`'s `onchange` handler drops the chosen `option_id` and double-fires the PATCH. Fix: remove the self-disabling `onchange` + redundant `htmx.trigger`; add `hx-disabled-elt="this"`. |
| `dashboard/routers/runtime_overrides.py` (read-only) | `patch_step_runtime_override` is correct — absent `option_id` legitimately means "clear / inherit" (the `— inherit —` option). No change. |
| `orch/agent_runtime/resolver.py` (read-only) | Cascade is correct; it was correctly falling through because the override was never persisted. No change. |
| `tests/dashboard/test_runtime_override_templates.py` (modify, or new sibling test file) | Add a regression test asserting the rendered editable `<select>` carries `hx-disabled-elt="this"` and does **not** carry a self-disabling `onchange` / `htmx.trigger(`. Add a server-side test that `patch_step_runtime_override` persists a valid `option_id` and that the resolver then picks it. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | In `item_overview.html`, replace the editable-step CLI `<select>`'s `onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');"` with `hx-disabled-elt="this"` (and drop the now-redundant `onchange` entirely). Add a short comment explaining why the control must not self-disable. Touch nothing else in the file. | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | tests-impl | Regression + reproduction tests (see "Test to Reproduce") | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Cross-agent final review of S01..S04 | — |
| S06 | qv-gate (lint) | `make lint` | — |
| S07 | qv-gate (format) | `make format-check` | — |
| S08 | qv-gate (typecheck) | `make type-check` | — |
| S09 | qv-gate (arch-check) | `make arch-check` | — |
| S10 | qv-gate (security-sast) | `make security-sast` | — |
| S11 | qv-gate (unit-tests) | `make test-unit` | — |
| S12 | qv-gate (integration-tests) | `make test-integration` (timeout 900) | — |
| S13 | qv-browser | Browser verification of the fix end-to-end in the isolated worktree stack | — |
| S14 | self-assess-impl | Self-assessment via the iw-item-analyze skill (project has `self_assess = true`) | — |

No `frontend-tsc` / `frontend-tests` gate: this project has no `frontend/` directory; the dashboard's `tests/dashboard/` suite is exercised by `make test-integration` (which runs `pytest tests/integration/ tests/dashboard/`).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no alembic revision generated.

### Code Changes

- **Files to modify**: `dashboard/templates/fragments/item_overview.html` (the editable-step CLI `<select>` only); `tests/dashboard/test_runtime_override_templates.py` (add regression test) — a new sibling test file `tests/dashboard/test_i00076_runtime_override_select.py` is also acceptable.
- **Nature of change**: Remove a self-disabling inline `onchange` handler that breaks htmx form serialization; replace with `hx-disabled-elt="this"`; drop the redundant `htmx.trigger(this,'change')`. Add tests.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00076_Issue_Design.md` | Design | This document |
| `I-00076_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00076_S01_Frontend_prompt.md` | Prompt | S01 — apply the `hx-disabled-elt` fix |
| `prompts/I-00076_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 — per-agent review of S01 |
| `prompts/I-00076_S03_Tests_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00076_S04_CodeReview_Tests_prompt.md` | Prompt | S04 — per-agent review of S03 |
| `prompts/I-00076_S05_CodeReview_Final_prompt.md` | Prompt | S05 — cross-agent final review |
| `prompts/I-00076_S13_BrowserVerification_prompt.md` | Prompt | S13 — qv-browser verification |
| `prompts/I-00076_S14_SelfAssess_prompt.md` | Prompt | S14 — self-assessment |

Reports are created during execution under `ai-dev/active/I-00076/reports/`.

## Test to Reproduce

The behaviour that broke is client-side (htmx form serialization), so the *reproduction* test is a template-render assertion plus a server-side persistence assertion. Both fail against pre-fix code and pass after.

**Test-file location**: `tests/dashboard/` — these tests render a Jinja2 template via the dashboard `client` fixture and/or call a FastAPI route, so they must live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py`).

```python
def test_i00076_editable_step_select_does_not_self_disable(client, db_session):
    """Pre-fix: the <select> had onchange='…this.disabled=true; htmx.trigger(this,'change')'.
    Post-fix: it carries hx-disabled-elt='this' and no self-disabling onchange / redundant trigger."""
    # Arrange: seed a project + work item + a workflow step in 'failed' status, plus runtime options.
    # Act:
    html = client.get(f"/project/{project_id}/item/{item_id}/tab/overview").text
    # Assert (semantic, not shape):
    assert 'hx-disabled-elt="this"' in html
    assert "this.disabled=true" not in html
    assert "htmx.trigger(this" not in html
    # The PATCH endpoint and option_id field are still present:
    assert f'hx-patch="/project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override"' in html
    assert 'name="option_id"' in html


def test_i00076_patch_step_override_persists_chosen_option(client, db_session):
    """A PATCH carrying a real option_id sets workflow_steps.agent_runtime_option_id;
    an absent option_id clears it (the '— inherit —' path)."""
    # Arrange: failed step, enabled AgentRuntimeOption id=5 ('claude', 'claude-opus-4-7').
    # Act + Assert: PATCH with option_id=5 → 204, step.agent_runtime_option_id == 5.
    # Act + Assert: PATCH with no body → 204, step.agent_runtime_option_id is None.
```

If a non-template integration test of `resolve_runtime` is added, it MUST assert the *specific* resolved row (e.g. `assert resolved.cli_tool == "claude" and resolved.model == "claude-opus-4-7"`), not merely that a row was returned.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a work item with a step in 'pending' or 'failed' status, shown in the Overview tab
When the operator selects a non-default runtime option in that step's CLI <select>
Then the PATCH to …/step/{step_id}/runtime-override carries option_id=<chosen id>,
  workflow_steps.agent_runtime_option_id is set to <chosen id>,
  exactly one runtime_override_changed event is emitted with new_option_id=<chosen id>,
  and the next launch of that step uses the chosen option's cli_tool/model
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing tests pass — the rendered editable <select> carries hx-disabled-elt="this",
  carries no self-disabling onchange and no htmx.trigger(this,'change'),
  and patch_step_runtime_override persists a valid option_id (and clears on an absent one)
```

### AC3: No regression to the "inherit" path

```
Given a step with an existing runtime override
When the operator selects the '— inherit —' option (empty value)
Then the PATCH clears workflow_steps.agent_runtime_option_id (back to NULL / inherit) as before
```

## Regression Prevention

- A template-render regression test (above) pins the corrected `<select>` markup, so re-introducing a self-disabling `onchange` or the redundant `htmx.trigger` fails CI.
- The fix itself replaces an error-prone hand-rolled pattern with htmx's purpose-built `hx-disabled-elt`, which is the documented way to lock a control during an in-flight request without dropping its value.
- A short inline comment in `item_overview.html` records *why* the control must not self-disable, so the next person editing it doesn't "helpfully" re-add `disabled=true`.

## Dependencies

- **Depends on**: F-00081 (introduced the runtime-override `<select>` and the cascade resolver)
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/fragments/item_overview.html`
- `tests/dashboard/test_runtime_override_templates.py`
- `tests/dashboard/test_i00076_runtime_override_select.py`

## TDD Approach

- Reproducing test: `test_i00076_editable_step_select_does_not_self_disable` (template render) — fails pre-fix because the rendered HTML contains `this.disabled=true` / `htmx.trigger(this, 'change')` and lacks `hx-disabled-elt`.
- Unit / dashboard tests: `test_i00076_patch_step_override_persists_chosen_option` — `patch_step_runtime_override` sets the override for a valid id and clears it for an absent one.
- Integration tests: optional `resolve_runtime` assertion that with `workflow_steps.agent_runtime_option_id` set, the resolver returns that exact (cli_tool, model) pair rather than the project default.

**Assertion scoping for CSS / attribute strings** — when asserting on rendered HTML, anchor on the attribute form (`assert 'hx-disabled-elt="this"' in html`, not a bare `hx-disabled-elt`) so a stray token in a script block or comment can't false-positive (I-00067).

## Notes

- A working-tree mitigation has already been applied on the design host (`dashboard/templates/fragments/item_overview.html` was edited to use `hx-disabled-elt="this"` and drop the bad `onchange`), and verified manually: re-selecting "Claude Code + Opus 4.7" via the UI persisted `agent_runtime_option_id = 5` and the daemon launched the step with `claude --model claude-opus-4-7`. This incident exists to land that fix in `main` properly (with review, tests, and a regression guard). The agent should implement the fix from scratch off `main` HEAD per the prompt — do not rely on any uncommitted working-tree state.
- Out of scope: the unrelated cosmetic tweaks to the same `<select>` that are sitting uncommitted on the design host (`w-24` → `w-48` width, `cli_label` → `display_name` in the option text). Those belong to separate in-progress work; do not include them.
- Cosmetic follow-up (not required here): the editable `<select>` pre-selects the *last run's* option (e.g. opencode/minimax for a failed step), not `— inherit —`, which is mildly misleading. Harmless — picking a value still sets the override correctly. Leave for a future CR if desired.
