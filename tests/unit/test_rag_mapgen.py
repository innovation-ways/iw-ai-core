"""Unit tests for orch.rag.mapgen — _build_mermaid enhancements."""

from unittest.mock import MagicMock, patch

import pytest

from orch.rag.mapgen import MapGenerator


class TestBuildMermaid:
    """Tests for MapGenerator._build_mermaid() — semantic color and purpose extraction."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_build_mermaid_returns_tuple(self, mock_config):
        """_build_mermaid must return a (dsl, purpose) tuple."""
        llm_response = MagicMock()
        llm_response.text = """\
Here is the diagram:

```mermaid
graph TD
  A[iw CLI] --> B[Daemon]
  B --> C[(DB)]
  class A api
  class B core
  class C data
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

    def test_build_mermaid_extracts_purpose_from_purpose_block(self, mock_config):
        """Purpose paragraph is extracted from ```purpose block and normalized to single line."""
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
        assert purpose == "This diagram shows the top-level architecture of the system."

    def test_build_mermaid_fallback_purpose(self, mock_config):
        """When no purpose block is found, fallback purpose is used."""
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

    def test_build_mermaid_includes_classdef_api(self, mock_config):
        """Generated DSL contains classDef with api class for API/CLI entry points."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  CLI[iw CLI] --> Daemon[Daemon]
  class CLI api
```
```purpose
Architecture overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef api" in dsl, f"DSL must contain 'classDef api', got: {dsl}"

    def test_build_mermaid_includes_classdef_data(self, mock_config):
        """Generated DSL contains classDef with data class for DB/storage components."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  DB[(PostgreSQL)] --> Worker[Worker]
  class DB data
```
```purpose
Architecture overview.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        assert "classDef data" in dsl, f"DSL must contain 'classDef data', got: {dsl}"

    def test_build_mermaid_includes_all_classdef_entries(self, mock_config):
        """Generated DSL contains all 6 classDef color classes."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[API]:::api --> B[DB]:::data
  B --> C[Worker]:::worker
  C --> D[External]:::external
  D --> E[UI]:::ui
  E --> F[Core]:::core
```
```purpose
Full architecture.
```
"""
        gen = MapGenerator()
        with patch("orch.rag.mapgen.Ollama") as mock_ollama:
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            dsl, _purpose = gen._build_mermaid("components answer", mock_config)

        for cls in ["api", "data", "worker", "external", "ui", "core"]:
            assert f"classDef {cls}" in dsl, f"DSL must contain 'classDef {cls}', got: {dsl}"

    def test_build_mermaid_elk_frontmatter_preserved(self, mock_config):
        """Existing elk frontmatter injection logic is preserved."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
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

        assert "layout: elk" in dsl, f"DSL must contain 'layout: elk', got: {dsl}"

    def test_build_mermaid_fallback_graph(self, mock_config):
        """When no mermaid block is found, fallback graph is used."""
        llm_response = MagicMock()
        llm_response.text = """\
No diagram here.
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

        assert "graph TD" in dsl
        assert "A[System]" in dsl


class TestBuildMermaidPrompt:
    """Tests for the LLM prompt enhancement in _build_mermaid."""

    @pytest.fixture
    def mock_config(self):
        """Provide mock config for tests."""
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        return config

    def test_prompt_contains_classdef_instructions(self, mock_config):
        """Prompt includes classDef block instructions for semantic colors."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
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

            gen._build_mermaid("components answer", mock_config)

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "classDef api" in prompt, "Prompt must include classDef api instruction"
            assert "classDef data" in prompt, "Prompt must include classDef data instruction"
            assert "classDef worker" in prompt, "Prompt must include classDef worker instruction"
            assert "classDef external" in prompt, (
                "Prompt must include classDef external instruction"
            )
            assert "classDef ui" in prompt, "Prompt must include classDef ui instruction"
            assert "classDef core" in prompt, "Prompt must include classDef core instruction"

    def test_prompt_contains_abstraction_level_instruction(self, mock_config):
        """Prompt includes instruction to show only high-level architectural components."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
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

            gen._build_mermaid("components answer", mock_config)

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "abstraction" in prompt.lower() or "high-level" in prompt.lower(), (
                "Prompt must include abstraction-level instruction"
            )

    def test_prompt_contains_why_instruction(self, mock_config):
        """Prompt instructs to output a purpose block after the diagram."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
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

            gen._build_mermaid("components answer", mock_config)

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "purpose" in prompt.lower(), "Prompt must include purpose block instruction"

    def test_prompt_contains_class_assignment_rules(self, mock_config):
        """Prompt includes rules for which components get which class."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph TD
  A[System]
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

            gen._build_mermaid("components answer", mock_config)

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "API" in prompt or "router" in prompt.lower(), (
                "Prompt must include API/router entry point guidance"
            )
            assert "database" in prompt.lower() or "repository" in prompt.lower(), (
                "Prompt must include database/repository guidance"
            )
            assert "worker" in prompt.lower() or "background" in prompt.lower(), (
                "Prompt must include worker/background job guidance"
            )
