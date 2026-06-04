"""Unit tests for MapGenerator._build_mermaid ELK frontmatter injection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBuildMermaidElkInjection:
    """Tests for ELK layout frontmatter injection in _build_mermaid."""

    @pytest.fixture
    def mock_config(self):
        """Minimal mock CodeUnderstandingConfig."""
        cfg = MagicMock()
        cfg.resolved_llm_model.return_value = "gemma4:e4b"
        cfg.ollama_url = "http://localhost:11434"
        return cfg

    def test_elk_frontmatter_injected_when_llm_omits_it(self, mock_config):
        """When LLM returns mermaid block without ELK frontmatter, it is injected."""
        from orch.rag.mapgen import MapGenerator

        mock_response = MagicMock()
        mock_response.text = "```mermaid\ngraph TD\n  A[CLI] --> B[Daemon]\n  B --> C[DB]\n```"

        with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = mock_response
            mock_ollama_cls.return_value = mock_llm_instance

            generator = MapGenerator()
            dsl, _purpose = generator._build_mermaid(
                "- **CLI**: command interface\n- **Daemon**: background runner",
                mock_config,
            )

        assert "layout: elk" in dsl, "ELK frontmatter must be injected when LLM omits it"
        assert dsl.count("layout: elk") == 1, "ELK frontmatter must appear exactly once"

    def test_elk_frontmatter_not_duplicated_when_llm_includes_it(self, mock_config):
        """When LLM already includes ELK frontmatter, it is not duplicated."""
        from orch.rag.mapgen import MapGenerator

        mock_response = MagicMock()
        mock_response.text = (
            "```mermaid\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[CLI] --> B[Daemon]\n```"
        )

        with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = mock_response
            mock_ollama_cls.return_value = mock_llm_instance

            generator = MapGenerator()
            dsl, _purpose = generator._build_mermaid(
                "- **CLI**: command interface\n- **Daemon**: background runner",
                mock_config,
            )

        assert dsl.count("layout: elk") == 1, "ELK frontmatter must not be duplicated"

    def test_fallback_dsl_when_no_fenced_block(self, mock_config):
        """When LLM returns prose with no fenced mermaid block, fallback DSL is returned."""
        from orch.rag.mapgen import MapGenerator

        mock_response = MagicMock()
        mock_response.text = "The system has a CLI component and a Daemon component."

        with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = mock_response
            mock_ollama_cls.return_value = mock_llm_instance

            generator = MapGenerator()
            dsl, _purpose = generator._build_mermaid(
                "- **CLI**: command interface\n- **Daemon**: background runner",
                mock_config,
            )

        assert "graph TD" in dsl, "Fallback DSL must contain 'graph TD'"
        assert "layout: elk" in dsl, "Fallback DSL must still get ELK frontmatter injected"
