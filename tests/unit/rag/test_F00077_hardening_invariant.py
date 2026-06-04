"""Unit tests for F-00077 — hardening lines on every system prompt (Invariant 8).

Per Invariant 8: the hardening lines must appear on every system prompt
produced by qa.py. This tests all paths:
1. _build_system_prompt(context_level="architecture", ...)
2. _build_system_prompt(context_level="module", ...)
3. The work-item-aware system prompt assembled via workitem_section
"""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.rag.qa import (
    SYSTEM_PROMPT_HARDENING,
    QAEngine,
)


class TestHardeningInvariant:
    """Invariant 8: SYSTEM_PROMPT_HARDENING appears on every system prompt."""

    def test_architecture_context_system_prompt_has_hardening(self) -> None:
        """_build_system_prompt with architecture context includes hardening lines."""
        config = MagicMock()
        engine = QAEngine(project_id="test-project", config=config)

        prompt = engine._build_system_prompt(
            context_doc_content="## Architecture\nTest architecture doc.",
            chunks=["// code snippet here"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=None,
            workitem_section="",
        )

        assert SYSTEM_PROMPT_HARDENING in prompt, (
            "HARDENING lines must appear in architecture system prompt."
        )

    def test_module_context_system_prompt_has_hardening(self) -> None:
        """_build_system_prompt with module context includes hardening lines."""
        config = MagicMock()
        engine = QAEngine(project_id="test-project", config=config)

        prompt = engine._build_system_prompt(
            context_doc_content="## Module\nTest module doc.",
            chunks=["// module code"],
            module_path="orch/daemon/main.py",
            module_name="DaemonMain",
            fallback_triggered=False,
            context_chips=None,
            workitem_section="",
        )

        assert SYSTEM_PROMPT_HARDENING in prompt, (
            "HARDENING lines must appear in module system prompt."
        )

    def test_workitem_section_system_prompt_has_hardening(self) -> None:
        """_build_system_prompt with workitem_section includes hardening lines."""
        config = MagicMock()
        engine = QAEngine(project_id="test-project", config=config)

        workitem_section = (
            "## Work Item Context\n\n"
            "F-00077 — Chat memory persistence with query rewriting.\n\n"
            "The user is investigating the daemon loop."
        )

        prompt = engine._build_system_prompt(
            context_doc_content="## Architecture\nTest.",
            chunks=["// code"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=None,
            workitem_section=workitem_section,
        )

        assert SYSTEM_PROMPT_HARDENING in prompt, (
            "HARDENING lines must appear in workitem-aware system prompt."
        )

    def test_hardening_not_duplicated(self) -> None:
        """SYSTEM_PROMPT_HARDENING appears exactly once per system prompt."""
        config = MagicMock()
        engine = QAEngine(project_id="test-project", config=config)

        prompt = engine._build_system_prompt(
            context_doc_content="## Architecture\nTest.",
            chunks=["// code"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=None,
            workitem_section="",
        )

        count = prompt.count(SYSTEM_PROMPT_HARDENING)
        assert count == 1, f"SYSTEM_PROMPT_HARDENING should appear exactly once, found {count}."

    def test_hardening_preserved_with_rendering_capabilities(self) -> None:
        """Hardening appears alongside RENDERING_CAPABILITIES_BLOCK, after it."""
        config = MagicMock()
        engine = QAEngine(project_id="test-project", config=config)

        prompt = engine._build_system_prompt(
            context_doc_content="## Architecture\nTest.",
            chunks=["// code"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=["diagram"],
            workitem_section="",
        )

        assert SYSTEM_PROMPT_HARDENING in prompt
        assert engine.RENDERING_CAPABILITIES_BLOCK in prompt
        # Hardening should come AFTER rendering capabilities
        hardening_pos = prompt.rfind(SYSTEM_PROMPT_HARDENING)
        rendering_pos = prompt.rfind(engine.RENDERING_CAPABILITIES_BLOCK)
        assert hardening_pos > rendering_pos, (
            "Hardening should appear after RENDERING_CAPABILITIES_BLOCK"
        )
