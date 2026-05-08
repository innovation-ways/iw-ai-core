# CR-00036: Batch-level `auto_merge` toggle with operator-approved manual merge

**Type**: Change Request
**Priority**: Medium
**Reason**: Operators need an opportunity to review the worktree branch before it lands on `main` for sensitive items, experiments, or human-in-the-loop scenarios. Today every successful item is squash-merged automatically with no chance to interject.
**Created**: 2026-05-07
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. No agent in this CR launches, stops, restarts, or rebuilds any docker container.

## ⛔ Migrations: agents generate, daemon applies

This CR adds a single Alembic migration (`auto_merge` column on `batches`, plus a new value on the `batch_item_status` enum). The Database step writes the migration FILE only; the daemon applies it during the merge pipeline.

## Description

Today every batch item that finishes its workflow steps successfully is automatically picked up by the merge queue and squash-merged into `main`. This CR adds a per-batch `auto_merge` flag (default `true`, configurable per project in `projects.toml`, overridable in the batch creation form). When `auto_merge = false`, the synthetic MERGE step transitions to a new `awaiting_approval` state instead of being processed by the merge queue. The item detail page surfaces a **Merge** button on that step; clicking it transitions the batch item back to the queue's pickable state, after which the existing merge logic runs verbatim (pre-merge migration rebase, squash-merge, worktree deletion).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Especially:
- The merge queue at `orch/daemon/merge_queue.py` is the sole code path that performs the merge — this CR adds a *gate* in front of it, not a new merge implementation.
- The synthetic MERGE step is rendered by `dashboard/routers/items.py::_synthetic_merge_step` and `_merge_status` — these are the integration points for the new `awaiting_approval` UI state.
- `projects.toml` is parsed by `orch/daemon/project_registry.py::_build_project_config`, mirroring the existing `self_assess` boolean.
- Composite PKs `(project_id, id)` apply to every batch/work-item read.

## Current Behavior

1. A `WorkItem` runs through its `WorkflowStep`s; when all non-merge steps complete successfully, `BatchManager` advances `BatchItem.status` to `BatchItemStatus.completed`.
2. On the next daemon poll cycle, `process_merge_queue(...)` (in `orch/daemon/merge_queue.py:76`) picks the oldest `completed` batch item for the project and:
   1. Runs `run_pre_merge_rebase` (rebases against latest `main`, rewrites stale migration `down_revisions`).
   2. Runs `run_pre_merge_dry_run` (apply pending migrations to a testcontainer DB).
   3. Calls `worktree_commit.sh` to squash-merge the branch into `main`.
   4. Runs `run_post_merge_apply` (live DB migration apply).
   5. Sets `BatchItem.status = merged`, `BatchItem.merged_at`, and triggers post-merge hooks (doc regeneration).
3. On the dashboard, the **synthetic** MERGE row (rendered by `_synthetic_merge_step` in `dashboard/routers/items.py:565`) shows status derived from `_merge_status` (`pending` → `in_progress` → `completed` / `failed` / `merge_failed`). Operator-recoverable failure surfaces **Restart Merge** / **Abandon Merge** buttons (CR-00028).
4. There is no operator-controlled gate: a successful item always reaches `merged` automatically.

The `Batch` ORM model carries `max_parallel: int` and `auto_publish: bool` columns (`orch/db/models.py:946,953`). The CLI `iw batch-create` exposes `--max-parallel` and `--auto-publish` flags; the dashboard plan tab exposes a `max-parallel` `<select>` editable while batch is in `planning|approved|paused`.

`projects.toml` carries per-project keys parsed in `_build_project_config` (`enabled`, `display_name`, `self_assess`, …). There is no `auto_merge` key today.

## Desired Behavior

1. **Project default**: `projects.toml` accepts an optional per-project key `auto_merge` (boolean). Absent → `true`. Loaded onto `ProjectConfig.auto_merge_default`.
2. **Batch creation**: `Batch` carries a new `auto_merge: bool` column (NOT NULL, DEFAULT `true`). Both batch-creation entry points pre-fill the value from the project default but allow override:
   - CLI `iw batch-create`: new flags `--auto-merge / --no-auto-merge`. Absent flag → use project default.
   - Dashboard "Create batch from selection" form: new toggle pre-filled with the project default.
3. **Plan tab**: `Batch.auto_merge` renders next to `max_parallel` on the batch detail Plan tab. Editable while batch is in `planning|approved|paused` (mirrors `max_parallel` editability), via a new htmx endpoint `POST /project/{project_id}/api/batch/{batch_id}/auto-merge`.
4. **Merge gate**: when a batch item finishes all its workflow steps and would today be set to `BatchItemStatus.completed` by `BatchManager`, it is instead set to a new state `BatchItemStatus.awaiting_merge_approval` if `batch.auto_merge = false`. `process_merge_queue` only ever picks `completed` items — `awaiting_merge_approval` is invisible to it, so no automatic merge happens.
5. **Dashboard rendering**: `_merge_status` returns the new string `awaiting_approval` when `BatchItem.status == awaiting_merge_approval`. The synthetic MERGE step row renders a **Merge** action button when status is `awaiting_approval`, gated only by dashboard access (no per-user auth).
6. **Manual merge trigger** (dashboard): `POST /actions/item/{item_id}/approve-merge` transitions `BatchItem.status` from `awaiting_merge_approval` → `completed`. The next daemon tick picks it up via the existing merge queue path, unchanged. Returns the standard action response (toast + SSE refresh).
7. **Manual merge trigger** (CLI): `iw item approve-merge <item_id> [--project <id>]` performs the same transition. Useful for scripting and parity with other CLI verbs.
8. **Failure semantics**: A merge triggered by manual approval that fails behaves identically to today's automatic merge failure — the existing `merge_failed` / `migration_invalid` / `migration_rebase_failed` paths surface the existing **Restart Merge** / **Abandon Merge** buttons. No special retry handling for manual merges.
9. **Auth & multi-item**: any dashboard user can click **Merge**. If multiple items in a batch are simultaneously `awaiting_merge_approval`, they are released in operator-click order; no enforced sequencing.
10. **Worktree lifecycle**: unchanged — the worktree stays alive until the merge step runs (which already deletes it). An item paused in `awaiting_merge_approval` continues to hold its slot, exactly as today's `completed` items briefly do while the merge queue picks them up. **Stall-checker exemption**: `awaiting_merge_approval` is a *waiting-on-human* state, not a *stuck* state — the daemon's stall monitor (driven by `IW_CORE_STALL_THRESHOLD`) MUST NOT auto-fail items in this state. Operators may legitimately leave items parked for days; the dashboard surfaces the wait via the existing `BatchItem.updated_at` timestamp.
11. **Failed items unaffected**: only successful items reach the gate. `failed`, `setup_failed`, `stalled`, `skipped`, etc. terminate as today.
12. **`auto_merge = true`**: behavior is byte-for-byte identical to today — the gate is bypassed and the batch item goes straight to `completed`.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `batches` table | `auto_publish boolean DEFAULT false` last column | Adds `auto_merge boolean NOT NULL DEFAULT true` |
| `batch_item_status` enum | 14 values (`pending` → `merged`/`failed`/...) | 15 values — adds `awaiting_merge_approval` |
| `BatchItemStatus` Python enum | 14 members | 15 members — adds `awaiting_merge_approval` |
| `TERMINAL_BATCH_ITEM_STATUSES` | Excludes `awaiting_merge_approval` | Unchanged (it's a *transient* state, not terminal) |
| `ProjectConfig` dataclass | `self_assess_enabled` flag from `projects.toml` | Adds `auto_merge_default: bool = True` from `projects.toml` |
| `BatchManager` | Sets `BatchItem.status = completed` on workflow-success | Sets `awaiting_merge_approval` if `batch.auto_merge=false`, else `completed` |
| `process_merge_queue` | Picks `BatchItemStatus.completed` items | **Unchanged** — gate is upstream |
| `dashboard/routers/items.py::_merge_status` | Returns `pending`/`in_progress`/`completed`/`failed`/`merge_failed` | Adds `awaiting_approval` return for new state |
| `dashboard/routers/actions.py` | Has `restart-merge` / `abandon-merge` / `update-batch-max-parallel` | Adds `approve-merge` and `update-batch-auto-merge` |
| `dashboard/templates/components/action_button.html` | `restart_merge_button`, `abandon_merge_button`, … | Adds `approve_merge_button` |
| `dashboard/templates/fragments/item_overview.html` | Branches on MERGE step status | Adds branch for `awaiting_approval` rendering the new button |
| `dashboard/templates/pages/project/batch_detail.html` | Plan tab shows `max-parallel` `<select>` | Adds `auto-merge` toggle next to it |
| `dashboard/templates/fragments/batch_detail_header.html` | Shows `Max parallel: N` | Also shows `Auto-merge: yes/no` |
| `iw batch-create` CLI | `--max-parallel`, `--auto-publish` | Adds `--auto-merge / --no-auto-merge` (default = project's `auto_merge_default`) |
| `iw item ...` CLI | `approve`, `item-status` | Adds `approve-merge` |
| `projects.toml` | Schema documented in registry parser | Adds optional `auto_merge` boolean per-project |

### Breaking Changes

- **None.** New `Batch.auto_merge` column has `DEFAULT true` so existing batches keep current behavior. Missing `projects.toml` key defaults to `true`. New enum value is purely additive — nothing reads `BatchItemStatus.completed` and treats `awaiting_merge_approval` as equivalent.

### Data Migration

- **Forward**: add `auto_merge BOOLEAN NOT NULL DEFAULT true` to `batches`; add `awaiting_merge_approval` to `batch_item_status` enum (`ALTER TYPE ... ADD VALUE`).
- **Backfill**: implicit (`DEFAULT true` covers existing rows; new enum value is unused on existing data).
- **Reverse**: drop the column; remove enum value via the standard "create new type, migrate, swap" pattern (Postgres does not support `ALTER TYPE … DROP VALUE`). Reversibility is **possible but operationally non-trivial** — flag this in the migration's `downgrade()` docstring.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `database-impl` | `Batch.auto_merge` column, `BatchItemStatus.awaiting_merge_approval` enum value, Alembic migration, schema doc update | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `backend-impl` | `ProjectConfig.auto_merge_default` parsing; `BatchManager` gate; `approve_merge` service; `iw item approve-merge` CLI; `iw batch-create --auto-merge/--no-auto-merge` flag; `_merge_status` and `_synthetic_merge_step` updates; CLI spec doc update; daemon design doc update | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `api-impl` | `POST /actions/item/{item_id}/approve-merge`; `POST /project/{project_id}/api/batch/{batch_id}/auto-merge` (htmx); ensure "create batch from selection" route accepts `auto_merge` form field | — |
| S06 | `code-review-impl` | Review S05 | — |
| S07 | `frontend-impl` | `approve_merge_button` macro; `item_overview.html` button branch; `batch_detail.html` Plan tab toggle; `batch_detail_header.html` summary line; "create batch from selection" form toggle; status badge styling for `awaiting_approval` | — |
| S08 | `code-review-impl` | Review S07 | — |
| S09 | `tests-impl` | Unit + integration coverage: column DDL, enum DDL, projects.toml parsing, `BatchManager` gate, `approve_merge` service, `approve-merge` route, `iw item approve-merge` CLI, item-overview rendering, full happy path with `auto_merge=false` | — |
| S10 | `code-review-impl` | Review S09 | — |
| S11 | `code-review-final-impl` | Cross-agent integration review S01..S10 | — |
| S12..S16 | `qv-gate` | lint, format, typecheck, unit-tests, integration-tests | — |
| S17 | `qv-browser` | Verify batch creation form, plan tab, manual merge end-to-end | — |
| S18 | `self-assess-impl` | Self-assessment via `iw-item-analyze` (project has `self_assess = true`) | — |

Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None.
- **Modified tables**: `batches` (add `auto_merge`); `batch_item_status` enum (add `awaiting_merge_approval`).
- **Migration notes**: Use `op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'awaiting_merge_approval'")` inside an autonomous transaction (`with op.get_context().autocommit_block()`), since `ALTER TYPE … ADD VALUE` cannot run inside a transaction in older Postgres versions. The downgrade path needs the swap-type pattern (create new type without the value, alter column, drop old type, rename) and is documented as "supported but heavy" in the migration docstring.

### API Changes

- **New endpoints**:
  - `POST /actions/item/{item_id}/approve-merge` — htmx fragment route, returns toast + triggers SSE refresh.
  - `POST /project/{project_id}/api/batch/{batch_id}/auto-merge` — htmx form post, body `auto_merge=on|off`, returns 204; SSE refresh re-renders the header.
- **Modified endpoints**:
  - `POST /actions/batch/from-selection` (or whatever the current "create batch from selection" route is — to be confirmed in S05): accept new optional `auto_merge` form field; default to the project's `auto_merge_default`.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**:
  - `approve_merge_button(project_id, item_id)` macro in `action_button.html`.
- **Modified components**:
  - `dashboard/templates/fragments/item_overview.html` — new branch for `step.step_id == 'MERGE' and step.status == 'awaiting_approval'` rendering `approve_merge_button`.
  - `dashboard/templates/pages/project/batch_detail.html` — Plan tab adds `auto-merge` toggle row beneath the `max-parallel` row, same htmx + disabled-when-running pattern.
  - `dashboard/templates/fragments/batch_detail_header.html` — adds `Auto-merge: yes/no` line next to `Max parallel: N`.
  - "Create batch from selection" form (location to be confirmed in S07) — adds toggle field pre-filled from the current project's default.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00036/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00036_CR_Design.md` | Design | This document |
| `CR-00036_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00036_S01_Database_prompt.md` | Prompt | S01 — schema + migration |
| `prompts/CR-00036_S02_CodeReview_Database_prompt.md` | Prompt | S02 — review S01 |
| `prompts/CR-00036_S03_Backend_prompt.md` | Prompt | S03 — registry, BatchManager gate, approve-merge service + CLI, doc updates |
| `prompts/CR-00036_S04_CodeReview_Backend_prompt.md` | Prompt | S04 — review S03 |
| `prompts/CR-00036_S05_API_prompt.md` | Prompt | S05 — dashboard endpoints |
| `prompts/CR-00036_S06_CodeReview_API_prompt.md` | Prompt | S06 — review S05 |
| `prompts/CR-00036_S07_Frontend_prompt.md` | Prompt | S07 — UI templates and macros |
| `prompts/CR-00036_S08_CodeReview_Frontend_prompt.md` | Prompt | S08 — review S07 |
| `prompts/CR-00036_S09_Tests_prompt.md` | Prompt | S09 — additional coverage |
| `prompts/CR-00036_S10_CodeReview_Tests_prompt.md` | Prompt | S10 — review S09 |
| `prompts/CR-00036_S11_CodeReview_Final_prompt.md` | Prompt | S11 — cross-agent final review |
| `prompts/CR-00036_S17_BrowserVerification_prompt.md` | Prompt | S17 — qv-browser script |
| `prompts/CR-00036_S18_SelfAssess_prompt.md` | Prompt | S18 — self-assessment |

Reports are created during execution in `ai-dev/work/CR-00036/reports/`.

## Acceptance Criteria

### AC1: Project default carries through to batch creation

```
Given projects.toml entry [projects.iw-ai-core] sets auto_merge = false
And no --auto-merge / --no-auto-merge flag is passed
When the operator runs iw batch-create CR-00036
Then the resulting Batch row has auto_merge = false
```

### AC2: CLI flag overrides project default

```
Given projects.toml entry [projects.iw-ai-core] sets auto_merge = false
When the operator runs iw batch-create CR-00036 --auto-merge
Then the resulting Batch row has auto_merge = true
```

### AC3: Project default carries through to dashboard form

```
Given projects.toml entry [projects.iw-ai-core] sets auto_merge = false
When the operator opens the "Create batch from selection" form
Then the auto-merge toggle is pre-filled to "no"
```

### AC4: Dashboard form override is respected

```
Given the project default is "no" but the operator toggles the form to "yes"
When the operator submits "Create batch from selection"
Then the resulting Batch row has auto_merge = true
```

### AC5: Successful item with auto_merge=false halts at MERGE step

```
Given a batch with auto_merge=false has one item that finishes all workflow steps successfully
When BatchManager would normally set BatchItem.status = completed
Then BatchItem.status is set to awaiting_merge_approval instead
And process_merge_queue does NOT pick it up on subsequent ticks
And the synthetic MERGE step on the item detail page shows status "awaiting_approval"
And a "Merge" button is rendered next to the MERGE step
```

### AC6: Manual merge via dashboard executes existing merge logic

```
Given a batch item is in awaiting_merge_approval state
When any dashboard user clicks the "Merge" button
Then the action route transitions BatchItem.status from awaiting_merge_approval to completed
And on the next daemon poll tick, process_merge_queue picks the item up
And the existing merge pipeline runs verbatim (pre-merge rebase, dry-run, squash-merge, post-merge apply, worktree deletion)
And on success the item reaches BatchItemStatus.merged exactly as today
```

### AC7: Manual merge via CLI executes existing merge logic

```
Given a batch item is in awaiting_merge_approval state
When the operator runs iw item approve-merge <item_id>
Then BatchItem.status transitions to completed and the same merge pipeline runs as in AC6
```

### AC8: Manual merge failure surfaces existing recovery UI

```
Given an item was approved manually and the merge subsequently fails (e.g., rebase conflict)
When the failure is recorded
Then BatchItem.status becomes one of merge_failed / migration_invalid / migration_rebase_failed
And the item detail page renders the existing Restart Merge and Abandon Merge buttons (CR-00028)
And no new retry path or special handling is invoked
```

### AC9: auto_merge=true preserves today's behavior

```
Given a batch with auto_merge=true (default) finishes all workflow steps successfully
When the daemon polls
Then BatchItem.status transitions completed → merging → merged
And no awaiting_merge_approval state is ever entered for any item in this batch
And no Merge button is rendered for any item in this batch
```

### AC10: Failed items bypass the gate entirely

```
Given a batch with auto_merge=false has an item that fails on any workflow step
When the failure is recorded
Then BatchItem.status follows the existing failure terminal states (failed / setup_failed / stalled / etc.)
And the item never enters awaiting_merge_approval
And no Merge button is rendered for the failed item
```

### AC11a: Plan-tab toggle is editable while batch is pre-execution

```
Given a batch is in status planning, approved, or paused
When the operator opens the Plan tab
Then the auto-merge toggle is enabled and can be changed
And changing it persists Batch.auto_merge via POST /project/.../api/batch/.../auto-merge
And the batch header re-renders with the new value
```

### AC11b: Plan-tab toggle is disabled while batch is running or done

```
Given a batch is in status executing or completed
When the operator opens the Plan tab
Then the auto-merge toggle is disabled (mirrors max-parallel disable rule)
```

## Rollback Plan

- **Database**: the migration's `downgrade()` drops `batches.auto_merge` and replays the swap-type pattern to remove `awaiting_merge_approval` from the enum. **Pre-condition for downgrade**: no row may currently hold the new enum value. The downgrade docstring documents this and emits a clear error if violated.
- **Code**: revert the merge commit. The new `auto_merge` column is invisible to old code; old code never reads or writes `awaiting_merge_approval`. No feature flag is needed — the project-level default in `projects.toml` is itself a kill-switch (set every project to `true` to revert behavior across the fleet without code change).
- **Data**: no data loss on rollback. Items currently in `awaiting_merge_approval` would need to be operator-promoted to `completed` (`UPDATE batch_items SET status = 'completed' WHERE status = 'awaiting_merge_approval'`) before the downgrade runs.

## Dependencies

- **Depends on**: None.
- **Blocks**: None.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/cr00036_*.py`
- `orch/daemon/project_registry.py`
- `orch/daemon/batch_manager.py`
- `orch/cli/batch_commands.py`
- `orch/cli/item_commands.py`
- `dashboard/routers/items.py`
- `dashboard/routers/actions.py`
- `dashboard/templates/components/action_button.html`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/batch_detail_header.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/static/styles.css`
- `docs/IW_AI_Core_Database_Schema.md`
- `docs/IW_AI_Core_CLI_Spec.md`
- `docs/IW_AI_Core_Daemon_Design.md`
- `tests/unit/**`
- `tests/integration/**`
- `tests/dashboard/**`

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_batch_manager.py` — gate logic: with `auto_merge=true`, items go to `completed`; with `auto_merge=false`, items go to `awaiting_merge_approval`.
  - `test_project_registry.py` — `auto_merge` parsing: missing key → `True`, explicit `true` → `True`, explicit `false` → `False`, non-bool → warning + `True`.
  - `test_batch_commands.py` — CLI flag resolution: `--auto-merge` / `--no-auto-merge` / absent flag with project default true / absent flag with project default false.
- **Integration tests** (`tests/integration/`, testcontainer-backed):
  - `test_models.py` — `Batch.auto_merge` round-trips with default `true`; `BatchItemStatus.awaiting_merge_approval` round-trips.
  - `test_merge_queue_auto_merge_gate.py` (new) — full happy path: create batch with `auto_merge=false`, run an item to completion, assert merge queue does NOT pick it up; trigger `approve_merge`; assert it does pick up on next poll and reaches `merged`.
  - `test_dashboard_actions.py` — `POST /actions/item/.../approve-merge` happy path and rejection paths (item not in `awaiting_merge_approval`).
  - `test_cli_batches.py` — `iw batch-create --no-auto-merge` writes `Batch.auto_merge=false`; default flag uses project default.
  - `test_cli_items.py` (new or extended) — `iw item approve-merge` happy path.
- **Dashboard tests** (`tests/dashboard/`):
  - `test_item_overview_awaiting_merge.py` (new) — synthetic MERGE step renders `approve_merge_button` when status is `awaiting_approval`; does not render when other statuses.
  - `test_batch_detail_auto_merge_toggle.py` (new) — Plan tab renders the toggle and disables it when status not in `planning|approved|paused`.
- **Updated tests**: any test currently asserting `Batch(...)` constructor signatures must be reviewed to either pass the new column explicitly or rely on the SQL default. `BatchItemStatus` enum-iteration tests (e.g. `test_entity_type_classification.py`) must include `awaiting_merge_approval`.

## Notes

- **State name choice**: `awaiting_merge_approval` was chosen over `merge_pending` / `merge_held` for symmetry with the user-facing button label "Merge" — operators who see the state in the DB should immediately understand it's awaiting their approval.
- **Endpoint verb choice**: `approve-merge` was chosen over `merge` to match the existing semantic naming (`approve`, `restart-merge`, `abandon-merge`) and to make CLI command pages discoverable via tab-completion (`iw item app...`).
- **Cancel/discard path is out of scope** — operators can still abandon items via existing tooling. A first-class "discard" action without merging is deferred to a follow-up.
- **`auto_publish` vs `auto_merge` (independent flags)**: `Batch.auto_publish` (existing) governs whether the daemon pushes the merged commit to `origin/main` after a successful merge — see `batch_manager.py::check_auto_publish`. `Batch.auto_merge` (new, this CR) governs whether the merge to local `main` happens automatically or waits for operator approval. The two flags are orthogonal: a batch can be `auto_merge=false, auto_publish=true` (operator approves each merge, then the daemon pushes) or any other combination. Do NOT collapse or rename these.
- **Docs already documented**: this CR updates `docs/IW_AI_Core_Database_Schema.md` (DDL), `docs/IW_AI_Core_CLI_Spec.md` (`batch-create` flags + new `item approve-merge` command), and `docs/IW_AI_Core_Daemon_Design.md` (gate description in the merge queue section, plus the stall-checker exemption for `awaiting_merge_approval`). Other docs are unaffected.
