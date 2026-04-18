# CR-00009_S01_Backend_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md` — design document
- `orch/rag/qa.py` — file to modify

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S01_Backend_report.md` — step report

## Context

You are extending the RAG QA engine so that the LLM is aware of which module the user is currently viewing, and so that retrieval gracefully falls back when the module-scoped search returns nothing. Read the design document's **Current Behavior**, **Desired Behavior**, and **Acceptance Criteria** (AC3, AC4, AC5) before coding. Read `CLAUDE.md` and `orch/CLAUDE.md` for conventions.

## Requirements

### 1. Extend `_build_system_prompt` signature and output

Current signature (`orch/rag/qa.py:124`):

```python
def _build_system_prompt(self, context_doc_content: str, chunks: list[str]) -> str:
```

New signature:

```python
def _build_system_prompt(
    self,
    context_doc_content: str,
    chunks: list[str],
    module_path: str | None = None,
    module_name: str | None = None,
    fallback_triggered: bool = False,
) -> str:
```

Prompt structure:

```
You are a codebase expert assistant. Answer questions about the codebase accurately and concisely.

## Current Focus — Module      <-- only when module_path is non-empty
The user is currently viewing the `<module_path>` module[ ("<module_name>")].
Prioritize this module in your answer. If the question is clearly about this module,
ground your answer in the excerpts below and the module's role in the architecture.

## Retrieval Note               <-- only when fallback_triggered is True
No indexed content matched the current module on the first retrieval pass.
The excerpts below come from a project-wide fallback search. If the excerpts do not
cover the module directly, say so explicitly in your answer.

## Architecture Context

<context_doc_content or "(No architecture document available)">

## Relevant Code Excerpts

<for each chunk: "---\n{chunk}\n">

Answer the user's question based on the above context.
If the context does not contain enough information, say so clearly.
```

Rules:

- Omit the `## Current Focus — Module` block entirely when `module_path` is `None` or empty string.
- When `module_name` is empty/None, render the module block with just the path: `` The user is currently viewing the `<module_path>` module. ``
- Omit the `## Retrieval Note` block when `fallback_triggered` is `False`.
- All existing behavior when no module is set must be byte-identical to today. This is critical for the tests.

### 2. Implement the retrieval fallback in `answer_stream`

Current retrieval (lines 67-88): when `context_level == "module"` and `module_path` is set, LanceDB is searched with a `file_path LIKE '<module_path>%'` filter. If that search returns zero rows, the LLM only sees the architecture doc.

Change: after the filtered search resolves, if `context_level == "module"`, `module_path` is truthy, AND the filtered search returned zero chunks, execute a second search without the `file_path LIKE` filter (the seed filter still applies). Record whether the fallback fired in a local `fallback_triggered: bool` variable.

Pass `module_path`, `module_name`, and `fallback_triggered` through to `_build_system_prompt`.

Rules:

- The unfiltered search uses the same `embedding_vector`, the same `seed_filter`, and the same `self.TOP_K`.
- If the initial `try` block raises an exception (LanceDB unavailable), keep existing behavior — `chunks = []`, no fallback attempt (the module block is still emitted; `fallback_triggered` stays `False` so we don't lie about a fallback we didn't run).
- When `context_level != "module"` or `module_path` is empty, the first search already runs unfiltered — do NOT fall back a second time.

### 3. Add a `module_name` parameter to `answer_stream`

Current signature (line 36):

```python
async def answer_stream(
    self,
    question: str,
    context_level: str,
    context_doc_id: str | None,
    conversation_history: list[dict[str, str]],
    session: AsyncSession,
    module_path: str | None = None,
) -> AsyncGenerator[str, None]:
```

Add `module_name: str | None = None` after `module_path`. Forward it to `_build_system_prompt`. Default `None` so existing callers (router, tests) are untouched.

### 4. Keep the architecture context block exactly as-is when no module is set

AC5 requires byte-identical output for the no-module case. The simplest safe implementation is: build the module block and retrieval-note block as optional strings, concatenate them only when non-empty, and leave the rest of the prompt template unchanged.

## Project Conventions

- Read `CLAUDE.md` (root), `orch/CLAUDE.md` for the `orch/rag/` layer (sync SQLAlchemy; the QA module is an exception that uses async because it's called from FastAPI streaming).
- No new dependencies. No changes to Ollama / LanceDB client code beyond what's described.
- Follow the existing docstring style in `orch/rag/qa.py` — terse module-level docstrings and a multi-line description in `_build_system_prompt`.
- Do not add Python comments that only restate what the code does. A one-line comment explaining the fallback's *why* (module miss → degraded but useful) is acceptable.

## TDD Requirement

Follow RED → GREEN → REFACTOR:

1. **RED**: Do NOT write the S07 tests here — that's the tests-impl agent's job. Instead, write a *scratch* test or use the Python REPL to assert your new prompt branches render correctly, then delete the scratch. Alternatively: if `tests/unit/test_qa_engine.py` already exists, you MAY extend it with minimal tests covering AC3/AC4/AC5 branches (module block present/absent, retrieval-note present/absent). S07 will expand coverage.
2. **GREEN**: Implement the changes above.
3. **REFACTOR**: Keep the function readable. If the prompt construction grows past ~30 lines, extract the block builders into private helpers (`_module_block`, `_retrieval_note_block`) — but only if it improves readability.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit`
2. `uv run ruff check orch/rag/qa.py`
3. `uv run mypy orch/rag/qa.py`
4. Do NOT report `tests_passed: true` unless all three pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00009",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/qa.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
