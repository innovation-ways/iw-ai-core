# F-00049: Code Understanding: Q&A Panel (SSE Streaming)

**Type**: Feature
**Priority**: High
**Created**: 2026-04-15
**Status**: Draft
**Depends on**: F-00047 (Code tab container), F-00046 (LanceDB index + CodeIndexer)
**Blocks**: None (parallel with F-00048)

---

## Description

Adds a persistent, collapsible Q&A panel to the Code tab. Users can ask natural-language questions about the codebase at any point. Answers stream token-by-token via SSE. Context is injected based on the current view level (Level 1 = architecture context, Level 2 = module context). Maintains last N turns of conversation history stored in the browser — stateless on the server.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- FastAPI + Jinja2 + htmx (no TypeScript, no build step)
- Tailwind CSS loaded from CDN — do NOT use dynamic class construction
- SSE already used via `StreamingResponse` and `EventSource` patterns in existing code
- Templates in `fragments/` must NOT extend `base.html`
- Routes are thin — business logic belongs in `orch/` layer
- `orch/rag/` package exists (from F-00045/F-00046) with `CodeIndexer` and `CodeUnderstandingConfig`
- Ollama LLM via `llama-index-llms-ollama`; embeddings via `llama-index-embeddings-ollama`

## Scope

### In Scope

- `orch/rag/qa.py` — `QAEngine` class with `answer_stream()` async generator
- `POST /api/projects/{project_id}/code/qa` — SSE endpoint for token streaming
- `dashboard/templates/fragments/code_qa_panel.html` — Q&A panel fragment with embedded JS
- Unit tests: `_build_system_prompt()` correctness, `MAX_HISTORY_TURNS` truncation logic
- Integration tests: full API endpoint round-trip with mocked Ollama, error handling

### Out of Scope

- Persistent server-side conversation storage (conversation history is browser-side only)
- Authentication/authorization on the endpoint
- Level 3 (symbol-level) context (only "architecture" and "module" are in scope)
- Level 2 doc generation (F-00048)

---

## UI Design

### Q&A Panel (persistent, bottom of Code tab)

```
┌─────────────────────────────────────────────────────────┐
│ ▼ Ask about this codebase                    [collapse] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ You: What does the ring buffer do?              │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Assistant: The RingBuffer<T> is a fixed-        │   │
│  │ capacity, lock-free circular buffer using two   │   │
│  │ atomic indices...                               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Context: engine/ module                               │
│                                                         │
│  ┌─────────────────────────────────────┐ [Ask →]       │
│  │ Ask a question about the codebase...│               │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

**Context indicator**: Shows "Architecture" when at Level 1, "engine/ module" when at Level 2. Automatically updates when user navigates between levels.

**Streaming**: Tokens appear progressively in the assistant bubble as they arrive. No full page reload.

**Collapsed state**: Panel shows only "▶ Ask about this codebase" header bar. Click to expand.

**Loading state**: Input disabled, spinner shown, [Ask] button shows loading state while streaming.

**Error state**: If Ollama is unavailable, show "⚠ Local AI unavailable. Check that Ollama is running." in the response area.

---

## Architecture

### orch/rag/qa.py — QAEngine

```python
class QAEngine:
    """
    Context-aware RAG Q&A engine with conversation history.
    Stateless — conversation history is passed in on each request.
    """
    TOP_K = 8
    MAX_HISTORY_TURNS = 5  # Keep last 5 turns (10 messages) in context

    def __init__(self, project_id: str, config: CodeUnderstandingConfig): ...

    async def answer_stream(
        self,
        question: str,
        context_level: str,                 # "architecture" | "module"
        context_doc_id: str | None,         # ID of current Level 1 or Level 2 ProjectDoc
        conversation_history: list[dict],   # [{"role": "user"|"assistant", "content": str}]
        session: AsyncSession,
        module_path: str | None = None,     # Required when context_level == "module"
    ) -> AsyncGenerator[str, None]:
        """
        1. Embed question via Ollama embedding model
        2. Retrieve top-k chunks from LanceDB
           - If context_level == "module": filter by module_path metadata prefix
           - If context_level == "architecture": no filter (full index)
        3. Load context_doc (Level 1 or Level 2 ProjectDoc content) from DB as system context
        4. Build prompt: system_context + retrieved_chunks + conversation_history + question
        5. Stream response tokens via Ollama LLM
        6. Yield each token as a string
        """
        ...

    def _build_system_prompt(self, context_doc_content: str, chunks: list[str]) -> str:
        """
        Assembles:
        - "You are a codebase expert. Here is the architecture overview: {Level1 or Level2 doc}"
        - "Here are relevant code excerpts: {chunks}"
        - "Answer the user's question about this codebase."
        """
        ...

    def _truncate_history(
        self, history: list[dict]
    ) -> list[dict]:
        """Return last MAX_HISTORY_TURNS * 2 messages from history."""
        ...
```

Implementation notes for `answer_stream()`:
- Use `OllamaEmbedding` from `llama-index-embeddings-ollama` — same model as indexer (`config.resolved_embed_model()`)
- LanceDB table name: `f"code_{project_id.replace('-', '_')}"` (same convention as `CodeIndexer`)
- LanceDB module filter: use metadata filter `file_path LIKE '{module_path}%'` or equivalent LanceDB filter syntax
- Build `ChatMessage` objects for conversation history (from `llama_index.core.llms`)
- Use `OllamaLLM` from `llama-index-llms-ollama` with `stream_chat()` for streaming
- `_truncate_history()` called before injecting history into prompt to enforce `MAX_HISTORY_TURNS`
- If `context_doc_id` is provided, load the `ProjectDoc.content` from DB via async select; if not found, use empty string

### API Request/Response

```
POST /api/projects/{project_id}/code/qa
Content-Type: application/json
Response: text/event-stream

Body (Pydantic model QARequest):
{
  "question": "How does the ring buffer handle overflow?",   // required, max 1000 chars
  "context_level": "module",                                // "architecture" | "module"
  "context_doc_id": "iw-ai-core:some-doc-id",              // optional str
  "module_path": "engine/",                                 // optional str
  "conversation_history": [
    {"role": "user", "content": "What does the engine module do?"},
    {"role": "assistant", "content": "The engine module handles..."}
  ]
}
```

SSE token stream format:
```
data: {"token": "The"}
data: {"token": " ring"}
data: {"token": " buffer"}
data: {"event": "done", "full_response": "The ring buffer handles overflow by..."}
```

Error event (Ollama down):
```
data: {"event": "error", "message": "Local AI unavailable. Check that Ollama is running."}
```

HTTP error codes (non-streaming):
- `400` — validation failure (empty question, question > 1000 chars, invalid context_level)
- `404` — project not found or no LanceDB index exists for project
- `503` — returned as SSE error event (not HTTP 503) to preserve the stream contract

### Endpoint Implementation Notes

- Router module: `dashboard/routers/code_qa.py` (new file, registered in `dashboard/app.py`)
- Use `StreamingResponse` with `media_type="text/event-stream"` and headers:
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`
  - `Connection: keep-alive`
- Validate `QARequest` with Pydantic; return `HTTPException(400)` on validation failure
- Wrap `QAEngine.answer_stream()` in a try/except; catch `httpx.ConnectError` or `ConnectionRefusedError` → yield SSE error event before closing generator
- Check project exists in DB; return `HTTPException(404)` if not found
- Check LanceDB index exists on disk; return `HTTPException(404, "No code index found for this project")` if missing

---

## Template: code_qa_panel.html

File: `dashboard/templates/fragments/code_qa_panel.html`

Must NOT extend `base.html` — it is a partial fragment included via `{% include %}` in `project_code.html`.

### Key Structural Elements

```html
<div id="qa-panel" class="border border-border rounded-lg bg-card mt-4">

  <!-- Header / collapse toggle -->
  <div id="qa-panel-header" class="flex items-center justify-between px-4 py-2 cursor-pointer ...">
    <span id="qa-panel-toggle-icon">▼</span>
    <span class="font-medium text-sm">Ask about this codebase</span>
    <button id="qa-collapse-btn" class="text-xs text-muted-foreground">collapse</button>
  </div>

  <!-- Collapsible body -->
  <div id="qa-panel-body" class="px-4 pb-4">

    <!-- Conversation history display -->
    <div id="qa-conversation" class="space-y-3 max-h-72 overflow-y-auto mb-3"></div>

    <!-- Context indicator -->
    <div class="text-xs text-muted-foreground mb-2">
      Context: <span id="qa-context-label">Architecture</span>
    </div>

    <!-- Input row -->
    <div class="flex gap-2">
      <input id="qa-input" type="text"
             placeholder="Ask a question about the codebase..."
             class="flex-1 border border-border rounded px-3 py-1.5 text-sm bg-background" />
      <button id="qa-submit-btn" class="px-4 py-1.5 bg-primary text-primary-foreground rounded text-sm font-medium">
        Ask →
      </button>
    </div>

  </div>
</div>
```

### JavaScript (embedded in template, no external file)

The script must handle:

1. **Panel collapse/expand**: Toggle `#qa-panel-body` visibility; swap icon between ▼ and ▶; update button text between "collapse" and "expand".

2. **Context tracking**: On load and on htmx navigation, read `document.querySelector('[data-context-level]')?.dataset` to get `contextLevel` ("architecture" | "module") and `contextDocId`, `modulePath`. Update `#qa-context-label` display text.

3. **Conversation history**: `let qaHistory = []` JS array. On each completed answer, push `{role: "user", content: question}` and `{role: "assistant", content: fullResponse}`. Cap at `MAX_HISTORY_TURNS * 2 = 10` messages in the JS array (trim oldest first).

4. **Submit**: On [Ask →] click or Enter key:
   - Read question from `#qa-input`; skip if empty
   - Disable `#qa-input` and `#qa-submit-btn`
   - Append user bubble to `#qa-conversation`
   - Append empty assistant bubble (streaming target) to `#qa-conversation`
   - POST JSON to `/api/projects/PROJECT_ID/code/qa` using `fetch()` (not htmx, not `EventSource` — fetch with ReadableStream for POST body streaming)
   - Read response body as a `ReadableStream`, decode line by line
   - Parse `data: {...}` lines: append tokens to assistant bubble; on `event: done`, store `full_response` in history; on `event: error`, show error message in bubble
   - Re-enable input, clear `#qa-input`, scroll `#qa-conversation` to bottom

5. **Streaming implementation note**: Because the endpoint is a POST with JSON body, use `fetch()` with `ReadableStream` response body parsing (not `EventSource` which only supports GET). Parse the SSE `data:` lines from the streaming response text.

6. **Auto-scroll**: After each token append, call `qaConversation.scrollTop = qaConversation.scrollHeight`.

7. **Loading state**: While streaming, show a spinner in the button; set `#qa-submit-btn` text to "..." and add `opacity-50` class.

### Message Bubble Templates (JS-generated HTML)

User bubble:
```html
<div class="bg-muted rounded-lg px-3 py-2 text-sm text-right ml-8">
  <span class="font-medium text-xs text-muted-foreground block mb-1">You</span>
  {question text}
</div>
```

Assistant bubble:
```html
<div class="bg-background border border-border rounded-lg px-3 py-2 text-sm mr-8" id="qa-assistant-bubble-{N}">
  <span class="font-medium text-xs text-muted-foreground block mb-1">Assistant</span>
  <span class="qa-response-text"></span>
</div>
```

Error bubble:
```html
<div class="bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2 text-sm text-destructive mr-8">
  ⚠ Local AI unavailable. Check that Ollama is running.
</div>
```

---

## Integration with project_code.html (F-00047)

The panel is included at the bottom of the `#code-architecture-panel` section in `project_code.html`:

```html
<!-- at the bottom of the Code tab content area -->
{% include "fragments/code_qa_panel.html" %}
```

The `project_code.html` template must set a `data-context-level` attribute on a stable container element so the Q&A panel JS can read the current context level:

```html
<div id="code-content-root"
     data-context-level="architecture"
     data-context-doc-id="{{ index_status.level1_doc_id | default('') }}"
     data-module-path="">
```

When Level 2 view is active (F-00048), the `data-context-level` is updated to `"module"` by the Level 2 fragment's JS.

---

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `orch/rag/qa.py` — QAEngine with streaming RAG + conversation history | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | api-impl | `POST /api/projects/{id}/code/qa` SSE endpoint in `dashboard/routers/code_qa.py` | — |
| S04 | code-review-impl | Review S03 output | — |
| S05 | frontend-impl | `code_qa_panel.html` fragment + embedded JS SSE client + context tracking | — |
| S06 | code-review-impl | Review S05 output | — |
| S07 | code-review-final-impl | Final cross-agent review | — |
| S08 | qv-gate (lint) | `uv run ruff check .` | — |
| S09 | qv-gate (format) | `uv run ruff format --check .` | — |
| S10 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S11 | qv-gate (unit-tests) | `uv run pytest tests/unit/ -v` | — |
| S12 | qv-gate (integration-tests) | `uv run pytest tests/integration/ -v --alluredir=allure-results` | — |

---

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00049_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00049_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `prompts/F-00049_S02_CodeReview_prompt.md` | Prompt | S02 code review of S01 |
| `prompts/F-00049_S03_API_prompt.md` | Prompt | S03 API implementation |
| `prompts/F-00049_S04_CodeReview_prompt.md` | Prompt | S04 code review of S03 |
| `prompts/F-00049_S05_Frontend_prompt.md` | Prompt | S05 frontend implementation |
| `prompts/F-00049_S06_CodeReview_prompt.md` | Prompt | S06 code review of S05 |
| `prompts/F-00049_S07_CodeReview_Final_prompt.md` | Prompt | S07 final cross-agent review |

## Files to Create / Modify

| File | Action |
|------|--------|
| `orch/rag/qa.py` | Create — QAEngine class |
| `dashboard/routers/code_qa.py` | Create — POST /api/projects/{id}/code/qa endpoint |
| `dashboard/app.py` | Modify — register `code_qa` router |
| `dashboard/templates/fragments/code_qa_panel.html` | Create — Q&A panel fragment |
| `dashboard/templates/project_code.html` | Modify — add data-context-level attrs + {% include %} |
| `tests/unit/test_qa_engine.py` | Create — unit tests for QAEngine |
| `tests/integration/test_code_qa_routes.py` | Create — integration tests for the endpoint |

---

## Acceptance Criteria

### AC1: Token Streaming

```
Given a project with an existing LanceDB index
And Ollama is available
When POST /api/projects/{project_id}/code/qa is called with a question
Then the response Content-Type is text/event-stream
And multiple data: {"token": "..."} events are received before done
And the final event is data: {"event": "done", "full_response": "..."}
```

### AC2: Context Level Filtering

```
Given context_level = "module" and module_path = "engine/"
When QAEngine retrieves chunks from LanceDB
Then only chunks with file_path starting with "engine/" are retrieved
```

### AC3: Architecture Context (No Filter)

```
Given context_level = "architecture"
When QAEngine retrieves chunks from LanceDB
Then all chunks in the index are candidates (no file_path filter)
```

### AC4: Conversation History Truncation

```
Given MAX_HISTORY_TURNS = 5
And conversation_history has 12 messages (6 turns)
When _truncate_history() is called
Then only the last 10 messages (5 turns) are returned
```

### AC5: Ollama Unavailable

```
Given Ollama is not reachable
When POST /api/projects/{project_id}/code/qa is called
Then the SSE stream delivers data: {"event": "error", "message": "..."}
And the stream closes gracefully
```

### AC6: Project Not Found

```
Given a project_id that does not exist
When POST /api/projects/{project_id}/code/qa is called
Then HTTP 404 is returned (not a stream)
```

### AC7: No Index Found

```
Given a valid project_id but no LanceDB index exists on disk
When POST /api/projects/{project_id}/code/qa is called
Then HTTP 404 is returned with message "No code index found for this project"
```

### AC8: Input Validation

```
Given a question with more than 1000 characters
When POST /api/projects/{project_id}/code/qa is called
Then HTTP 400 is returned
```

### AC9: UI Panel — Collapse/Expand

```
Given the Q&A panel is rendered on the Code tab
When the user clicks the collapse button
Then the panel body is hidden and the icon changes to ▶
When the user clicks again
Then the panel body is shown and the icon changes to ▼
```

### AC10: UI Panel — Context Label Updates

```
Given the user is viewing the architecture (Level 1) view
Then the context label in the Q&A panel shows "Architecture"
Given the user navigates to the engine/ module (Level 2) view
Then the context label updates to "engine/ module"
```

---

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty question | `question: ""` | HTTP 400 |
| Question > 1000 chars | Long string | HTTP 400 |
| Invalid context_level | `"symbol"` (not yet supported) | HTTP 400 |
| Project not in DB | Unknown project_id | HTTP 404 |
| No LanceDB index | Valid project, no index | HTTP 404 |
| Ollama connection refused | Ollama not running | SSE error event, stream closes |
| Empty conversation history | `conversation_history: []` | Works (first turn) |
| History > MAX_HISTORY_TURNS | 6+ turns sent | Truncated to 5 turns before LLM call |
| context_doc_id not found | Invalid doc ID | Use empty context doc content, do not fail |
| No chunks retrieved | Question about topic not in codebase | LLM answers with "No relevant code found" in prompt |

## Invariants

1. Conversation history is NEVER stored server-side — it is fully client-owned.
2. `answer_stream()` is an `AsyncGenerator[str, None]` — it yields individual token strings.
3. The SSE stream always ends with either a `done` or `error` event — never silently.
4. LanceDB table name always follows `code_{project_id.replace('-', '_')}`.
5. `MAX_HISTORY_TURNS = 5` is enforced by `_truncate_history()` in the engine, not in the router.
6. The template fragment does NOT extend `base.html`.

## Dependencies

- **Depends on**: F-00047 (Code tab container with `data-context-level` attribute), F-00046 (LanceDB index, `CodeIndexer`, `CodeUnderstandingConfig`)
- **Parallel with**: F-00048 (Level 2 Component Docs)
- **Blocks**: None

## Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v --alluredir=allure-results
```

Browser verification is required: use `playwright-cli` to confirm the Q&A panel renders, collapses, and shows the context label correctly.

## TDD Approach

- **Unit tests** (`tests/unit/test_qa_engine.py`): `_build_system_prompt()` output shape with and without context doc; `_truncate_history()` below / at / above `MAX_HISTORY_TURNS`; `answer_stream()` returns an async generator; `answer_stream()` yields an `__ERROR__:` token when Ollama raises `httpx.ConnectError`. All external calls (LanceDB, Ollama) patched with `unittest.mock`.
- **Integration tests** (`tests/integration/test_code_qa_routes.py`): project-not-found (404); index-not-found (404); Pydantic validation failures (422: empty question, > 1000 chars, invalid `context_level`); happy-path SSE stream (tokens + `done` event); `__ERROR__:` → SSE error event; empty `conversation_history` works. `QAEngine.answer_stream` patched — no live Ollama, no real LanceDB. Uses testcontainers for PostgreSQL per `tests/CLAUDE.md`.
- **Edge cases**: `context_doc_id` referencing a non-existent doc (engine uses empty context, does not fail); empty retrieved chunk set; conversation history of exactly `MAX_HISTORY_TURNS * 2` messages (boundary); streaming responses that get interrupted mid-token.
- **Browser verification**: `playwright-cli` confirms the panel renders on the Code tab, collapses/expands correctly, and the context label updates after Level 2 navigation.

## Notes

- **Depends on unbuilt packages**: `orch/rag/config.py` (`CodeUnderstandingConfig`) and `orch/rag/indexer.py` (`CodeIndexer`, LanceDB table naming) are delivered by F-00045/F-00046. F-00049 cannot start until those merge. The batch planner must sequence accordingly.
- **LanceDB filter syntax**: LanceDB accepts SQL-style WHERE clauses on metadata columns via `table.search(vec).where("file_path LIKE 'engine/%'")`. The backend agent must verify the exact syntax against the LanceDB version pinned in `pyproject.toml` before committing to a filter string.
- **SSE error envelope safety**: The API layer MUST serialize error events with `json.dumps({"event": "error", "message": msg})` rather than f-string interpolation, so error messages containing quotes or backslashes cannot break the stream contract.
- **Statelessness**: Conversation history is owned exclusively by the browser. Reloading the page clears history by design — no server-side persistence is in scope for this feature.
- **Parallel with F-00048**: This feature shares the Code tab container with F-00048 (Level 2 views). Both must agree on the `data-context-level` / `data-module-path` contract on `#code-content-root`. F-00048 is responsible for updating those attributes when navigating into a module; F-00049 only reads them.
- **Risk**: If F-00047 does not expose `current_project` to `project_code.html`, the `QA_PROJECT_ID` template variable in S05 will be empty. The frontend agent must verify the Jinja context before rendering.
