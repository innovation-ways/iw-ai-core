# CR-00071: Pi Runtime Context-Usage Percentage Support

**Type**: Change Request
**Priority**: High
**Reason**: A just-shipped feature (CR-00067 context-usage indicator) is invisible for the AI Assistant's default runtime. CR-00067 wired `context_pct` for OpenCode tabs only; commit `365413e1` then made Pi the default runtime, so the indicator is dark for effectively all new chats.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This change adds, modifies, and removes no migrations.** The context-window source column (`agent_runtime_options.context_window_tokens`) already exists — added by CR-00066 migration `891343247f66`.

## Description

CR-00067 added a context-usage percentage indicator to the AI Assistant message-box footer, but only computed `context_pct` for the OpenCode runtime. The `get_tab()` Pi branch returns its `{tab, session, messages}` payload before reaching the injection block, so Pi tabs never carry a `context_pct` and the frontend keeps the indicator hidden. This CR extends the Pi branch of `get_tab()` to compute and inject `context_pct`, using the existing `agent_runtime_options.context_window_tokens` column as the Pi context-window source.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant areas: `dashboard/routers/chat.py` (the tab-scoped chat API, F-00086), `orch/chat/context_usage.py` (pure context-usage helpers, CR-00067), `orch/chat/pi/pi_runtime.py` (Pi runtime adapter, F-00087), `orch/db/models.py` (`AgentRuntimeOption`, the Pi model catalogue).

## Current Behavior

`GET /api/chat/tabs/{tab_id}` (`get_tab()` in `dashboard/routers/chat.py`) has two branches:

- **Pi branch** (`tab.runtime == "pi"`): fetches `session` and `messages` from `PiRuntime`, then `return`s `{tab, session, messages}` directly — it never computes `context_pct`.
- **OpenCode branch**: after fetching `session`/`messages`, runs a `contextlib.suppress(Exception)`-wrapped block that resolves the model via `context_usage.resolve_model_from_tab()`, looks up the context window from the cached `/config/providers` payload via `context_usage.lookup_context_window()`, computes the percentage via `context_usage.compute_context_pct()`, and injects `session["context_pct"]`.

The frontend (`chat.js` `_applyContextPct()`) reads `session.context_pct`; when it is `undefined` — which is always the case for Pi tabs — it hides the `#chat-assistant-context-pct` span. Because the AI Assistant default runtime is now Pi (commit `365413e1`), every new chat tab is a Pi tab and the indicator is never shown.

`compute_context_pct(messages, context_window)` is already runtime-agnostic: it scans messages for the most-recent assistant message carrying positive `tokens` data and divides by the context window, returning `None` whenever usage cannot be determined. Only `lookup_context_window()` is OpenCode-specific (it parses the `/config/providers` JSON shape).

The Pi context-window source already exists: `AgentRuntimeOption.context_window_tokens` (nullable `Integer`, added by CR-00066) holds the maximum context window for each `(cli_tool, model)` pair. Pi tab models are stored as `"pi/<model>"`.

## Desired Behavior

`get_tab()`'s Pi branch computes and injects `context_pct` into the returned `session` dict, mirroring the OpenCode branch:

- The Pi model is resolved from `tab.model` (`"pi/<model>"` → `cli_tool="pi"`, `model="<model>"`).
- The context window is looked up from `agent_runtime_options.context_window_tokens` for that `(cli_tool, model)` row.
- Token usage is read from the Pi `messages` list via `compute_context_pct()`. S01 must investigate the live Pi `get_messages()` payload to confirm the per-message token shape; if Pi's token keys differ from the OpenCode shape (`{input, output, reasoning, cache:{read,write}}`), S01 adds a small pure normalizer in `orch/chat/context_usage.py` so `compute_context_pct()` can consume Pi messages.
- The whole computation is wrapped so any failure is non-fatal — `context_pct` is simply omitted, never an HTTP error.

**Graceful degradation is intrinsic and preserved.** When Pi messages carry no token data, when the model has no `context_window_tokens` row, or when anything else fails, `context_pct` is omitted exactly as today — the indicator stays hidden. There is therefore **no regression risk**: the worst case equals current behavior.

When Pi messages do carry token usage and a `context_window_tokens` value is configured, the percentage appears for Pi tabs identically to OpenCode tabs — immediately on tab activation and refreshed by the existing 5 s frontend poll.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `get_tab()` Pi branch (`dashboard/routers/chat.py`) | Returns `{tab, session, messages}` with no `context_pct` | Computes `context_pct` (Pi context-window lookup + `compute_context_pct`) and injects it into `session`, suppressing all errors |
| `orch/chat/context_usage.py` | Helpers cover the OpenCode message/provider shape | Adds a pure Pi token-shape normalizer **only if** S01 finds Pi's token keys differ from OpenCode's |
| `GET /api/chat/tabs/{tab_id}` response (Pi tabs) | `session` never contains `context_pct` | `session` contains `context_pct` (float `[0,100]`) when computable; still omitted otherwise |

### Breaking Changes

- None. `context_pct` is an additive, optional field in the `session` payload. The OpenCode branch is untouched. The frontend already handles both presence and absence.

### Data Migration

- None. No schema change. `agent_runtime_options.context_window_tokens` already exists (CR-00066).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Investigate Pi `get_messages()` token shape; add Pi context-window lookup from `agent_runtime_options`; extend `get_tab()` Pi branch to compute + inject `context_pct`; add pure Pi token normalizer if needed; TDD unit + integration tests | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH/MEDIUM_FIXABLE findings | — |
| S04 | code-review-final-impl | Cross-agent final review | — |
| S05 | code-review-fix-final-impl | Fix final review findings | — |
| S06 | qv-gate | `make test-unit` | — |
| S07 | qv-gate | `make test-integration` | — |
| S08 | qv-browser | Browser verification — % visible on a Pi tab | — |
| S09 | self-assess-impl | Self-assessment via the iw-item-analyze skill | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. `agent_runtime_options.context_window_tokens` already exists (CR-00066 / `891343247f66`).

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `GET /api/chat/tabs/{tab_id}` — for Pi tabs, `session.context_pct` is now populated when computable (additive, optional field)
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None — `chat.js` `_applyContextPct()` / `_refreshContextPct()` and the `#chat-assistant-context-pct` element from CR-00067 already consume `session.context_pct` generically and need no change.
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00071/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00071_CR_Design.md` | Design | This document |
| `CR-00071_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00071_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00071_S02_CodeReview_prompt.md` | Prompt | S02 code review instructions |
| `prompts/CR-00071_S03_CodeReviewFix_prompt.md` | Prompt | S03 fix instructions |
| `prompts/CR-00071_S04_CodeReviewFinal_prompt.md` | Prompt | S04 final review instructions |
| `prompts/CR-00071_S05_CodeReviewFixFinal_prompt.md` | Prompt | S05 final-fix instructions |
| `prompts/CR-00071_S08_BrowserVerification_prompt.md` | Prompt | S08 browser verification instructions |
| `prompts/CR-00071_S09_SelfAssess_prompt.md` | Prompt | S09 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00071/reports/`.

## Acceptance Criteria

### AC1: Context percentage injected for a Pi tab with token data

```
Given an active Pi chat tab whose most recent assistant message carries positive token usage
  And the tab's Pi model has a configured agent_runtime_options.context_window_tokens value
When GET /api/chat/tabs/{tab_id} is called
Then the returned session object contains a numeric context_pct in the range [0, 100]
  And context_pct equals used_tokens / context_window_tokens * 100
```

### AC2: Context percentage omitted when Pi token data is absent

```
Given an active Pi chat tab whose messages carry no token usage (e.g. a brand-new empty chat)
When GET /api/chat/tabs/{tab_id} is called
Then the returned session object does NOT contain a context_pct field
  And the response is otherwise unchanged (no error, no zero placeholder)
```

### AC3: Context percentage omitted when the Pi model context window is unknown

```
Given an active Pi chat tab whose Pi model has no agent_runtime_options.context_window_tokens value (NULL)
When GET /api/chat/tabs/{tab_id} is called
Then the returned session object does NOT contain a context_pct field
  And the response is otherwise unchanged (no error)
```

### AC4: No regression for OpenCode tabs

```
Given an active OpenCode chat tab
When GET /api/chat/tabs/{tab_id} is called
Then context_pct is computed exactly as before this change (provider-payload context-window lookup)
  And the OpenCode branch behavior is byte-for-byte unchanged
```

### AC5: Indicator renders end-to-end for a Pi tab

```
Given the AI Assistant is open on a Pi tab with conversation history carrying token usage
When the tab is activated in the browser
Then the context percentage appears to the left of the Clear button
  And its colour band follows the CR-00067 thresholds (neutral < 70%, amber 70–89%, red >= 90%)
```

## Rollback Plan

- **Database**: Not applicable — no schema change.
- **Code**: Revert the merge commit. The change is confined to the Pi branch of `get_tab()` plus an optional pure helper; reverting restores the documented graceful-degradation behavior (Pi indicator hidden).
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00067 (context-usage indicator — frontend + `context_usage.py` helpers + OpenCode path), CR-00066 (`agent_runtime_options.context_window_tokens` column). Both are merged.
- **Blocks**: None

## Impacted Paths

- `dashboard/routers/chat.py`
- `orch/chat/context_usage.py`
- `tests/unit/**`
- `tests/integration/**`
- `tests/dashboard/**`

## TDD Approach

- **Unit tests** (`tests/unit/test_context_usage.py`): if S01 adds a Pi token-shape normalizer, cover it directly — Pi-shaped messages with/without tokens, partial token fields, malformed input → `None`/0. `compute_context_pct()` is already covered by CR-00067; extend only if the normalizer changes its inputs.
- **Integration tests** (`tests/integration/` or `tests/dashboard/test_chat_router_pi.py`): `get_tab()` on a Pi tab injects `session.context_pct` when the Pi runtime is mocked to return token-bearing messages and the model has a `context_window_tokens` row (AC1); omits `context_pct` when messages carry no token data (AC2); omits `context_pct` when the model row has `context_window_tokens = NULL` (AC3). Seed `agent_runtime_options` rows in the testcontainer; mock `PiRuntime.get_messages()` to return the investigated Pi message shape.
- **Updated tests**: `tests/dashboard/test_chat_router_pi.py` currently mocks `get_messages` returning `[]` — keep that case (it exercises AC2) and add the token-bearing case. Confirm the existing OpenCode `context_pct` integration tests still pass unchanged (AC4).

## Notes

- **The single genuine unknown** is the Pi `get_messages()` per-message token shape. The CR-00067 S01 report flagged it as "unknown and unverified without a live Pi binary," and the current test fixtures only ever return empty message lists. S01 must investigate the live Pi RPC payload (`{"type": "get_messages"}` response). Three outcomes, all safe:
  1. Pi token keys match the OpenCode shape → no normalizer needed; wire the branch directly.
  2. Pi token keys differ → add a small pure normalizer in `orch/chat/context_usage.py`.
  3. Pi exposes no per-message token usage at all → the wiring still ships (it is harmless: `compute_context_pct()` returns `None`, indicator stays hidden = current behavior). S01 records the finding in its report and the percentage remains a no-op for Pi until Pi exposes tokens. **The CR is low-risk by construction** — the worst case is byte-equivalent to today.
- **Layer boundary**: `orch/chat/context_usage.py` is documented as pure (no I/O, no DB). The `agent_runtime_options` lookup is a DB query and therefore belongs in `dashboard/routers/chat.py` (the router already holds a `Session`), not in `context_usage.py`. Any helper added to `context_usage.py` must stay pure (e.g. a normalizer that takes already-fetched rows or message dicts).
- **No new caching needed**: unlike the OpenCode `/config/providers` HTTP lookup (which CR-00067 cached in `_providers_cache`), the Pi context window is a single indexed DB read on a tiny catalogue table — acceptable on every `get_tab()` poll without a cache.
- **Live updates** are already handled: the frontend polls `GET /api/chat/tabs/{tab_id}` every 5 s and on tab activation. Once the Pi branch injects `context_pct`, both immediate-on-activation and live-refresh behaviors work for Pi with no frontend change.
