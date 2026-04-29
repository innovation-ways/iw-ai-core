"""Unit tests for QAEngine system prompt blocks."""

from __future__ import annotations

from orch.rag.qa import QAEngine


class TestRenderingCapabilitiesBlock:
    """Tests for RENDERING_CAPABILITIES_BLOCK content."""

    def test_rendering_capabilities_includes_callout_note(self) -> None:
        assert "[!NOTE]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

    def test_rendering_capabilities_includes_callout_warning(self) -> None:
        assert "[!WARNING]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

    def test_rendering_capabilities_includes_callout_danger(self) -> None:
        assert "[!DANGER]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

    def test_rendering_capabilities_includes_structure_guidance(self) -> None:
        block = QAEngine.RENDERING_CAPABILITIES_BLOCK
        assert "H2" in block or "heading" in block.lower()

    def test_rendering_capabilities_includes_list_guidance(self) -> None:
        block = QAEngine.RENDERING_CAPABILITIES_BLOCK
        assert "bullet" in block.lower() or "list" in block.lower()

    def test_build_system_prompt_includes_capabilities_block(self) -> None:
        engine = QAEngine.__new__(QAEngine)
        prompt = engine._build_system_prompt(
            context_doc_content="ctx",
            chunks=[],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=None,
        )
        assert "[!WARNING]" in prompt

    def test_rendering_capabilities_preserves_mermaid_mention(self) -> None:
        assert "mermaid" in QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()

    def test_rendering_capabilities_preserves_d2_mention(self) -> None:
        assert "d2" in QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()

    def test_unknown_callout_type_not_in_block(self) -> None:
        block = QAEngine.RENDERING_CAPABILITIES_BLOCK
        assert "[!CUSTOM]" not in block
        assert "[!EXTRA]" not in block

    def test_capabilities_block_does_not_suggest_every_answer_needs_heading(self) -> None:
        block = QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()
        assert "not" in block or "only" in block
