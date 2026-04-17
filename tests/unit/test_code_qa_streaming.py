"""Unit tests for the non-buffering SSE bridge in dashboard/routers/code_qa.py.

Tests prove that `_sse_generator` yields SSE frames as tokens are produced,
not after all tokens are produced (the buffering bug).

Uses pytest-asyncio for async test support.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from dashboard.routers.code_qa import _sse_generator
from orch.rag.config import CodeUnderstandingConfig

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class FakeAnswerStream:
    """Async generator yielding tokens with a configurable delay between each."""

    def __init__(self, delay_s: float = 0.1, tokens: list[str] | None = None) -> None:
        self.delay_s = delay_s
        self.tokens = tokens or ["a ", "b ", "c ", "d ", "e"]

    async def __call__(self, **kwargs: object) -> AsyncGenerator[str, None]:
        for tok in self.tokens:
            await asyncio.sleep(self.delay_s)
            yield tok


@pytest.mark.asyncio
async def test_sse_generator_streams_tokens_live() -> None:
    """First token must arrive well before the last — proves no end-to-end buffering."""
    fake_stream = FakeAnswerStream(delay_s=0.1)

    class FakeEngine:
        def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
            del project_id, config

        async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
            async for t in fake_stream(**kwargs):
                yield t

    with patch("orch.rag.qa.QAEngine", FakeEngine):
        cfg = CodeUnderstandingConfig()
        timestamps: list[tuple[float, str]] = []

        async for frame in _sse_generator(
            project_id="P1",
            question="q",
            context_level="architecture",
            context_doc_id=None,
            module_path=None,
            conversation_history=[],
            db_session=None,
            config=cfg,
        ):
            timestamps.append((time.monotonic(), frame))

    assert len(timestamps) == 6
    token_frames = [frame for _t, frame in timestamps if '"token"' in frame]
    assert len(token_frames) == 5

    first_ts = timestamps[0][0]
    last_token_ts = timestamps[4][0]
    assert last_token_ts - first_ts >= 0.3, (
        f"Expected last token >= 0.3s after first, got {last_token_ts - first_ts:.3f}s. "
        "This suggests buffering — tokens should arrive incrementally."
    )


@pytest.mark.asyncio
async def test_sse_generator_handles_connection_error() -> None:
    """When QAEngine raises ConnectionRefusedError, an error event is yielded."""

    class FailingEngine:
        def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
            del project_id, config

        async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
            raise ConnectionRefusedError("no ollama")
            yield

    with patch("orch.rag.qa.QAEngine", FailingEngine):
        frames: list[str] = []
        async for f in _sse_generator(
            project_id="P1",
            question="q",
            context_level="architecture",
            context_doc_id=None,
            module_path=None,
            conversation_history=[],
            db_session=None,
            config=CodeUnderstandingConfig(),
        ):
            frames.append(f)

    assert any('"event"' in f and "error" in f for f in frames), (
        f"Expected error event in frames, got: {frames}"
    )
    assert any("Local AI unavailable" in f for f in frames), (
        f"Expected 'Local AI unavailable' message in frames, got: {frames}"
    )
