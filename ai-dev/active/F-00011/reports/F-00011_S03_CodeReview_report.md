# F-00011_S03_CodeReview_Backend_report

**Step**: S03 — Code Review (Backend)
**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Steps Reviewed**: S01 (Database) + S02 (Backend)
**Date**: 2026-04-13

---

## Verdict: PASS

All checklist items verified. S01 + S02 implementation is correct and complete.

---

## Files Changed (Reviewed)

| File | Step | Change |
|------|------|--------|
| `orch/db/models.py` | S01 | Added 5 ENUMs, 3 models, FTS SQL constants |
| `orch/db/migrations/versions/6a5e03db855a_add_project_docs_tables.py` | S01 | Alembic migration with ENUMs, tables, FTS trigger |
| `tests/integration/conftest.py` | S01 | Added PROJECT_DOCS_FTS_* SQL to test fixtures |
| `tests/integration/test_project_docs.py` | S01 | 19 integration tests for models |
| `orch/doc_service.py` | S02 | DocService class with 8 CRUD methods |
| `tests/integration/test_doc_service.py` | S02 | 14 integration tests for DocService |

---

## Checklist Verification

### Schema Correctness ✅
- `ProjectDoc.id` is composite `"{project_id}:{doc_id}"` string PK — correct
- `content_search` named correctly as TSVECTOR — not a reserved name
- `ProjectDocVersion.content` is `NOT NULL` — correct
- `DocGenerationJob.id` is Text PK (UUID string) — all tests pass explicit `str(uuid.uuid4())`
- All 5 ENUMs defined as Python `enum.Enum` + SQLAlchemy `ENUM(create_type=False)`

### Migration Completeness ✅
- All 5 ENUMs created before tables using them
- `project_docs`, `project_doc_versions`, `doc_generation_jobs` all created
- FTS trigger function + trigger created via `op.execute()`
- `downgrade()` drops in correct reverse order (trigger → function → tables → ENUMs)
- `UniqueConstraint("project_id", "doc_id")` present
- Indexes on `project_id` lookups created

### FTS Trigger ✅
- Uses `coalesce()` for NULL handling: `coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, '')`
- `PROJECT_DOCS_FTS_FUNCTION_SQL` and `PROJECT_DOCS_FTS_TRIGGER_SQL` defined in `models.py`
- Both executed in `conftest.py` after `Base.metadata.create_all()`

### DocService Correctness ✅
- `create_doc()` raises `ValueError` for unknown project
- `update_doc()` uses SHA-256 hash comparison before creating version snapshot
- `update_doc()` clears `html_path`/`pdf_path` when content changes
- `update_doc()` raises `KeyError` for unknown doc
- `upsert_doc()` returns `(doc, created)` tuple correctly
- `list_docs()` applies FTS ranking via `ts_rank()` when search provided
- `get_stale_docs()` filters by `generated_at < now() - timedelta(hours=threshold_hours)`

### Invariant Enforcement ✅
- Invariant 2 (version = snapshot count): Enforced in `update_doc` — version increments only when new snapshot created
- Invariant 3 (new snapshot only when content differs): SHA-256 hash comparison in `update_doc`
- Invariant 7 (pdf_path only on success): `update_doc` sets `pdf_path = None` on content change; no code sets `pdf_path` to a success value (reserved for Phase 2)

### Architecture Compliance ✅
- `DocService` at `orch/doc_service.py` — correct package root location (no `services/` directory existed)
- Uses SQLAlchemy 2.0 style: `select()` + `scalars()` — matches project conventions
- No cross-layer imports (service imports only from `orch.db.models`)

### Test Quality ✅
- All tests use testcontainers (not live DB)
- FTS tests insert real content and query with `plainto_tsquery`
- `test_update_doc_content_unchanged_no_new_version` present and correctly verifies no new snapshot when content unchanged

---

## Test Results

```
make test-unit:   576 passed, 1 warning in 1.12s
make test-integration: 297 passed, 3 warnings in 9.50s
make quality:     ruff: PASS | ruff format: PASS | mypy: pre-existing errors only
```

**Pre-existing mypy errors** (unrelated to S01/S02):
- `orch/cli/worktree_commands.py:187`: Unused `type: ignore` comment
- `dashboard/routers/worktrees.py:194,245,271,345`: Unused `type: ignore` comments and `no-redef`

---

## Issues Found

None. The implementation is correct and complete.

**Minor observation** (not a bug): `DocGenerationJob.id` is Text PK without an explicit `default=lambda: str(uuid4())` in the model. All tests and production code must pass `id=str(uuid.uuid4())` explicitly. This matches the design intent (UUID PK) and works correctly — but if a future code path creates `DocGenerationJob` without providing an id, it would fail. This is acceptable since no Phase 1 code creates jobs without providing an id.

---

## Notes for Next Steps

- S04 (API/CLI) will implement `iw doc-update` using `DocService.upsert_doc()`
- S05 (Frontend) will call dashboard routes that use `DocService`
- FTS index on `content_search` (GIN) is set up by S01 migration — ready for use
