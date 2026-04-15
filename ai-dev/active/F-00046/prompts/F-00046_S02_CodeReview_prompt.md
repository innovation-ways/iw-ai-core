# F-00046_S02_CodeReview_prompt

**Work Item**: F-00046 -- Code Understanding: Indexing Engine + Level 1 Map Generation
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00046/F-00046_Feature_Design.md` -- Design document
- `ai-dev/work/F-00046/reports/F-00046_S01_Backend_report.md` -- S01 implementation report
- `orch/rag/indexer.py` -- CodeIndexer
- `orch/rag/job.py` -- CodeIndexJobRunner + JOB_REGISTRY
- `orch/rag/mapgen.py` -- MapGenerator
- `tests/unit/test_code_indexer.py` -- Unit tests

## Output Files

- `ai-dev/work/F-00046/reports/F-00046_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the S01 backend implementation for F-00046. This step built three new modules: `CodeIndexer`, `CodeIndexJobRunner`, and `MapGenerator`. Read the design document first to understand what was intended, then read the S01 report and all implementation files.

## Review Checklist

### 1. Architecture Compliance

- Does `CodeIndexer` exactly match the class signature in the design document? Check all method signatures including `progress_callback` parameter.
- Does `CodeIndexJobRunner` implement the full job lifecycle (all 11 steps listed in the design)?
- Is `JOB_REGISTRY` a module-level dict in `orch/rag/job.py`, not inside a class?
- Is `start_index_job(job, project, *, mode)` defined in `orch/rag/job.py`, and does it raise `JobAlreadyRunningError` when `JOB_REGISTRY[project.id]` is already populated?
- Is `JobAlreadyRunningError` defined in `orch/rag/job.py` and exported (either directly or via `orch/rag/__init__.py`)?
- Does `CodeIndexJobRunner.__init__` accept `mapgen_only: bool = False`, and does `run()` skip the indexing phase when it is True?
- **Scope boundary**: is there any new file under `dashboard/routers/`? If yes — CRITICAL scope violation (HTTP layer belongs to F-00047).
- Does `MapGenerator` use all 8 `QUESTIONS` from the design document?
- Is the LanceDB store path correctly constructed as `{index_path}/{project_id}/vectors/`?
- Is the manifest path correctly `{index_path}/{project_id}/manifest.json`?
- Is the LanceDB table name `f"code_{project_id.replace('-', '_')}"` (with hyphens replaced by underscores)?
- Does `MapGenerator._assemble_markdown()` produce all 8 sections plus the Mermaid diagram?
- Is the `ProjectDoc` created with `doc_type="research"`, `tier="fully_automated"`, `editorial_category="technical"`?
- Is `generated_by = "code-understanding:level1"` set on the ProjectDoc?
- Does `CodeIndexJobRunner.run()` remove itself from `JOB_REGISTRY` in a `finally` block?

### 2. Chunking and Language Support

- Is `CodeSplitter` used with `chunk_lines=40, chunk_lines_overlap=5`?
- Is `language="python"` used for `.py` files?
- Is `language="cpp"` used for `.cpp`/`.hpp`/`.h` files?
- Is there a `try/except` fallback to character-based splitting when tree-sitter fails on C++?
- Are hidden directories (`.git`, `__pycache__`, `.venv`, `node_modules`) excluded from file discovery?
- Are the correct file extensions included: `.py`, `.cpp`, `.hpp`, `.h`?

### 3. Error Handling

- If Ollama is unreachable, does the error propagate correctly to `CodeIndexJobRunner.run()`?
- Does `CodeIndexJobRunner.run()` catch ALL exceptions (not just specific types)?
- Is `str(e)` stored in the `errors` JSONB field on failure?
- Is the error phase event `{"event": "progress", "phase": "error", "message": str(e)}` emitted?

### 4. Progress Events

- Are progress events emitted during the indexing loop (not just at the end)?
- Does the progress event structure match exactly: `{"event": "progress", "files_indexed": N, "files_total": M, "chunks_created": K, "phase": "indexing"}`?
- Is there a `phase="mapgen"` event emitted before map generation starts?
- Is there a `phase="done"` event emitted on successful completion?

### 5. Code Quality

- Are there type annotations on all public methods?
- Is there appropriate error handling in `_build_mermaid()` for the case where mermaid extraction fails?
- Does `_build_mermaid()` fall back to a minimal valid diagram if parsing fails?
- Are imports organized correctly (stdlib, third-party, local)?
- No hardcoded paths, URLs, or model names — everything from config?

### 6. Session Handling

- If `orch/db/session.py` only provides sync sessions, are DB calls wrapped in `asyncio.to_thread()`?
- No session leaked between calls (sessions closed/committed properly)?

### 7. Testing

- Are all 10 unit tests from the S01 prompt present in `tests/unit/test_code_indexer.py`?
- Do test names clearly describe what they verify?
- Are tests truly unit tests (no DB, no network, no file system beyond `tmp_path`)?
- Does `test_manifest_roundtrip` use `tmp_path` for isolation?
- Does `test_build_mermaid_contains_graph_td` mock the Ollama LLM call?

### 8. Security

- No hardcoded credentials, API keys, or secrets
- Input validation: `repo_path` existence checked before walking?
- No path traversal vulnerability in manifest path construction?

## Test Verification (NON-NEGOTIABLE)

Before submitting review:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/
uv run pytest tests/unit/ -v
```

Report results accurately.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00046",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
