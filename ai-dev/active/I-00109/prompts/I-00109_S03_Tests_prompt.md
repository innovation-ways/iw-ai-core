# I00109_S03_Tests_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run any `alembic upgrade/downgrade/stamp` command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00109 --json`.
- `ai-dev/active/I-00109/I-00109_Issue_Design.md` -- Design document (read §Acceptance Criteria and §TDD Approach in full — the AC pins the EXACT semantic assertions this step must encode).
- `ai-dev/active/I-00109/reports/I-00109_S01_Backend_report.md` -- S01 report (notes the post-fix `XPASS(strict)` on the route sweep).
- `ai-dev/active/I-00109/reports/I-00109_S02_CodeReview_report.md` -- S02 review.
- `dashboard/routers/docs.py` -- Read-only: confirm S01's guard landed (verify the `try/except` mirrors `docs_pdf_view`'s pattern at lines 256-266).
- `tests/dashboard/test_route_contract_sweep.py` -- You'll modify this file: remove the one `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf` at line ~142.
- `tests/dashboard/conftest.py` -- Read-only: the `client` fixture (FastAPI `TestClient`), `db_session` / `db_engine` / `test_project` (testcontainer-backed). **The `client` fixture is registered HERE only — tests using it MUST live under `tests/dashboard/` per the file-location rule in `tests/CLAUDE.md` (a test placed under `tests/unit/` or `tests/integration/` will fail with `fixture 'client' not found`, see I-00067).**
- `tests/CLAUDE.md` -- Test layer conventions, isolation rules.
- `skills/iw-ai-core-testing/SKILL.md` -- Assertion-strength rules (read §0 mutation-test question).

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_S03_Tests_report.md` -- Step report.

## Context

S01 wrapped the cache-write block in `docs_pdf` in `try / except Exception`, mirroring `docs_pdf_view`'s guard. Two test-side jobs remain:

1. Add a **dedicated regression test** at `tests/dashboard/test_docs_pdf_cache_failure.py` that pins the exact failure mode and asserts SEMANTIC correctness (specific status code, specific Content-Type, PDF magic bytes, Content-Disposition header, AND the DB-side `pdf_path` is still None after the failed write).
2. **Remove the `EXPECTED_5XX` entry** for `/project/{project_id}/docs/{doc_id}/pdf` from `tests/dashboard/test_route_contract_sweep.py` at line ~142. After S01's fix the parametrized case `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` reports `XPASS(strict)` (fail) because the strict-xfail marker still holds. Removing the entry flips it to a normal pass — the GREEN end-state.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert resp.status_code < 500` (would have passed even if the route returned 400 / 404 / a generic error page — the bug is "returns 500 when it should return 200 with a PDF body", and a 503 / 404 would also be wrong).
- BAD: `assert "pdf" in resp.headers["content-type"]` (would match `text/x-pdf-error-page`, or a JSON error wrapper that mentions "pdf" in the message).
- GOOD: `assert resp.status_code == 200` AND `assert resp.headers["content-type"] == "application/pdf"` AND `assert resp.content.startswith(b"%PDF")` AND `"attachment" in resp.headers["content-disposition"]`. Together these pin the exact post-fix contract — they cannot pass on any of the failure modes the bug could regress to.
- GOOD: after the failed cache write, `db_session.refresh(doc); assert doc.pdf_path is None` — proves the cache write actually failed (not silently succeeded), which is what the guard catches.

## Requirements

### 1. Add `tests/dashboard/test_docs_pdf_cache_failure.py`

Create a new file at `tests/dashboard/test_docs_pdf_cache_failure.py`. The file MUST live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py`; a file under `tests/unit/` or `tests/integration/` would fail with `fixture 'client' not found`, see I-00067).

Structure:

```python
"""Regression tests for I-00109: docs_pdf must return the PDF even when the
on-disk cache write fails (PermissionError on a read-only repo_root).

Pre-fix: dashboard/routers/docs.py::docs_pdf had an unguarded cache write that
surfaced PermissionError as HTTP 500.
Post-fix: the cache write is wrapped in try/except Exception (mirroring
docs_pdf_view's existing guard at lines 256-266), the PDF bytes are returned
unconditionally, and a warning is logged.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from orch.db.models import Project, ProjectDoc  # adjust imports as needed
# … any helper imports …


def test_docs_pdf_returns_200_when_cache_dir_not_writable(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the on-disk PDF cache write raises PermissionError, the route
    MUST still return the freshly-generated PDF bytes with HTTP 200 —
    the cache is optional; the PDF response is not.

    Pins I-00109. Pre-fix the route returned 500. Post-fix it returns 200
    with the PDF body, logs a warning, and leaves ProjectDoc.pdf_path
    unchanged (the cache write failed, so the DB column must NOT have
    been updated).
    """
    # Arrange — seed a ProjectDoc with content but no pdf_path so the route
    # goes through the generate-then-cache branch (not the cached fast path).
    doc = ProjectDoc(
        project_id=test_project.id,
        id="I-00109-fixture-doc",
        slug="i-00109-fixture",
        version=1,
        title="I-00109 fixture",
        content="# Hello",
        # Adjust required fields per the actual ProjectDoc schema:
        doc_type="module",
        tier="ai",
        editorial_category="reference",
        pdf_path=None,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # Patch render_pdf_chromium to return deterministic bytes — avoids the
    # need for a real Chromium binary in the test environment.
    monkeypatch.setattr(
        "dashboard.routers.docs.render_pdf_chromium",
        lambda html: b"%PDF-1.4 fake bytes for I-00109 regression test",
    )

    # Patch Path.mkdir to raise PermissionError ONLY for the docs cache dir
    # — letting unrelated mkdirs (test harness, etc.) through. This is what
    # a read-only repo_root looks like in practice.
    real_mkdir = Path.mkdir

    def fail_mkdir_on_docs_cache(self: Path, *args: object, **kwargs: object) -> None:
        if ".generated" in str(self):
            raise PermissionError(f"[Errno 13] Permission denied: '{self}'")
        return real_mkdir(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(Path, "mkdir", fail_mkdir_on_docs_cache)

    # Act
    with caplog.at_level("WARNING", logger="dashboard.routers.docs"):
        resp = client.get(f"/project/{test_project.id}/docs/{doc.id}/pdf")

    # Assert — SEMANTIC (every assertion would fail if the bug regressed):
    assert resp.status_code == 200, (
        f"status={resp.status_code} body={resp.text[:300]!r}"
    )
    assert resp.headers["content-type"] == "application/pdf", (
        f"content-type was {resp.headers.get('content-type')!r}; "
        "must be application/pdf even when the cache write fails"
    )
    assert resp.content.startswith(b"%PDF"), (
        f"response body must be the PDF (starts with %PDF); got {resp.content[:50]!r}"
    )
    assert "attachment" in resp.headers.get("content-disposition", ""), (
        f"content-disposition was {resp.headers.get('content-disposition')!r}; "
        "download responses must carry Content-Disposition: attachment"
    )

    # Semantic check on the warning log — operators grep for this exact message.
    cache_warning_records = [
        rec for rec in caplog.records
        if rec.levelname == "WARNING"
        and "Failed to write pdf_path cache for doc" in rec.getMessage()
    ]
    assert len(cache_warning_records) >= 1, (
        f"expected at least one WARNING containing "
        f"'Failed to write pdf_path cache for doc'; "
        f"got {[r.getMessage() for r in caplog.records]}"
    )

    # Semantic check on DB state — the failed cache write must NOT have
    # updated ProjectDoc.pdf_path (proves the guard caught the exception
    # before svc.update_doc landed).
    db_session.refresh(doc)
    assert doc.pdf_path is None, (
        f"pdf_path must stay None when the cache write failed; got {doc.pdf_path!r}"
    )
```

**Notes on the fixture & seeding code above:**

- The exact `ProjectDoc(...)` keyword set depends on the live model — read `orch/db/models.py` and adjust required-vs-optional columns before writing the test. The key columns you MUST set: `project_id`, `id`, `slug`, `version`, `title`, `content`, plus any other NOT NULL columns. The test must arrive at a state where `doc.pdf_path is None` so `docs_pdf` is forced through the generate-then-cache branch.
- `client` + `db_session` + `test_project` are session/function-scoped fixtures from `tests/dashboard/conftest.py` and the root `tests/conftest.py`. Follow the existing patterns in other `tests/dashboard/test_*.py` files for how to combine them. If a `client`-backed pattern with `db_session` overrides already exists in the dashboard suite (e.g. `tests/dashboard/test_jobs_filter_ui.py` uses `app.dependency_overrides[get_db]`), follow that pattern exactly.
- The `monkeypatch.setattr("dashboard.routers.docs.render_pdf_chromium", ...)` line patches the route-local symbol, so the real Chromium binary is not required. Verify the import name matches the actual symbol used in `dashboard/routers/docs.py` (it may be re-exported from a helper module — adjust the dotted path accordingly).
- The mkdir-patching strategy is narrow (`".generated"` substring guard) to avoid breaking unrelated test-infra `mkdir` calls. If `Path.write_bytes` is easier to patch reliably in your environment, that is also acceptable — both raise `PermissionError` on a read-only `repo_root` and exercise the same guard. Pick one and document the choice in the test docstring.

### 2. Remove the `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf`

In `tests/dashboard/test_route_contract_sweep.py` around line 142, remove the entire dictionary entry:

```python
"/project/{project_id}/docs/{doc_id}/pdf": (
    "TODO(file-incident): docs_pdf() in dashboard/routers/docs.py raises an "
    "unhandled PermissionError (-> HTTP 500) when the optional on-disk PDF "
    "cache dir under project.repo_root is not writable — the PDF itself was "
    "already generated. The sibling handler docs_pdf_view() guards the same "
    "cache write in try/except and degrades gracefully; docs_pdf() must do "
    "the same. Genuine pre-existing handler bug — operator follow-up."
),
```

After removal, `EXPECTED_5XX` may become an empty dict `{}` — that is fine; the comment block above it explains the data type. Do NOT remove the surrounding `EXPECTED_5XX: dict[str, str] = {}` declaration or the explanatory comment block.

**If S01's fix is not yet in `dashboard/routers/docs.py`** (i.e. the guard is still missing), STOP and raise a blocker — do NOT remove the `EXPECTED_5XX` entry, because doing so would convert a currently-`XFAIL` case into a hard `FAIL`. Verify S01's fix landed by `grep -n "Failed to write pdf_path cache for doc" dashboard/routers/docs.py` (must return TWO matches — one in `docs_pdf_view`, one in `docs_pdf`) before removing the entry.

### 3. Targeted Test Verification (NON-NEGOTIABLE)

Run **only** the two files you touched:

```bash
uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

Expected:
- `test_docs_pdf_returns_200_when_cache_dir_not_writable` — passes GREEN.
- `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` — passes as a normal pass (no longer xfail-marked).
- All other sweep cases — pass unchanged.

**Do NOT run `make test-unit`, `make test-integration`, or the full dashboard suite.** Those are S10/S11 QV gates; duplicating them here burns this step's timeout budget (see I-00073/S03 post-mortem, 2026-05-08).

### 4. No Manual Revert RED-Check Inside This Step

Do NOT `git checkout HEAD~1 -- dashboard/routers/docs.py`, `git stash`, or otherwise revert source files at runtime to "verify the test would have caught the bug." That is a design-time exercise — the design author proved the bug existed via the strict-xfail marker pinned in CR-00072. Reverting source files mid-workflow in the worktree is thrash-prone, not a verification.

### 5. Scope Discipline

You may modify ONLY:

- `tests/dashboard/test_docs_pdf_cache_failure.py` (new file).
- `tests/dashboard/test_route_contract_sweep.py` (one dictionary entry removal).

Do NOT edit:

- `dashboard/routers/docs.py` (S01's territory — your fix verification is via running tests, not editing the production file).
- Any other file under `tests/` or `dashboard/`.

### 6. TDD Evidence

The reproduction test you write IS the GREEN test — it passes against S01's fixed code. To capture RED→GREEN evidence:

1. Note in your report that S01's `tdd_red_evidence` already captured the strict-xfail flip (`XPASS(strict)` on `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]`). That is the canonical RED→GREEN demonstration for the FIX itself.
2. For S03's own contribution, the evidence is that removing the `EXPECTED_5XX` entry causes the sweep case to record as a normal pass (no longer `xfail(strict=True)`-marked, no longer `XPASS(strict)`). Capture the post-removal pytest line, e.g. `tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf] PASSED`.
3. Use `"tdd_red_evidence": "n/a — Tests step adds regression coverage after S01's fix; the strict-xfail flip captured in S01's report is the RED→GREEN signal. S03's new test (test_docs_pdf_returns_200_when_cache_dir_not_writable) passes against the fixed code by construction; removing the EXPECTED_5XX entry flips the sweep case from XPASS(strict)→FAIL to PASSED."` in the result contract.

## Project Conventions

Read `CLAUDE.md`, `tests/CLAUDE.md`, and `skills/iw-ai-core-testing/SKILL.md`. Specific to this step:

- The `client` fixture is `tests/dashboard/`-only — do not place this test elsewhere (I-00067 lesson).
- Use `monkeypatch` for filesystem and import-path patches; do NOT use `mock.patch` decorators (the suite convention is fixture-style `monkeypatch`).
- Use `caplog.at_level("WARNING", logger="dashboard.routers.docs")` to capture the warning from the route's own logger — narrower than capturing all warnings.
- The test docstring MUST mention I-00109 by ID (operators grep tests by incident ID when investigating regressions).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report:

1. **`make format`** — auto-fixes formatting drift in your new file and the edited sweep file.
2. **`make type-check`** — zero errors involving the files you touched.
3. **`make lint`** — zero errors. Pay attention to `ruff` rules around `BLE001`, `S101`, and `T201`. Your test file uses `assert` statements (that is correct for pytest) — `S101` is suppressed for `tests/`; do NOT add `# noqa` annotations unnecessarily.

Record results in `preflight`.

## Test Verification (NON-NEGOTIABLE)

Targeted only — `uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov`. See Requirement 3.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00109",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_docs_pdf_cache_failure.py",
    "tests/dashboard/test_route_contract_sweep.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "test_docs_pdf_returns_200_when_cache_dir_not_writable: PASSED; test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]: PASSED (now a normal pass after EXPECTED_5XX removal); <N> total sweep cases pass, 0 failed",
  "tdd_red_evidence": "n/a — Tests step adds regression coverage after S01's fix; the strict-xfail flip captured in S01's report is the RED→GREEN signal. The new test passes against the fixed code by construction; removing the EXPECTED_5XX entry flips the sweep case from XPASS(strict)→FAIL to PASSED.",
  "blockers": [],
  "notes": "EXPECTED_5XX entry for /project/{project_id}/docs/{doc_id}/pdf removed; the dict may now be empty — left declared as `EXPECTED_5XX: dict[str, str] = {}` per S01's design."
}
```
