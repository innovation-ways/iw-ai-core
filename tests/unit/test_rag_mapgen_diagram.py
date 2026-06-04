"""Unit tests for MapGenerator._build_mermaid() diagram prompt enhancements.

Verifies semantic correctness: specific canonical hex values, exact format
strings, and purpose comment placement — not just output shape.
"""

from unittest.mock import MagicMock, patch

import pytest

from orch.rag.mapgen import MapGenerator


class TestBuildMermaidSemanticColors:
    """Tests for classDef color palette injection in _build_mermaid()."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_build_mermaid_includes_classdef_api_fill_dbeafe(self, mock_config):
        """classDef api uses the canonical #DBEAFE fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  CLI[iw CLI] --> Daemon[Daemon]
  class CLI api
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef api fill:#DBEAFE" in dsl, (
            f"DSL must contain canonical 'classDef api fill:#DBEAFE', got: {dsl}"
        )

    def test_build_mermaid_includes_classdef_data_fill_d1fae5(self, mock_config):
        """classDef data uses the canonical #D1FAE5 fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  DB[(PostgreSQL)] --> Worker[Worker]
  class DB data
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef data fill:#D1FAE5" in dsl, (
            f"DSL must contain canonical 'classDef data fill:#D1FAE5', got: {dsl}"
        )

    def test_build_mermaid_includes_classdef_worker_fill_fef3c7(self, mock_config):
        """classDef worker uses the canonical #FEF3C7 fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  Worker[Background Job] --> DB[(DB)]
  class Worker worker
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef worker fill:#FEF3C7" in dsl, (
            f"DSL must contain canonical 'classDef worker fill:#FEF3C7', got: {dsl}"
        )

    def test_build_mermaid_includes_classdef_external_fill_f3f4f6(self, mock_config):
        """classDef external uses the canonical #F3F4F6 fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  External[Ollama API] --> Core[Core Service]
  class External external
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef external fill:#F3F4F6" in dsl, (
            f"DSL must contain canonical 'classDef external fill:#F3F4F6', got: {dsl}"
        )

    def test_build_mermaid_includes_classdef_ui_fill_ede9fe(self, mock_config):
        """classDef ui uses the canonical #EDE9FE fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  UI[Dashboard] --> API[API]
  class UI ui
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef ui fill:#EDE9FE" in dsl, (
            f"DSL must contain canonical 'classDef ui fill:#EDE9FE', got: {dsl}"
        )

    def test_build_mermaid_includes_classdef_core_fill_fee2e2(self, mock_config):
        """classDef core uses the canonical #FEE2E2 fill color."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  Core[Orchestrator] --> DB[(DB)]
  class Core core
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef core fill:#FEE2E2" in dsl, (
            f"DSL must contain canonical 'classDef core fill:#FEE2E2', got: {dsl}"
        )


class TestBuildMermaidPurpose:
    """Tests for purpose block extraction in _build_mermaid()."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_build_mermaid_returns_tuple_with_purpose_string(self, mock_config):
        """Returns tuple (dsl, purpose) when LLM includes a purpose block."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
```
```purpose
This diagram shows the top-level architecture of the system.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            result = gen._build_mermaid("components answer", mock_config)

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2 elements, got {len(result)}"
        dsl, purpose = result
        assert isinstance(dsl, str), f"dsl must be str, got {type(dsl)}"
        assert isinstance(purpose, str), f"purpose must be str, got {type(purpose)}"
        assert purpose == "This diagram shows the top-level architecture of the system."

    def test_build_mermaid_purpose_fallback_default_string(self, mock_config):
        """Falls back to default purpose when LLM omits purpose block."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            _dsl, purpose = gen._build_mermaid("components answer", mock_config)

        assert purpose == "This diagram shows the top-level architecture of the system."

    def test_build_mermaid_purpose_normalized_to_single_line(self, mock_config):
        """Purpose from purpose block is normalized to a single line."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
```
```purpose
This diagram shows
the top-level architecture
of the system.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            _dsl, purpose = gen._build_mermaid("components answer", mock_config)

        assert "\n" not in purpose, f"Purpose must be single line, got: {purpose!r}"


class TestStoredContentFormat:
    """Tests for the stored content format in _build_mermaid()."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_stored_content_starts_with_purpose_comment(self, mock_config):
        """The stored content starts with <!-- purpose: --> comment before DSL.

        This is the format stored by store_arch_diagram().
        """
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
```
```purpose
This diagram shows the architecture.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, purpose = gen._build_mermaid("components answer", mock_config)

        stored = f"<!-- purpose: {purpose} -->\n{dsl}"
        import re

        assert re.match(r"<!-- purpose: .+ -->\n---\nconfig:", stored), (
            f"Stored content must match '<!-- purpose: ... -->\n---\nconfig:', got: {stored}"
        )


class TestBuildMermaidBoundaryBehaviors:
    """Boundary behavior tests for _build_mermaid()."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_diagram_empty_components_fallback_no_crash(self, mock_config):
        """LLM returns empty graph → fallback diagram renders without crash."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
```
```purpose
Overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, purpose = gen._build_mermaid("", mock_config)

        assert dsl is not None
        assert purpose is not None
        assert "graph TD" in dsl

    def test_diagram_no_mermaid_block_fallback_no_crash(self, mock_config):
        """LLM returns no mermaid block → fallback graph used without crash."""
        llm_response = MagicMock()
        llm_response.text = "No diagram here at all."
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, purpose = gen._build_mermaid("components answer", mock_config)

        assert dsl is not None
        assert "graph TD" in dsl
        assert "A[System]" in dsl

    def test_diagram_no_purpose_no_crash(self, mock_config):
        """LLM returns mermaid block but no purpose block → fallback purpose used."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System] --> B[Service]
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            _dsl, purpose = gen._build_mermaid("components answer", mock_config)

        assert purpose == "This diagram shows the top-level architecture of the system."
