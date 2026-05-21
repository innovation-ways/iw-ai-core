# CR-00070: Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns

**Type**: Change Request
**Priority**: Medium
**Reason**: UX — the runtime-override dropdowns hide which agent/model a step will actually use behind the word "Inherit", so an operator cannot know the effective runtime until *after* the step has executed.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR introduces no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This CR leaves migrations unchanged** — no schema change, no new Alembic revision. It is a dashboard display change plus one pure-Python resolver helper.

## Description

Every workflow step's runtime-override `<select>` defaults its empty option to the literal text `— inherit —`, which obscures the agent + model that will actually run. This CR replaces that label — on both the per-step dropdown and the "Apply to remaining steps" bulk dropdown — with the *resolved* runtime option's display name suffixed with `(inherited)`, e.g. `Pi + MiniMax 2.7 (inherited)`. The `value=""` mechanism is unchanged; only the visible label changes.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Relevant background: runtime resolution for a step follows a fixed cascade implemented in `orch/agent_runtime/resolver.py:resolve_runtime()` — step override → item override → `projects.toml` `(cli_tool, model)` lookup → `agent_runtime_options.is_default=true` catalogue row. The dashboard steps table is the htmx fragment `dashboard/templates/fragments/item_steps_table.html`.

## Current Behavior

The work-item steps table (`dashboard/templates/fragments/item_steps_table.html`) renders a runtime `<select>` for every editable step (status `pending` or `failed`), plus one "Apply to remaining steps" bulk `<select>` at the table footer.

- The per-step `<select>` (line ~74) opens with `<option value="">— inherit —</option>`, then one `<option>` per enabled `agent_runtime_options` row labelled with that row's `display_name`.
- The bulk "Apply to remaining steps" `<select>` (line ~244) opens with the same `<option value="">— inherit —</option>`, then one `<option>` per enabled row labelled with `cli_label / model_label` — an inconsistent format versus the per-step list.
- When a step has no explicit override and the item has no item-level override, `StepDetail.runtime_option_id` is `None`, so the empty option is selected and the operator sees only `— inherit —`. The actual `(cli_tool, model)` that will run — resolved by the daemon's `resolve_runtime()` cascade at launch time — is never surfaced in the UI.
- The effective runtime first becomes visible only *after* the step runs, when the CLI and Model columns show the executed option (e.g. `Pi` / `MiniMax 2.7`).

`item_steps_table.html` is rendered by three code paths, each of which independently builds the `runtime_options` template context:
1. `dashboard/routers/items.py::item_detail` (the full item page, which includes `item_overview.html` → `item_steps_table.html`).
2. `dashboard/routers/items.py::item_tab_overview` (the htmx overview-tab fragment).
3. `dashboard/routers/runtime_overrides.py::_render_steps_fragment` (the steps-table fragment returned by the runtime-override PATCH endpoints).

## Desired Behavior

The empty `<option value="">` in **both** the per-step `<select>` and the "Apply to remaining steps" `<select>` displays the *effective inherited* runtime option's `display_name` suffixed with ` (inherited)` — for example `Pi + MiniMax 2.7 (inherited)`.

- The displayed value reflects the **true resolution cascade**: when the work item has an item-level override, the inherited label shows that option; otherwise it shows the `projects.toml` lookup result, falling back to the catalogue default. It must match what the daemon's `resolve_runtime()` would pick for a step with no step-level override.
- The empty option keeps `value=""`. Selecting it still means "no explicit step/bulk override" — the override-clearing behaviour of the PATCH endpoints is unchanged.
- The `(inherited)` suffix keeps the option visually distinguishable from an explicitly-pinned option that happens to resolve to the same agent + model.
- The bulk dropdown's non-empty options also use each row's `display_name` (consistent with the per-step list), replacing the current `cli_label / model_label` format.
- Edge case: if no runtime option can be resolved (the `agent_runtime_options` catalogue has no enabled rows at all), the page must still render — the empty option falls back to a neutral label (`— inherit —`) rather than raising and breaking the steps table.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `item_steps_table.html` per-step `<select>` empty option | `— inherit —` | `{{ inherited_runtime_label }} (inherited)` |
| `item_steps_table.html` bulk `<select>` empty option | `— inherit —` | `{{ inherited_runtime_label }} (inherited)` |
| `item_steps_table.html` bulk `<select>` non-empty options | `cli_label / model_label` | `display_name` (consistent with per-step list) |
| `orch/agent_runtime/resolver.py` | `resolve_runtime()` only | adds `resolve_inherited_runtime()` helper |
| `items.py::item_detail` / `item_tab_overview` render context | builds `runtime_options` only | also builds `inherited_runtime_label` |
| `runtime_overrides.py::_render_steps_fragment` render context | builds `runtime_options` only | also builds `inherited_runtime_label` |

### Breaking Changes

- None. No API contract, route, request/response shape, database schema, or DaemonEvent changes. The `<select>` `name`, `value=""`, htmx `hx-patch` targets, and PATCH endpoints are untouched — only option label text changes.

### Data Migration

- None. No schema change and no Alembic revision. Not applicable.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `resolve_inherited_runtime()` to `orch/agent_runtime/resolver.py` and export it from `orch/agent_runtime/__init__.py`; wire the 3 dashboard render paths to compute and pass `inherited_runtime_label`; TDD unit/integration tests | — |
| S02 | frontend-impl | Replace both `— inherit —` labels in `item_steps_table.html` with `{{ inherited_runtime_label }} (inherited)` (with neutral fallback); align bulk option labels to `display_name`; template-render test | — |
| S03 | code-review-impl | Review S01 + S02 output | — |
| S04 | code-review-fix-impl | Fix CRITICAL / HIGH / MEDIUM_FIXABLE findings | — |
| S05 | code-review-final-impl | Cross-agent global review of all work | — |
| S06 | code-review-fix-final-impl | Fix final review findings | — |
| S07 | qv-gate | `make test-integration` | — |
| S08 | qv-browser | Browser verification of relabeled dropdowns in the isolated worktree stack | — |
| S09 | self-assess-impl | Self-assessment via the iw-item-analyze skill | — |

S02 depends on S01 (the template consumes the `inherited_runtime_label` context variable produced by the routers); steps execute sequentially.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no Alembic revision is generated by this CR.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None — the runtime-override PATCH/GET endpoints in `runtime_overrides.py` keep their existing contracts. Only the HTML fragment they return changes its option label text.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `dashboard/templates/fragments/item_steps_table.html` — the two `<option value="">` labels and the bulk `<select>` non-empty option labels.
- **Removed components**: None

### Backend / Resolver Changes

- New helper `resolve_inherited_runtime(session, *, item, project) -> AgentRuntimeOption | None` in `orch/agent_runtime/resolver.py`. It computes the runtime a step would inherit when it carries no step-level override, by delegating to `resolve_runtime()` with a no-step-override sentinel (an object whose `agent_runtime_option_id` is `None`). It returns `None` instead of raising when the catalogue cannot resolve any option, so callers can render a graceful fallback. Exported from `orch/agent_runtime/__init__.py`.
- The three dashboard render paths each load the project's `ProjectConfig` (via `orch.daemon.project_registry.load_projects_toml()` keyed by `project_id`, the same source the daemon uses) and the `WorkItem`, call `resolve_inherited_runtime()`, and pass `inherited_runtime_label` (the resolved option's `display_name`, or `None`) into the `item_steps_table.html` context. A single small dashboard helper SHOULD be factored so the logic is not triplicated.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00070/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00070_CR_Design.md` | Design | This document |
| `CR-00070_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00070_S01_Backend_prompt.md` | Prompt | S01 — resolver helper + dashboard router wiring |
| `prompts/CR-00070_S02_Frontend_prompt.md` | Prompt | S02 — template label changes |
| `prompts/CR-00070_S03_CodeReview_prompt.md` | Prompt | S03 — per-agent code review |
| `prompts/CR-00070_S04_CodeReviewFix_prompt.md` | Prompt | S04 — fix review findings |
| `prompts/CR-00070_S05_CodeReviewFinal_prompt.md` | Prompt | S05 — cross-agent final review |
| `prompts/CR-00070_S06_CodeReviewFixFinal_prompt.md` | Prompt | S06 — fix final review findings |
| `prompts/CR-00070_S08_BrowserVerification_prompt.md` | Prompt | S08 — browser verification |
| `prompts/CR-00070_S09_SelfAssess_prompt.md` | Prompt | S09 — self-assessment |

Reports are created during execution in `ai-dev/work/CR-00070/reports/`.

## Acceptance Criteria

### AC1: Per-step dropdown shows the resolved inherited runtime

```
Given a work item with an editable step (status pending or failed) that has no step-level
  and no item-level runtime override
When the operator views the item's steps table
Then the per-step runtime <select> empty option reads "<resolved display_name> (inherited)"
  (for example "Pi + MiniMax 2.7 (inherited)") instead of "— inherit —"
And that empty option is the selected option
```

### AC2: "Apply to remaining steps" dropdown shows the resolved inherited runtime

```
Given a work item with at least one editable step and no item-level override
When the operator views the item's steps table
Then the "Apply to remaining steps" <select> empty option reads "<resolved display_name> (inherited)"
And its non-empty options are labelled with each runtime option's display_name
```

### AC3: Inherited label reflects an item-level override

```
Given a work item that has an item-level runtime override set to a specific option
  and an editable step with no step-level override
When the operator views the item's steps table
Then the empty option of that step's <select> reads "<item-override display_name> (inherited)"
  — not the catalogue default
```

### AC4: Inherit mechanism is unchanged

```
Given an editable step whose <select> empty option is now relabelled
When the operator selects that empty option and the htmx PATCH fires
Then the request still carries an empty option_id
And the step's agent_runtime_option_id is cleared to NULL (no explicit override)
```

### AC5: Graceful fallback when no option resolves

```
Given the agent_runtime_options catalogue has no enabled rows
When the operator views the item's steps table
Then the steps table still renders without error
And the empty option falls back to a neutral label ("— inherit —")
```

### AC6: Relabel applies across all three render paths

```
Given the steps table is rendered via the full item page, the htmx overview-tab fragment,
  or the runtime-override PATCH response fragment
When any of those responses is produced
Then the relabelled "(inherited)" empty option appears in every case
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the single squash-merge commit for CR-00070. The change is confined to one template, one resolver module (additive helper), and three dashboard render-path call sites; reverting fully restores the `— inherit —` label.
- **Data**: No data loss on rollback — no rows are written, updated, or deleted by this CR.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/agent_runtime/resolver.py`
- `orch/agent_runtime/__init__.py`
- `dashboard/routers/items.py`
- `dashboard/routers/runtime_overrides.py`
- `dashboard/templates/fragments/item_steps_table.html`
- `tests/unit/**`
- `tests/integration/**`
- `tests/dashboard/**`

## TDD Approach

- **Unit / resolver tests** (`tests/integration/` — `resolve_inherited_runtime` needs seeded `agent_runtime_options` rows in a DB):
  - With no item-level override, `resolve_inherited_runtime()` returns the `projects.toml`/catalogue-default option.
  - With an item-level override set, it returns the item-override option (ignores any step-level override).
  - With an empty `agent_runtime_options` catalogue, it returns `None` rather than raising.
- **Dashboard template tests** (`tests/dashboard/test_runtime_override_templates.py`):
  - The per-step `<select>` empty option renders `... (inherited)` and no longer renders `— inherit —` when an option resolves.
  - The "Apply to remaining steps" `<select>` empty option renders `... (inherited)`.
  - When the work item has an item-level override, the empty option shows that override's `display_name`.
  - With no resolvable option, the table renders and the empty option falls back to `— inherit —`.
  - Coverage spans all three render paths (item page, overview-tab fragment, PATCH-response fragment).
- **Updated tests**: `test_runtime_override_templates.py` — the docstring of `test_i00076_patch_step_override_clears_on_empty_body` references the `— inherit —` path; update the wording and keep the assertion on the cleared `agent_runtime_option_id`. Audit any other assertion in the dashboard suite that string-matches `— inherit —`.

## Notes

- **Why a `(inherited)` suffix** (not a bare model name, not `Default:`): chosen by the requester. It keeps the model + agent plainly visible — no longer obscured by the word "Inherit" — while still distinguishing an inherited step from one explicitly pinned to the same option. A future change of the project default then visibly stays "inherited".
- The inherited value is identical for every per-step dropdown within one item (the cascade below the step level — item override → `projects.toml` → catalogue default — does not vary per step), so `inherited_runtime_label` is computed once per render, not per step.
- `resolve_inherited_runtime()` deliberately returns `None` instead of raising the `RuntimeError` that `resolve_runtime()` raises in its "unreachable" branch, because a dashboard render must degrade gracefully rather than 500 the steps table.
- No regression risk to the daemon: `resolve_runtime()` itself is not modified; the new helper only wraps it.
