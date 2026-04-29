"""Unit tests for orch.rag.module_gen — _generate_and_store_module_diagram enhancements."""

from unittest.mock import MagicMock, patch

import pytest

from orch.rag.module_gen import ModuleGenerator


class TestGenerateModuleDiagram:
    """Tests for module diagram generation with semantic colors and purpose."""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/index"
        return config

    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def test_generates_and_stores_returns_tuple(self, mock_config, mock_session):
        """_generate_and_store_module_diagram processes response to extract purpose."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller] --> B[Service]
  B --> C[(Repo)]
  class A api
  class B core
  class C data
```
```purpose
This diagram shows the internal component structure of the orch.rag module.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-project-module-orch-rag"),
            patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance
            mock_doc_service = MagicMock()
            mock_doc_service_cls.return_value = mock_doc_service
            mock_doc_service.get_doc.return_value = None

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["context chunk 1", "context chunk 2"],
                )
            )

    def test_purpose_extracted_and_normalized_to_single_line(self, mock_config, mock_session):
        """Purpose is extracted from purpose block and normalized to a single line."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
This diagram shows the internal
component structure of the module.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance
            mock_doc_service = MagicMock()
            mock_doc_service_cls.return_value = mock_doc_service
            mock_doc_service.get_doc.return_value = None

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            create_call = mock_doc_service.create_doc.call_args
            content = create_call[1]["content"]
            purpose_match = content.split("---")[0] if "---" in content else ""
            assert "purpose:" in purpose_match, f"Purpose comment missing, got: {content[:200]}"
            assert "\n" not in purpose_match or purpose_match.count("\n") <= 1, (
                f"Purpose should be single line, got: {purpose_match!r}"
            )

    def test_fallback_purpose_uses_module_name(self, mock_config, mock_session):
        """When no purpose block found, fallback uses the module name."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance
            mock_doc_service = MagicMock()
            mock_doc_service_cls.return_value = mock_doc_service
            mock_doc_service.get_doc.return_value = None

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            create_call = mock_doc_service.create_doc.call_args
            content = create_call[1]["content"]
            assert "purpose:" in content, f"Purpose comment missing, got: {content[:200]}"
            assert "orch.rag" in content, "Module name should be in fallback purpose"

    def test_classdef_api_included_in_dsl(self, mock_config, mock_session):
        """DSL contains classDef api for API/CLI entry points."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Router] --> B[Service]
  class A api
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance
            mock_doc_service = MagicMock()
            mock_doc_service_cls.return_value = mock_doc_service
            mock_doc_service.get_doc.return_value = None

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            create_call = mock_doc_service.create_doc.call_args
            content = create_call[1]["content"]
            assert "classDef api" in content, f"DSL must contain classDef api, got: {content}"

    def test_all_six_classdef_entries_present(self, mock_config, mock_session):
        """DSL contains all 6 classDef entries."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Router]:::api --> B[Service]:::core
  B --> C[(DB)]:::data
  C --> D[Worker]:::worker
  D --> E[External]:::external
  E --> F[UI]:::ui
```
```purpose
Full module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance
            mock_doc_service = MagicMock()
            mock_doc_service_cls.return_value = mock_doc_service
            mock_doc_service.get_doc.return_value = None

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            create_call = mock_doc_service.create_doc.call_args
            content = create_call[1]["content"]

            for cls in ["api", "data", "worker", "external", "ui", "core"]:
                assert f"classDef {cls}" in content, (
                    f"DSL must contain 'classDef {cls}', got: {content}"
                )


class TestModuleDiagramPrompt:
    """Tests for the LLM prompt enhancement in _generate_and_store_module_diagram."""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/index"
        return config

    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def test_prompt_uses_left_to_right_direction(self, mock_config, mock_session):
        """Module diagram uses LR (left-to-right) direction instead of TD."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "graph LR" in prompt or "LR" in prompt, (
                "Prompt must specify LR (left-to-right) direction"
            )

    def test_prompt_contains_classdef_instructions(self, mock_config, mock_session):
        """Prompt includes classDef block instructions for semantic colors."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "classDef api" in prompt, "Prompt must include classDef api instruction"
            assert "classDef data" in prompt, "Prompt must include classDef data instruction"
            assert "classDef worker" in prompt, "Prompt must include classDef worker instruction"

    def test_prompt_contains_structural_elements_only_instruction(self, mock_config, mock_session):
        """Prompt instructs to show only structural elements, not utilities/DTOs."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            structural_keywords = ["controller", "service", "repository", "adapter", "domain"]
            has_structural = any(kw in prompt.lower() for kw in structural_keywords)
            assert has_structural, "Prompt must include structural element guidance"

    def test_prompt_contains_why_instruction(self, mock_config, mock_session):
        """Prompt instructs to output a purpose block after the diagram."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "purpose" in prompt.lower(), "Prompt must include purpose block instruction"

    def test_prompt_contains_class_assignment_rules(self, mock_config, mock_session):
        """Prompt includes rules for which components get which class."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller]
```
```purpose
Module structure.
```
"""
        gen = ModuleGenerator()
        with (
            patch("orch.rag.module_gen.Ollama") as mock_ollama,
            patch.object(gen, "_make_slug", return_value="test-slug"),
            patch("orch.rag.module_gen.DocService"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm_instance.complete.return_value = llm_response
            mock_ollama.return_value = mock_llm_instance

            import asyncio

            asyncio.run(
                gen._generate_and_store_module_diagram(
                    project_id="test-project",
                    module_path="orch/rag",
                    module_name="orch.rag",
                    config=mock_config,
                    session=mock_session,
                    retrieved_nodes=["chunk1"],
                )
            )

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "database" in prompt.lower() or "repository" in prompt.lower(), (
                "Prompt must include database/repository guidance"
            )
            assert "worker" in prompt.lower() or "background" in prompt.lower(), (
                "Prompt must include worker/background job guidance"
            )
