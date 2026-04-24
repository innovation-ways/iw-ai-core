"""End-to-end contract tests for the E2E Ollama stub.

Regression guards for F-00060 S14 browser-verification. The stub must speak
the exact response shapes the pinned `llama_index.llms.ollama.Ollama` and
`llama_index.embeddings.ollama.OllamaEmbedding` clients parse — otherwise
every Q&A call fails silently (the exception is swallowed into the thread
executor's Future) and the SSE stream terminates at `event: done` with zero
content tokens.

These tests boot the stub on an ephemeral port and exercise both clients the
way `orch/rag/qa.py:answer_stream` does, so the moment the stub drifts from
the llama_index contract the test fails — not the browser verification.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

STUB_PATH = Path(__file__).resolve().parents[2] / "scripts" / "e2e_ollama_stub.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/tags", timeout=0.5)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"stub at {base_url} did not start within {timeout}s")


@pytest.fixture
def stub() -> Iterator[str]:
    port = _free_port()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(STUB_PATH), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_ready(base)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class TestStubEmbeddingShape:
    def test_scalar_input_is_parseable_by_llama_index(self, stub: str) -> None:
        """`OllamaEmbedding.get_query_embedding(str)` must return a single vector.

        The llama_index client wraps the server response in pydantic's
        `EmbedResponse` which requires `embeddings: list[list[float]]`. The
        stub must emit that shape even for scalar input — returning
        `{"embedding": [...]}` (singular) raises ValidationError and hangs
        the whole Q&A stream.
        """
        from llama_index.embeddings.ollama import OllamaEmbedding

        emb = OllamaEmbedding(model_name="stub:latest", base_url=stub)
        v = emb.get_query_embedding("hello world")
        assert isinstance(v, list)
        assert len(v) == 768
        assert all(isinstance(f, float) for f in v[:3])

    def test_batch_input_returns_one_vector_per_text(self, stub: str) -> None:
        """A list of N inputs must yield N distinct vectors."""
        from llama_index.embeddings.ollama import OllamaEmbedding

        emb = OllamaEmbedding(model_name="stub:latest", base_url=stub)
        vs = emb.get_text_embedding_batch(["hi", "there", "friend"])
        assert len(vs) == 3
        assert len(vs[0]) == 768
        assert vs[0] != vs[1], "distinct inputs must yield distinct embeddings"


class TestStubChatShape:
    def test_show_endpoint_satisfies_llama_index_context_probe(
        self,
        stub: str,
    ) -> None:
        """`Ollama.get_context_window` calls `/api/show` before streaming chat.

        The Ollama Python client parses the response as `ShowResponse`, which
        requires the `model_info` alias (not `modelinfo`). The stub must emit
        `{"model_info": {...}}` or the first chat call raises a pydantic
        ValidationError from inside `_model_kwargs` — before a single byte
        of `/api/chat` is ever sent.
        """
        from ollama import Client

        client = Client(host=stub)
        resp = client.show("stub:latest")
        # Accessing .modelinfo on the pydantic model is what llama_index does.
        assert resp.modelinfo is not None
        assert any("context_length" in key for key in resp.modelinfo), (
            "/api/show must expose a context_length key so llama_index can "
            "set num_ctx on the chat request"
        )

    def test_chat_stream_emits_tokens_via_llama_index(self, stub: str) -> None:
        """End-to-end: llama_index streams real content tokens from the stub."""
        from llama_index.core.llms import ChatMessage
        from llama_index.llms.ollama import Ollama

        async def run() -> list[str]:
            llm = Ollama(model="stub:latest", base_url=stub)
            stream = await llm.astream_chat(
                [ChatMessage(role="user", content="hi")],
            )
            tokens: list[str] = []
            async for chunk in stream:
                tokens.append(chunk.delta)
            return tokens

        tokens = asyncio.run(run())
        assert len(tokens) > 0, (
            "Chat stream returned zero tokens. Either /api/show, /api/chat, "
            "or the NDJSON framing in scripts/e2e_ollama_stub.py has drifted "
            "from the llama_index contract — re-sync it before shipping."
        )
        joined = "".join(tokens)
        assert "deterministic stub response" in joined, (
            f"Expected deterministic stub text in reply; got: {joined!r}"
        )
