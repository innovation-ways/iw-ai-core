"""CodeIndexer — indexes codebase into LanceDB using LlamaIndex CodeSplitter + Ollama embeddings."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.lancedb import LanceDBVectorStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from orch.rag.config import CodeUnderstandingConfig


@dataclass
class IndexResult:
    files_indexed: int
    chunks_created: int
    files_skipped: int
    files_discovered: int = 0
    languages_detected: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CodeIndexer:
    def __init__(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
        index_path: str,
    ) -> None:
        self.project_id = project_id
        self.config = config
        self.index_path = index_path

    def _get_manifest_path(self) -> Path:
        return Path(self.index_path) / self.project_id / "manifest.json"

    def _load_manifest(self) -> dict[str, str]:
        path = self._get_manifest_path()
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def _save_manifest(self, manifest: dict[str, str]) -> None:
        path = self._get_manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def _compute_sha(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def _get_changed_files(self, repo_path: str, manifest: dict[str, str]) -> list[Path]:
        changed: list[Path] = []
        repo = Path(repo_path)
        for file_path in repo.rglob("*.py"):
            if any(
                part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                for part in file_path.parts
            ):
                continue
            rel = str(file_path)
            if manifest.get(rel) != self._compute_sha(file_path):
                changed.append(file_path)
        for file_path in repo.rglob("*.cpp"):
            if any(
                part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                for part in file_path.parts
            ):
                continue
            rel = str(file_path)
            if manifest.get(rel) != self._compute_sha(file_path):
                changed.append(file_path)
        for file_path in repo.rglob("*.hpp"):
            if any(
                part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                for part in file_path.parts
            ):
                continue
            rel = str(file_path)
            if manifest.get(rel) != self._compute_sha(file_path):
                changed.append(file_path)
        for file_path in repo.rglob("*.h"):
            if any(
                part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                for part in file_path.parts
            ):
                continue
            rel = str(file_path)
            if manifest.get(rel) != self._compute_sha(file_path):
                changed.append(file_path)
        return changed

    def _build_index(self, store_path: Path) -> tuple[VectorStoreIndex, LanceDBVectorStore]:
        """Create or open a LanceDB-backed VectorStoreIndex with Ollama embeddings."""
        store_path.mkdir(parents=True, exist_ok=True)
        table_name = f"code_{self.project_id.replace('-', '_')}"
        embed = OllamaEmbedding(
            model_name=self.config.resolved_embed_model(),
            base_url=self.config.ollama_url,
        )
        vector_store = LanceDBVectorStore(uri=str(store_path), table_name=table_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex([], storage_context=storage_context, embed_model=embed)
        return index, vector_store

    async def index(
        self,
        repo_path: str,
        _job_id: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> IndexResult:
        repo = Path(repo_path)
        discovered: list[Path] = []
        for pattern in ("*.py", "*.cpp", "*.hpp", "*.h"):
            for fp in repo.rglob(pattern):
                if any(
                    part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                    for part in fp.parts
                ):
                    continue
                discovered.append(fp)

        store_path = Path(self.index_path) / self.project_id / "vectors"
        index, _ = await asyncio.to_thread(self._build_index, store_path)

        manifest: dict[str, str] = {}
        files_indexed = 0
        chunks_created = 0
        errors: list[str] = []
        languages_seen: set[str] = set()

        for file_path in discovered:
            if progress_callback:
                await asyncio.to_thread(
                    progress_callback,
                    {
                        "event": "progress",
                        "files_indexed": files_indexed,
                        "files_total": len(discovered),
                        "chunks_created": chunks_created,
                        "phase": "indexing",
                    },
                )
            rel = str(file_path)
            try:
                nodes = await asyncio.to_thread(self._split_file, file_path)
                if nodes:
                    await asyncio.to_thread(index.insert_nodes, nodes)
                    chunks_created += len(nodes)
                    lang = nodes[0].metadata.get("language")
                    if lang:
                        languages_seen.add(str(lang))
                manifest[rel] = self._compute_sha(file_path)
                files_indexed += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")

        self._save_manifest(manifest)

        return IndexResult(
            files_indexed=files_indexed,
            chunks_created=chunks_created,
            files_skipped=0,
            files_discovered=len(discovered),
            languages_detected=sorted(languages_seen),
            errors=errors,
        )

    async def reindex_changed(
        self,
        repo_path: str,
        _job_id: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> IndexResult:
        manifest = self._load_manifest()
        changed = self._get_changed_files(repo_path, manifest)

        store_path = Path(self.index_path) / self.project_id / "vectors"
        index, _ = await asyncio.to_thread(self._build_index, store_path)

        files_indexed = 0
        chunks_created = 0
        errors: list[str] = []
        languages_seen: set[str] = set()

        all_files: list[Path] = []
        repo = Path(repo_path)
        for pattern in ("*.py", "*.cpp", "*.hpp", "*.h"):
            for fp in repo.rglob(pattern):
                if any(
                    part.startswith(".") or part in ("__pycache__", ".venv", "node_modules")
                    for part in fp.parts
                ):
                    continue
                all_files.append(fp)
        total = len(all_files)

        for file_path in changed:
            if progress_callback:
                await asyncio.to_thread(
                    progress_callback,
                    {
                        "event": "progress",
                        "files_indexed": files_indexed,
                        "files_total": total,
                        "chunks_created": chunks_created,
                        "phase": "indexing",
                    },
                )
            rel = str(file_path)
            try:
                nodes = await asyncio.to_thread(self._split_file, file_path)
                if nodes:
                    await asyncio.to_thread(index.insert_nodes, nodes)
                    chunks_created += len(nodes)
                    lang = nodes[0].metadata.get("language")
                    if lang:
                        languages_seen.add(str(lang))
                manifest[rel] = self._compute_sha(file_path)
                files_indexed += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")

        self._save_manifest(manifest)

        return IndexResult(
            files_indexed=files_indexed,
            chunks_created=chunks_created,
            files_skipped=len(all_files) - len(changed),
            files_discovered=total,
            languages_detected=sorted(languages_seen),
            errors=errors,
        )

    def _split_file(self, file_path: Path) -> list[TextNode]:
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            language = "python"
        elif suffix in (".cpp", ".hpp", ".h"):
            language = "cpp"
        else:
            language = None

        metadata = {"file_path": str(file_path), "language": language or "text"}

        try:
            if language:
                splitter = CodeSplitter(
                    chunk_lines=40,
                    chunk_lines_overlap=5,
                    language=language,
                )
                text = file_path.read_text(encoding="utf-8", errors="replace")
                texts = splitter.split_text(text)
            else:
                splitter = SentenceSplitter(chunk_size=500, chunk_overlap=50)
                text = file_path.read_text(encoding="utf-8", errors="replace")
                texts = splitter.split_text(text)
        except Exception:
            splitter = SentenceSplitter(chunk_size=500, chunk_overlap=50)
            text = file_path.read_text(encoding="utf-8", errors="replace")
            texts = splitter.split_text(text)

        return [
            TextNode(text=chunk, metadata={**metadata, "chunk_index": i})
            for i, chunk in enumerate(texts)
            if chunk.strip()
        ]
