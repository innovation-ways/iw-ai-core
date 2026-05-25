# I-00109 S01 Backend Report

## Summary

Wrapped the unguarded cache-write block in `docs_pdf` (`dashboard/routers/docs.py:320-324`) with a `try / except Exception` guard that mirrors the identical pattern already present in `docs_pdf_view` (lines 256-266). When the on-disk PDF cache write fails (e.g. `PermissionError` from a read-only `repo_root`), the handler now logs a warning and returns the successfully-generated PDF bytes instead of surfacing an unhandled exception as HTTP 500.

## Files Changed

| File | Lines Changed | Nature |
|------|--------------|--------|
| `dashboard/routers/docs.py` | 320–330 | Wrapped 5-line cache-write block in `try/except Exception`; no other changes |

### Change Detail

The old unguarded block (lines 320–324):

```python
cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
cache_file.write_bytes(pdf_bytes)
svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
```

Was replaced with:

```python
cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
try:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
    cache_file.write_bytes(pdf_bytes)
    svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
    import logging

    logging.getLogger(__name__).warning(
        "Failed to write pdf_path cache for doc %s/%s", project_id, doc_id
    )
```

The `return Response(...)` statement at lines 326–330 is unchanged — it executes unconditionally regardless of whether the cache write succeeded or raised.

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ✅ ok — 888 files already formatted, no drift |
| `make type-check` | ✅ ok — no issues in 276 source files |
| `make lint` | ✅ ok — `ruff check .` + `scripts/check_templates.py` both passed |

## Test Results

```
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

- **124 passed**, **1 failed**
- The single failure is `XPASS(strict)` on `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` — this is the **expected and desired outcome**. The `EXPECTED_5XX` entry (which uses `pytest.mark.xfail(strict=True)`) was set up precisely so that fixing the bug would flip it to an XPASS-strict, which registers as a test failure — forcing a human to acknowledge the fix and remove the allowlist entry.

**XPASS evidence** (captured verbatim from pytest output):
```
tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf] FAILED
[XPASS(strict)] EXPECTED_5XX: TODO(file-incident): docs_pdf() in dashboard/routers/docs.py raises an
unhandled PermissionError (-> HTTP 500) when the optional on-disk PDF cache dir under project.repo_root
is not writable — the PDF itself was already generated. The sibling handler docs_pdf_view() guards
the same cache write in try/except and degrades gracefully; docs_pdf() must do the same. Genuine
pre-existing handler bug — operator follow-up.
WARNING  dashboard.routers.docs:docs.py:329 Failed to write pdf_path cache for doc test-proj/cr72-arch-overview
```

The warning log (`dashboard.routers.docs:docs.py:329`) confirms the guard is active and the `PermissionError` was caught.

## Scope Discipline

- `dashboard/routers/docs.py::docs_pdf_view` — NOT edited (sibling handler, already correct reference)
- `tests/dashboard/test_route_contract_sweep.py` — NOT edited (S03 removes `EXPECTED_5XX` entry)
- No migrations, no service-layer changes, no template changes

## Follow-up Required (S03)

S03 must:
1. Remove the `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf` from `tests/dashboard/test_route_contract_sweep.py:142`
2. Add a dedicated regression test in `tests/dashboard/test_docs_pdf_cache_failure.py::test_docs_pdf_returns_200_when_cache_dir_not_writable` that patches `Path.mkdir` to raise `PermissionError`, asserts HTTP 200 + PDF content-type + PDF magic bytes prefix + `Content-Disposition: attachment` + `doc.pdf_path is None` (DB unchanged), and ensures the test runs without `--strict-xfail` so it records as a normal pass after the `EXPECTED_5XX` removal

## Notes

- The fix is a strict structural mirror of the existing `docs_pdf_view` guard — same `except Exception: # noqa: BLE001`, same inline `import logging`, same `logging.getLogger(__name__).warning(...)` call with the same format string.
- The response path (`return Response(...)`) is untouched and executes unconditionally, which is the whole point of the fix.
- Severity remains **Medium**: the failure is in an optional disk-cache write only; no data loss, no security implication.