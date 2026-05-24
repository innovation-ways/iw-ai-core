# I-00109: `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-24
**Reported By**: CR-00072 contract-route-sweep test layer (`tests/dashboard/test_route_contract_sweep.py` `EXPECTED_5XX` entry with `TODO(file-incident)` rationale, merged 2026-05-22). Filed from `ai-dev/work/TESTS_ENHANCEMENT.md` §10 "Phase 3 operator-follow-up incidents".
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. **This item adds no migration and no schema change.**)

## Description

The download-PDF route `GET /project/{project_id}/docs/{doc_id}/pdf` (handler `docs_pdf` in `dashboard/routers/docs.py`) generates a PDF on-the-fly, then writes a cache file under `project.repo_root / "docs" / ".generated" / project_id / `. The `cache_dir.mkdir(...)` + `cache_file.write_bytes(...)` + `svc.update_doc(...)` block at `dashboard/routers/docs.py:320-324` is **unguarded** — when `project.repo_root` (or any segment under it) is not writable, the call raises `PermissionError`, which propagates as an unhandled exception → HTTP 500. The PDF bytes themselves were already generated successfully; the failure is purely in the optional disk-cache write. The sibling handler `docs_pdf_view` (lines 188-268, the iframe-embedded variant) performs the exact same write but wraps it in `try / except Exception` at lines 256-266 and logs a warning — `docs_pdf` simply missed that guard.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key facts for this item: the dashboard is FastAPI + Jinja2 + htmx (`dashboard/CLAUDE.md`); routers must stay thin (validation + delegation); the route contract sweep at `tests/dashboard/test_route_contract_sweep.py` (introduced by CR-00072) parametrizes every GET route in the app and `xfail(strict=True)`-marks anything listed in `EXPECTED_5XX`. The fix is a strict mirror of the existing guard pattern in `docs_pdf_view`; no new framework, no new logging plumbing, no service-layer change.

## Steps to Reproduce

1. Make `project.repo_root` read-only for any registered project (e.g. `chmod -R a-w <repo_root>`), OR run iw-ai-core in an environment where the user lacks write access to the repo root (hardened container, read-only mount, restrictive umask).
2. Open the project's Docs page in the dashboard → click "Download PDF" on any document where `doc.pdf_path is None` (or `doc.pdf_path` is set but the file no longer exists).
3. Observe the response in the browser.

**Expected**: HTTP 200, the PDF bytes are streamed to the client with `Content-Disposition: attachment`, and a warning is logged about the failed cache write — mirroring the existing `docs_pdf_view` behaviour at `dashboard/routers/docs.py:256-266` (`"Failed to write pdf_path cache for doc %s/%s"`).

**Actual**: HTTP 500, unhandled `PermissionError` propagates from `cache_dir.mkdir(...)` or `cache_file.write_bytes(...)` at `dashboard/routers/docs.py:320-324`, no PDF is served to the client (even though the PDF bytes were already generated successfully one line earlier).

## Root Cause Analysis

The `docs_pdf` callback at `dashboard/routers/docs.py:271-330` runs the following sequence:

1. Look up the project + doc; 404 if missing.
2. If `doc.pdf_path` is set AND the file exists, return its bytes — fast path.
3. Otherwise: render the PDF Jinja2 template, call `render_pdf_chromium(html_content)` to get PDF bytes.
4. If Chromium isn't installed, return a styled 503 JSON.
5. **Cache the bytes to disk and update `ProjectDoc.pdf_path`** (lines 320-324):
   ```python
   cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
   cache_dir.mkdir(parents=True, exist_ok=True)
   cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
   cache_file.write_bytes(pdf_bytes)
   svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
   ```
6. Return the PDF bytes with `Content-Disposition: attachment; filename="..."`.

Step 5 is **unguarded**. Any one of `mkdir`, `write_bytes`, or `svc.update_doc` can raise — most commonly `PermissionError` from a read-only `repo_root` — and FastAPI surfaces the uncaught exception as HTTP 500.

The sibling handler `docs_pdf_view` (lines 188-268) does the **identical** sequence (lines 254-260) and wraps it in `try / except Exception` (lines 256-266) with a `logging.getLogger(__name__).warning("Failed to write pdf_path cache for doc %s/%s", ...)`. The fix is to mirror that exact pattern in `docs_pdf` — same `try/except Exception`, same warning, same response (return the PDF bytes regardless of whether the disk cache succeeded).

The bug was caught by CR-00072's contract-route-sweep test layer (`tests/dashboard/test_route_contract_sweep.py`, merged 2026-05-22). The route is in the `EXPECTED_5XX` allowlist at line 142, with this rationale (verbatim — this is the operator-evidence quote required by Step 2c when `browser_verification: false`):

```
TODO(file-incident): docs_pdf() in dashboard/routers/docs.py raises an
unhandled PermissionError (-> HTTP 500) when the optional on-disk PDF
cache dir under project.repo_root is not writable — the PDF itself was
already generated. The sibling handler docs_pdf_view() guards the same
cache write in try/except and degrades gracefully; docs_pdf() must do
the same. Genuine pre-existing handler bug — operator follow-up.
```

The sweep marks the case `pytest.mark.xfail(strict=True)` (see `test_route_contract_sweep.py:213-219`). The strict marker means: once the route stops returning 5xx, the case turns `XPASS(strict)` which **fails** the run — that is the regression-net signal that the fix landed. S03 removes the entry from `EXPECTED_5XX` so the test records as a normal pass.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/routers/docs.py::docs_pdf` (lines 271-330) | Unhandled `PermissionError` from optional cache write at lines 320-324 surfaces as HTTP 500 even though the PDF bytes were already generated successfully |
| `tests/dashboard/test_route_contract_sweep.py` (`EXPECTED_5XX` at line 142) | The route is `xfail(strict=True)`-marked; the fix flips it to `XPASS(strict)` → S03 must remove the entry so the case records as a normal pass |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern (one module or closely-related file group). Split multi-concern work across multiple steps. See `skills/iw-workflow/SKILL.md` for the canonical rule.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Wrap the `cache_dir.mkdir(...)` + `cache_file.write_bytes(...)` + `svc.update_doc(...)` block in `docs_pdf` (lines 320-324) in `try / except Exception`, mirroring the guard pattern at lines 256-266 in `docs_pdf_view`. Log a warning on failure (`"Failed to write pdf_path cache for doc %s/%s"`). Return the PDF response unconditionally — the bytes were generated successfully. | — |
| S02 | code-review-impl | Per-agent review of S01: the guard mirrors `docs_pdf_view`'s pattern exactly (same logger, same warning message, same `except Exception: ... noqa: BLE001`); the response path is unchanged when the cache write succeeds; no other route is touched. | — |
| S03 | tests-impl | Add a dashboard TestClient regression test that monkeypatches `Path.mkdir` (or `Path.write_bytes`) to raise `PermissionError`, drives the `docs_pdf` route, and asserts HTTP 200 + PDF bytes + warning log. Remove the `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf` from `tests/dashboard/test_route_contract_sweep.py:142` — the strict-xfail is no longer expected. | — |
| S04 | code-review-impl | Per-agent review of S03: regression test asserts SEMANTIC correctness (HTTP 200 AND `Content-Type: application/pdf` AND non-empty PDF body, NOT just "status < 500"); the `EXPECTED_5XX` removal is in the same commit as the route fix; targeted test verification only. | — |
| S05 | code-review-final-impl | Global cross-agent review of S01..S04: AC1 (route returns 200 with PDF on read-only `repo_root`) + AC2 (regression test exists, `EXPECTED_5XX` entry removed, sweep records the route as a normal pass) verified end-to-end. Scope check: `git diff origin/main` is limited to the three allowlisted paths. | — |
| S06..S13 | qv-gate | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | self-assess-impl | Self-assessment via `iw-item-analyze` | — |

Agent slugs: `backend-impl`, `code-review-impl`, `tests-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None (no schema change)

### Code Changes

- **Files to modify**: `dashboard/routers/docs.py` (~5-10 LOC: wrap an existing 5-line block in `try/except` mirroring lines 256-266), `tests/dashboard/test_route_contract_sweep.py` (remove one entry from `EXPECTED_5XX`).
- **Files to add**: `tests/dashboard/test_docs_pdf_cache_failure.py` (new regression test; ~50 LOC).
- **Nature of change**: Defensive `try/except` around an optional disk-cache write, copied verbatim in spirit from a sibling handler. No service-layer change, no template change, no schema change.

## File Manifest

All files for this work item live under `ai-dev/active/I-00109/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00109_Issue_Design.md` | Design | This document |
| `I-00109_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00109_S01_Backend_prompt.md` | Prompt | S01 backend fix — guard the cache write |
| `prompts/I-00109_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00109_S03_Tests_prompt.md` | Prompt | S03 regression test + remove `EXPECTED_5XX` entry |
| `prompts/I-00109_S04_CodeReview_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00109_S05_CodeReview_Final_prompt.md` | Prompt | S05 global cross-agent review |
| `prompts/I-00109_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess via `iw-item-analyze` |

Reports are created during execution in `ai-dev/active/I-00109/reports/`.

## Test to Reproduce

**Test-file location**: This test drives a FastAPI route via the dashboard `client` fixture, so per the rule in `tests/CLAUDE.md` it MUST go under `tests/dashboard/`. Pure-Python helpers belong under `tests/unit/`; testcontainer-backed tests under `tests/integration/`. This test is dashboard-layer.

A new regression test in `tests/dashboard/test_docs_pdf_cache_failure.py` (or appended to `tests/dashboard/test_route_contract_sweep.py`). Sketch:

```python
def test_docs_pdf_returns_200_when_cache_dir_not_writable(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the on-disk PDF cache write fails (PermissionError on read-only
    repo_root), the route MUST still return the freshly-generated PDF bytes
    with HTTP 200 — the cache is optional; the PDF response is not.

    Pins I-00109: docs_pdf() used to surface the cache PermissionError as an
    unhandled exception → HTTP 500, even though the PDF was already generated.
    """
    # Arrange: seed a ProjectDoc with content but no pdf_path so docs_pdf must
    # go through the on-the-fly generate + cache branch.
    doc = _seed_doc(db_session, test_project, content="# Hello", pdf_path=None)

    # Patch the cache write to raise PermissionError, mimicking a read-only repo_root.
    real_mkdir = Path.mkdir

    def fail_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        # Only fail the docs-cache mkdir; let unrelated mkdirs (test infra) through.
        if ".generated" in str(self):
            raise PermissionError(f"[Errno 13] Permission denied: '{self}'")
        return real_mkdir(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    # Patch render_pdf_chromium to return deterministic bytes (no real Chromium needed).
    monkeypatch.setattr(
        "dashboard.routers.docs.render_pdf_chromium",
        lambda html: b"%PDF-1.4 fake bytes",
    )

    # Act
    resp = client.get(f"/project/{test_project.id}/docs/{doc.id}/pdf")

    # Assert — semantic, not just shape:
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:200]}"
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF"), "response body must be PDF, not error HTML"
    assert "attachment" in resp.headers.get("content-disposition", "")
    # And the doc's pdf_path was NOT updated (the cache write failed) — semantic:
    db_session.refresh(doc)
    assert doc.pdf_path is None, "pdf_path must stay None when the cache write failed"
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a project with `project.repo_root` that is not writable (e.g. chmod -R a-w),
  AND a ProjectDoc with content but no pdf_path on disk,
When a client issues GET /project/{project_id}/docs/{doc_id}/pdf,
Then the response status is 200,
  AND the Content-Type is application/pdf,
  AND the body starts with the PDF magic bytes (%PDF),
  AND the Content-Disposition header is "attachment; filename=...",
  AND a warning is logged ("Failed to write pdf_path cache for doc %s/%s"),
  AND no unhandled PermissionError propagates out of the handler,
  AND ProjectDoc.pdf_path is NOT updated (the cache write failed).
```

### AC2: Regression test exists

```
Given the fix is applied,
When `uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py -v` runs,
Then test_docs_pdf_returns_200_when_cache_dir_not_writable passes GREEN,
  AND the EXPECTED_5XX entry for "/project/{project_id}/docs/{doc_id}/pdf" has been
      removed from tests/dashboard/test_route_contract_sweep.py:142,
  AND the route sweep records that parametrized case as a normal pass
      (no longer xfail(strict=True)).
```

## Regression Prevention

- The new test `test_docs_pdf_returns_200_when_cache_dir_not_writable` pins the exact failure mode and turns the bug into a hard test failure if the guard is ever removed.
- Removing the `EXPECTED_5XX` entry restores the route to the sweep's full coverage: any future regression that re-introduces a 5xx on `/project/{project_id}/docs/{doc_id}/pdf` will fail `test_route_returns_no_5xx` directly.
- The fix is a structural mirror of the existing `docs_pdf_view` guard (lines 256-266) — no new pattern is introduced. The two handlers are now symmetric, which makes future drift between them visible at review time.

## Dependencies

- **Depends on**: CR-00072 (which authored the route-sweep `EXPECTED_5XX` allowlist and listed this route as an operator follow-up).
- **Blocks**: None.

## Impacted Paths

- `dashboard/routers/docs.py`
- `tests/dashboard/test_route_contract_sweep.py`
- `tests/dashboard/test_docs_pdf_cache_failure.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_docs_pdf_cache_failure.py::test_docs_pdf_returns_200_when_cache_dir_not_writable` — patches `Path.mkdir` to raise `PermissionError` for the `.generated` cache directory and asserts HTTP 200 + PDF body + warning log + `pdf_path` not updated. Before S01's fix this test FAILS (status 500). After S01 it PASSES.
- **Unit tests**: None — the bug lives in the route handler's response path and is only meaningfully exercised end-to-end via the FastAPI `TestClient` fixture (`tests/dashboard/conftest.py`).
- **Integration tests**: None new (the existing route sweep covers all GETs; removing the `EXPECTED_5XX` entry restores normal-pass coverage for this route).

**Assertion scoping**: the test asserts on SEMANTIC correctness — exact status code (200), exact content type (`application/pdf`), PDF magic bytes prefix, `Content-Disposition: attachment`, AND DB-side `pdf_path is None` after the failed write. NOT a shape-only check (e.g. `assert resp.status_code < 500`, `assert "pdf" in resp.headers["content-type"]`), which would pass even if the response body was empty or garbled.

## Notes

- Severity is **Medium**, not High: PDF generation itself works; the failure is in optional disk caching only, and only on hosts where `project.repo_root` is not writable (read-only mount, hardened container, restrictive umask). No data loss, no security implication, no schema change. The user-visible symptom is "click Download PDF → 500" on those hosts, which is what gates the Medium classification.
- The fix is intentionally a structural mirror of the existing `docs_pdf_view` guard. Do NOT refactor the two handlers into a shared helper as part of this incident — that would expand scope. If a shared helper is desired, file a separate CR after this incident merges.
- `browser_verification: false`: the verification is "the route returns 200 OK (or a graceful response) instead of 500", which is fully expressible via FastAPI's `TestClient` — no Playwright is needed. The `EXPECTED_5XX` allowlist entry (`tests/dashboard/test_route_contract_sweep.py:142`) is the operator evidence; no new browser screenshot is required.
