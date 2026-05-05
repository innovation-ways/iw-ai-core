# I-00064 S03 Tests Report

## What Was Done

Written three regression integration tests for I-00064 in
`tests/integration/test_i00064_doc_generation_view_document_url.py`.

## Files Changed

- `tests/integration/test_i00064_doc_generation_view_document_url.py` — new file (3 test cases)

## Test Cases

### `test_i00064_reproduces_bug`
Asserts that `JobsAggregator.get_job()` for a `doc_generation` job returns `row.raw["doc_id"] == "code-index"` (the inner identifier), NOT `"iw-ai-core:code-index"` (the composite FK).
Also asserts `":" not in row.raw["doc_id"]` and `row.raw["doc_id"] != "iw-ai-core:code-index"` as semantic guards.
**Pre-fix behavior**: the composite FK `"iw-ai-core:code-index"` would be returned → test FAILS on main.
**Post-fix behavior**: inner id `"code-index"` returned → test PASSES on current branch.

### `test_i00064_view_document_link_resolves`
End-to-end FastAPI TestClient test. After inserting a Project + ProjectDoc + DocGenerationJob, calls `JobsAggregator.get_job()` and builds the URL the template uses:
`/project/iw-ai-core/docs/{row.raw['doc_id']}`.
Asserts `response.status_code == 200` and the doc title appears in the HTML.
**Pre-fix**: URL resolves to `/project/iw-ai-core/docs/iw-ai-core:code-index` → 404.
**Post-fix**: URL resolves to `/project/iw-ai-core/docs/code-index` → 200.

### `test_i00064_orphan_doc_id_is_none`
Asserts `row.raw["doc_id"] is None` for two orphan cases:
1. Job inserted with `doc_id=None` (no FK target).
2. Job inserted pointing at a ProjectDoc, then the doc is deleted (`ondelete=SET NULL`).
This protects the template guard `{% if raw.get('doc_id') %}` from a regression.

## Key Fixes During Test Writing

1. **Enum values**: `doc_type`, `tier`, and `editorial_category` are proper Python enum types (`DocType`, `DocTier`, `EditorialCategory`), not bare strings. The string values from the issue design sketch were incorrect.
2. **Unused variable lint**: F841 (job_null, job_orphan) — removed by restructuring to call `_make_doc_generation_job` directly without binding.
3. **Import order**: I001 (import block unsorted) — fixed by matching the existing project's import pattern.
4. **`from __future__ import annotations`**: Used for forward references in TYPE_CHECKING block, following the project's conventions.

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ✅ OK (ruff format) |
| `make typecheck` | ✅ OK (zero type errors) |
| `make lint` | ⚠️ Pre-existing error in `orch/daemon/worktree_compose.py` (TC004 pathlib.Path in TYPE_CHECKING block) — unrelated to this change; verified by S01 as pre-existing on main. |

## Test Results

- **`make test-integration`** (I-00064 tests only): **3 passed** in ~18s
- **`make test-unit`**: 2574 passed, 6 failed — the 6 failures are pre-existing `test_worktree_compose.py` tests (Jinja2 path issues) unrelated to this change; verified by S01 report as pre-existing on main.

## Notes

- The lint error in `orch/daemon/worktree_compose.py` is pre-existing on main and not caused by this step.
- All 3 new tests are semantically correct (assert specific values, not just shape), satisfying the CR-00023 I003 lesson.
- Test file uses the existing `db_session` testcontainer fixture and the standard `client` pattern from `test_pages_lazy_libs.py`.
