"""RAG query performance budget.

Methodology: measures one full `CodeQA.answer_stream` invocation against a
tmp_path-backed LanceDB index fixture (10 documents) with a deterministic stub
embedding (hash-to-fixed-dim vector — NO Ollama dependency, opposite stance to
tests/integration/rag/'s skip-when-no-Ollama hook).

Initial measurement (2026-05-26, S03 run):
  mean = 24.93 ms, σ/μ = 0.048
  σ/μ = 0.048 < 0.3 → using mean
  BUDGET_S = ceil(24.93 * 1.5) ms = 38 ms = 0.04 s
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import lancedb
import pytest
from llama_index.embeddings.ollama import OllamaEmbedding

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBED_DIM: int = 768  # matches nomic-embed-code / qwen3-embedding:8b

# Frozen budget — set after initial measurement on 2026-05-26.
# Operator-only updates via `make test-perf-update-baseline` (CR review required).
# BUDGET_S = ceil(initial_mean * 1.5) ms / 1000  (σ/μ = 0.048 < 0.3 → using mean)
BUDGET_S: float = 0.04


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_embedding(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic hash-based embedding: blake2b -> float32 list, normalised.

    Produces a consistent 768-dim vector for any given text string so that
    retrieval is deterministic and reproducible across runs without any Ollama
    dependency. The blake2b key is varied per-dimension-slice to avoid flat
    correlation across the vector.
    """
    vec: list[float] = []
    for i in range(0, dim, 32):
        key = i.to_bytes(4, "little")
        chunk = hashlib.blake2b(text.encode(), digest_size=32, key=key).digest()
        vec.extend(chunk)
    vec = vec[:dim]
    while len(vec) < dim:
        vec.append(0.0)
    return [float(v) / 255.0 for v in vec[:dim]]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tmp_path_rag_index(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    """Build a tmp_path-backed LanceDB index with 10 synthetic documents.

    Returns (index_path, project_id) matching the layout `qa.py` expects:
      {index_path}/{project_id}/vectors/code_{project_id}.table

    The path lives under pytest's RAM-backed tempdir so the I/O cost is
    negligible and the measurement focuses on retrieval + ranking + assembly.
    """
    import pyarrow as pa

    tmp = tmp_path_factory.mktemp("rag_vectors")
    project_id = "perf-proj"

    # Same layout qa.py expects: {index_path}/{project_id}/vectors/
    vectors_dir = tmp / project_id / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(vectors_dir)

    db = lancedb.connect(db_path)

    schema = pa.schema(
        [
            ("id", pa.string()),
            ("text", pa.string()),
            ("file_path", pa.string()),
            ("vector", pa.list_(pa.float32(), EMBED_DIM)),
        ]
    )
    table_name = f"code_{project_id.replace('-', '_')}"
    table = db.create_table(table_name, schema=schema)

    docs = [
        {
            "id": "1",
            "text": (
                "The daemon polls the PostgreSQL database every 60 seconds for approved batches."
            ),
            "file_path": "orch/daemon/main.py",
        },
        {
            "id": "2",
            "text": (
                "BatchManager handles batch execution: process_batches scans "
                "for approved batches, then spawns worktrees."
            ),
            "file_path": "orch/daemon/batch_manager.py",
        },
        {
            "id": "3",
            "text": (
                "WorkItem status transitions: draft -> in_progress -> "
                "completed. Phase is active or work."
            ),
            "file_path": "orch/db/models.py",
        },
        {
            "id": "4",
            "text": (
                "The daemon creates git worktrees for each batch item. "
                "Worktrees are isolated Docker environments."
            ),
            "file_path": "orch/daemon/worktree_compose.py",
        },
        {
            "id": "5",
            "text": (
                "DocGenerationJob rows are polled by DocJobPoller. "
                "Completed jobs trigger Slack notifications."
            ),
            "file_path": "orch/doc_service.py",
        },
        {
            "id": "6",
            "text": (
                "Project configuration is stored in projects.toml and synced "
                "to the DB on SIGHUP via ProjectRegistry."
            ),
            "file_path": "orch/daemon/project_registry.py",
        },
        {
            "id": "7",
            "text": (
                "LanceDB stores code chunk embeddings. The index is built "
                "by the code indexer and queried during RAG."
            ),
            "file_path": "orch/rag/qa.py",
        },
        {
            "id": "8",
            "text": (
                "The dashboard is a FastAPI app on port 9900. It uses htmx "
                "for partial page updates and Jinja2 templates."
            ),
            "file_path": "dashboard/app.py",
        },
        {
            "id": "9",
            "text": (
                "pytest-benchmark is used for performance regression testing. "
                "Budgets are mean × 1.5 with 25% tolerance."
            ),
            "file_path": "tests/perf/test_rag_query.py",
        },
        {
            "id": "10",
            "text": (
                "Testcontainers spins up a PostgreSQL 16 instance for "
                "integration tests. The DB is seeded with representative rows."
            ),
            "file_path": "tests/perf/conftest.py",
        },
    ]

    rows = []
    for doc in docs:
        rows.append(
            {
                "id": doc["id"],
                "text": doc["text"],
                "file_path": doc["file_path"],
                "vector": _make_stub_embedding(doc["text"]),
            }
        )

    table.add(rows)

    return str(tmp), project_id


@pytest.fixture(autouse=True)
def _stub_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace OllamaEmbedding.get_query_embedding with a synchronous deterministic stub.

    The method is called via `asyncio.to_thread(embed_instance.get_query_embedding, ...)`
    in qa.py, so the stub must be a regular function (not async) that returns the
    embedding directly.  This is autouse=True so every RAG perf test runs without
    any Ollama dependency — opposite stance to tests/integration/rag/'s
    skip-when-no-Ollama hook.
    """
    _original_get = OllamaEmbedding.get_query_embedding

    def _stub_get_query_embedding(self, text: str) -> list[float]:
        # self.model_name is ignored; the stub is deterministic regardless
        return _make_stub_embedding(text)

    monkeypatch.setattr(OllamaEmbedding, "get_query_embedding", _stub_get_query_embedding)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def _async_rag_query(
    index_path: str,
    project_id: str,
    question: str,
) -> list[str]:
    """Run one CodeQA.answer_stream call and collect all tokens into a list."""
    from orch.rag.config import CodeUnderstandingConfig
    from orch.rag.qa import QAEngine

    config = MagicMock(spec=CodeUnderstandingConfig)
    config.resolved_embed_model.return_value = "nomic-embed-text"
    config.resolved_llm_model.return_value = "llama3.2:3b"
    config.ollama_url = "http://localhost:11434"
    config.index_path = index_path

    engine = QAEngine(project_id=project_id, config=config)

    # Replace the Ollama class in qa.py so answer_stream uses our mock
    import orch.rag.qa as qa_module

    _orig_ollama = getattr(qa_module, "Ollama")
    _mock_ollama = MagicMock()
    _mock_instance = MagicMock()
    _mock_ollama.return_value = _mock_instance

    # astream_chat must return an async generator (not a coroutine) because
    # the llama_index wrapper does `await llm.astream_chat(...)` and then
    # `async for chunk in stream`.  So we use AsyncMock with return_value set
    # to an async generator.
    async def _stream_gen(_messages: object) -> object:
        yield MagicMock(delta=f"Stub answer for: {question[:30]}...")

    _mock_instance.astream_chat = AsyncMock()
    _mock_instance.astream_chat.return_value = _stream_gen(None)

    qa_module.Ollama = _mock_ollama

    try:
        tokens: list[str] = []
        async for token in engine.answer_stream(
            question=question,
            context_level="architecture",
            context_doc_id=None,
            conversation_history=[],
            session=MagicMock(),
        ):
            tokens.append(token)
        return tokens
    finally:
        qa_module.Ollama = _orig_ollama


def _run_one_rag_query(
    index_path_and_project: tuple[str, str],
    question: str,
) -> list[str]:
    """Synchronous entry-point for benchmark.pedantic."""
    return asyncio.run(
        _async_rag_query(index_path_and_project[0], index_path_and_project[1], question)
    )


def test_rag_query_within_budget(
    benchmark: pytest.Benchmark,
    tmp_path_rag_index: tuple[str, str],
) -> None:
    """Measure RAG retrieval + ranking + result-assembly cost (no LLM latency).

    Uses the tmp_path-backed LanceDB index (10 docs) and a deterministic
    stub embedding. The mock LLM is also stubbed so the measurement captures
    only the RAG pipeline overhead.
    """
    benchmark.pedantic(
        _run_one_rag_query,
        args=(tmp_path_rag_index, "What does the daemon do?"),
        rounds=10,
        warmup_rounds=5,
    )
    assert benchmark.stats.stats.mean < BUDGET_S, (
        f"RAG query mean {benchmark.stats.stats.mean:.3f} s exceeds budget {BUDGET_S} s"
    )
