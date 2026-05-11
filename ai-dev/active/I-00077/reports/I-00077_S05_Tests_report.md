# I-00077 S05 Tests Implementation Report

**Step**: S05 — tests-impl
**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Agent**: tests-impl
**Completion**: 2026-05-11

---

## Summary

Implemented all reproduction and regression tests for I-00077. The three areas covered:

1. **Unit** — `_effective_guide` three-level fallback (already existed, verified completeness)
2. **Integration** — `create_doc_job` snapshots `_default` guide for diagram docs (NEW)
3. **Dashboard** — `docs_running_jobs` includes failed jobs + `docs_library.html` wires `docJobFailed` listener (NEW)

---

## Analysis of Existing Tests

### Unit (`tests/unit/test_doc_type_guide_service.py`)

The existing `TestEffectiveGuide` class fully covers the three-level resolution order:

| Test | Branch | Status |
|------|--------|--------|
| `test_effective_guide_falls_back_to_default_when_no_specific_guide` | `_default` fallback | Already present |
| `test_effective_guide_returns_instance_guide_when_present` | instance > doc_type > _default | Already present |
| `test_effective_guide_returns_doc_type_guide_when_no_instance_guide` | doc_type > _default | Already present |
| `test_effective_guide_returns_none_when_no_guide_exists` | Nothing available | Already present |

No changes needed — all four branches verified.

### Integration (`tests/integration/test_doc_type_guides.py`)

The file had `test_guide_snapshot_captured_at_job_creation` which creates a `module` doc and seeds a `module`-type guide. **Missing**: a test for a doc type (e.g. `diagram`) that has NO type guide but relies on `_default`.

### Dashboard (`tests/dashboard/test_docs_running_jobs.py`)

The `TestRunningJobsFailedIncluded` class added by S03 already covers:
- Recently failed job appears in strip with error text
- Dismiss button present, no Cancel button
- No EventSource for failed jobs
- Stale (>10 min) failed jobs excluded
- Running jobs ordered before failed jobs

**Missing**: a test verifying `docs_library.html` (full catalogue page, not just the fragment) has the `docJobFailed` addEventListener and calls `showToast`.

---

## Changes Made

### `tests/integration/test_doc_type_guides.py`

Added two new tests:

**`test_create_doc_job_snapshots_default_guide_for_diagram_doc`** — Reproduction for I-00077:
- Creates a `Project` and a `ProjectDoc` with `doc_type=DocType.diagram`
- Seeds only the `_default` `DocTypeGuide` (no diagram-type guide, no instance guide)
- Calls `DocService(db_session).create_doc_job(...)`
- Asserts `job.guide_snapshot == _DEFAULT_GUIDE` (the exact content from the seeded `_default` row)
- Asserts `job.section_guides_snapshot is None` (diagram has no section guides)

**`test_create_doc_job_instance_guide_takes_precedence_over_default`** — No-regression:
- Seeds both `_default` guide and an instance guide for the specific doc
- Verifies instance guide wins (not `_default`)

### `tests/dashboard/test_docs_running_jobs.py`

Added `TestDocsLibraryDocJobFailedListener` with:

**`test_docs_library_page_has_docjobfailed_listener`** — Regression for I-00077:
- Renders the full `/project/{id}/docs` catalogue page via GET
- Asserts `addEventListener('docJobFailed'` is present in the HTML
- Asserts `showToast` is referenced (from `components/toast.html`)

---

## Test Results

```
uv run pytest tests/unit/test_doc_type_guide_service.py tests/integration/test_doc_type_guides.py tests/dashboard/test_docs_running_jobs.py -v
```

**26 passed, 0 failed** (coverage failure is from `fail-under=46` global target, not test failures — the three modified files all pass cleanly).

| File | Passed | Failed |
|------|--------|--------|
| `tests/unit/test_doc_type_guide_service.py` | 8 | 0 |
| `tests/integration/test_doc_type_guides.py` | 6 | 0 |
| `tests/dashboard/test_docs_running_jobs.py` | 12 | 0 |

---

## Preflight

| Check | Result |
|-------|--------|
| `make format` | `ruff format` reformatted 2 files; all 665 files now pass |
| `make typecheck` | `mypy orch/ dashboard/` → Success: no issues found |
| `make lint` | All checks passed (`scripts/check_templates.py` + `ruff check` + `node --check`) |

---

## Semantic Correctness Notes

Following the I-003 lesson on semantic assertions vs. shape checking:

- The integration test asserts `job.guide_snapshot == _DEFAULT_GUIDE` (exact content match, not just `is not None`)
- The dashboard failed-job tests assert exact attribute presence (`'id="docs-rjob-job-failed-001"' in resp.text`) using scoped selectors
- The `docJobFailed` listener test asserts both the event listener name AND the `showToast` call (two independent conditions)

---

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/test_doc_type_guides.py` | Added `test_create_doc_job_snapshots_default_guide_for_diagram_doc` and `test_create_doc_job_instance_guide_takes_precedence_over_default` |
| `tests/dashboard/test_docs_running_jobs.py` | Added `TestDocsLibraryDocJobFailedListener.test_docs_library_page_has_docjobfailed_listener` |

Unit test file `tests/unit/test_doc_type_guide_service.py` — no changes needed (already complete).