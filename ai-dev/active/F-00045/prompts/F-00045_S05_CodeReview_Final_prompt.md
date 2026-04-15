# F-00045_S05_CodeReview_Final_prompt

**Work Item**: F-00045 -- Code Understanding: Foundation
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## Input Files

- `ai-dev/active/F-00045/F-00045_Feature_Design.md` — Design document
- `ai-dev/work/F-00045/reports/F-00045_S01_Database_report.md` — S01 implementation report
- `ai-dev/work/F-00045/reports/F-00045_S02_CodeReview_report.md` — S02 review report
- `ai-dev/work/F-00045/reports/F-00045_S03_Backend_report.md` — S03 implementation report
- `ai-dev/work/F-00045/reports/F-00045_S04_CodeReview_report.md` — S04 review report
- All files changed across S01 and S03:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/<revision_id>_add_code_index_jobs.py`
  - `orch/rag/__init__.py`
  - `orch/rag/config.py`
  - `orch/config.py`
  - `tests/integration/test_code_index_job.py`
  - `tests/unit/test_rag_config.py`

## Output Files

- `ai-dev/work/F-00045/reports/F-00045_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **Code Understanding: Foundation (F-00045)**.

This feature has two implementation agents (database-impl in S01, backend-impl in S03) whose work must integrate correctly. Per-agent reviews were done in S02 and S04. Your job is to catch cross-cutting issues they could not — integration, completeness, consistency, and holistic test coverage.

---

## Review Checklist

### 1. Completeness vs Design Document

Verify every item from the design document's "In Scope" section has been implemented:

- [ ] `code_index_jobs` table created (via migration + ORM model)
- [ ] `CodeIndexJob` ORM model in `orch/db/models.py`
- [ ] Alembic migration chaining from `add_doc_instance_guides` (the actual current head — not `f7a8b9c0d1e2`, which is several revisions behind)
- [ ] `orch/rag/__init__.py` created
- [ ] `orch/rag/config.py` with `CodeUnderstandingProvider`, `IndexTier`, `TIER_DEFAULTS`, `CodeUnderstandingConfig`
- [ ] `IW_CORE_INDEX_PATH` added to `DaemonConfig` in `orch/config.py`
- [ ] Unit tests for config validation in `tests/unit/test_rag_config.py`
- [ ] Integration tests for `CodeIndexJob` in `tests/integration/test_code_index_job.py`

Verify every acceptance criterion from the design:
- [ ] AC1: CodeIndexJob table exists and is queryable with correct defaults
- [ ] AC2: Status lifecycle (queued → running → completed with completed_at)
- [ ] AC3: FK constraint enforced on missing project_id
- [ ] AC4: FAST tier defaults (gemma4:e4b, qwen3-embedding:8b)
- [ ] AC5: Explicit model override wins over tier default
- [ ] AC6: IW_CORE_INDEX_PATH absent → `~/.iw-ai-core/indexes`; set → custom value
- [ ] AC7: Invalid provider raises ValidationError
- [ ] AC8: Invalid index_tier raises ValidationError

Check every boundary case from the Boundary Behavior table:
- [ ] Unknown provider → ValidationError
- [ ] Unknown tier → ValidationError
- [ ] Explicit model overrides tier default
- [ ] Null doc_id FK → insert succeeds
- [ ] Invalid doc_id FK → IntegrityError
- [ ] IW_CORE_INDEX_PATH unset → default
- [ ] IW_CORE_INDEX_PATH set → custom
- [ ] files_discovered/files_indexed/chunks_created default to 0
- [ ] CodeIndexJob with non-existent project_id → IntegrityError

### 2. Cross-Agent Consistency

- Does the `CodeIndexJob` ORM model's field names match what the Pydantic `CodeUnderstandingConfig` describes? Specifically:
  - ORM `provider` column values: `"local"` — matches `CodeUnderstandingProvider.LOCAL`
  - ORM `index_tier` column values: `"fast"`, `"balanced"`, `"quality"` — match `IndexTier` enum values
- Are `llm_model` and `embed_model` nullable in the ORM model (matching the Pydantic model's `str | None`)?
- Does `DaemonConfig.index_path` use the same default string (`"~/.iw-ai-core/indexes"`) as documented?

### 3. Integration Points

- Is `orch/rag/` a valid Python package (has `__init__.py`)?
- Can `from orch.rag.config import CodeUnderstandingConfig` be imported without errors?
- Does `orch/config.py` still import and work correctly after the `index_path` addition?
- Does the migration correctly reference `projects(id)` and `project_docs(id)` as FK targets?
- Do integration tests properly use the `db_session` and `test_project` fixtures from `conftest.py`?

### 4. Test Coverage (Holistic)

- Are both happy path AND error paths covered end-to-end?
- Unit tests cover all three tiers for both `resolved_llm_model()` and `resolved_embed_model()`?
- Unit tests cover `IW_CORE_INDEX_PATH` both unset and set?
- Integration tests cover all boundary cases for `CodeIndexJob` (FK violations, JSONB defaults, status transitions)?
- Are there any cross-module test gaps — e.g., does any test verify that `CodeUnderstandingConfig` can parse the `code_understanding` key from a project's JSONB config dict?

If there is no test verifying that `CodeUnderstandingConfig(**project.config["code_understanding"])` works with a dict that matches the design document's example, flag this as a MEDIUM_FIXABLE finding and suggest adding it.

### 5. Architecture Compliance

- Is `orch/rag/` a proper subpackage of `orch/` (not standalone)?
- Are there any circular imports between `orch.rag.config` and `orch.config`?
- Does `orch/rag/config.py` import from `orch.db.models`? (It should NOT — config models are independent of the ORM layer)
- Does `orch/db/models.py` import from `orch/rag/`? (It should NOT)
- Is the config layer (`orch/rag/config.py`) independent of the DB layer (`orch/db/`)? This is the correct layering.

### 6. Security (Cross-Cutting)

- No hardcoded credentials, API keys, or URLs other than the documented Ollama default (`http://localhost:11434`)
- `IW_CORE_INDEX_PATH` has a safe default — no path traversal concerns introduced
- FK constraints properly prevent orphaned `CodeIndexJob` rows

### 7. Invariants (from Design Document)

Verify each invariant holds in the implementation:
1. Every `CodeIndexJob` has a valid `project_id` (FK CASCADE enforces this)
2. `CodeIndexJob.status` is always one of the four valid values (no DB ENUM enforces this — it relies on application code; confirm this is documented or an issue is raised)
3. `resolved_llm_model()` always returns a non-empty string
4. `resolved_embed_model()` always returns a non-empty string
5. `DaemonConfig.index_path` is always a non-empty string
6. `TIER_DEFAULTS` covers all three tiers (no `KeyError` possible)

Note on invariant #2: `status` is a `VARCHAR` in the DB without a CHECK constraint. If this is the case, raise it as a MEDIUM_SUGGESTION to add a DB CHECK constraint in a follow-up, not as a blocking issue for this feature.

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the full unit test suite: `uv run pytest tests/unit/ -v`
2. Run the full integration test suite: `uv run pytest tests/integration/ -v`
3. Run lint: `uv run ruff check .`
4. Run type check: `uv run mypy orch/ dashboard/`
5. Report actual pass/fail counts for both unit and integration suites
6. If integration tests fail, this is a CRITICAL finding

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

---

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00045",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
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

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
- `missing_requirements`: List any design document requirements that have no corresponding implementation. Each missing requirement is automatically a CRITICAL finding.
- `cross_cutting`: Set to `true` on findings that span multiple agents' work or affect integration points.
