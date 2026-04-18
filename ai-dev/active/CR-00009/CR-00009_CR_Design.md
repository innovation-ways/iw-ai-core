# CR-00009: Chat panel context awareness (header label + module-aware system prompt + retrieval fallback)

**Type**: Change Request
**Priority**: Medium
**Reason**: Usability / correctness bug — on module pages, the chat silently produces "no context provided" replies because (a) the header gives no hint what the chat is scoped to, (b) the system prompt never tells the LLM which module the user is viewing, and (c) when module-filtered retrieval returns zero chunks, the LLM only receives the architecture map.
**Created**: 2026-04-18
**Status**: Draft

---

## Description

Make the docked chat panel context-aware in three mutually reinforcing ways: (1) the chat header displays the current context (`Chat — <module-path> (<module-name>)` when a module is selected, `Chat — Architecture` otherwise); (2) the RAG QA system prompt explicitly names the module the user is viewing and tells the LLM to prioritize it; (3) when module-filtered LanceDB retrieval returns zero chunks, fall back to an unfiltered project-wide search and tell the LLM the fallback happened so it can flag the degraded context in its answer.

## Project Context

Read `CLAUDE.md` at the repo root for architecture, conventions, and hard rules. Dashboard conventions live in `dashboard/CLAUDE.md` (FastAPI + Jinja2 + htmx, no build step). Orchestration package conventions live in `orch/CLAUDE.md`.

## Current Behavior

- `dashboard/templates/chat/panel.html:11` hard-codes the header as `<h2 class="text-sm font-medium">Chat</h2>`. It never reflects what the user is viewing.
- `dashboard/templates/project_code.html:89-94` exposes `data-context-level`, `data-context-doc-id`, `data-module-path=""`, and `data-project-id` on `#code-content-root` — but **not** `data-module-name`. `dashboard/static/chat/composer.js:85-105` reads `data-module-path` to render a `module:<path>` chip — however **nothing in the codebase ever mutates that attribute**: it is declared empty and stays empty. Module navigation targets `#code-detail-panel` (see `code_module_cards.html:12`), not `#code-content-root`, so the composer's `htmx:afterSwap` listener (which keys on `e.detail.target.id === 'code-content-root'`) never fires on module clicks either. Net effect today: the composer `module:<path>` chip never actually appears. CR-00008 shipped a dead read path that this CR must fix while adding the header-label behavior.
- `dashboard/routers/code_qa.py::QARequest` already carries `context_level`, `context_doc_id`, `module_path`, and `conversation_history`. It forwards `module_path` to `QAEngine.answer_stream`.
- `orch/rag/qa.py:76-83` correctly filters the LanceDB search by `module_path` when `context_level == "module"`. **However**, if that filter returns zero rows, `chunks` is empty and no further retrieval is attempted.
- `orch/rag/qa.py::_build_system_prompt` (lines 124-158) takes only `context_doc_content` and `chunks`. It emits an "Architecture Context" block and a "Relevant Code Excerpts" block with no mention of the user's current module. When both blocks are effectively empty, the LLM produces answers like "I cannot answer this question because there is no information provided about a 'daemon' or any specific codebase in the provided context."

## Desired Behavior

1. **Header label**: `#chat-panel` header shows `Chat — <module-path> (<module-name>)` when a module is loaded, `Chat — Architecture` otherwise. The label updates on every `htmx:afterSwap` that changes `#code-content-root`'s `data-module-path` / `data-module-name` (see item 6 for how those attrs get populated).
2. **Module-aware system prompt**: when `module_path` is non-empty, `_build_system_prompt()` emits a `## Current Focus — Module` block naming the module (path + optional human-readable name) and instructing the LLM to prioritize that module in its answer. When `module_path` is empty, the prompt omits the block and behaves as today.
3. **Retrieval fallback**: when `context_level == "module"` and the module-filtered LanceDB search returns zero chunks, fall back to an unfiltered project-wide search (same embedding, same `TOP_K`, same seed filter). The system prompt then emits a `## Retrieval Note` line telling the LLM "no indexed content matched the current module; answering from whole-project context". When the filter yields at least one chunk, behavior is unchanged.
4. **QARequest**: `code_qa.py::QARequest` accepts an optional `module_name: str | None` alongside the existing `module_path`. The router forwards it to `QAEngine.answer_stream`.
5. **Frontend payload**: the chat POST body includes `module_name` (derived from the same `#code-content-root` data-attr as `module_path`).
6. **Module-attribute propagation onto `#code-content-root`**: the module-detail fragment (`code_module_detail.html`) is the first place where the module's path + name are known client-side. It must carry both on its root node and ship an inline `<script>` that mirrors them onto `#code-content-root` as `data-module-path` / `data-module-name`. A companion listener on the architecture-view swap (or any swap whose target is `#code-detail-panel` that does NOT contain `#code-module-detail`) clears those attrs back to `""`, so navigating back to the architecture view resets the header and chip state. This fixes the pre-existing composer-chip dead read path as a side-effect.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/rag/qa.py::_build_system_prompt` | `(context_doc_content, chunks) -> str` | `(context_doc_content, chunks, module_path=None, module_name=None, fallback_triggered=False) -> str` |
| `orch/rag/qa.py::answer_stream` | No fallback when filtered search returns 0 rows | Falls back to unfiltered search + signals fallback to system prompt |
| `dashboard/routers/code_qa.py::QARequest` | Fields: question, context_level, context_doc_id, module_path, conversation_history | Adds optional `module_name: str \| None` |
| `dashboard/templates/chat/panel.html` | Static `<h2>Chat</h2>` | `<h2 id="chat-context-label">Chat — Architecture</h2>` (default text, updated by JS) |
| `dashboard/templates/project_code.html` | `#code-content-root` has no `data-module-name` | Adds `data-module-name=""` |
| `dashboard/templates/fragments/code_module_detail.html` | Carries only `data-module-slug`; does not propagate path or name to `#code-content-root` (composer-chip dead read) | Adds `data-module-path="{{ module.path }}"` and `data-module-name="{{ module.name }}"` on `#code-module-detail`, plus a trailing inline `<script>` that mirrors both attrs onto `#code-content-root` and dispatches a synthetic `iw:code-context-changed` event |
| `dashboard/static/chat/panel.js` (or a new `header.js`) | No header sync; nothing resets module attrs on architecture navigation | Syncs `#chat-context-label` on load, on `iw:code-context-changed`, and on raw `htmx:afterSwap` into `#code-content-root`. Adds an `htmx:afterSwap` reset listener that clears `#code-content-root`'s `data-module-path` / `data-module-name` when the swap target is `#code-components-section`, OR is `#code-detail-panel` with no `#code-module-detail` in the new content, then re-dispatches `iw:code-context-changed` |
| `dashboard/static/chat/composer.js` | Sends `module_path` in POST body (but in practice it's always empty — dead read path); `syncContextChip` only listens to `htmx:afterSwap` on `#code-content-root`, which never fires on module navigation | Sends `module_name` in POST body alongside `module_path`; `syncContextChip` gains an additional listener for `iw:code-context-changed` so the chip actually appears on module navigation |

### Breaking Changes

- None. `QARequest.module_name` is optional. `_build_system_prompt` gains optional kwargs with defaults preserving current behavior. No API path or response shape changes.

### Data Migration

- None. No DB schema or LanceDB schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `orch/rag/qa.py`: extend `_build_system_prompt` and `answer_stream` — module block, retrieval note, unfiltered fallback | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | api-impl | `dashboard/routers/code_qa.py`: add optional `module_name` to `QARequest`, pass through to `QAEngine.answer_stream` | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | frontend-impl | `chat/panel.html` header hook, `project_code.html` `data-module-name`, `fragments/code_module_detail.html` propagation, `static/chat/panel.js` or `header.js` sync, `static/chat/composer.js` payload | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | tests-impl | Unit tests for `_build_system_prompt`, integration tests for router round-trip, optional light DOM test | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | code-review-final-impl | Cross-agent final review | — |
| S10 | code-review-fix-final-impl | Apply final-review findings | — |
| S11 | qv-gate (lint) | `uv run ruff check .` | — |
| S12 | qv-gate (format) | `uv run ruff format --check .` | — |
| S13 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S14 | qv-gate (unit-tests) | `make test-unit` | — |
| S15 | qv-gate (integration-tests) | `make test-integration` | — |
| S16 | qv-browser | Browser verification in isolated worktree stack | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `POST /api/projects/{project_id}/code/qa` — request body accepts optional `module_name: str | null` (non-breaking)
- **Removed endpoints**: None

### Frontend Changes

- **New components**: Optional new `dashboard/static/chat/header.js` (or inline the sync logic inside `panel.js`). Either approach is acceptable; the frontend agent picks the one with the lowest blast radius and updates `project_code.html` script tags if a new file is introduced.
- **Modified components**: `dashboard/templates/chat/panel.html`, `dashboard/templates/project_code.html`, `dashboard/templates/fragments/code_module_detail.html`, `dashboard/static/chat/panel.js`, `dashboard/static/chat/composer.js`
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00009/`.

| File | Type | Purpose |
|------|------|---------|
| `CR-00009_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00009_S01_Backend_prompt.md` | Prompt | S01 — backend-impl (qa.py) |
| `prompts/CR-00009_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/CR-00009_S03_Api_prompt.md` | Prompt | S03 — api-impl (QARequest) |
| `prompts/CR-00009_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/CR-00009_S05_Frontend_prompt.md` | Prompt | S05 — frontend-impl |
| `prompts/CR-00009_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/CR-00009_S07_Tests_prompt.md` | Prompt | S07 — tests-impl |
| `prompts/CR-00009_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `prompts/CR-00009_S09_CodeReview_Final_prompt.md` | Prompt | S09 — final cross-agent review |
| `prompts/CR-00009_S10_CodeReview_Fix_Final_prompt.md` | Prompt | S10 — apply final-review fixes |
| `prompts/CR-00009_S16_BrowserVerification_prompt.md` | Prompt | S16 — qv-browser |

### Files to Modify (source tree)

- `orch/rag/qa.py`
- `dashboard/routers/code_qa.py`
- `dashboard/templates/chat/panel.html`
- `dashboard/templates/project_code.html`
- `dashboard/templates/fragments/code_module_detail.html`
- `dashboard/static/chat/panel.js`
- `dashboard/static/chat/composer.js`
- `tests/unit/test_qa_engine.py` (extend or create)
- `tests/integration/test_code_qa_routes.py` (extend)

Reports are created during execution in `ai-dev/active/CR-00009/reports/`.

## Acceptance Criteria

### AC1: Header reflects architecture view

```
Given a user opens a project's code page with no module selected
When  the chat panel renders
Then  the header text is exactly "Chat — Architecture"
```

### AC2: Header reflects module view

```
Given a user navigates to the "Orchestration Daemon" module (path "orch/daemon/", name "Orchestration Daemon")
When  the module-detail fragment has been swapped into #code-detail-panel AND
      its inline mirror script has copied data-module-path / data-module-name
      onto #code-content-root
Then  the chat header text is exactly "Chat — orch/daemon/ (Orchestration Daemon)"
```

### AC3: System prompt names the module

```
Given a question is asked with context_level="module", module_path="orch/daemon/", module_name="Orchestration Daemon"
When  QAEngine.answer_stream builds the system prompt
Then  the system prompt contains a "## Current Focus — Module" block that includes both "orch/daemon/" and "Orchestration Daemon"
And   the prompt instructs the LLM to prioritize that module in its answer
```

### AC4: Retrieval falls back when filtered search is empty

```
Given context_level="module" and module_path="orch/daemon/"
And   the LanceDB filtered search returns zero rows for that module
When  QAEngine.answer_stream retrieves context
Then  it issues a second, unfiltered search and uses those chunks
And   the system prompt contains a "## Retrieval Note" line stating the fallback occurred
```

### AC5: Retrieval does NOT fall back when filtered search yields results

```
Given context_level="module" and the filtered search returns at least one row
When  QAEngine.answer_stream retrieves context
Then  no fallback search is issued
And   the system prompt omits the "## Retrieval Note" line
```

### AC6: End-to-end chat reply references the module

```
Given the user views the "Orchestration Daemon" module and asks "how does the daemon work?"
When  the chat reply streams to completion
Then  the reply references the daemon module specifically (not a generic "no context" refusal)
```

### AC7: QARequest accepts module_name without breaking existing callers

```
Given a POST /api/projects/{project_id}/code/qa request with no module_name field
When  the router validates the body
Then  the request is accepted (module_name defaults to None)
```

## Rollback Plan

- **Database**: Not applicable (no schema changes)
- **Code**: Revert the merge commit. The CR is isolated to `orch/rag/qa.py`, `dashboard/routers/code_qa.py`, and the `dashboard/templates/chat/` + `dashboard/static/chat/` files. No cross-cutting side effects.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00008 (code-module-chat-docked-panel — delivered the docked panel this CR enhances)
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_qa_engine.py`):
  - `_build_system_prompt` emits the module block only when `module_path` is provided
  - `_build_system_prompt` emits the retrieval-note line only when `fallback_triggered=True`
  - `answer_stream` calls the unfiltered search path when the filtered search yields zero chunks (mock LanceDB)
  - `answer_stream` does NOT call the unfiltered search path when the filtered search yields chunks
- **Integration tests** (`tests/integration/test_code_qa_routes.py`):
  - POST /code/qa with `module_name` round-trips into the engine call
  - POST /code/qa without `module_name` still works (backwards-compat)
- **Updated tests**: `tests/unit/test_module_gen_prompt.py` only if it happens to exercise `_build_system_prompt` (unlikely — it targets module-doc generation, not QA).
- **Frontend**: A light JSDOM or pure-DOM test for the header-label sync is optional; final coverage is delivered by the qv-browser step.

## Notes

- **Module-attr propagation mechanism (Option A, decided during design review)**: module path+name enter the client via `code_module_detail.html` (server-side, autoescaped). The fragment root (`#code-module-detail`) carries both as `data-module-path` / `data-module-name`. An inline `<script>` at the bottom of the fragment runs on insertion and mirrors both attrs onto `#code-content-root` (which is the anchor the chat header and composer chip already observe). A single `htmx:afterSwap` listener in `panel.js` resets `#code-content-root`'s `data-module-path` / `data-module-name` to `""` when `#code-detail-panel` is swapped and the new content does NOT contain `#code-module-detail` (back-to-architecture navigation). This was chosen over `hx-swap-oob` because the server already renders the fragment and an inline script is a smaller blast radius than changing the swap protocol; it also avoids requiring the backend to emit a second OOB element per module response.
- The module name surface: the server-side view that renders the fragment has access to the `module` dict (`name`, `path`, `description`, `slug`) from `orch/rag/parser.py::parse_modules_from_level1`, so both `{{ module.path }}` and `{{ module.name }}` are available at render time.
- **Risk**: If the module name contains characters that break HTML attribute escaping, Jinja's default autoescape handles it. The frontend agent must verify both attributes are rendered through `{{ module.path }}` / `{{ module.name }}` (autoescape on) and not raw.
- **Risk**: The inline-script approach runs *after* the `htmx:afterSwap` listeners on the body fire for the same swap. Any listener that reads `#code-content-root` data-attrs synchronously in its swap handler would see stale values. Mitigation: the chat header sync and composer chip sync already listen to `htmx:afterSwap`, and the mirror script sets the attrs then dispatches a synthetic event (or the listeners re-read on their own next natural trigger — S05 agent picks the approach but MUST verify the header updates on module-click without a manual re-render). If timing becomes fragile, switch to `hx-swap-oob` in a follow-up.
- **Risk**: The fallback search doubles LanceDB round-trips on a module-scope miss. Accepted: a module miss is rare, and the UX cost of a dead-end refusal outweighs one extra query.
- **Out of scope**: Multi-module chat, cross-module search, citation surfacing in the header. Those belong in a follow-up CR if user feedback demands them.
