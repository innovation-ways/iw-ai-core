"""Integration tests for F-00048 code module + symbol API endpoints.

Tests the 4 new endpoints added to dashboard/routers/code.py:
  GET  /api/projects/{project_id}/code/modules
  GET  /api/projects/{project_id}/code/modules/{module_slug}
  POST /api/projects/{project_id}/code/modules/{module_slug}/generate
  GET  /api/projects/{project_id}/code/symbol

All DB operations use testcontainers (NEVER the live platform DB on port 5433).
External services (LanceDB, Ollama) are mocked using monkeypatch.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DocTier, DocType, EditorialCategory, Project, ProjectDoc

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


FIXTURE_LEVEL1_DOC = """# Architecture Map

## Components

- `engine/` -- C++ Sensor Engine for high-throughput UDP ingestion
- `api/` -- Python FastAPI backend exposing REST and WebSocket endpoints
- `worker/` -- Celery async workers for background processing
"""


def _insert_level1_doc(db: Session, project_id: str, content: str) -> None:
    """Insert a Level 1 architecture map ProjectDoc for the given project."""
    doc = ProjectDoc(
        id=f"{project_id}:architecture-map",
        project_id=project_id,
        doc_id="architecture-map",
        title="Test Project — Architecture Map",
        slug=f"{project_id}-architecture-map",
        doc_type=DocType.research,
        tier=DocTier.fully_automated,
        editorial_category=EditorialCategory.technical,
        content=content,
        version=1,
    )
    db.add(doc)
    db.flush()


def _fake_doc(content: str = "## Module Content\n\nTest module description.") -> ProjectDoc:
    """Return a minimal fake ProjectDoc for mocking."""
    doc = MagicMock(spec=ProjectDoc)
    doc.content = content
    doc.title = "Test Module"
    return doc


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


class TestListModules:
    def test_list_modules_returns_404_when_no_level1_doc(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(f"/api/projects/{test_project.id}/code/modules")
        assert resp.status_code == 404

    def test_list_modules_returns_html_fragment(
        self, client: TestClient, test_project: Project, db_session: Session
    ) -> None:
        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.get(f"/api/projects/{test_project.id}/code/modules")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "code-components-section" in resp.text
        assert "engine/" in resp.text
        assert "api/" in resp.text

    def test_list_modules_empty_when_no_components_section(
        self, client: TestClient, test_project: Project, db_session: Session
    ) -> None:
        _insert_level1_doc(db_session, test_project.id, "# Architecture Map\n\nNo components here.")
        resp = client.get(f"/api/projects/{test_project.id}/code/modules")
        assert resp.status_code == 200
        assert "code-components-section" in resp.text


class TestGetModule:
    def test_get_module_404_when_no_level1_doc(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
        assert resp.status_code == 404

    def test_get_module_404_when_module_not_found(
        self, client: TestClient, test_project: Project, db_session: Session
    ) -> None:
        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.get(f"/api/projects/{test_project.id}/code/modules/nonexistent")
        assert resp.status_code == 404

    def test_get_module_generates_and_renders_detail(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def mock_get_or_generate(*args: object, **kwargs: object) -> tuple[ProjectDoc, bool]:
            return (_fake_doc(), False)

        from dashboard.routers import code as code_module

        monkeypatch.setattr(code_module.ModuleGenerator, "get_or_generate", mock_get_or_generate)

        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
        assert resp.status_code == 200
        assert "freshly generated" in resp.text.lower() or "generating" in resp.text.lower()

    def test_get_module_returns_cached_badge_on_hit(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def mock_get_or_generate(*args: object, **kwargs: object) -> tuple[ProjectDoc, bool]:
            return (_fake_doc(), True)

        from dashboard.routers import code as code_module

        monkeypatch.setattr(code_module.ModuleGenerator, "get_or_generate", mock_get_or_generate)

        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
        assert resp.status_code == 200
        assert "cached" in resp.text.lower() or "cache" in resp.text.lower()

    def test_get_module_returns_generating_fragment_on_timeout(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def slow_gen(*args: object, **kwargs: object) -> tuple[ProjectDoc, bool]:
            await asyncio.sleep(2)
            return (_fake_doc(), False)

        from dashboard.routers import code as code_module

        monkeypatch.setattr(code_module.ModuleGenerator, "get_or_generate", slow_gen)

        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.get(f"/api/projects/{test_project.id}/code/modules/engine")
        assert resp.status_code == 200
        assert "hx-trigger" in resp.text or "generating" in resp.text.lower()


class TestRegenerateModule:
    def test_regenerate_module_404_when_no_level1_doc(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.post(f"/api/projects/{test_project.id}/code/modules/engine/generate")
        assert resp.status_code == 404

    def test_regenerate_module_skips_cache(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from dashboard.routers import code as code_module

        mock_get_or_generate = MagicMock()
        gen2_calls: list = []

        async def async_gen_level2(*args: object, **kwargs: object) -> ProjectDoc:
            gen2_calls.append(True)
            return _fake_doc()

        monkeypatch.setattr(code_module.ModuleGenerator, "get_or_generate", mock_get_or_generate)
        monkeypatch.setattr(code_module.ModuleGenerator, "generate_level2", async_gen_level2)

        _insert_level1_doc(db_session, test_project.id, FIXTURE_LEVEL1_DOC)
        resp = client.post(f"/api/projects/{test_project.id}/code/modules/engine/generate")
        assert resp.status_code == 200
        mock_get_or_generate.assert_not_called()
        assert len(gen2_calls) > 0, "generate_level2 should have been called"


class TestExplainSymbol:
    def test_explain_symbol_returns_html_fragment(
        self, client: TestClient, test_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_explain_symbol(*args: object, **kwargs: object) -> str:
            return "## RingBuffer\n\nFixed-capacity buffer.\n"

        from dashboard.routers import code as code_module

        monkeypatch.setattr(code_module.SymbolGenerator, "explain_symbol", mock_explain_symbol)

        resp = client.get(
            f"/api/projects/{test_project.id}/code/symbol",
            params={"file_path": "engine/main.cpp"},
        )
        assert resp.status_code == 200
        assert "symbol-panel" in resp.text.lower() or "ringbuffer" in resp.text.lower()

    def test_explain_symbol_rejects_path_traversal(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(
            f"/api/projects/{test_project.id}/code/symbol",
            params={"file_path": "../../etc/passwd"},
        )
        assert resp.status_code == 400

    def test_explain_symbol_rejects_absolute_path(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(
            f"/api/projects/{test_project.id}/code/symbol",
            params={"file_path": "/etc/passwd"},
        )
        assert resp.status_code == 400

    def test_explain_symbol_with_symbol_name(
        self, client: TestClient, test_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_explain_symbol(*args: object, **kwargs: object) -> str:
            return "RingBuffer is a lock-free buffer.\n"

        from dashboard.routers import code as code_module

        monkeypatch.setattr(code_module.SymbolGenerator, "explain_symbol", mock_explain_symbol)

        resp = client.get(
            f"/api/projects/{test_project.id}/code/symbol",
            params={"file_path": "engine/buffer/ring.h", "symbol_name": "RingBuffer"},
        )
        assert resp.status_code == 200
        assert "RingBuffer" in resp.text

    def test_explain_symbol_missing_file_path_param(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(f"/api/projects/{test_project.id}/code/symbol")
        assert resp.status_code == 422
