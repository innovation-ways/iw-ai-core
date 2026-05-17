# CR-00057: AI Assistant chat model allowlist (per-project, with Ollama provider)

**Type**: Change Request
**Priority**: Medium
**Reason**: The Dashboard AI Assistant chat panel currently populates its model dropdown by flattening every provider/model that opencode happens to advertise (39 entries today, mostly MiniMax variant duplicates). Operators want an explicit, per-project allowlist so the dropdown shows exactly the models we sanctioned — and so a new Ollama provider (gemma4:26b on iw-dev-01) is reachable.
**Created**: 2026-05-17
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR does not start, stop, or rebuild containers.

## ⛔ Migrations: agents generate, daemon applies

This CR does **NOT** add or modify any Alembic migration. The allowlist is stored as a key inside the existing `Project.config` JSONB column (no schema change).

## Description

Replace the AI Assistant chat panel's dropdown source. Instead of returning every model opencode's `/config/providers` advertises, the dashboard reads a curated allowlist from each project's `[ai_assistant]` block in `projects.toml`, persisted into `Project.config["ai_assistant"]` JSONB by `project_registry.py`, and returns only the intersection of that allowlist with what opencode actually reports as reachable. Ollama (gemma4:26b on iw-dev-01) is added to opencode's provider config so it becomes one of the reachable backends.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Per-package guides:
- `dashboard/CLAUDE.md` — FastAPI routes, htmx/SSE patterns, fragment rules.
- `orch/CLAUDE.md` — daemon/CLI/RAG/jobs layout, table inventory, conventions.

The AI Assistant chat panel itself is described in `orch/chat/__init__.py` (managed `opencode serve` subprocess) and `dashboard/routers/chat.py` (the nine `/api/chat/*` endpoints).

## Current Behavior

- `GET /api/chat/config` (dashboard/routers/chat.py:311) calls opencode's `/config` and `/config/providers`, flattens **every** `(providerId, modelId)` pair into a `"providerId/modelId"` string list, and returns it as `{models, default_model, default_agent}` with a 30 s TTL cache. There is no whitelist and no project context — the same list is served on every page.
- The frontend `chat.js:644` reads the unfiltered list straight into the `<select id="chat-assistant-model">` element. The browser pre-evidence captured at `evidences/pre/CR-00057_before_unfiltered_dropdown.png` shows 39 options, the vast majority of which are duplicate MiniMax variants (`minimax-cn-coding-plan/MiniMax-M2`, `minimax-cn/MiniMax-M2.5-highspeed`, etc.) plus a handful of Claude, GPT, and other rows.
- `chat.js:145 _createSession()` does not send a `directory` or `project_id` — the chat panel is installation-wide and unaware of the project page the operator is viewing.
- Opencode is currently configured with the providers it ships defaults for (minimax, anthropic, openai/codex). There is **no** Ollama provider configured, so `ollama/gemma4:26b` is not reachable from chat.
- `Project.config` (JSONB) already stores `cli_tool`, `test_config`, `quality_config`, `browser_verification`, `post_archive_commands`, and `max_parallel`. There is no `ai_assistant` key today.
- `orch/daemon/project_registry.py:_build_project_config` reads `[projects.<id>]` from `projects.toml`, layers `.iw-orch.json` on top, and writes the merged dict to `Project.config` on SIGHUP. It does not currently look for an `ai_assistant` block.

## Desired Behavior

- `projects.toml` supports a new optional table per project:

  ```toml
  [projects.iw-ai-core.ai_assistant]
  models = [
    "anthropic/claude-opus-4-7",
    "anthropic/claude-sonnet-4-6",
    "minimax/MiniMax-M2.7",
    "openai/gpt-5.3-codex",
    "ollama/gemma4:26b",
  ]
  default_model = "anthropic/claude-opus-4-7"
  ```

- `project_registry.py` parses this block, validates every entry against `^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$`, validates that `default_model` (when supplied) is in `models`, and writes the structure into `Project.config["ai_assistant"]` on next SIGHUP. Invalid entries are dropped with a logged warning; the project is **not** skipped (graceful degradation).
- `GET /api/chat/config` accepts an optional `?project_id=…` query parameter. When supplied and a matching project has `config["ai_assistant"]`, the endpoint computes the intersection of `config["ai_assistant"]["models"]` with the set of `"providerId/modelId"` strings opencode actually advertises, preserves the allowlist's ordering, and returns that filtered list. The cache key includes `project_id`.
- Fail-open semantics: if the project has no `ai_assistant` block, or no `project_id` was supplied, the endpoint returns today's behavior (full opencode list). This is logged at INFO so operators see the fallback in flight.
- `default_model` for the response: prefer the allowlist's `default_model` when it survived the intersection; else the first surviving allowlist entry; else fall back to today's `_pick_default_model` logic.
- The frontend `chat.js` infers `project_id` from `window.location.pathname` (regex `^/project/([^/]+)/`). When present it is appended to `/api/chat/config` and stored on the JS module so `/api/chat/sessions` POSTs can pass it as `directory` (already supported by the opencode client; sets the working dir of the session). Pages without a project (e.g. `/`, `/system/*`, `/docs/*`) send no `project_id` and the server returns the fail-open list.
- Opencode is configured with an `ollama` provider in `~/.config/opencode/opencode.json` (or whatever the 1.14.x docs prescribe — verified during S05) pointing at `http://iw-dev-01:11434`. Both `gemma4:26b` and any other Ollama tag operators add later become reachable.
- The frontend dropdown for the `iw-ai-core` project shows exactly: **Claude Opus 4.7, Claude Sonnet 4.6, MiniMax 2.7, GPT-5.3 Codex, Gemma4 26B** — in that order — with Opus selected by default.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `projects.toml` schema | No `ai_assistant` block recognised | Optional `[projects.X.ai_assistant]` block with `models` + `default_model` |
| `orch/daemon/project_registry.py::_build_project_config` | Ignores any `ai_assistant` key | Parses + validates the block; merges into `Project.config["ai_assistant"]` |
| `Project.config` JSONB | Has no `ai_assistant` key | New `ai_assistant: {models, default_model}` key (additive) |
| `dashboard/routers/chat.py::get_config` | Returns full opencode provider flatten; no project awareness | Accepts `?project_id`; intersects allowlist with opencode providers; cache keyed by project_id |
| `dashboard/routers/chat.py::create_session` | `body.directory` accepted but never sent by the client | Receives `directory` from the frontend (project repo_root) to scope the session |
| `dashboard/static/chat_assistant/chat.js` | Calls `/api/chat/config` without context; `_createSession` sends no directory | Infers project_id from URL; appends `?project_id=…`; passes directory at session creation |
| Opencode config (`~/.config/opencode/opencode.json`) | No `ollama` provider | Adds `ollama` provider pointing at `http://iw-dev-01:11434` |
| `projects.toml` for `iw-ai-core` | No `[ai_assistant]` block | Seeded with the 5-model allowlist + default |
| Docs | No reference to chat allowlist | New `docs/IW_AI_Core_AI_Assistant_Models.md`; `CLAUDE.md` "Quick Navigation" gains a row |

### Breaking Changes

- **None.** Endpoints keep their existing shape; the new query parameter is optional; absent allowlist → today's behavior. Existing chat sessions and saved settings work unchanged. The label "Claude Code · Opus 4.7" in the dropdown routes through opencode's `anthropic` provider (Anthropic API key auth), not the `claude-code` CLI — this is called out explicitly so the label is not misread.

### Data Migration

- **None.** `Project.config` is already JSONB; adding a new key requires no DDL. `project_registry` writes the key on next SIGHUP. Reversible: removing the `[ai_assistant]` block + SIGHUP drops the key on the next sync (the registry overwrites `config` wholesale).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `project_registry.py` parses `[projects.X.ai_assistant]`, validates entries, syncs to `Project.config["ai_assistant"]`. Unit tests for the parser + validator. | — |
| S02 | api-impl | `dashboard/routers/chat.py::get_config` accepts `?project_id`; reads allowlist; intersects with opencode providers; project-keyed 30 s cache. `create_session` accepts and forwards `directory`. | — |
| S03 | frontend-impl | `chat.js` infers project_id from URL; appends `?project_id` to `/api/chat/config`; passes `directory` (project repo_root) on session creation; dropdown labels respect the allowlist's order. | — |
| S04 | tests-impl | Integration coverage: project_registry round-trip into `Project.config`; chat router intersection logic; fail-open path; frontend smoke (dashboard test client). | — |
| S05 | template-impl | Seed `[projects.iw-ai-core.ai_assistant]` in `projects.toml`; document opencode ollama-provider config; add `docs/IW_AI_Core_AI_Assistant_Models.md`; update CLAUDE.md "Quick Navigation". | — |
| S06 | code-review-impl | Per-agent review of S01..S05 | — |
| S07 | code-review-fix-impl | Address CRITICAL/HIGH review findings | — |
| S08 | code-review-final-impl | Global cross-agent review | — |
| S09 | code-review-fix-final-impl | Address final-review CRITICAL/HIGH findings | — |
| S10 | qv-gate | `make lint` | parallel with S11..S14 |
| S11 | qv-gate | `make format` (formatter idempotency) | parallel |
| S12 | qv-gate | `make typecheck` | parallel |
| S13 | qv-gate | `make test-unit` | parallel |
| S14 | qv-gate | `make allure-integration` (integration tests) | parallel |
| S15 | qv-browser | Verify dropdown reflects the 5-model allowlist on `/project/iw-ai-core/`, smoke each | — |
| S16 | self-assess-impl | Run `iw-item-analyze` on the completed item (iw-ai-core has `self_assess=true`) | — |

No migration-check gate is needed (no Alembic revision generated).

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: This CR intentionally **does not** generate an Alembic migration. The allowlist lives inside the existing `Project.config` JSONB column. If a future CR wants stricter schema enforcement, that's a separate decision.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: `GET /api/chat/config` accepts a new optional `project_id` query parameter. Response shape is unchanged (`{models, default_model, default_agent}`). `POST /api/chat/sessions` already accepts `directory` in `CreateSessionRequest`; no schema change, but it is now actually populated by the frontend.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: `dashboard/static/chat_assistant/chat.js` only — adds a `_currentProjectId()` helper that parses `window.location.pathname`, wires it into the config fetch (`/api/chat/config?project_id=…`) and into `_createSession` (passes `directory: <project repo_root>` when available). No HTML/template changes — the `<select>` element and its IDs stay identical.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00057/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00057_CR_Design.md` | Design | This document |
| `CR-00057_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions (S01..S16) + `scope.allowed_paths` |
| `prompts/CR-00057_S01_Backend_prompt.md` | Prompt | project_registry parser + Project.config sync |
| `prompts/CR-00057_S02_API_prompt.md` | Prompt | Chat router allowlist intersection + project-keyed cache |
| `prompts/CR-00057_S03_Frontend_prompt.md` | Prompt | chat.js project_id inference + directory wiring |
| `prompts/CR-00057_S04_Tests_prompt.md` | Prompt | Additional integration test coverage |
| `prompts/CR-00057_S05_Template_prompt.md` | Prompt | projects.toml seed + opencode ollama provider config + docs |
| `prompts/CR-00057_S06_CodeReview_prompt.md` | Prompt | Per-agent review |
| `prompts/CR-00057_S07_CodeReview_FIX_prompt.md` | Prompt | Per-agent review fixes |
| `prompts/CR-00057_S08_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/CR-00057_S09_CodeReview_FIX_Final_prompt.md` | Prompt | Global review fixes |
| `prompts/CR-00057_S15_BrowserVerification_prompt.md` | Prompt | Playwright-cli verification |
| `prompts/CR-00057_S16_SelfAssess_prompt.md` | Prompt | iw-item-analyze invocation |

Reports are created during execution in `ai-dev/active/CR-00057/reports/`.

## Acceptance Criteria

### AC1: Configured allowlist drives the dropdown

```
Given projects.toml contains
        [projects.iw-ai-core.ai_assistant]
        models = ["anthropic/claude-opus-4-7", "anthropic/claude-sonnet-4-6",
                  "minimax/MiniMax-M2.7", "openai/gpt-5.3-codex",
                  "ollama/gemma4:26b"]
        default_model = "anthropic/claude-opus-4-7"
  And the daemon has reloaded the project registry
When  an operator opens http://localhost:9900/project/iw-ai-core/ and expands
      the AI Assistant chat panel
Then  the model dropdown contains exactly those 5 entries in that order
  And the selected value is "anthropic/claude-opus-4-7"
  And no other provider/model is offered (no MiniMax variant duplicates, no
      anthropic legacy aliases, no codex-mini, etc.)
```

### AC2: Project_registry round-trips the allowlist into Project.config

```
Given projects.toml is updated with an [ai_assistant] block on iw-ai-core
When  the daemon receives SIGHUP (or project_registry.sync_projects_from_toml
      is invoked from a test)
Then  Project.config["ai_assistant"] is set to {models: [...], default_model: "..."}
  And the values match projects.toml verbatim
  And invalid entries (e.g. "MiniMax-M2.7" without provider) are dropped
      with a logged warning
```

### AC3: Fail-open when no allowlist exists

```
Given a project that has no [ai_assistant] block in projects.toml
When  the dashboard requests GET /api/chat/config?project_id=<that project>
Then  the response models list is the full opencode provider flatten
      (today's behavior — no filtering)
  And the response is identical (modulo cache key) to GET /api/chat/config
      with no project_id
  And a single INFO log line is emitted noting the fallback
```

### AC4: Unreachable allowlist entries are filtered out

```
Given the allowlist contains "ollama/gemma4:26b"
  And opencode's /config/providers does NOT include an ollama provider
      (e.g. the provider config was forgotten on a fresh machine)
When  the dashboard requests GET /api/chat/config?project_id=iw-ai-core
Then  the response models list omits "ollama/gemma4:26b"
  And the response default_model falls through to the next surviving
      allowlist entry (anthropic/claude-sonnet-4-6 in this scenario)
  And a single WARNING log line names the dropped entries
```

### AC5: Ollama provider is wired into opencode

```
Given opencode.json contains an ollama provider with baseURL
        http://iw-dev-01:11434
  And the gemma4:26b model is pulled on iw-dev-01
When  the operator selects "ollama/gemma4:26b" in the chat dropdown and sends
      a prompt
Then  the prompt is routed through opencode-serve to the Ollama backend
  And a non-empty assistant response is streamed back via SSE
  And the response is rendered in the chat panel with no console errors
```

### AC6: Pages outside a project gracefully send no project_id

```
Given the operator is viewing http://localhost:9900/system/status
When  the chat panel mounts and fetches /api/chat/config
Then  the request URL has no project_id query parameter
  And the response is the fail-open full list
  And the dropdown still renders without error
```

## Rollback Plan

- **Database**: N/A — no migration. To clear the new key from a project, remove the `[ai_assistant]` block from `projects.toml` and SIGHUP the daemon; `project_registry.sync_project_to_db` overwrites `config` wholesale and the key is gone.
- **Code**: A single revert of the merge commit reverts every change in this CR (parser + router + JS + projects.toml seed + opencode config doc). No feature flag is needed because the fail-open behavior makes the change inert when the allowlist isn't configured.
- **Data**: No data loss on rollback. Chat sessions and saved settings are untouched. The opencode `ollama` provider configuration on the operator's machine stays in place after a code revert — that's a host-level config file the daemon doesn't manage. If the operator wants it gone, they remove the block from `opencode.json` manually (this is documented in the new doc page).

## Dependencies

- **Depends on**: None.
- **Blocks**: None.

## Impacted Paths

- `orch/daemon/project_registry.py`
- `dashboard/routers/chat.py`
- `dashboard/static/chat_assistant/chat.js`
- `projects.toml`
- `CLAUDE.md`
- `docs/IW_AI_Core_AI_Assistant_Models.md`
- `tests/unit/daemon/test_project_registry_ai_assistant.py`
- `tests/dashboard/test_chat_router.py`
- `tests/integration/test_project_registry_ai_assistant.py`
- `tests/integration/test_chat_config_allowlist_intersection.py`
- `tests/integration/test_chat_endpoint_session_lifecycle.py`

## TDD Approach

- **Unit tests** (S01 backend, S02 api): allowlist parser handles valid blocks, drops invalid entries, validates `default_model ∈ models`; chat router intersects allowlist with mocked opencode provider response; project-keyed cache works (different `project_id`s don't poison each other); fail-open when allowlist absent; unreachable-entries filtering with warning log.
- **Integration tests** (S04 tests): project_registry round-trip — write a fixture `projects.toml`, call sync, assert `Project.config["ai_assistant"]` matches. Chat endpoint with a real `Project` row and a mocked `OpencodeClient`. Frontend dashboard test via `TestClient` confirms `/api/chat/config?project_id=iw-ai-core` returns the curated list.
- **Updated tests**: `tests/dashboard/test_chat_router.py::test_get_config_*` — these currently assume the full flatten; they need a parametrize fork (with vs without project_id, allowlist present vs absent). `tests/integration/test_chat_endpoint_session_lifecycle.py` already exercises the session lifecycle; extend it to assert the new `directory` parameter is forwarded.

## Notes

- **Risk: opencode 1.14.x provider-config shape.** S05 must verify the exact JSON shape opencode expects for an `ollama` provider against the current opencode docs (context7) before committing the doc page. If the shape changed across versions, S05 reports the verified shape and adjusts the doc accordingly.
- **Label honesty.** Under approach A, "Claude Opus 4.7" in the dropdown means *opencode's anthropic provider talking to claude-opus-4-7*, **not** the standalone `claude-code` CLI. The doc page and the dropdown labels make this distinction explicit (e.g. label `Claude Opus 4.7 (via opencode)` is acceptable). A future CR could add a native `claude-code` chat runtime; that's explicitly out of scope here.
- **Out of scope (explicit).** Native `claude-code` chat runtime. Direct-Ollama chat path. Migrating the daemon-side `agent_runtime_options` catalogue. UI for editing the allowlist (it lives in `projects.toml`; edits happen through git + SIGHUP).
- **Cache TTL semantics.** The 30 s TTL stays. Operators reloading `projects.toml` see the new allowlist within `SIGHUP delay + 30 s cache TTL`. Documented in the new doc page.
