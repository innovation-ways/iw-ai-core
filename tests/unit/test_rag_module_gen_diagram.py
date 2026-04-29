"""Unit tests for ModuleGenerator._generate_and_store_module_diagram() prompt enhancements.

Verifies the prompt contains the specific instruction strings: graph LR direction,
classDef palette, and structural-elements-only instruction.
"""

from unittest.mock import MagicMock, patch

import pytest

from orch.rag.module_gen import ModuleGenerator


class TestModuleDiagramPromptContent:
    """Tests that the module diagram prompt contains required instructions."""

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

    def test_module_diagram_prompt_uses_lr_direction(self, mock_config, mock_session):
        """Module diagram prompt specifies LR (left-to-right) direction."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "graph LR" in prompt, (
                f"Prompt must specify 'graph LR' (left-to-right), got: {prompt[:200]}"
            )

    def test_module_diagram_prompt_contains_classdef_api(self, mock_config, mock_session):
        """classDef api palette instruction is in the module diagram prompt."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "classDef api" in prompt, (
                f"Prompt must include 'classDef api' instruction, got: {prompt[:300]}"
            )

    def test_module_diagram_prompt_contains_classdef_data(self, mock_config, mock_session):
        """classDef data palette instruction is in the module diagram prompt."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "classDef data" in prompt, (
                f"Prompt must include 'classDef data' instruction, got: {prompt[:300]}"
            )

    def test_module_diagram_prompt_structural_only_instruction_do_not_show(
        self, mock_config, mock_session
    ):
        """Prompt instructs LLM to exclude utilities/DTOs/config via Do NOT show."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "Do NOT show" in prompt or "do NOT show" in prompt, (
                f"Prompt must contain 'Do NOT show' for utility exclusion, got: {prompt[:300]}"
            )
            assert "utility" in prompt.lower(), (
                f"Prompt must mention 'utility' classes exclusion, got: {prompt[:300]}"
            )

    def test_module_diagram_prompt_maximum_12_nodes(self, mock_config, mock_session):
        """Prompt instructs maximum 12 nodes."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "12 nodes" in prompt or "12" in prompt, (
                f"Prompt must instruct maximum 12 nodes, got: {prompt[:300]}"
            )

    def test_module_diagram_prompt_elk_frontmatter_required(self, mock_config, mock_session):
        """Prompt requires YAML frontmatter with elk layout."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "layout: elk" in prompt, (
                f"Prompt must require 'layout: elk' in frontmatter, got: {prompt[:300]}"
            )

    def test_module_diagram_prompt_purpose_block_instruction(self, mock_config, mock_session):
        """Prompt instructs LLM to output a purpose block after the diagram."""
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

            call_args = mock_llm_instance.complete.call_args
            prompt = call_args[0][0]

            assert "```purpose" in prompt, (
                f"Prompt must instruct to output ```purpose block, got: {prompt[:300]}"
            )


class TestModuleDiagramStoredContent:
    """Tests for the stored content format in _generate_and_store_module_diagram()."""

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

    def test_stored_content_starts_with_purpose_comment(self, mock_config, mock_session):
        """Stored content starts with <!-- purpose: --> comment before DSL."""
        llm_response = MagicMock()
        llm_response.text = """\
```mermaid
graph LR
  A[Controller] --> B[Service]
```
```purpose
This diagram shows the internal structure.
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

            assert content.startswith("<!-- purpose:"), (
                f"Content must start with '<!-- purpose:', got: {content[:50]}"
            )
            import re

            assert re.match(r"<!-- purpose: .+ -->\n", content), (
                f"Content must have '<!-- purpose: ... -->\n' format, got: {content[:60]}"
            )
