"""Unit tests for orch.rag.index_gen."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from orch.db.models import DocType


class TestExtractFirstSentence:
    """Tests for _extract_first_sentence()."""

    def test_none_content_returns_em_dash(self):
        from orch.rag.index_gen import _extract_first_sentence

        assert _extract_first_sentence(None) == "—"

    def test_empty_string_returns_em_dash(self):
        from orch.rag.index_gen import _extract_first_sentence

        assert _extract_first_sentence("") == "—"

    def test_strips_h1_header(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "# My Document\n\nThis is the first sentence."
        result = _extract_first_sentence(content)
        assert result == "This is the first sentence."

    def test_strips_h2_header(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "## Second Level\n\nAnother first sentence."
        result = _extract_first_sentence(content)
        assert result == "Another first sentence."

    def test_extracts_first_sentence_with_period(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "First sentence. Second sentence."
        result = _extract_first_sentence(content)
        assert result == "First sentence."

    def test_extracts_first_sentence_with_question_mark(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "Is this a question? Yes it is."
        result = _extract_first_sentence(content)
        assert result == "Is this a question?"

    def test_extracts_first_sentence_with_exclamation(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "Watch out! Something happened."
        result = _extract_first_sentence(content)
        assert result == "Watch out!"

    def test_uses_ellipsis_for_long_text_without_punctuation(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "A" * 100
        result = _extract_first_sentence(content)
        assert result == "A" * 80 + "…"

    def test_handles_multiple_blank_lines(self):
        from orch.rag.index_gen import _extract_first_sentence

        content = "# Header\n\n\n\nFirst sentence here."
        result = _extract_first_sentence(content)
        assert result == "First sentence here."


class TestBuildIndexContent:
    """Tests for _build_index_content()."""

    def _make_mock_doc(self, doc_id, title, doc_type_value, content=None, generated_at=None):
        doc = MagicMock()
        doc.doc_id = doc_id
        doc.title = title
        doc.doc_type = DocType(doc_type_value)
        doc.content = content
        doc.generated_at = generated_at or datetime.now(UTC)
        return doc

    def test_architecture_section_includes_architecture_map(self):
        from orch.rag.index_gen import _build_index_content

        arch_doc = self._make_mock_doc(
            "architecture-map",
            "Test Project — Architecture Map",
            "architecture",
            "# Architecture Map\n\nThis system provides orchestration.",
        )
        docs_by_type = {DocType.architecture: [arch_doc], DocType.diagram: []}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Architecture" in result
        assert "[Architecture Overview](code-map)" in result

    def test_architecture_section_includes_architecture_diagram(self):
        from orch.rag.index_gen import _build_index_content

        diagram_doc = self._make_mock_doc(
            "diagram-architecture",
            "Test Project — Architecture Diagram",
            "diagram",
            "<!-- purpose: Shows the system components -->",
        )
        docs_by_type = {DocType.architecture: [], DocType.diagram: [diagram_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Architecture" in result
        assert "[Architecture Diagram](diagram-architecture)" in result
        assert "Shows the system components" in result

    def test_module_documentation_section(self):
        from orch.rag.index_gen import _build_index_content

        module_doc = self._make_mock_doc(
            "module-orch",
            "Orch Module",
            "module",
            "# Orch Module\n\nThis module handles orchestration.",
        )
        docs_by_type = {DocType.module: [module_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Module Documentation" in result
        assert "[Orch Module](module-orch)" in result

    def test_module_diagrams_section(self):
        from orch.rag.index_gen import _build_index_content

        diagram_doc = self._make_mock_doc(
            "diagram-module-orch",
            "Orch Module Diagram",
            "diagram",
            "graph TD\n  A --> B",
        )
        docs_by_type = {DocType.diagram: [diagram_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Module Diagrams" in result
        assert "diagram-module-orch" in result

    def test_api_reference_section_when_apis_exist(self):
        from orch.rag.index_gen import _build_index_content

        api_doc = self._make_mock_doc(
            "api-dashboard",
            "Dashboard API",
            "api",
            "# Dashboard API\n\nREST endpoints for the dashboard.",
        )
        docs_by_type = {DocType.api: [api_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## API Reference" in result
        assert "[Dashboard API](api-dashboard)" in result

    def test_api_reference_section_when_no_apis(self):
        from orch.rag.index_gen import _build_index_content

        docs_by_type = {DocType.api: []}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## API Reference" in result
        assert "_No API documentation registered yet._" in result

    def test_research_section_with_docs(self):
        from orch.rag.index_gen import _build_index_content

        research_doc = self._make_mock_doc(
            "research-llm-evaluation",
            "LLM Evaluation Research",
            "research",
            "# LLM Evaluation\n\nStudy of LLM performance.",
            generated_at=datetime(2026, 4, 15, tzinfo=UTC),
        )
        docs_by_type = {DocType.research: [research_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Research" in result
        assert "[LLM Evaluation Research](research-llm-evaluation)" in result
        assert "2026-04-15" in result

    def test_research_section_when_no_research(self):
        from orch.rag.index_gen import _build_index_content

        docs_by_type = {DocType.research: []}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Research" in result
        assert "_No research documents._" in result

    def test_generated_date_in_content(self):
        from orch.rag.index_gen import _build_index_content

        docs_by_type = {DocType.architecture: []}

        result = _build_index_content("Test Project", docs_by_type)

        assert "<!-- generated:" in result


class TestGenerateIndexPage:
    """Tests for generate_index_page()."""

    def test_calls_create_doc_when_no_existing_doc(self):
        from unittest.mock import MagicMock, patch

        from orch.rag.index_gen import generate_index_page

        mock_session = MagicMock()

        mock_project = MagicMock()
        mock_project.display_name = "Test Project"
        mock_session.get.return_value = mock_project

        mock_doc_service = MagicMock()
        mock_doc_service.list_docs.return_value = []
        mock_doc_service.get_doc.return_value = None

        with (
            patch("orch.rag.index_gen.DocService", return_value=mock_doc_service),
            patch("orch.rag.index_gen.Project"),
        ):
            generate_index_page("test-proj", mock_session)

        mock_doc_service.create_doc.assert_called_once()
        call_kwargs = mock_doc_service.create_doc.call_args.kwargs
        assert call_kwargs["doc_id"] == "code-index"
        assert call_kwargs["doc_type"] == DocType.architecture

    def test_calls_update_doc_when_existing_doc(self):
        from unittest.mock import MagicMock, patch

        from orch.rag.index_gen import generate_index_page

        mock_session = MagicMock()

        mock_project = MagicMock()
        mock_project.display_name = "Test Project"
        mock_session.get.return_value = mock_project

        existing_doc = MagicMock()
        mock_doc_service = MagicMock()
        mock_doc_service.list_docs.return_value = [existing_doc]
        mock_doc_service.get_doc.return_value = existing_doc

        with (
            patch("orch.rag.index_gen.DocService", return_value=mock_doc_service),
            patch("orch.rag.index_gen.Project"),
        ):
            generate_index_page("test-proj", mock_session)

        mock_doc_service.update_doc.assert_called_once()
        call_kwargs = mock_doc_service.update_doc.call_args.kwargs
        assert call_kwargs["doc_id"] == "code-index"

    def test_empty_project_shows_no_documentation_note(self):
        from unittest.mock import MagicMock, patch

        from orch.rag.index_gen import generate_index_page

        mock_session = MagicMock()
        mock_session.get.return_value = None

        mock_doc_service = MagicMock()
        mock_doc_service.list_docs.return_value = []
        mock_doc_service.get_doc.return_value = None

        with (
            patch("orch.rag.index_gen.DocService", return_value=mock_doc_service),
            patch("orch.rag.index_gen.Project"),
        ):
            generate_index_page("empty-proj", mock_session)

        mock_doc_service.create_doc.assert_called_once()
        call_kwargs = mock_doc_service.create_doc.call_args.kwargs
        content = call_kwargs["content"]
        assert "No documentation has been generated" in content

    def test_generated_content_contains_module_documentation_header(self):
        from unittest.mock import MagicMock, patch

        from orch.rag.index_gen import generate_index_page

        mock_session = MagicMock()

        mock_project = MagicMock()
        mock_project.display_name = "Test Project"
        mock_session.get.return_value = mock_project

        module_doc = MagicMock()
        module_doc.doc_id = "module-foo"
        module_doc.title = "Foo Module"
        module_doc.doc_type = DocType.module
        module_doc.content = "# Foo Module\n\nThis is the foo module."
        module_doc.generated_at = datetime.now(UTC)

        mock_doc_service = MagicMock()
        mock_doc_service.list_docs.return_value = [module_doc]
        mock_doc_service.get_doc.return_value = None

        with (
            patch("orch.rag.index_gen.DocService", return_value=mock_doc_service),
            patch("orch.rag.index_gen.Project"),
        ):
            generate_index_page("test-proj", mock_session)

        mock_doc_service.create_doc.assert_called_once()
        call_kwargs = mock_doc_service.create_doc.call_args.kwargs
        content = call_kwargs["content"]
        assert "## Module Documentation" in content


class TestGenerateIndexPageGroups:
    """Tests for grouping behavior in generate_index_page()."""

    def test_index_groups_by_doc_type_module_under_module_documentation(
        self,
    ):
        """Index groups module docs under ## Module Documentation."""
        from unittest.mock import MagicMock

        from orch.db.models import DocType
        from orch.rag.index_gen import _build_index_content

        module_doc = MagicMock()
        module_doc.doc_id = "module-orch"
        module_doc.title = "Orch Module"
        module_doc.doc_type = DocType.module
        module_doc.content = "# Orch Module\n\nHandles orchestration."
        module_doc.generated_at = datetime.now(UTC)

        docs_by_type = {DocType.module: [module_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Module Documentation" in result
        assert "[Orch Module](module-orch)" in result

    def test_index_first_sentence_extraction_from_content(self):
        """Description extracted from first non-header sentence of content."""
        from orch.rag.index_gen import _extract_first_sentence

        content = "# My Module\n\nThis module orchestrates agents and work items."
        result = _extract_first_sentence(content)
        assert result == "This module orchestrates agents and work items."

    def test_index_none_content_renders_em_dash(self):
        """Doc with None content renders '—' as description."""
        from orch.rag.index_gen import _extract_first_sentence

        assert _extract_first_sentence(None) == "—"

    def test_index_empty_content_renders_em_dash(self):
        """Doc with empty content renders '—' as description."""
        from orch.rag.index_gen import _extract_first_sentence

        assert _extract_first_sentence("") == "—"

    def test_index_groups_api_docs_under_api_reference(self):
        """API docs are grouped under ## API Reference."""
        from unittest.mock import MagicMock

        from orch.db.models import DocType
        from orch.rag.index_gen import _build_index_content

        api_doc = MagicMock()
        api_doc.doc_id = "api-dashboard"
        api_doc.title = "Dashboard API"
        api_doc.doc_type = DocType.api
        api_doc.content = "# Dashboard API\n\nREST endpoints."
        api_doc.generated_at = datetime.now(UTC)

        docs_by_type = {DocType.api: [api_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## API Reference" in result
        assert "[Dashboard API](api-dashboard)" in result


class TestGenerateIndexPageBoundary:
    """Boundary behavior tests for generate_index_page()."""

    def test_index_missing_purpose_marker_no_key_error(self):
        """Old diagram doc without <!-- purpose: --> → no KeyError/AttributeError."""
        from unittest.mock import MagicMock

        from orch.db.models import DocType
        from orch.rag.index_gen import _build_index_content

        diagram_doc = MagicMock()
        diagram_doc.doc_id = "diagram-architecture"
        diagram_doc.title = "Architecture Diagram"
        diagram_doc.doc_type = DocType.diagram
        diagram_doc.content = "graph TD\n  A --> B"  # No purpose marker
        diagram_doc.generated_at = datetime.now(UTC)

        docs_by_type = {DocType.diagram: [diagram_doc]}

        result = _build_index_content("Test Project", docs_by_type)

        assert "## Architecture" in result
        assert "[Architecture Diagram](diagram-architecture)" in result
