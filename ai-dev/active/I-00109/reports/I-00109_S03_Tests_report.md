# I-00109 S03 Tests Report

**Agent**: tests-impl
**Work Item**: I-00109 — `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step**: S03
**Date**: 2026-05-24

## Summary

Added a dedicated regression test and removed the `EXPECTED_5XX` entry for the PDF download route so the route sweep records it as a normal pass.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_docs_pdf_cache_failure.py` | **Added** — new regression test `test_docs_pdf_returns_200_when_cache_dir_not_writable` |
| `tests/dashboard/test_route_contract_sweep.py` | **Modified** — removed the `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf` (dict is now `{}`) |

## What Was Done

### 1. New regression test (`tests/dashboard/test_docs_pdf_cache_failure.py`)

A targeted TestClient test that pins the exact failure mode from I-00109:

- **Arrange**: seeds a `ProjectDoc` with `content="# Hello"` and `pdf_path=None` so the route goes through the generate-then-cache branch.
- **Act**: `client.get(f"/project/{test_project.id}/docs/{doc.doc_id}/pdf")` with:
  - `render_pdf_chromium` monkeypatched to return deterministic fake PDF bytes (avoids Chromium binary dependency).
  - `Path.mkdir` monkeypatched to raise `PermissionError` only for `.generated` cache dirs (narrow — lets unrelated test-infra mkdirs through).
- **Asserts (SEMANTIC — not shape-only)**:
  1. `resp.status_code == 200` — would have been 500 before S01's fix.
  2. `resp.headers["content-type"] == "application/pdf"` — not a generic error.
  3. `resp.content.startswith(b"%PDF")` — the actual PDF body, not an error page.
  4. `"attachment" in resp.headers["content-disposition"]` — download response semantics.
  5. At least one WARNING log record containing `"Failed to write pdf_path cache for doc"` — proves the guard caught the exception and the exact message operators grep for was emitted.
  6. `doc.pdf_path is None` after `db_session.refresh(doc)` — proves the guard prevented `svc.update_doc` from running, so the failed cache write did not pollute the DB.

The `client` fixture is defined inline (not depending on `tests/dashboard/conftest.py` which only re-exports `db_session` from integration conftest). It rebinds module-level `SessionLocal` / `engine` on `dashboard.app`, `dashboard.dependencies`, and `orch.db.session` to the testcontainer engine before creating the FastAPI app — identical to `test_route_contract_sweep.py::sweep_client`.

### 2. Removed `EXPECTED_5XX` entry from `test_route_contract_sweep.py`

The entry for `/project/{project_id}/docs/{doc_id}/pdf` was removed. S01's fix (wrapped the cache write in `try/except Exception` mirroring `docs_pdf_view`'s guard at lines 256-266) makes the route return 200 — so the `xfail(strict=True)` marker would flip to `XPASS(strict)` → FAIL. Removing the entry converts the case to a normal pass with full regression coverage going forward.

**Verified**: `grep -n "Failed to write pdf_path cache for doc" dashboard/routers/docs.py` returns TWO matches (lines 265 and 330 — one in `docs_pdf_view`, one in `docs_pdf`), confirming S01's guard landed correctly.

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | `ruff format` applied to `test_docs_pdf_cache_failure.py` (1 file reformatted) |
| `make type-check` | `uv run mypy tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py` → Success: no issues found |
| `make lint` | `uv run ruff check tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py` → All checks passed |

## Test Results

```
uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov

126 passed in 55.39s
```

Key outcomes:
- `test_docs_pdf_returns_200_when_cache_dir_not_writable` — **PASSED** ✓
- `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` — **PASSED** ✓ (now a normal pass after `EXPECTED_5XX` removal)
- 124 other sweep cases — all passed unchanged

## TDD Evidence

**RED→GREEN for the fix itself** (S01's contribution): captured in S01's report — the strict-xfail flip (`XPASS(strict)`) on the sweep case proved the route stopped returning 500.

**RED→GREEN for S03's own contribution**: after removing the `EXPECTED_5XX` entry, the sweep case `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` records as a plain `PASSED` (no `xfail` marker, no `XPASS(strict)`). The new regression test passes against the fixed code by construction — it was designed to pass when the guard is in place and would fail if the guard is removed.

```json
{
  "tdd_red_evidence": "n/a — Tests step adds regression coverage after S01's fix; the strict-xfail flip captured in S01's report is the RED→GREEN signal. S03's new test (test_docs_pdf_returns_200_when_cache_dir_not_writable) passes against the fixed code by construction; removing the EXPECTED_5XX entry flips the sweep case from XPASS(strict)→FAIL to PASSED."
}
```

## Notes

- `EXPECTED_5XX` is now an empty dict `{}` — the declaration and explanatory comment block were kept intact as designed.
- No changes to `dashboard/routers/docs.py` (S01's territory) or any other test files.
- The `Path.mkdir` patching strategy uses a narrow `".generated"` substring guard rather than a blanket `PermissionError` on all mkdirs, ensuring unrelated test infrastructure mkdirs are not disrupted.
- The regression test is intentionally self-contained: it defines its own `client` fixture rather than depending on `tests/dashboard/conftest.py` (which only re-exports `db_session` from the integration conftest, and does not register a `client` fixture). This mirrors the pattern used in `test_route_contract_sweep.py::sweep_client`.