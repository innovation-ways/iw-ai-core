# F-00060_S07_Tests_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S07 — Cross-layer test coverage
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same rules as S01. Testcontainers via pytest fixtures allowed.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — *TDD Approach*, *Boundary Behavior*, *Invariants*
- All S01..S06 reports
- `tests/conftest.py`, `tests/integration/conftest.py`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S07_Tests_report.md` (new)
- Any integration or unit test files listed in the design's *File Manifest*
  that are not already present from S01..S06 (each prior step wrote its own
  RED-phase tests; this step closes gaps and adds cross-layer coverage).

## Context

S01..S06 each did their own TDD. This step exists to close Boundary Behavior
and Invariant coverage that spans multiple layers, plus any gap identified
during the code-review pass.

## Requirements

### 1. Fill Boundary Behavior coverage

For every row in the design doc's *Boundary Behavior* table, ensure at
least one test exists. Add tests for any row still uncovered:

- Retriever invoked on a project with zero work items.
- Semantic index missing (LanceDB table absent) → FTS + git-log carry the
  answer.
- Simulated LanceDB I/O error → semantic contribution empty; no exception
  escapes.
- Code chunks with no file overlap with any work item → empty
  `git_log_items`.
- Same work item in all three sources → single row; scores summed.
- LLM hallucinates a non-allowed ID → stripped from both text and citations.
- Concurrent re-index → 409.
- Reindex with all items unchanged → `items_indexed=0`.
- Embed-model change → table dropped + full re-index.
- Daemon kill mid-embedding → orphan recovery marks failed.
- Question length > context window → docs truncated, question preserved.
- Functional doc with NUL chars → sanitised before embedding.

### 2. Enforce every Invariant

- Inv 1: `answer_stream` code-only path byte-for-byte unchanged — include a
  snapshot test of the generated system prompt for a known code-only
  question.
- Inv 2: No new code writes to `code_index_jobs`. Grep-based assert in a
  test (or inspect the sqlalchemy ORM query log via event listener
  fixture).
- Inv 3: Every emitted citation has `work_item_id ∈ bundle.allowed_ids`.
  Assert in every retriever integration test.
- Inv 4: Cross-project data isolation — insert docs in project A and B,
  query from A, expect zero B rows.
- Inv 5: Monotonic status transitions — attempt invalid transition and
  assert it is not accepted.
- Inv 6: Orphan recovery runs before poll — assert ordering via a boot
  simulator in the integration tests.
- Inv 7: Prompt contains at most 3 full docs + 5 chunk snippets — assert
  on the generated prompt string.

### 3. Regression guard for `code_only`

Add `tests/integration/test_qa_v2_code_only_regression.py` that runs a
representative "show me the signature of foo" question end-to-end through
`answer_stream_v2` and asserts the response matches the pre-F-00060
behaviour (no Work Item Context section; no retrieve/finding-items/reading-docs
phase events).

### 4. Relevance-filter regression eval

Add a unit test `tests/unit/test_qa_v2_relevance_filter_eval.py` that:

- Builds a mock bundle with three items: F-A (added button), CR-B (coloured
  it blue), CR-C (reshaped to square).
- Produces a mocked LLM output that narrates only the colour history and
  cites only CR-B.
- Asserts that the final emitted citation list contains only CR-B.
- Asserts that CR-C is absent from both text and citations.

This is the long-term regression backstop for AC3 — it will catch future
prompt-layout or allowlist changes that regress the filter.

## Project Conventions

Read `tests/CLAUDE.md`. Testcontainer fixtures only; never live DB. LanceDB
tests use `tmp_path` fixtures for the index URI. Mock Ollama embeddings at
the interface level (inject a fake embedder) — do not rely on a running
Ollama instance for these tests.

## TDD Requirement

This step is test-only. Each added test MUST pass against the S01..S06
implementation. A failing test implies a prior-step regression — report it
as a blocker rather than patching the test to green.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass, zero failures.
2. `make test-integration` — pass, zero failures.
3. `make lint` + `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S07"`, `agent: "tests-impl"`, `work_item: "F-00060"`.
Include counts of new tests added per file in `notes`.
