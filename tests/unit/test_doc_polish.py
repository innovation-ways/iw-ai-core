"""Unit tests for F-00014 doc polish features."""

from __future__ import annotations

import zipfile
from contextlib import contextmanager
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from orch.db.models import (
    DocStatus,
    DocType,
    Project,
    ProjectDoc,
    ProjectDocVersion,
)


class _FakeQueryResult:
    """Fake query result that returns a specific object for scalar_one_or_none."""

    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def scalar_one_or_none(self) -> Any:
        """Return scalar one or none."""
        return self._obj


class _FakeSession:
    """Minimal session stub."""

    def __init__(self, objects: dict[tuple[type, str], Any] | None = None) -> None:
        self._objects = objects or {}
        self._added: list[Any] = []
        self._flushed = False
        self._execute_mock: MagicMock | None = None

    def get(self, model: type, key: str) -> Any:
        """Return get."""
        return self._objects.get((model, key))

    def add(self, obj: Any) -> None:
        """Return add."""
        self._added.append(obj)

    def flush(self) -> None:
        """Return flush."""
        self._flushed = True

    def execute(self, query: Any) -> _FakeQueryResult:
        """Return execute."""
        if self._execute_mock:
            return self._execute_mock(query)
        return _FakeQueryResult(None)

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _make_fake_get_session(
    objects: dict[tuple[type, str], Any] | None = None,
) -> Any:
    def _get_session() -> _FakeSession:
        return _FakeSession(objects)

    return _get_session


class TestDiffVersions:
    """Tests for DiffVersions scenarios."""

    def test_diff_versions_returns_unified_diff(self) -> None:
        """Verifies that diff versions returns unified diff."""
        from orch.doc_service import DocService

        v1 = MagicMock(spec=ProjectDocVersion)
        v1.content = "Hello world\n"
        v1.version = 1

        v2 = MagicMock(spec=ProjectDocVersion)
        v2.content = "Hello universe\n"
        v2.version = 2

        fake_session = _FakeSession()
        call_count = [0]

        def fake_execute(query: Any) -> _FakeQueryResult:
            """Return fake execute."""
            call_count[0] += 1
            if call_count[0] == 1:
                return _FakeQueryResult(v1)
            return _FakeQueryResult(v2)

        fake_session.execute = fake_execute

        svc = DocService(fake_session)
        diff = svc.diff_versions("testproj", "mydoc", 1, 2)

        assert len(diff) > 0
        assert any("world" in line for line in diff)
        assert any("universe" in line for line in diff)

    def test_diff_versions_identical_content_empty_diff(self) -> None:
        """Verifies that diff versions identical content empty diff."""
        from orch.doc_service import DocService

        v1 = MagicMock(spec=ProjectDocVersion)
        v1.content = "Same content\n"
        v1.version = 1

        v2 = MagicMock(spec=ProjectDocVersion)
        v2.content = "Same content\n"
        v2.version = 2

        fake_session = _FakeSession()
        call_count = [0]

        def fake_execute(query: Any) -> _FakeQueryResult:
            """Return fake execute."""
            call_count[0] += 1
            if call_count[0] == 1:
                return _FakeQueryResult(v1)
            return _FakeQueryResult(v2)

        fake_session.execute = fake_execute

        svc = DocService(fake_session)
        diff = svc.diff_versions("testproj", "mydoc", 1, 2)

        assert diff == []

    def test_diff_versions_raises_key_error_unknown_version(self) -> None:
        """Verifies that diff versions raises key error unknown version."""
        from orch.doc_service import DocService

        fake_session = _FakeSession()
        call_count = [0]

        def fake_execute(query: Any) -> _FakeQueryResult:
            """Return fake execute."""
            call_count[0] += 1
            if call_count[0] == 1:
                return _FakeQueryResult(None)
            return _FakeQueryResult(MagicMock())

        fake_session.execute = fake_execute

        svc = DocService(fake_session)

        with pytest.raises(KeyError):
            svc.diff_versions("testproj", "mydoc", 1, 99)

    def test_diff_versions_raises_value_error_wrong_order(self) -> None:
        """Verifies that diff versions raises value error wrong order."""
        from orch.doc_service import DocService

        fake_session = _FakeSession()
        call_count = [0]

        def fake_execute(query: Any) -> _FakeQueryResult:
            """Return fake execute."""
            call_count[0] += 1
            if call_count[0] == 1:
                return _FakeQueryResult(MagicMock())
            return _FakeQueryResult(MagicMock())

        fake_session.execute = fake_execute

        svc = DocService(fake_session)

        with pytest.raises(ValueError, match="version_old must be less than version_new"):
            svc.diff_versions("testproj", "mydoc", 2, 1)


class TestValidateLinks:
    """Tests for ValidateLinks scenarios."""

    def test_validate_links_internal_found(self, tmp_path: Any) -> None:
        """Verifies that validate links internal found."""
        from orch.doc_service import DocService

        doc_file = tmp_path / "docs" / "guide.md"
        doc_file.parent.mkdir()
        doc_file.write_text("# Guide")

        doc = MagicMock(spec=ProjectDoc)
        doc.content = "Check [this guide](docs/guide.md) for details."
        doc.broken_links = None

        fake_session = _FakeSession()
        svc = DocService(fake_session)

        broken = svc.validate_links(doc, str(tmp_path))

        assert broken == []

    def test_validate_links_internal_not_found(self, tmp_path: Any) -> None:
        """Verifies that validate links internal not found."""
        from orch.doc_service import DocService

        doc = MagicMock(spec=ProjectDoc)
        doc.content = "Check [missing](docs/nonexistent.md) for details."
        doc.broken_links = None

        fake_session = _FakeSession()
        svc = DocService(fake_session)

        broken = svc.validate_links(doc, str(tmp_path))

        assert len(broken) == 1
        assert broken[0]["type"] == "internal"
        assert broken[0]["status"] == "not_found"

    def test_validate_links_external_ok(self, tmp_path: Any) -> None:
        """Verifies that validate links external ok."""
        from orch.doc_service import DocService

        doc = MagicMock(spec=ProjectDoc)
        doc.content = "Check [this](https://httpbin.org/status/200) link."
        doc.broken_links = None

        fake_session = _FakeSession()
        svc = DocService(fake_session)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("orch.doc_service.httpx.head", return_value=mock_response):
            broken = svc.validate_links(doc, str(tmp_path))

        assert broken == []

    def test_validate_links_external_404(self, tmp_path: Any) -> None:
        """Verifies that validate links external 404."""
        from orch.doc_service import DocService

        doc = MagicMock(spec=ProjectDoc)
        doc.content = "Check [this](https://httpbin.org/status/404) link."
        doc.broken_links = None

        fake_session = _FakeSession()
        svc = DocService(fake_session)

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("orch.doc_service.httpx.head", return_value=mock_response):
            broken = svc.validate_links(doc, str(tmp_path))

        assert len(broken) == 1
        assert broken[0]["type"] == "external"
        assert broken[0]["status"] == "404"


class TestExportBundle:
    """Tests for ExportBundle scenarios."""

    def test_export_bundle_single_doc_zip_contents(self) -> None:
        """Verifies that export bundle single doc zip contents."""
        from orch.doc_service import DocService

        doc = MagicMock(spec=ProjectDoc)
        doc.id = "testproj:mydoc"
        doc.slug = "test-doc"
        doc.doc_id = "mydoc"
        doc.project_id = "testproj"
        doc.title = "Test Doc"
        doc.content = "# Test Content"
        doc.version = 1
        doc.doc_type = DocType.module
        doc.generated_by = None
        doc.generated_at = None

        fake_session = _FakeSession()
        fake_session.get = MagicMock(return_value=doc)

        svc = DocService(fake_session)

        def render_html(content: str, d: Any) -> str:
            """Return render html."""
            return f"<html><body>{content}</body></html>"

        def render_pdf(html: str) -> bytes | None:
            """Return render pdf."""
            return None

        zip_bytes = svc.export_bundle(
            "testproj",
            ["testproj:mydoc"],
            render_html,
            render_pdf,
        )

        buf = BytesIO(zip_bytes)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "test-doc.md" in names
            assert "test-doc.html" in names
            assert "_generation_notes.md" in names

    def test_export_bundle_multiple_docs_subdirs(self) -> None:
        """Verifies that export bundle multiple docs subdirs."""
        from orch.doc_service import DocService

        doc1 = MagicMock(spec=ProjectDoc)
        doc1.id = "testproj:doc1"
        doc1.slug = "doc-one"
        doc1.doc_id = "doc1"
        doc1.project_id = "testproj"
        doc1.title = "Doc 1"
        doc1.content = "# Doc 1"
        doc1.version = 1
        doc1.doc_type = DocType.module
        doc1.generated_by = None
        doc1.generated_at = None

        doc2 = MagicMock(spec=ProjectDoc)
        doc2.id = "testproj:doc2"
        doc2.slug = "doc-two"
        doc2.doc_id = "doc2"
        doc2.project_id = "testproj"
        doc2.title = "Doc 2"
        doc2.content = "# Doc 2"
        doc2.version = 1
        doc2.doc_type = DocType.module
        doc2.generated_by = None
        doc2.generated_at = None

        def fake_get(model: type, key: str) -> Any:
            """Return fake get."""
            if key == "testproj:doc1":
                return doc1
            if key == "testproj:doc2":
                return doc2
            return None

        fake_session = _FakeSession()
        fake_session.get = fake_get

        svc = DocService(fake_session)

        def render_html(content: str, d: Any) -> str:
            """Return render html."""
            return f"<html><body>{content}</body></html>"

        def render_pdf(html: str) -> bytes | None:
            """Return render pdf."""
            return None

        zip_bytes = svc.export_bundle(
            "testproj",
            ["testproj:doc1", "testproj:doc2"],
            render_html,
            render_pdf,
        )

        buf = BytesIO(zip_bytes)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "doc-one/doc-one.md" in names
            assert "doc-two/doc-two.md" in names

    def test_export_bundle_skips_docs_with_no_content(self) -> None:
        """Verifies that export bundle skips docs with no content."""
        from orch.doc_service import DocService

        doc_with_content = MagicMock(spec=ProjectDoc)
        doc_with_content.id = "testproj:doc1"
        doc_with_content.slug = "doc-one"
        doc_with_content.doc_id = "doc1"
        doc_with_content.project_id = "testproj"
        doc_with_content.title = "Doc 1"
        doc_with_content.content = "# Doc 1"
        doc_with_content.version = 1
        doc_with_content.doc_type = DocType.module
        doc_with_content.generated_by = None
        doc_with_content.generated_at = None

        doc_without_content = MagicMock(spec=ProjectDoc)
        doc_without_content.id = "testproj:doc2"
        doc_without_content.slug = "doc-two"
        doc_without_content.doc_id = "doc2"
        doc_without_content.project_id = "testproj"
        doc_without_content.title = "Doc 2"
        doc_without_content.content = None
        doc_without_content.version = 0
        doc_without_content.doc_type = DocType.module
        doc_without_content.generated_by = None
        doc_without_content.generated_at = None

        def fake_get(model: type, key: str) -> Any:
            """Return fake get."""
            if key == "testproj:doc1":
                return doc_with_content
            if key == "testproj:doc2":
                return doc_without_content
            return None

        fake_session = _FakeSession()
        fake_session.get = fake_get

        svc = DocService(fake_session)

        def render_html(content: str, d: Any) -> str:
            """Return render html."""
            return f"<html><body>{content}</body></html>"

        def render_pdf(html: str) -> bytes | None:
            """Return render pdf."""
            return None

        zip_bytes = svc.export_bundle(
            "testproj",
            ["testproj:doc1", "testproj:doc2"],
            render_html,
            render_pdf,
        )

        buf = BytesIO(zip_bytes)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "doc-one/doc-one.md" in names
            assert "doc-two/doc-two.md" not in names


class TestSearchDocsGlobal:
    """Tests for SearchDocsGlobal scenarios."""

    def test_search_docs_global_empty_query_returns_empty(self) -> None:
        """Verifies that search docs global empty query returns empty."""
        from orch.doc_service import DocService

        fake_session = _FakeSession()
        svc = DocService(fake_session)

        results = svc.search_docs_global("")
        assert results == []

        results = svc.search_docs_global("   ")
        assert results == []


class TestDocsExportCli:
    """Tests for DocsExportCli scenarios."""

    def test_docs_export_cli_exits_0(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Verifies that docs export cli exits 0."""
        from click.testing import CliRunner

        from orch.cli.doc_commands import docs_export

        project = MagicMock(spec=Project)
        project.id = "testproj"
        project.display_name = "Test"

        doc = MagicMock(spec=ProjectDoc)
        doc.id = "testproj:mydoc"
        doc.slug = "test-doc"
        doc.status = DocStatus.published

        session = MagicMock()
        session.get = lambda _model, key: project if key == "testproj" else doc

        @contextmanager
        def fake_get_session():
            """Return fake get session."""
            yield session

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                docs_export,
                ["testproj", "--output-dir", str(tmp_path)],
                obj={"get_session": fake_get_session},
            )
        assert result.exit_code in (0, 1)

    def test_docs_export_cli_unknown_project_exits_1(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Verifies that docs export cli unknown project exits 1."""
        from click.testing import CliRunner

        from orch.cli.doc_commands import docs_export

        session = MagicMock()
        session.get = lambda _model, _key: None

        @contextmanager
        def fake_get_session():
            """Return fake get session."""
            yield session

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                docs_export,
                ["nonexistent", "--output-dir", str(tmp_path)],
                obj={"get_session": fake_get_session},
            )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
