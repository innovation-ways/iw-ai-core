"""Regression tests for I-00109: docs_pdf must return the PDF even when the
on-disk cache write fails (PermissionError on a read-only repo_root).

Pre-fix: dashboard/routers/docs.py::docs_pdf had an unguarded cache write that
surfaced PermissionError as HTTP 500.
Post-fix: the cache write is wrapped in try/except Exception (mirroring
docs_pdf_view's existing guard at lines 256-266), the PDF bytes are returned
unconditionally, and a warning is logged.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, Project, ProjectDoc


@pytest.fixture
def client(
    db_session: Session,
    db_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """Return a TestClient bound to the testcontainer DB.

    Mirrors the pattern in ``test_help_router.py`` and
    ``test_route_contract_sweep.py::sweep_client`` — rebind module-level
    ``SessionLocal`` / ``engine`` before creating the app so any handler or
    middleware that reaches for them lands on the test DB, never port 5433.
    """
    import dashboard.app as app_module
    import dashboard.dependencies as deps_module
    import orch.db.session as session_module

    # Rebind orch.db.session so any handler using SessionLocal() hits test DB.
    monkeypatch.setattr(session_module, "_engine", db_engine, raising=False)
    monkeypatch.setattr(session_module, "_session_local", None, raising=False)
    test_session_local = session_module._get_session_local()

    # Rebind dashboard.app / dashboard.dependencies SessionLocal.
    monkeypatch.setattr(app_module, "engine", db_engine, raising=False)
    monkeypatch.setattr(app_module, "SessionLocal", test_session_local, raising=False)
    monkeypatch.setattr(deps_module, "SessionLocal", test_session_local, raising=False)

    # Remove DB-identity check guard so the test runs without a real instance_id.
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


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
        id=f"{test_project.id}:I-00109-fixture-doc",
        project_id=test_project.id,
        doc_id="I-00109-fixture-doc",
        title="I-00109 fixture",
        slug="i-00109-fixture",
        version=1,
        doc_type=DocType.module,
        tier=DocTier.fully_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        audience=[],
        source_paths=[],
        content="# Hello",
        pdf_path=None,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # Patch render_pdf_chromium to return deterministic bytes — avoids the
    # need for a real Chromium binary in the test environment.
    monkeypatch.setattr(
        "dashboard.routers.docs.render_pdf_chromium",
        lambda _html: b"%PDF-1.4 fake bytes for I-00109 regression test",
    )

    # Patch Path.mkdir to raise PermissionError ONLY for the docs cache dir
    # — letting unrelated mkdirs (test harness, etc.) through. This is what
    # a read-only repo_root looks like in practice.
    real_mkdir = Path.mkdir

    def fail_mkdir_on_docs_cache(self: Path, *args: Any, **kwargs: Any) -> None:
        if ".generated" in str(self):
            raise PermissionError(f"[Errno 13] Permission denied: '{self}'")
        real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_mkdir_on_docs_cache)

    # Act
    with caplog.at_level("WARNING", logger="dashboard.routers.docs"):
        resp = client.get(f"/project/{test_project.id}/docs/{doc.doc_id}/pdf")

    # Assert — SEMANTIC (every assertion would fail if the bug regressed):
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:300]!r}"
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
        rec
        for rec in caplog.records
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
