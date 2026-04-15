# F-00046_S05_CodeReview_Final_prompt

**Work Item**: F-00046 -- Code Understanding: Indexing Engine + Level 1 Map Generation
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## Input Files

- `ai-dev/active/F-00046/F-00046_Feature_Design.md` -- Design document
- `ai-dev/work/F-00046/reports/F-00046_S01_Backend_report.md`
- `ai-dev/work/F-00046/reports/F-00046_S02_CodeReview_report.md`
- `ai-dev/work/F-00046/reports/F-00046_S03_Tests_report.md`
- `ai-dev/work/F-00046/reports/F-00046_S04_CodeReview_report.md`
- All implementation files listed in reports

## Output Files

- `ai-dev/work/F-00046/reports/F-00046_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the final cross-agent review of ALL implementation work for F-00046. Two implementation agents (backend-impl, tests-impl) and two per-step reviewers have already done their work. Your job is to look at the complete picture and catch cross-cutting issues that individual reviews could not.

**Scope reminder (Option C)**: F-00046 is **Python-only library code**. It builds `orch/rag/*.py` and exposes `start_index_job` / `JOB_REGISTRY` / `CodeIndexJobRunner` / `JobAlreadyRunningError` for F-00047 to consume. There is NO `dashboard/routers/code*.py` file in F-00046's scope. If you find HTTP routes, FastAPI routers, or `TestClient` usage anywhere in this work, flag it CRITICAL as a scope violation — that work belongs to F-00047.

Read the design document to understand the full intended scope. Then read all reports and review all implementation files holistically.

## Review Checklist

### 1. Completeness vs Design Document

Verify every item from the Feature Design is implemented:

- [ ] `orch/rag/indexer.py` with `CodeIndexer` and `IndexResult` — all methods present
- [ ] `orch/rag/job.py` with `CodeIndexJobRunner`, `JOB_REGISTRY`, `start_index_job`, and `JobAlreadyRunningError`
- [ ] `orch/rag/mapgen.py` with `MapGenerator` and all 8 `QUESTIONS`
- [ ] Unit tests covering SHA manifest logic, config resolution, Mermaid generation
- [ ] Integration tests in `tests/integration/test_code_index_pipeline.py` covering all AC scenarios at the Python API level

Verify all Acceptance Criteria from the design:
- [ ] AC1: Full index cycle completes, ProjectDoc created, CodeIndexJob.status = "completed"
- [ ] AC2: Incremental reindex processes only changed files
- [ ] AC3: Progress queue delivers progress + terminal `done` events
- [ ] AC4: Ollama unavailable → CodeIndexJob.status = "failed" with error, terminal `phase="error"`
- [ ] AC5: Duplicate `start_index_job` call → `JobAlreadyRunningError` raised
- [ ] AC6: `mode="mapgen_only"` updates existing ProjectDoc (upsert, not duplicate)

### 2. Python API Surface

- Does `start_index_job(job, project, *, mode)` have the exact signature the design specifies?
- Are the three `mode` values (`"full"`, `"incremental"`, `"mapgen_only"`) all handled?
- Does `start_index_job` register the runner in `JOB_REGISTRY` **synchronously** before returning (not inside `run()`)?
- Is `JobAlreadyRunningError` defined in `orch/rag/job.py` and exported?
- Is the API surface (`start_index_job`, `JOB_REGISTRY`, `CodeIndexJobRunner`, `JobAlreadyRunningError`) exported from `orch/rag/__init__.py` or a documented path so F-00047 can import it cleanly?

### 3. JOB_REGISTRY Lifecycle

- Is `JOB_REGISTRY` defined at module level in `orch/rag/job.py`?
- Does `CodeIndexJobRunner.run()` always remove itself from the registry in a `finally` block (including on exception)?
- Could two concurrent calls to `start_index_job` for the same project both pass the check and both register? (The event loop serializes sync code — document this assumption.)

### 4. Invariant Verification

Check each invariant from the design document is enforced:
1. `JOB_REGISTRY` has at most one entry per project_id — verified by `start_index_job` raising `JobAlreadyRunningError`
2. Running job always in JOB_REGISTRY — verified by `start_index_job` registering before scheduling
3. Manifest SHA reflects LanceDB state — verified by saving manifest after successful indexing only
4. ProjectDoc slug is unique per project — verified by upsert logic in MapGenerator
5. Failed job has non-empty `errors` — verified by error handling in runner
6. LanceDB table name follows pattern — verified consistently across indexer and tests

### 5. Boundary Behaviors

Verify test coverage for every row in the "Boundary Behavior" table from the design:
- [ ] Job already running → `JobAlreadyRunningError`
- [ ] Empty repository → completed with 0 files
- [ ] C++ file with parse error → fallback chunking, no error
- [ ] Ollama HTTP error → failed job with error recorded + terminal `phase="error"` on queue
- [ ] Manifest missing → full index (treat all as changed)
- [ ] ProjectDoc already exists → upsert (not duplicate)
- [ ] Runner registration race → second call raises `JobAlreadyRunningError`

### 6. New Dependencies

- Were the new packages installed via `uv add`? Check `pyproject.toml` for:
  - `llama-index-core`
  - `llama-index-llms-ollama`
  - `llama-index-embeddings-ollama`
  - `llama-index-vector-stores-lancedb`
  - `lancedb`
  - `tree-sitter`
  - `tree-sitter-languages`

### 7. Architecture and Layer Boundaries

- **No HTTP / FastAPI / router code anywhere in F-00046's output** (scope moved to F-00047).
- **No `dashboard/routers/code*.py` file created by this feature.**
- `orch/rag/` modules do not import from `dashboard/`.
- DB session management is consistent — inside background tasks, the runner opens its own `SessionLocal()` (wrapped in `asyncio.to_thread` for sync calls).

### 8. Security

- No hardcoded paths, URLs, credentials across any file?
- LanceDB index path is restricted to `IW_CORE_INDEX_PATH` (no path traversal via `project_id`)?

## Test Verification (NON-NEGOTIABLE)

Run the full test suite before submitting:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v --alluredir=allure-results
```

Integration test failures are CRITICAL findings. Report all results accurately.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, scope violation (HTTP layer in F-00046), missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00046",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security|scope",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
