# F-00049_S01_Backend_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Full design document (read this first)
- `orch/rag/qa.py` — Does not exist yet; you are creating it
- `orch/rag/__init__.py` — Existing package init (read before writing)
- `orch/rag/config.py` — `CodeUnderstandingConfig` (read before writing)
- `orch/rag/indexer.py` — `CodeIndexer` (read to understand LanceDB table naming and embedding conventions)
- `orch/db/models.py` — `ProjectDoc` model (read to understand how to query it)
- `orch/db/session.py` — Session factory (read before writing)
- `tests/conftest.py` — Existing test fixtures (read before writing tests)
- `tests/CLAUDE.md` — Testing rules (NON-NEGOTIABLE)
- `CLAUDE.md` — Project-level conventions (NON-NEGOTIABLE)

## Output Files

- `orch/rag/qa.py` — New file: QAEngine class
- `tests/unit/test_qa_engine.py` — Unit tests for QAEngine
- `ai-dev/work/F-00049/reports/F-00049_S01_Backend_report.md` — Step report

---

## Context

You are implementing `orch/rag/qa.py` for **F-00049: Code Understanding Q&A Panel**. This module provides a context-aware RAG Q&A engine that streams answer tokens via an async generator. It is called by the API layer (S03) which wraps it into an SSE `StreamingResponse`.

Read `CLAUDE.md`, `orch/rag/config.py`, and `orch/rag/indexer.py` before writing any code.

---

## Requirements

### 1. File: orch/rag/qa.py

Create `orch/rag/qa.py` with the following class. Follow all conventions from the existing `orch/rag/` package.

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from orch.rag.config import CodeUnderstandingConfig


class QAEngine:
    """
    Context-aware RAG Q&A engine with streaming response and conversation history.

    Conversation history is passed in on each call — this class is stateless.
    """

    TOP_K: int = 8
    MAX_HISTORY_TURNS: int = 5  # Keep last 5 turns (10 messages) in context

    def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None: ...

    async def answer_stream(
        self,
        question: str,
        context_level: str,
        context_doc_id: str | None,
        conversation_history: list[dict],
        session: AsyncSession,
        module_path: str | None = None,
    ) -> AsyncGenerator[str, None]: ...

    def _build_system_prompt(
        self, context_doc_content: str, chunks: list[str]
    ) -> str: ...

    def _truncate_history(self, history: list[dict]) -> list[dict]: ...
```

**Implementation details for `answer_stream()`**:

1. **Embed question**: Use `OllamaEmbedding` (from `llama_index.embeddings.ollama`) initialized with `config.resolved_embed_model()` and `config.ollama_base_url`. Call `.get_query_embedding(question)` to obtain the embedding vector.

2. **LanceDB retrieval**:
   - Open LanceDB at `{config.index_path}/{project_id}/vectors/` using `lancedb.connect()`
   - Table name: `f"code_{project_id.replace('-', '_')}"`
   - If `context_level == "module"` and `module_path` is known: apply a metadata filter on `file_path` (pass `module_path` as a parameter through the engine; derive it from `context_doc_id` or pass explicitly — see note below)
   - Query: `table.search(embedding_vector).limit(TOP_K).to_pandas()` (or equivalent)
   - Collect the `text` column from the result rows as `list[str]`

3. **Load context doc**: If `context_doc_id` is not None, query the DB:
   ```python
   from sqlalchemy import select
   from orch.db.models import ProjectDoc
   result = await session.execute(select(ProjectDoc).where(ProjectDoc.id == context_doc_id))
   doc = result.scalar_one_or_none()
   context_doc_content = doc.content if doc else ""
   ```

4. **Build prompt**: Call `_build_system_prompt(context_doc_content, chunks)`.

5. **Truncate history**: Call `_truncate_history(conversation_history)` to cap at `MAX_HISTORY_TURNS * 2` messages.

6. **Build LlamaIndex messages**: Create a list of `ChatMessage` objects:
   - First: system message with the system prompt
   - Then: inject truncated conversation history as alternating user/assistant `ChatMessage` objects
   - Last: user `ChatMessage` with the current `question`

7. **Stream via Ollama**: Initialize `OllamaLLM` (from `llama_index.llms.ollama`) with `config.resolved_chat_model()` and `config.ollama_base_url`. Call `await llm.astream_chat(messages)` to obtain an async generator of `ChatResponse` chunks. Yield `chunk.delta` for each chunk.

**Note on module_path**: `answer_stream()` needs the `module_path` to filter LanceDB when `context_level == "module"`. Add `module_path: str | None = None` as an optional parameter to `answer_stream()`. When `module_path` is provided and `context_level == "module"`, apply the LanceDB filter.

**Implementation details for `_build_system_prompt()`**:

```
You are a codebase expert assistant. Answer questions about the codebase accurately and concisely.

## Architecture Context

{context_doc_content if non-empty, else "(No architecture document available)"}

## Relevant Code Excerpts

{for each chunk: "---\n{chunk}\n"}

Answer the user's question based on the above context. If the context does not contain enough information, say so clearly.
```

**Implementation details for `_truncate_history()`**:

Return the last `MAX_HISTORY_TURNS * 2` items from `history`. If `len(history) <= MAX_HISTORY_TURNS * 2`, return all items unchanged.

**Error handling in `answer_stream()`**:

- Wrap the Ollama LLM call in a try/except for `httpx.ConnectError` and `ConnectionRefusedError`. On these exceptions, yield the string `"__ERROR__:Local AI unavailable. Check that Ollama is running."` and return (do not re-raise). The API layer will detect this special prefix and convert it to an SSE error event.
- Wrap the LanceDB table open in a try/except for `FileNotFoundError` or any `Exception` indicating the table does not exist. If the index is missing, yield chunks from the prompt with empty context (graceful degradation) — the missing index case is a hard 404 at the API layer before `QAEngine` is called, so the engine itself need not re-raise.

---

### 2. Unit Tests: tests/unit/test_qa_engine.py

**NON-NEGOTIABLE rules** (from `tests/CLAUDE.md`):
- NEVER connect to live DB port 5433
- Unit tests must be fast and use mocking/patching, not testcontainers
- Do NOT call `Base.metadata.create_all()` in unit tests

**Test cases (TDD: write RED first)**:

```python
# test_build_system_prompt_includes_context_doc
# Given: context_doc_content = "MyApp is a web app", chunks = ["def foo(): pass"]
# When: engine._build_system_prompt(context_doc_content, chunks) is called
# Then: returned string contains "MyApp is a web app"
# And: returned string contains "def foo(): pass"
# And: returned string contains "Architecture Context"
# And: returned string contains "Relevant Code Excerpts"

# test_build_system_prompt_empty_context_doc
# Given: context_doc_content = "", chunks = ["def bar(): ..."]
# When: engine._build_system_prompt("", chunks) is called
# Then: returned string contains "(No architecture document available)"
# And: returned string contains "def bar(): ..."

# test_truncate_history_within_limit
# Given: history with 4 messages (2 turns)
# When: engine._truncate_history(history) is called
# Then: all 4 messages are returned unchanged (within MAX_HISTORY_TURNS)

# test_truncate_history_at_limit
# Given: history with exactly 10 messages (5 turns = MAX_HISTORY_TURNS)
# When: engine._truncate_history(history) is called
# Then: all 10 messages returned unchanged

# test_truncate_history_exceeds_limit
# Given: history with 12 messages (6 turns)
# When: engine._truncate_history(history) is called
# Then: only the last 10 messages are returned
# And: len(result) == 10

# test_truncate_history_empty
# Given: history = []
# When: engine._truncate_history([]) is called
# Then: [] is returned

# test_answer_stream_returns_async_generator
# Given: QAEngine initialized with a mock config and mocked LanceDB/Ollama dependencies
# When: answer_stream() is called
# Then: the return type is an AsyncGenerator (has __aiter__ and __anext__)
# Implementation note: patch lancedb.connect, OllamaEmbedding, OllamaLLM at module level

# test_answer_stream_error_token_on_ollama_down
# Given: OllamaLLM.astream_chat raises httpx.ConnectError
# When: answer_stream() is consumed
# Then: the first yielded token starts with "__ERROR__:"
```

For tests that call `answer_stream()`, use `unittest.mock.AsyncMock` and `unittest.mock.patch` to mock:
- `lancedb.connect` → returns a mock table with a `.search().limit().to_pandas()` chain returning an empty DataFrame
- `llama_index.embeddings.ollama.OllamaEmbedding.get_query_embedding` → returns a list of floats
- `llama_index.llms.ollama.OllamaLLM.astream_chat` → returns an async generator yielding mock `ChatResponse` objects with `.delta` attribute

---

## Project Conventions

- `from __future__ import annotations` at top of every new file
- Use `TYPE_CHECKING` guard for type-only imports (especially `AsyncSession`)
- Async functions use `async def`; async generators use `async def` + `yield`
- Follow the existing import style in `orch/rag/indexer.py`
- No hardcoded model names — always use `config.resolved_chat_model()` and `config.resolved_embed_model()`
- No hardcoded paths — always use `config.index_path`
- `orch/rag/qa.py` must be importable with `from orch.rag.qa import QAEngine`

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write all unit tests in `tests/unit/test_qa_engine.py` first. They should fail (ImportError is acceptable at this stage since `qa.py` does not exist).
2. **GREEN**: Create `orch/rag/qa.py` with the full implementation. Run tests and verify they pass.
3. **REFACTOR**: Clean up any duplication, ensure docstrings are accurate, remove dead code.

Do not skip the RED phase.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run: `uv run pytest tests/unit/test_qa_engine.py -v`
2. Run: `uv run ruff check orch/rag/qa.py tests/unit/test_qa_engine.py`
3. Run: `uv run mypy orch/rag/qa.py`
4. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures
5. If tests fail, fix them before reporting completion

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/qa.py",
    "tests/unit/test_qa_engine.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
