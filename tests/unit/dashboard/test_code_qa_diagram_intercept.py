"""Unit tests for diagram block detection and SSE image-event emission in code_qa."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from dashboard.routers.code_qa import _find_new_diagram_blocks, _sse_generator
from orch.rag.config import CodeUnderstandingConfig

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class TestFindNewDiagramBlocks:
    """Tests for _find_new_diagram_blocks."""

    def test_find_new_blocks_detects_mermaid(self) -> None:
        """Complete mermaid fence is detected and returned as (lang, dsl) tuple."""
        text = "```mermaid\ngraph TD\n  A --> B\n```"
        processed: set[tuple[str, str]] = set()
        result = _find_new_diagram_blocks(text, processed)
        assert result == [("mermaid", "graph TD\n  A --> B")]

    def test_find_new_blocks_ignores_partial_block(self) -> None:
        """Mermaid block without closing fence returns empty list."""
        text = "```mermaid\ngraph TD\n  A --> B\n"
        processed: set[tuple[str, str]] = set()
        result = _find_new_diagram_blocks(text, processed)
        assert result == []

    def test_find_new_blocks_deduplicates(self) -> None:
        """Already-processed block is not returned again."""
        text = "```mermaid\ngraph TD\n  A --> B\n```"
        dsl = "graph TD\n  A --> B"
        processed: set[tuple[str, str]] = {("mermaid", dsl)}
        result = _find_new_diagram_blocks(text, processed)
        assert result == []

    def test_find_new_blocks_detects_d2(self) -> None:
        """Complete d2 fence is detected and returned as (lang, dsl) tuple."""
        text = "```d2\nA -> B: uses\n```"
        processed: set[tuple[str, str]] = set()
        result = _find_new_diagram_blocks(text, processed)
        assert result == [("d2", "A -> B: uses")]

    def test_find_new_blocks_detects_multiple(self) -> None:
        """Two separate mermaid blocks are both detected."""
        text = (
            "```mermaid\ngraph TD\n  A --> B\n```\n\n"
            "Some text\n\n"
            "```mermaid\ngraph LR\n  X --> Y\n```"
        )
        processed: set[tuple[str, str]] = set()
        result = _find_new_diagram_blocks(text, processed)
        assert len(result) == 2
        assert result[0] == ("mermaid", "graph TD\n  A --> B")
        assert result[1] == ("mermaid", "graph LR\n  X --> Y")

    def test_find_new_blocks_never_raises(self) -> None:
        """Passing None as text returns [] instead of raising."""
        processed: set[tuple[str, str]] = set()
        result = _find_new_diagram_blocks(None, processed)
        assert result == []


class TestSseGeneratorDiagramEmission:
    """Tests for image event emission in _sse_generator."""

    @pytest.mark.asyncio
    async def test_sse_generator_emits_image_event_when_render_succeeds(
        self,
    ) -> None:
        """When a complete mermaid block arrives and render succeeds, event: image is yielded."""
        tokens = ["```mermaid\n", "graph TD\n", "  A --> B\n", "```"]

        async def fake_answer_stream_v2(
            **kwargs: object,
        ) -> AsyncGenerator[dict[str, object], None]:
            for t in tokens:
                yield {"kind": "token", "text": t}

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                async for item in fake_answer_stream_v2(**kwargs):
                    yield item

        rendered_svg = "<svg>test</svg>"

        def fake_session_factory() -> object:
            return None

        with (
            patch(
                "dashboard.routers.code_qa.render_mermaid",
                return_value=rendered_svg,
            ),
            patch("dashboard.routers.code_qa._DIAGRAM_RENDER_AVAILABLE", True),
            patch("orch.rag.qa.QAEngine", FakeEngine),
        ):
            frames: list[str] = []
            async for frame in _sse_generator(
                project_id="P1",
                question="q",
                context_level="architecture",
                context_doc_id=None,
                module_path=None,
                module_name=None,
                conversation_id="test-conv-id",
                session_factory=fake_session_factory,
                config=CodeUnderstandingConfig(),
            ):
                frames.append(frame)

            full_output = "".join(frames)
            assert "event: image" in full_output, (
                f"Expected 'event: image' in output, got: {full_output}"
            )

            img_frames = [f for f in frames if f.startswith("event: image")]
            assert len(img_frames) == 1, f"Expected 1 image frame, got {len(img_frames)}"

            data_match = img_frames[0].split("data: ", 1)[1]
            payload = json.loads(data_match.strip())

            svg_b64 = payload.get("svg_b64", "")
            decoded_svg = base64.b64decode(svg_b64.encode("ascii")).decode("utf-8")
            assert decoded_svg == rendered_svg, (
                f"Expected SVG {rendered_svg!r}, got {decoded_svg!r}"
            )

            assert payload.get("source_type") == "mermaid"
            assert payload.get("block_index") == 0

    @pytest.mark.asyncio
    async def test_sse_generator_no_image_event_when_render_returns_none(
        self,
    ) -> None:
        """When render returns None, no image event is emitted."""
        tokens = ["```mermaid\n", "graph TD\n", "  A --> B\n", "```"]

        async def fake_answer_stream_v2(
            **kwargs: object,
        ) -> AsyncGenerator[dict[str, object], None]:
            for t in tokens:
                yield {"kind": "token", "text": t}

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                async for item in fake_answer_stream_v2(**kwargs):
                    yield item

        with (
            patch(
                "dashboard.routers.code_qa.render_mermaid",
                return_value=None,
            ),
            patch("dashboard.routers.code_qa._DIAGRAM_RENDER_AVAILABLE", True),
            patch("orch.rag.qa.QAEngine", FakeEngine),
        ):
            frames: list[str] = []
            async for frame in _sse_generator(
                project_id="P1",
                question="q",
                context_level="architecture",
                context_doc_id=None,
                module_path=None,
                module_name=None,
                conversation_id="test-conv-id",
                session_factory=lambda: None,
                config=CodeUnderstandingConfig(),
            ):
                frames.append(frame)

            full_output = "".join(frames)
            assert "event: image" not in full_output, (
                f"Did not expect 'event: image' when render returns None, got: {full_output}"
            )

    @pytest.mark.asyncio
    async def test_sse_generator_no_image_event_when_render_unavailable(
        self,
    ) -> None:
        """When _DIAGRAM_RENDER_AVAILABLE is False, no image event is emitted."""
        tokens = ["```mermaid\n", "graph TD\n", "  A --> B\n", "```"]

        async def fake_answer_stream_v2(
            **kwargs: object,
        ) -> AsyncGenerator[dict[str, object], None]:
            for t in tokens:
                yield {"kind": "token", "text": t}

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                async for item in fake_answer_stream_v2(**kwargs):
                    yield item

        with (
            patch("dashboard.routers.code_qa._DIAGRAM_RENDER_AVAILABLE", False),
            patch("orch.rag.qa.QAEngine", FakeEngine),
        ):
            frames: list[str] = []
            async for frame in _sse_generator(
                project_id="P1",
                question="q",
                context_level="architecture",
                context_doc_id=None,
                module_path=None,
                module_name=None,
                conversation_id="test-conv-id",
                session_factory=lambda: None,
                config=CodeUnderstandingConfig(),
            ):
                frames.append(frame)

            full_output = "".join(frames)
            assert "event: image" not in full_output, (
                f"Did not expect 'event: image' when render unavailable, got: {full_output}"
            )
