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
# Matches the candidate blocks emitted by
# orch.rag.qa.QAEngine._build_workitem_system_prompt:
#     ### Candidate 1: F-00060-ORIGINAL — New project button ... (feature)
#     <functional doc content, possibly multiple paragraphs>
#
#     ### Candidate 2: CR-00060-RECOLOR — Recolor button blue (change_request)
#     ...
# The ID may be any F-/CR-/I- prefix with the five-digit sequence optionally
# followed by -<SUFFIX> (the e2e fixture uses ORIGINAL / RECOLOR / RESHAPE
# suffixes on the same five-digit root).
WORKITEM_CANDIDATE_RE = re.compile(
    r"###\s+Candidate\s+(\d+):\s+((?:F|CR|I)-\d{5}(?:-[A-Z0-9_-]+)?)"
    r"\s+—\s+(.+?)\s+\((\w+)\)\s*\n(.*?)(?=\n###\s+Candidate|\Z)",
    re.DOTALL,
)

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


def _extract_workitem_candidates(
    messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Parse the ``## Work Item Context`` block from the system prompt.

    ``orch.rag.qa.QAEngine._build_workitem_system_prompt`` emits one
    ``### Candidate N: <ID> — <title> (<type>)`` block per work item, each
    followed by the functional-doc excerpt on subsequent lines. We extract
    them so the stub can emit a citation-style reply with [N] markers —
    which is what the F-00060 V2/V3/V4 verifications assert on.

    Returns a list of dicts with keys: ``index``, ``id``, ``title``,
    ``type``, ``content``. Empty list if there is no Work Item Context
    block (code-only path).
    """
    candidates: list[dict[str, str]] = []
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content", "")
        if "## Work Item Context" not in content:
            continue
        for m in WORKITEM_CANDIDATE_RE.finditer(content):
            candidates.append(
                {
                    "index": m.group(1),
                    "id": m.group(2),
                    "title": m.group(3).strip(),
                    "type": m.group(4),
                    "content": m.group(5).strip(),
                }
            )
    return candidates


_QUESTION_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    },
)


def _score_candidate(candidate: dict[str, str], question: str) -> int:
    """Count keyword overlap between the question and a candidate's title+content.

    Not a real semantic match — good enough for the deterministic stub to
    prefer ``CR-00060-RECOLOR`` over ``CR-00060-RESHAPE`` when the user
    asks about colour, which is what F-00060 V3 asserts.
    """
    q_words = {
        w.strip(".,!?;:'\"()[]{}").lower()
        for w in question.split()
        if w.strip(".,!?;:'\"()[]{}").lower()
    } - _QUESTION_STOPWORDS
    if not q_words:
        return 0
    text = (candidate["title"] + " " + candidate["content"]).lower()
    return sum(1 for w in q_words if len(w) > 2 and w in text)


def _rank_candidates(
    candidates: list[dict[str, str]],
    question: str,
) -> list[dict[str, str]]:
    """Return candidates sorted by question-match score, most relevant first.

    Stable on the original candidate order when scores tie, so the stub's
    output is fully deterministic.
    """
    scored = sorted(
        enumerate(candidates),
        key=lambda t: (-_score_candidate(t[1], question), t[0]),
    )
    return [c for _, c in scored]


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_reply(
    module_ref: str | None,
    question: str,
    candidates: list[dict[str, str]] | None = None,
) -> str:
    """Build a deterministic reply that exercises the client's surface.

    When ``candidates`` is present (workitem-aware path), the reply opens
    with an overt citation in ``[N]`` form and paraphrases the most
    question-relevant candidate's title so V2/V3/V4 can assert the cited
    ID flows through the allowlist into the UI. Without candidates it
    falls back to the old module-ref / generic echo shape that code-only
    and pre-F-00060 verifications rely on.
    """
    if candidates:
        ranked = _rank_candidates(candidates, question)
        top = ranked[0]
        first_line = (
            # The "[1]" bracket is the hook citation_allowlist.extract_citations
            # looks for; the ID on the same line is what the UI renders as a
            # citation chip and what the allowlist filter checks.
            f"[1] {top['id']} — {top['title']} directly addresses the "
            f"question. {top['content'][:200].replace(chr(10), ' ').strip()}"
            if top["content"]
            else f"[1] {top['id']} — {top['title']} is the most relevant candidate."
        )
        body = (
            f" Based on the excerpts, {top['title'].lower()} is the origin of "
            f"the behaviour asked about in: {question!r}. "
            "This is a deterministic stub response for E2E verification."
        )
        return first_line + body
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
    """Mimic modern Ollama's /api/embed response shape.

    The llama_index Ollama client pinned in this repo parses the response
    as ``EmbedResponse(embeddings: list[list[float]])`` — one vector per
    input, regardless of whether the caller passed a scalar string or a
    list. Returning ``{"embedding": [...]}`` (singular) makes the client
    raise pydantic.ValidationError *outside* the ConnectionRefusedError /
    OSError net in dashboard/routers/code_qa.py, which then ends the Q&A
    SSE stream at ``event: done`` with zero tokens.
    """
    body = await req.json()
    raw = body.get("prompt") if "prompt" in body else body.get("input")
    if raw is None:
        raw = ""
    inputs: list[str] = raw if isinstance(raw, list) else [raw]
    return {
        "model": "stub:latest",
        "embeddings": [_fake_embedding(str(p)) for p in inputs],
    }


@app.post("/api/show")
async def show(req: Request) -> dict[str, Any]:
    """Mimic Ollama's /api/show so llama_index can probe the context window.

    ``llama_index.llms.ollama.Ollama.get_context_window()`` runs on the
    first chat call and parses the response as ``ShowResponse``, whose
    ``modelinfo`` field has ``alias='model_info'``. Without this endpoint
    the first chat call raises ``ollama.ResponseError: 404`` before
    /api/chat is ever hit — and that error is swallowed by the narrow
    except in dashboard/routers/code_qa.py.
    """
    body = await req.json()
    model = body.get("model") or body.get("name", "stub:latest")
    return {
        "model_info": {
            "general.architecture": "stub",
            # llama_index looks for any key containing "context_length".
            "llama.context_length": 4096,
        },
        "details": {
            "family": "stub",
            "families": ["stub"],
            "format": "gguf",
            "parameter_size": "0B",
            "quantization_level": "Q0",
            "parent_model": model,
        },
        "capabilities": ["completion"],
    }


@app.post("/api/chat")
async def chat(req: Request) -> StreamingResponse:
    body = await req.json()
    messages = body.get("messages", [])
    model = body.get("model", "stub:latest")
    module_ref = _extract_module_ref(messages)
    candidates = _extract_workitem_candidates(messages)
    user_msg = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    reply = _build_reply(module_ref, user_msg, candidates=candidates)
    return StreamingResponse(
        _stream_chat(model, reply),
        media_type="application/x-ndjson",
    )


@app.post("/api/generate")
async def generate(req: Request) -> StreamingResponse:
    body = await req.json()
    model = body.get("model", "stub:latest")
    prompt = body.get("prompt", "")
    pseudo_messages = [{"role": "system", "content": prompt}]
    module_ref = _extract_module_ref(pseudo_messages)
    candidates = _extract_workitem_candidates(pseudo_messages)
    reply = _build_reply(module_ref, prompt, candidates=candidates)
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
