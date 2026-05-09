# F-00081: Per-Item / Per-Step Agent + Model Override

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-07
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This feature adds **one** Alembic migration (new `agent_runtime_options` table, partial unique index, three nullable FK columns on `work_items`, `workflow_steps`, `step_runs`, plus seed rows). The migration is generated in S01 by the database agent; the daemon applies it during the merge pipeline.

## Description

Today every step the daemon launches runs with the same `(opencode, minimax)` pair, hardcoded via `cli_tool` in `.iw-orch.json` and the implicit MiniMax default of OpenCode. This feature introduces a catalogue of **paired (CLI, model) runtime options**, three nullable FK overrides (project default → item → step), and UI controls to set them. The compressed batch-items step strip frees horizontal room for two new dropdown columns; the item detail page exposes per-step CLI / Model dropdowns that lock once a step starts running.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key knowns this feature relies on:

- Daemon launch sites: `orch/daemon/batch_manager.py:1109` (initial step launch) and `orch/daemon/fix_cycle.py:1456` (fix cycle launch).
- Project config loader: `orch/daemon/project_registry.py` already reads `cli_tool` from `.iw-orch.json` (line 117). This feature **also** reads `cli_tool` and `model` from `projects.toml` per-project entry, with `.iw-orch.json` as fallback for `cli_tool` (backwards compatibility).
- "PostgreSQL is the sole source of truth" (orch/CLAUDE.md). The catalogue lives in DB, not in code, not in TOML.

## Scope

### In Scope

- New `agent_runtime_options` table with seed rows (5 pairs).
- Three nullable FK columns: `work_items.agent_runtime_option_id`, `workflow_steps.agent_runtime_option_id`, `step_runs.agent_runtime_option_id` (the last records *what actually ran*).
- `projects.toml` per-project entries gain `model` (new) alongside the existing `cli_tool`. Fallback `cli_tool = "opencode"`, `model = "minimax"`.
- Resolver `orch/agent_runtime/resolver.py` implementing the cascade: step → item → projects.toml → catalogue `is_default=true` row.
- Refactor `batch_manager.py:1109` and `fix_cycle.py:1456` to call the resolver and inject `--model <model>` into the launched command (`opencode run … --model <m>` and `claude -p … --model <m>`). The resolved option id is written to `step_runs.agent_runtime_option_id`.
- API endpoints (htmx-friendly):
  - `GET /project/{p}/api/runtime-options` — returns enabled rows for dropdown population.
  - `PATCH /project/{p}/api/item/{iid}/runtime-override` — set/clear item-level override.
  - `PATCH /project/{p}/api/item/{iid}/step/{sid}/runtime-override` — set/clear step-level override.
  - `PATCH /project/{p}/api/item/{iid}/runtime-override/bulk` — set the same override on every still-editable step.
  - All write endpoints validate that affected steps are in `pending | failed | paused`. They emit a single coalesced `daemon_events` row per call (even when the bulk endpoint touches N steps).
- Compressed step strip macro (`components/step_pipeline.html`): each step → 6×14px segment with hover-tooltip; total strip ≤ 120px.
- New `CLI` and `Model` columns in `fragments/batch_items_rows.html` (read-only badges, sourced from item-level override or `(default)`, with a small dot if any step override exists).
- New `CLI` and `Model` columns in `fragments/item_overview.html`. Editable inline `<select>` when the step is in an editable state, htmx PATCH on `change`. Read-only badge sourced from `step_runs.agent_runtime_option_id` once the step runs.
- DB constraint preventing the deletion or `enabled=false` toggling of the row marked `is_default=true`.
- Tests (S06): unit tests for resolver, integration tests for cascade + mid-flight + bulk + lock, dashboard TestClient tests for new endpoints/templates.

### Out of Scope

- A `/system/agent-runtimes` admin CRUD page (deferred — operators add rows via Alembic for now).
- Per-fix-cycle override (fix cycles inherit the step's resolved pair).
- Cost estimation or guardrails on Opus selection — user explicitly opted out (trust the user).
- Changing the agent on a step that is already `in_progress` (mid-flight non-preemption is the rule).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `database-impl` | Alembic migration: new table, seed rows, partial unique index, three FK columns | — |
| S02 | `backend-impl` | Resolver + project_registry extension + launch-site refactor + DaemonEvent emission helper | — |
| S03 | `code-review-impl` | Review S02 | — |
| S04 | `api-impl` | PATCH endpoints (single + bulk) and GET catalogue endpoint, with edit-state validation | S05 |
| S05 | `frontend-impl` | Compressed strip macro, new columns + dropdowns in batch and item templates | S04 |
| S06 | `tests-impl` | Unit + integration + dashboard tests | — |
| S07 | `code-review-final-impl` | Cross-layer review | — |
| S08..S15 | `qv-gate` | lint, format-check, type-check, arch-check, security-sast, test-unit, test-frontend, test-integration | — |
| S16 | `qv-browser` | End-to-end browser verification of the new UI | — |
| S17 | `self-assess-impl` | Project self-assessment (project has `self_assess=true`) | — |

Note: S04 (API) and S05 (Frontend) can run in parallel after S03 passes — the contract between them is a small set of endpoint paths + JSON payloads documented in this design doc.

### Database Changes

- **New tables**: `agent_runtime_options` — `(id PK, cli_tool TEXT, model TEXT, cli_label TEXT, model_label TEXT, display_name TEXT, is_default BOOLEAN DEFAULT false, enabled BOOLEAN DEFAULT true, sort_order INT DEFAULT 0)`. Unique on `(cli_tool, model)`. Partial unique index on `is_default = true` to enforce a single default row.
- **Modified tables**:
  - `work_items` — add `agent_runtime_option_id INT NULL REFERENCES agent_runtime_options(id)`.
  - `workflow_steps` — add `agent_runtime_option_id INT NULL REFERENCES agent_runtime_options(id)`.
  - `step_runs` — add `agent_runtime_option_id INT NULL REFERENCES agent_runtime_options(id)` (records what actually ran).
- **Seed rows** (in the migration's `op.bulk_insert`):
  | cli_tool | model | display_name | is_default |
  |---|---|---|---|
  | opencode | minimax | OpenCode + MiniMax 2.7 | ✓ |
  | opencode | claude-sonnet-4-6 | OpenCode + Claude Sonnet 4.6 | |
  | opencode | claude-opus-4-7 | OpenCode + Claude Opus 4.7 | |
  | claude | claude-sonnet-4-6 | Claude Code + Sonnet 4.6 | |
  | claude | claude-opus-4-7 | Claude Code + Opus 4.7 | |
- **Migration notes**: All FK columns are NULL by default → existing rows are unaffected. Down-migration drops the FK columns first, then the table.

### API Changes

- **New endpoints**:
  - `GET /project/{p}/api/runtime-options` — list enabled rows for dropdown population.
  - `PATCH /project/{p}/api/item/{iid}/runtime-override` (form: `option_id` or `null` to clear).
  - `PATCH /project/{p}/api/item/{iid}/step/{sid}/runtime-override` (same form).
  - `PATCH /project/{p}/api/item/{iid}/runtime-override/bulk` (form: `option_id`, applied to every still-editable step under the item).
- **Modified endpoints**: None.

### Frontend Changes

- **Modified components**:
  - `dashboard/templates/components/step_pipeline.html` — new compressed segment rendering (6×14px segments, hover-tooltip preserved).
  - `dashboard/templates/fragments/batch_items_rows.html` — add CLI and Model columns; render the item-level pair (or `(default)`) plus a small dot badge if any step override exists.
  - `dashboard/templates/fragments/item_overview.html` — add CLI and Model columns. Editable inline `<select>` for `pending | failed | paused` steps, read-only badge for terminal/in-flight states sourced from `step_runs`.
- **New components**: None.
- **CSS**: Plain CSS rules appended to `dashboard/static/styles.css` per the I-00067 mitigation (Tailwind toolchain unreliable in worktrees).

## File Manifest

All files for this work item live under `ai-dev/active/F-00081/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00081_Feature_Design.md` | Design | This document |
| `F-00081_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00081_S01_Database_prompt.md` | Prompt | S01 — migration + table + seed |
| `prompts/F-00081_S02_Backend_prompt.md` | Prompt | S02 — resolver + launch refactor |
| `prompts/F-00081_S03_CodeReview_prompt.md` | Prompt | S03 — review S02 |
| `prompts/F-00081_S04_API_prompt.md` | Prompt | S04 — PATCH endpoints |
| `prompts/F-00081_S05_Frontend_prompt.md` | Prompt | S05 — UI changes |
| `prompts/F-00081_S06_Tests_prompt.md` | Prompt | S06 — additional test coverage |
| `prompts/F-00081_S07_CodeReview_Final_prompt.md` | Prompt | S07 — final cross-layer review |
| `prompts/F-00081_S16_BrowserVerification_prompt.md` | Prompt | S16 — qv-browser end-to-end |
| `prompts/F-00081_S17_SelfAssess_prompt.md` | Prompt | S17 — self-assessment |

Reports are created during execution in `ai-dev/active/F-00081/reports/`.

## Acceptance Criteria

### AC1: Default behaviour preserved

```
Given no overrides on the item and no step-level overrides
When the daemon launches a step
Then it resolves to the catalogue row with is_default=true,
  the launched command is `opencode run … --model minimax …` (or the project's projects.toml default if set),
  and step_runs.agent_runtime_option_id records that pair
```

### AC2: Item-level override applied

```
Given work_items.agent_runtime_option_id is set to the (claude, claude-opus-4-7) row
When the daemon launches a pending step with no step-level override
Then the launched command is `claude -p … --model claude-opus-4-7 --dangerously-skip-permissions`
  and step_runs.agent_runtime_option_id matches the item's override
```

### AC3: Step-level override beats item-level

```
Given a step row override of (opencode, minimax)
  under an item override of (claude, claude-opus-4-7)
When the daemon launches that step
Then the command uses opencode + minimax (step wins over item)
```

### AC4: UI lock semantics

```
Given a step in status in_progress | completed | skipped | cancelled
When the user views the item detail page
Then the CLI / Model cells render as read-only badges showing the value from step_runs (if a run exists)
  or "(default)" for skipped steps that never ran;
  no <select> element is rendered for that row
And given a step in status pending | failed | paused
Then the CLI / Model cells render as <select> dropdowns with htmx PATCH bindings
```

### AC5: Mid-flight non-preemption

```
Given an item executing step S03 (in_progress) with no overrides set
When the user changes the item-level override to (claude, claude-opus-4-7)
Then S03 continues unchanged with its original (opencode, minimax) command
And S04 (the next pending step) picks up (claude, claude-opus-4-7) when launched
And the running step's step_runs row is NOT modified
```

### AC6: Bulk audit coalescing

```
Given an item with five pending steps
When the user submits the bulk PATCH endpoint with option_id = X
Then exactly ONE daemon_events row is written
  with event_type='runtime_override_changed'
  and event_metadata = {item_id, scope: "bulk", step_ids: [S04, S05, S06, S07, S08],
                       old_option_id: null, new_option_id: X, actor: "<user>"}
And every targeted step now has agent_runtime_option_id = X
```

### AC7: Catalogue integrity — default cannot be disabled

```
Given the catalogue row R with is_default=true and enabled=true
When an admin SQL UPDATE attempts to set R.enabled = false
Then the database rejects the change
  (enforced by a CHECK constraint or a trigger that refuses when is_default=true)
And the API endpoint that mutates rows (if any) returns HTTP 400
```

### AC8: Compressed step strip

```
Given an item with 8 workflow steps in mixed statuses
When the batch items tab renders that row
Then the step strip is at most 120px wide regardless of step count
  and each segment is 6×14px with the same colour mapping as today
  (success/in-progress/failed/skipped/pending)
And hovering any segment shows the same step_id, agent_label, status, duration tooltip
```

## Boundary Behavior

Define edge cases. **Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Catalogue empty (no rows match cli_tool) | Operator deleted all `(opencode, *)` rows; project `cli_tool=opencode` | Resolver falls back to `is_default=true` row; logs a warning. |
| Override points to disabled row | step.agent_runtime_option_id refers to row with enabled=false | Resolver ignores it (treats as null) and falls back up the chain. Logs a warning. |
| Bulk PATCH on an item with zero editable steps | All steps in_progress/completed | Endpoint returns 200 with `affected: 0` and emits NO DaemonEvent (zero changes). |
| Step transitions mid-PATCH (race) | User PATCHes a `pending` step that just transitioned to `in_progress` | Endpoint returns 409 Conflict with body indicating the step is no longer editable. The single-step PATCH is rejected; the bulk variant skips that step and proceeds for the rest. |
| Project default in projects.toml references a missing pair | `[projects.X] cli_tool="opencode" model="bogus"` | Daemon logs a warning at registration and falls back to the catalogue default. |
| Existing item registered before this feature | All rows have agent_runtime_option_id NULL | Resolver returns project default → catalogue default. No behavioural change vs. today. |
| Catalogue row deletion attempted while in use | DELETE row referenced by step_runs | Foreign key prevents deletion (`ON DELETE` is `RESTRICT` by default). Endpoint returns 409 with referencing-row count. |
| User sets item-level override after the item is `done` | Item status terminal | Endpoint returns 400; only items with at least one editable step accept overrides. |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. The catalogue table always has exactly one row with `is_default=true`. (Enforced by the partial unique index plus a non-null seed migration.)
2. Every row in `step_runs` written by the daemon after this feature ships has `agent_runtime_option_id IS NOT NULL`.
3. The launched command always contains `--model <model>` whenever the resolved cli_tool is `opencode` or `claude` and the model field is non-empty.
4. A single API call (single, bulk, or step-level) emits **at most one** `daemon_events` row with `event_type='runtime_override_changed'`.
5. Editing an override never modifies a `step_runs` row (append-only invariant preserved).
6. The compressed step strip width is bounded: `width ≤ 6 * step_count + 14 * (step_count - 1) ≤ 120px` for any item with ≤ 12 steps.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

```
orch/db/models.py
orch/db/migrations/versions/**
orch/agent_runtime/**
orch/daemon/project_registry.py
orch/daemon/batch_manager.py
orch/daemon/fix_cycle.py
dashboard/routers/runtime_overrides.py
dashboard/app.py
dashboard/templates/components/step_pipeline.html
dashboard/templates/components/runtime_dropdown.html
dashboard/templates/fragments/batch_items_rows.html
dashboard/templates/fragments/item_overview.html
dashboard/static/styles.css
projects.toml
tests/unit/**
tests/integration/**
tests/dashboard/**
```

## TDD Approach

- **Unit tests**:
  - `orch/agent_runtime/resolver.py`: cascade resolution table-tested across (project default, item override, step override, all combinations); fallback when override points to disabled row; fallback when `(cli_tool, model)` lookup misses.
  - DaemonEvent emission helper: shape of `event_metadata` for single vs. bulk paths.
- **Integration tests**:
  - End-to-end cascade: register item with overrides → run daemon launch path against testcontainer → assert `step_runs.agent_runtime_option_id` and the recorded command.
  - Mid-flight non-preemption: simulate a running step, mutate item-level override, assert running step's step_runs row is untouched and the next launched step picks up the new pair.
  - Bulk audit: issue bulk PATCH covering N steps, assert exactly one DaemonEvent and N rows updated.
  - Catalogue integrity: attempt to disable the default row → assert DB rejection and 400 from the API.
- **Dashboard tests** (TestClient):
  - GET `/api/runtime-options` returns enabled rows.
  - PATCH endpoints accept valid input, reject overrides on non-editable steps with 409.
  - Template rendering: compressed strip respects width budget; CLI/Model dropdowns render only on editable rows.
- **Edge cases** (covered by Boundary Behavior table): catalogue empty, disabled override row, bulk on zero editable steps, projects.toml mis-reference, pre-feature item shapes, FK referential integrity on delete, post-terminal mutation.

## Notes

- The pair `(opencode, claude-sonnet-4-6)` and `(opencode, claude-opus-4-7)` rely on OpenCode's `--model anthropic/claude-…` flag (or equivalent provider prefix). The S02 backend agent should verify the exact flag form against the locally installed OpenCode build before committing the launch-command refactor; if the flag form differs, document it in the S02 report and update this design doc rather than guessing.
- The MERGE pseudo-step ("S00" / synthetic) is not part of the override surface — it's a daemon operation, not an LLM agent run. UI must not render dropdowns for synthetic rows.
- The user's project rule applies: when "make css" reports "Nothing to be done" or fails, append plain CSS to `dashboard/static/styles.css` directly (I-00067 mitigation).
- Trust-the-user policy on cost: no Opus confirmations, no per-project policy gates. If we ever add cost guardrails it would be a separate Feature.
- Future enhancement (out of scope here): a `/system/agent-runtimes` admin page so non-engineers can add catalogue rows from the dashboard.
