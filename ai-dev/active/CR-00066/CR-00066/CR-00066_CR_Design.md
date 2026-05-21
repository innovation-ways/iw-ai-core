# CR-00066: Context Window Usage Progress Bar

**Type**: Change Request
**Priority**: Medium
**Reason**: Agents running with models that have limited context windows (e.g. MiniMax-M2.7) can exhaust the window mid-run and crash without any visible warning. Operators need real-time visibility into how much of the context window each step is consuming.
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds columns to two tables (`agent_runtime_options`, `step_runs`) and seeds `context_window_tokens` values for known models. The Database step generates the Alembic migration; the daemon applies it.

## Description

When a step crashes due to context window exhaustion (as happened with CR-00064 S01 on MiniMax-M2.7), there is no visible indicator of how close to the limit the agent was getting. This CR adds a **Context column** in the item steps table showing a mini progress bar (color-coded green/yellow/red) with the percentage of context window consumed. The daemon's `step_monitor` polls the pi session JSONL every cycle to extract `totalTokens` from the latest assistant message, storing the running peak in `StepRun.context_tokens_peak`. The context window size for each model is stored in `AgentRuntimeOption.context_window_tokens`. For completed steps, the bar shows the maximum context utilisation reached during the run.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Key areas:
- `AgentRuntimeOption` in `orch/db/models.py` is the model catalogue (cli_tool + model pairs).
- `StepRun` is append-only — each retry is a new row; `context_tokens_peak` captures the high-water mark.
- `step_monitor.py` in `orch/daemon/` runs every poll cycle; this CR adds token extraction alongside the session file resolution added in CR-00065.
- `item_steps_table.html` already has the Logs column added by CR-00065 — this CR adds the Context column immediately to its right.
- `items.py` router assembles the `StepInfo` dataclass for each step; it already loads `StepRun` fields.

## Current Behavior

- `AgentRuntimeOption` has no `context_window_tokens` field — there is no record of each model's context limit.
- `StepRun` has no token usage fields — there is no record of how many tokens an agent used during a run.
- The item steps table has no context usage indicator. An agent can consume 95% of the context window with no visible warning.
- When a step crashes due to context overflow, the only signal is the cryptic `error_message` on `StepRun` (e.g. `"invalid params, context window exceeds limit (2013)"`).

## Desired Behavior

- `AgentRuntimeOption.context_window_tokens` (INT NULL) stores each model's context limit. Seeded for known models at migration time. NULL = unknown.
- `StepRun.context_tokens_peak` (INT NULL) stores the highest `totalTokens` value observed during the run. Updated by `step_monitor` each poll cycle for pi runs.
- `StepRun.context_tokens_last` (INT NULL) stores the most recent `totalTokens` value (may differ from peak in compaction scenarios where context resets lower).
- A **"Context" column** in the item steps table shows:
  - A compact `{N}K` figure + mini color-coded bar + percentage.
  - Colors: 0–60% green, 61–85% yellow, >85% red.
  - For in-progress steps: shows live current usage (auto-refreshes via existing SSE/htmx poll).
  - For completed/failed steps: shows peak usage reached.
  - For pending steps or NULL data: shows "—".
  - When `context_window_tokens` is NULL: shows the raw token count without a percentage or bar.
- The progress bar is visible without opening any popup — it is a permanent column in the step table.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `agent_runtime_options` table | No context window field | New `context_window_tokens INT NULL` |
| `step_runs` table | No token usage fields | New `context_tokens_peak INT NULL`, `context_tokens_last INT NULL` |
| `orch/daemon/step_monitor.py` | Resolves pi session file (CR-00065) | Also extracts + stores token counts from session JSONL |
| `dashboard/routers/items.py` | Loads StepRun fields | Also loads `context_window_tokens` from AgentRuntimeOption |
| `dashboard/templates/fragments/item_steps_table.html` | Has Logs column (CR-00065) | New Context column with progress bar |

### Breaking Changes

- None. All new DB columns are nullable; template/router changes are additive.

### Data Migration

- New nullable `context_window_tokens INT` on `agent_runtime_options`. Seeded via `op.execute` UPDATE in the migration for known models:
  - `anthropic/claude-opus-4-7`: 200,000
  - `anthropic/claude-sonnet-4-6`: 200,000
  - `anthropic/claude-haiku-4-5-20251001`: 200,000
  - `minimax/MiniMax-M2.7`: 200,000
  - All others: NULL
- New nullable `context_tokens_peak INT` and `context_tokens_last INT` on `step_runs`. No backfill — existing rows remain NULL; only new pi runs will have values.
- Reversible: `alembic downgrade` drops all three columns.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add 3 columns + migration + seed context_window_tokens for known models | — |
| S02 | qv-gate | `make migration-check` | — |
| S03 | backend-impl | `step_monitor` reads token counts from pi session JSONL; updates peak/last | — |
| S04 | frontend-impl | Items router passes context data; Context column + progress bar in template | — |
| S05 | code-review-impl | Review S01–S04 | — |
| S06 | code-review-fix-impl | Fix CRITICAL/HIGH/MEDIUM_FIXABLE | — |
| S07 | code-review-final-impl | Cross-agent final review | — |
| S08 | code-review-fix-final-impl | Fix final findings | — |
| S09 | qv-gate | `make test-integration` | — |
| S10 | qv-browser | Browser verification — progress bar visible, correct colors | — |
| S11 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `agent_runtime_options` (+1 column), `step_runs` (+2 columns)
- **Migration notes**: Seed UPDATE for known models included in migration; NULL-safe for unknown models

### API Changes

- **New endpoints**: None
- **Modified endpoints**: The existing items detail endpoint already loads StepRun — extend to also load `AgentRuntimeOption.context_window_tokens` for each step's last run
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `item_steps_table.html` — new Context column; `dashboard/routers/items.py` — StepInfo dataclass gains `context_tokens_peak`, `context_tokens_last`, `context_window_tokens` fields

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00066_CR_Design.md` | Design | This document |
| `CR-00066_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00066_S01_Database_prompt.md` | Prompt | Database step |
| `prompts/CR-00066_S02_MigrationCheck_prompt.md` | Prompt | QV migration-check |
| `prompts/CR-00066_S03_Backend_prompt.md` | Prompt | Backend step |
| `prompts/CR-00066_S04_Frontend_prompt.md` | Prompt | Frontend step |
| `prompts/CR-00066_S05_CodeReview_prompt.md` | Prompt | Code review |
| `prompts/CR-00066_S06_CodeReviewFix_prompt.md` | Prompt | Code review fix |
| `prompts/CR-00066_S07_CodeReviewFinal_prompt.md` | Prompt | Final code review |
| `prompts/CR-00066_S08_CodeReviewFixFinal_prompt.md` | Prompt | Final code review fix |
| `prompts/CR-00066_S09_QvGate_prompt.md` | Prompt | QV integration tests |
| `prompts/CR-00066_S10_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `prompts/CR-00066_S11_SelfAssess_prompt.md` | Prompt | Self-assessment |

## Acceptance Criteria

### AC1: context_window_tokens seeded for known models

```
Given the migration has been applied
When SELECT model, context_window_tokens FROM agent_runtime_options
Then anthropic/claude-opus-4-7, anthropic/claude-sonnet-4-6, minimax/MiniMax-M2.7
  each have context_window_tokens = 200000
And models not in the known list have context_window_tokens = NULL
```

### AC2: context_tokens_peak updated by daemon for pi runs

```
Given a pi step is running
And the step's session JSONL contains assistant messages with usage.totalTokens
When the daemon's step_monitor runs a poll cycle
Then step_runs.context_tokens_last = the most recent totalTokens value
And step_runs.context_tokens_peak = MAX(totalTokens seen so far for this run)
```

### AC3: Context column visible in step table

```
Given a user views the item steps table
Then a "Context" column is visible immediately right of the "Logs" column
And each step row that has context data shows a mini progress bar + percentage
And steps with no data show "—"
```

### AC4: Correct color coding

```
Given a step where context_tokens_peak / context_window_tokens = 0.45 (45%)
Then the progress bar is green

Given a step where the ratio = 0.72 (72%)
Then the progress bar is yellow/amber

Given a step where the ratio = 0.91 (91%)
Then the progress bar is red
```

### AC5: Peak shown for completed runs

```
Given a step that completed with context_tokens_peak = 150000
And context_window_tokens = 200000
When the user views the step table
Then the Context cell shows "150K / 200K (75%)" with a yellow bar
And the value does not change after the step has completed
```

### AC6: NULL context_window_tokens — raw count only

```
Given a step where context_tokens_peak = 80000
And the model's context_window_tokens is NULL
When the user views the step table
Then the Context cell shows "80K" without a percentage or progress bar
```

## Rollback Plan

- **Database**: `alembic downgrade -1` drops `context_window_tokens`, `context_tokens_peak`, `context_tokens_last`. No data loss — columns are nullable/new.
- **Code**: Revert the merge commit.
- **Data**: No data loss. Token counts are re-derivable from the pi session JSONL files if needed.

## Dependencies

- **Depends on**: CR-00065 (adds `session_file` to StepRun; CR-00066's step_monitor reuses it to locate the JSONL without re-deriving the path — if CR-00065 is not yet merged, the backend step must also include the slug-derivation fallback)
- **Blocks**: None

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/step_monitor.py`
- `dashboard/routers/items.py`
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/static/styles.css`
- `tests/integration/test_context_tokens_migration.py`
- `tests/unit/test_step_monitor_token_poll.py`

## TDD Approach

- **Unit tests**: `test_step_monitor_token_poll.py` — token extraction from pi JSONL (latest totalTokens, peak tracking, compaction reset handling, NULL for non-pi runs).
- **Integration tests**: `test_context_tokens_migration.py` — migration round-trip; `context_window_tokens` seed values present; `context_tokens_peak`/`last` read/write via ORM.
- **Updated tests**: None expected (new nullable columns are backward-compatible).

## Notes

- `totalTokens` in the pi session = `cacheRead + input + output`. For MiniMax-M2.7 this was ~110K at the time of crash for CR-00064 S01 (with a 200K window limit). The `cacheRead` field dominates because MiniMax caches the prompt.
- After a `compaction` event in the pi session, `totalTokens` resets to a lower value. `context_tokens_peak` must NOT decrease on compaction — it stores the all-time high. `context_tokens_last` tracks the post-compaction current value.
- For `claude` and `opencode` runs: token usage is not easily extractable from the stdout log. Leave `context_tokens_peak`/`last` as NULL for non-pi runs in this CR. A future CR can add claude token extraction.
- The Context column is intentionally narrow (no word-wrap) — keep the bar under 80px and use abbreviated notation (`150K / 200K`).
- Color thresholds (0–60% green, 61–85% yellow, >85% red) are applied via plain CSS classes to avoid Tailwind rebuild dependency.
