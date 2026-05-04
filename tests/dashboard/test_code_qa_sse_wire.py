"""Contract tests for the SSE wire format on POST /api/projects/{project_id}/code/qa.

Tests the named-event + base64 format, citation ordering, done/error exclusivity,
and the image attachment stub.
"""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from testcontainers.postgres import PostgresContainer

from dashboard.routers.code_qa import _CitationTracker, _sse_generator
from orch.rag.config import CodeUnderstandingConfig

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def decode_b64(data_payload: str) -> str:
    """Decode a base64 payload from a token event data field."""
    parsed = json.loads(data_payload)
    b64 = parsed["b64"]
    return base64.b64decode(b64.encode("ascii")).decode("utf-8")


class TestTokenEventShape:
    """test_token_event_shape — a short stream with a token containing \\n arrives
    as event: token + valid data: {"b64": "..."}; decoding gives back the exact bytes."""

    @pytest.mark.asyncio
    async def test_token_event_shape(self) -> None:
        """Token with embedded newline arrives as named event with valid b64 payload."""
        tokens = ["hello", "wo\nrld", "fine"]

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                for t in tokens:
                    yield t

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                for t in tokens:
                    yield {"kind": "token", "text": t}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            token_frames = [f for f in frames if f.startswith("event: token")]
            assert len(token_frames) == len(tokens)

            for i, (frame, expected) in enumerate(zip(token_frames, tokens, strict=True)):
                assert frame.startswith("event: token\ndata: ")
                data_part = frame[len("event: token\ndata: ") :]
                decoded = decode_b64(data_part)
                assert decoded == expected, (
                    f"Token {i} round-trip failed: {decoded!r} != {expected!r}"
                )

    @pytest.mark.asyncio
    async def test_done_event_emitted_once(self) -> None:
        """At most one done event is emitted, and the stream ends immediately after."""

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                yield "done"
                yield "## Summary"
                yield "The answer is 42."

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                for t in ("done", "## Summary", "The answer is 42."):
                    yield {"kind": "token", "text": t}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            done_frames = [f for f in frames if f.startswith("event: done")]
            assert len(done_frames) == 1, f"Expected exactly one done frame, got {len(done_frames)}"

            done_idx = frames.index(done_frames[0])
            assert done_idx == len(frames) - 1, "done must be the final event"

    @pytest.mark.asyncio
    async def test_error_event_on_connection_refused(self) -> None:
        """Upstream ConnectionRefusedError yields event: error with a message, no done."""

        class FailingEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                raise ConnectionRefusedError("no ollama")
                yield  # unreachable but makes this an async generator

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                raise ConnectionRefusedError("no ollama")
                yield  # unreachable

        with patch("orch.rag.qa.QAEngine", FailingEngine):
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

            error_frames = [f for f in frames if f.startswith("event: error")]
            assert len(error_frames) == 1, (
                f"Expected exactly one error frame, got {len(error_frames)}"
            )

            done_frames = [f for f in frames if f.startswith("event: done")]
            assert len(done_frames) == 0, "No done event should follow an error"

    @pytest.mark.asyncio
    async def test_citation_event_monotonic_if_any(self) -> None:
        """If citations are emitted, their n values are strictly increasing from 1."""

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                yield "first"
                yield "second"
                yield "third"

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                for t in ("first", "second", "third"):
                    yield {"kind": "token", "text": t}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            citation_frames = [f for f in frames if f.startswith("event: citation")]
            if not citation_frames:
                pytest.skip("No citation events emitted by this engine version")

            n_values: list[int] = []
            for cf in citation_frames:
                data_match = re.search(r"data: (\{.*\})", cf)
                assert data_match, f"Citation frame missing data: {cf}"
                payload = json.loads(data_match.group(1))
                n_values.append(payload["n"])

            assert n_values == list(range(1, len(n_values) + 1)), (
                f"Citation n values must be strictly increasing from 1, got {n_values}"
            )
            assert len(set(n_values)) == len(n_values), "Citation n values must be unique"


class TestTokenEventNewlineAndEncoding:
    """AC3 — tokens containing newlines or multibyte chars survive base64 round-trip."""

    @pytest.mark.asyncio
    async def test_token_event_newline_in_payload(self) -> None:
        """Token with embedded \\n\\n does not corrupt SSE framing."""
        tokens = ["hello", "wo\n\nrld", "fine"]

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                for t in tokens:
                    yield t

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                for t in tokens:
                    yield {"kind": "token", "text": t}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            token_frames = [f for f in frames if f.startswith("event: token")]
            assert len(token_frames) == len(tokens)
            for i, (frame, expected) in enumerate(zip(token_frames, tokens, strict=True)):
                data_part = frame[len("event: token\ndata: ") :]
                decoded = decode_b64(data_part)
                assert decoded == expected, (
                    f"Token {i} round-trip failed: {decoded!r} != {expected!r}"
                )

    @pytest.mark.asyncio
    async def test_utf8_multibyte_token_roundtrip(self) -> None:
        """Tokens with emoji / CJK chars decode back to identical UTF-8."""
        tokens = ["你好世界", "Hello 👋🚀 世界", "日本語", "emoji: 🎉"]

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                for t in tokens:
                    yield t

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                for t in tokens:
                    yield {"kind": "token", "text": t}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            token_frames = [f for f in frames if f.startswith("event: token")]
            assert len(token_frames) == len(tokens)
            for i, (frame, expected) in enumerate(zip(token_frames, tokens, strict=True)):
                data_part = frame[len("event: token\ndata: ") :]
                decoded = decode_b64(data_part)
                assert decoded == expected, (
                    f"Token {i} multibyte round-trip failed: {decoded!r} != {expected!r}"
                )


class TestDoneAndErrorEvents:
    """event: done and event: error semantics."""

    @pytest.mark.asyncio
    async def test_done_event_has_ok_true(self) -> None:
        """done event data payload is {\"ok\": true}."""

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                yield "final token"

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                yield {"kind": "token", "text": "final token"}

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            done_frames = [f for f in frames if f.startswith("event: done")]
            assert len(done_frames) == 1, f"Expected exactly one done frame, got {len(done_frames)}"
            data_part = done_frames[0][len("event: done\ndata: ") :]
            payload = json.loads(data_part)
            assert payload == {"ok": True}

    @pytest.mark.asyncio
    async def test_error_event_on_upstream_connection_refused(self) -> None:
        """Upstream ConnectionRefusedError yields event: error with a message, no done."""
        _ = self  # avoid unused warning

        class FailingEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                raise ConnectionRefusedError("no ollama")
                yield  # unreachable but makes this an async generator

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                raise ConnectionRefusedError("no ollama")
                yield  # unreachable

        with patch("orch.rag.qa.QAEngine", FailingEngine):
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

            error_frames = [f for f in frames if f.startswith("event: error")]
            assert len(error_frames) == 1, (
                f"Expected exactly one error frame, got {len(error_frames)}"
            )

            done_frames = [f for f in frames if f.startswith("event: done")]
            assert len(done_frames) == 0, "No done event should follow an error"


class TestCumulativeCitations:
    """AC7 / AC3 — citations are deduplicated by symbol identity; n strictly increases."""

    @pytest.mark.xfail(
        reason=(
            "Citation emission is not wired in _sse_generator yet. "
            "_CitationTracker is defined but unused; QAEngine.answer_stream "
            "has no citation channel. Tracked for follow-up CR."
        ),
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_cumulative_citations_deduplicated_by_n(self) -> None:
        """Emitting the same citation twice yields one event; n values strictly increase."""

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                yield "first symbol"
                yield "second symbol"
                yield "first symbol"  # duplicate — should not emit a new citation
                yield "third symbol"

        with patch("orch.rag.qa.QAEngine", FakeEngine):
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

            citation_frames = [f for f in frames if f.startswith("event: citation")]
            assert len(citation_frames) == 3, (
                f"Expected 3 citation events, got {len(citation_frames)}"
            )

            n_values: list[int] = []
            for cf in citation_frames:
                data_match = re.search(r"data: (\{.*\})", cf)
                assert data_match, f"Citation frame missing data: {cf}"
                payload = json.loads(data_match.group(1))
                n_values.append(payload["n"])

            assert n_values == [1, 2, 3], f"Citation n values must be [1, 2, 3], got {n_values}"
            assert n_values == list(range(1, len(n_values) + 1))
            assert len(set(n_values)) == len(n_values), "Citation n values must be unique"


class TestImageAttachmentStub:
    """AC13 — multipart image upload returns 501 stub."""

    def test_image_attachment_stub_returns_501_with_detail(self) -> None:
        """POST to /projects/{id}/code/qa-with-image returns 501 with expected detail."""
        from fastapi.testclient import TestClient

        from dashboard.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/projects/test-project/code/qa-with-image",
            files={"file": b"fake-png-bytes"},
        )

        assert response.status_code == 501
        assert response.json()["detail"] == "Image attachments coming soon"


class TestStreamingResponseHeaders:
    """AC3 — SSE response carries required headers to prevent proxy buffering."""

    @pytest.mark.asyncio
    async def test_response_headers_preserved(self) -> None:
        """StreamingResponse has no-cache, no-buffer, keep-alive headers."""
        import tempfile
        from pathlib import Path

        class FakeEngine:
            def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
                del project_id, config

            async def answer_stream(self, **kwargs: object) -> AsyncGenerator[str, None]:
                yield "hello"

            async def answer_stream_v2(
                self, **kwargs: object
            ) -> AsyncGenerator[dict[str, object], None]:
                yield {"kind": "token", "text": "hello"}

        from fastapi.testclient import TestClient

        from dashboard.app import create_app
        from dashboard.dependencies import get_db
        from orch.db.models import Project

        app = create_app()

        with tempfile.TemporaryDirectory() as tmp_dir:
            index_base = Path(tmp_dir)
            (index_base / "test-project" / "vectors").mkdir(parents=True, exist_ok=True)

            with PostgresContainer("postgres:15-alpine") as pg:
                url = pg.get_connection_url().replace(
                    "postgresql+psycopg2://", "postgresql+psycopg://"
                )
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker

                engine = create_engine(url)
                from orch.db.models import Base

                Base.metadata.create_all(engine)
                session_factory = sessionmaker(bind=engine)
                test_db_session = session_factory()

                test_db_session.add(
                    Project(
                        id="test-project",
                        display_name="Test",
                        repo_root="/tmp",  # noqa: S108
                        config={"code_understanding": {"index_path": str(index_base)}},
                    )
                )
                test_db_session.commit()

                def override_get_db():
                    yield test_db_session

                app.dependency_overrides[get_db] = override_get_db
                client = TestClient(app, raise_server_exceptions=False)

                with patch("orch.rag.qa.QAEngine", FakeEngine):
                    response = client.post(
                        "/api/projects/test-project/code/qa",
                        json={
                            "question": "test",
                            "context_level": "architecture",
                        },
                    )

                app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("X-Accel-Buffering") == "no"
        assert response.headers.get("Connection") == "keep-alive"


class TestCitationTracker:
    """Unit tests for _CitationTracker."""

    def test_add_returns_new_index(self) -> None:
        tracker = _CitationTracker()
        assert tracker.add("sym1") == 1
        assert tracker.add("sym2") == 2
        assert tracker.add("sym3") == 3

    def test_add_returns_none_for_duplicates(self) -> None:
        tracker = _CitationTracker()
        assert tracker.add("sym1") == 1
        assert tracker.add("sym1") is None
        assert tracker.add("sym1") is None

    def test_indices_start_at_one(self) -> None:
        tracker = _CitationTracker()
        indices = [tracker.add(f"sym{i}") for i in range(5)]
        assert indices == [1, 2, 3, 4, 5]
