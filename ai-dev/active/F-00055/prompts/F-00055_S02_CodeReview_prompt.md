# F-00055_S02_CodeReview_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — design document (read Scope + AC1, AC8, AC9 + Invariants 5, 8, 9, 10)
- `ai-dev/active/F-00055/reports/F-00055_S01_Pipeline_report.md` — S01 step report
- `orch/rag/indexer.py`, `orch/rag/job.py`, `tests/unit/test_rag_docs_indexer.py` — changed files from S01
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S02_CodeReview_report.md`

## Review Focus

This step reviews S01 (design-doc indexer extension). Produce findings with severities CRITICAL / HIGH / MEDIUM / LOW.

### Must-check items

1. **Table name convention** — `docs_{project_id}` replaces hyphens with underscores (AC Invariant-equivalent to `code_` convention).
2. **Null-safety on `design_doc_content`** — items with `design_doc_content = NULL` must NOT crash the pipeline; summary-only fallback path exists.
3. **Per-project isolation** — every row in `docs_` carries its `project_id`; no cross-project leakage.
4. **Incremental mode correctness** — only rows with `WorkItem.updated_at > previous_completed_at` are re-embedded; existing rows are preserved.
5. **Error handling** — doc-pass failure does NOT fail the overall `CodeIndexJob`; error is logged and surfaced via `errors` list.
6. **No Alembic migration introduced** — confirm no new migration file under `orch/db/migrations/versions/`.
7. **Embedding model consistency** — doc index uses the same `config.resolved_embed_model()` as the code index.
8. **`mode="mapgen_only"` untouched** — map-regen does not re-embed docs.
9. **Existing `code_{project_id}` behavior unchanged** — filter-by-`file_path` for `context_level == "module"` still works.
10. **Test coverage** — RED-GREEN-REFACTOR evident; tests cover chunking, null-content skip, summary-only fallback, incremental filter, table shape.

### Project conventions

- psycopg v3, sync SQLAlchemy 2.0, no psycopg2.
- No test hits port 5433 (live DB); testcontainers only.
- Log formatting matches existing `orch/rag/*.py`.
- `design_doc_search` TSVECTOR maintained by existing FTS trigger; indexer does NOT write to it.

## Review Output Format

Write findings to the report file in this structure:

```markdown
# F-00055 S02 Code Review Report

## Summary
{N} findings: {critical} CRITICAL, {high} HIGH, {medium} MEDIUM, {low} LOW
Overall assessment: approve | approve-with-fixes | reject

## Findings

### F01 [SEVERITY]: {title}
**File**: `path/to/file.py:line`
**Issue**: {description}
**Fix**: {specific fix recommendation}
```

Close with a `Subagent Result Contract` JSON block.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve|approve-with-fixes|reject",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "notes": ""
}
```
