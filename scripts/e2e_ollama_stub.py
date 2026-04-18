"""Minimal Ollama API stub for E2E browser verification.

Implements the subset of endpoints the dashboard/RAG layer calls via
llama_index's Ollama + OllamaEmbedding clients:

  GET  /              → "Ollama is running" (llama_index health probe)
  POST /api/embeddings → fake deterministic 768-dim vector
  POST /api/embed      → same (newer endpoint name)
  POST /api/chat       → NDJSON stream; echoes the module reference
                         extracted from the system prompt so V3 can assert
  POST /api/generate   → NDJSON stream; mirrors /api/chat output shape

Run with:  uv run python scripts/e2e_ollama_stub.py --port 11434

No external dependencies beyond the project's existing FastAPI + uvicorn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

EMBED_DIM = 768
MODULE_BACKTICK_RE = re.compile(r"`([A-Za-z_][\w./-]+)`\s+module")

app = FastAPI(title="ollama-stub", version="0.1")


def _fake_embedding(text: str) -> list[float]:
    """Return a deterministic pseudo-random 768-dim unit vector derived from text."""
    seed = hashlib.sha256(text.encode()).digest()
    floats: list[float] = []
    i = 0
    while len(floats) < EMBED_DIM:
        byte = seed[i % len(seed)]
        # Map 0..255 → -1..1
        floats.append((byte / 127.5) - 1.0)
        i += 1
    # Normalise to unit length (not strictly required but closer to real embeddings)
    norm = sum(v * v for v in floats) ** 0.5 or 1.0
    return [v / norm for v in floats]


def _extract_module_ref(messages: list[dict[str, Any]]) -> str | None:
    """Find the first backtick-quoted module path in the system message.

    qa._build_system_prompt emits strings like:
        The user is currently viewing the `orch/daemon` module ("Orchestration Daemon").
    """
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content", "")
        m = MODULE_BACKTICK_RE.search(content)
        if m:
            return m.group(1)
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_reply(module_ref: str | None, question: str) -> str:
    if module_ref:
        return (
            f"The `{module_ref}` module handles its slice of the system. "
            f"Based on the excerpts above, it coordinates the behaviour "
            f"asked about in: {question!r}. "
            "This is a deterministic stub response for E2E verification."
        )
    return (
        "This is a deterministic stub response for E2E verification — "
        f"question received: {question!r}."
    )


async def _stream_chat(model: str, reply: str) -> AsyncGenerator[bytes, None]:
    """Emit Ollama-style NDJSON lines, one token per space-delimited word."""
    tokens = reply.split(" ")
    for i, tok in enumerate(tokens):
        piece = tok if i == 0 else " " + tok
        line = {
            "model": model,
            "created_at": _now(),
            "message": {"role": "assistant", "content": piece},
            "done": False,
        }
        yield (json.dumps(line) + "\n").encode()
    final = {
        "model": model,
        "created_at": _now(),
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "total_duration": 1,
        "done_reason": "stop",
    }
    yield (json.dumps(final) + "\n").encode()


async def _stream_generate(model: str, reply: str) -> AsyncGenerator[bytes, None]:
    tokens = reply.split(" ")
    for i, tok in enumerate(tokens):
        piece = tok if i == 0 else " " + tok
        line = {
            "model": model,
            "created_at": _now(),
            "response": piece,
            "done": False,
        }
        yield (json.dumps(line) + "\n").encode()
    final = {
        "model": model,
        "created_at": _now(),
        "response": "",
        "done": True,
        "total_duration": 1,
        "done_reason": "stop",
    }
    yield (json.dumps(final) + "\n").encode()


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "Ollama is running"


@app.get("/api/tags")
async def tags() -> dict[str, Any]:
    return {"models": [{"name": "stub:latest", "model": "stub:latest", "size": 0}]}


@app.post("/api/embeddings")
@app.post("/api/embed")
async def embeddings(req: Request) -> dict[str, Any]:
    body = await req.json()
    prompt = body.get("prompt") or body.get("input") or ""
    if isinstance(prompt, list):
        return {"embeddings": [_fake_embedding(str(p)) for p in prompt]}
    return {"embedding": _fake_embedding(str(prompt))}


@app.post("/api/chat")
async def chat(req: Request) -> StreamingResponse:
    body = await req.json()
    messages = body.get("messages", [])
    model = body.get("model", "stub:latest")
    module_ref = _extract_module_ref(messages)
    user_msg = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    reply = _build_reply(module_ref, user_msg)
    return StreamingResponse(
        _stream_chat(model, reply),
        media_type="application/x-ndjson",
    )


@app.post("/api/generate")
async def generate(req: Request) -> StreamingResponse:
    body = await req.json()
    model = body.get("model", "stub:latest")
    prompt = body.get("prompt", "")
    module_ref = _extract_module_ref(
        [{"role": "system", "content": prompt}],
    )
    reply = _build_reply(module_ref, prompt)
    return StreamingResponse(
        _stream_generate(model, reply),
        media_type="application/x-ndjson",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Ollama stub server")
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
