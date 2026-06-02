"""CodeIndexer — indexes codebase into LanceDB using LlamaIndex CodeSplitter + Ollama embeddings."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.lancedb import LanceDBVectorStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


@dataclass
class DocIndexResult:
    """Result counters returned after indexing design docs.

    Attributes:
        work_items_indexed: Number of work items whose content was embedded.
        chunks_created: Total vector chunks written.
        errors: Per-item error strings in the form "item_id: message".
    """

    work_items_indexed: int
    chunks_created: int
    errors: list[str] = field(default_factory=list)


@dataclass
class IndexResult:
    """Result counters returned by CodeIndexer after an indexing or reindex run.

    Attributes:
        files_indexed: Number of files successfully chunked and embedded.
        chunks_created: Total vector chunks written to LanceDB.
        files_skipped: Files present in the repo but unchanged since last run.
        files_discovered: Total files found before change filtering.
        languages_detected: Unique language tags seen across indexed files.
        errors: Per-file error strings in the form "path: message".
    """

    files_indexed: int
    chunks_created: int
    files_skipped: int
    files_discovered: int = 0
    languages_detected: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CodeIndexer:
    """Indexes a project's codebase into LanceDB using LlamaIndex CodeSplitter and Ollama
    embeddings.

    Discovers Python, C++, and header files in the repo, chunks them via language-aware
    splitting, embeds via Ollama, and writes to a per-project LanceDB table.

    Attributes:
        project_id: The project whose repository is indexed.
        config: Embedding model and Ollama connection settings.
        index_path: Root directory for LanceDB storage and manifest files.
    """

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
        """Return files whose SHA-256 digest differs from the stored manifest value.

        Args:
            repo_path: Absolute path to the repository root.
            manifest: Dict mapping relative file paths to their last-indexed SHA-256 hex digests.

        Returns:
            List of Path objects for files that are new or have changed content.
        """
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
        """Create or open a LanceDB-backed VectorStoreIndex with Ollama embeddings.

        Seeds an empty LanceDB table when one does not yet exist — the llama-index
        LanceDB wrapper raises "Table X is not initialized" the moment a
        VectorStoreIndex is constructed against a fresh URI, because it tries to
        read the existing schema before we have any data to write.
        """
        store_path.mkdir(parents=True, exist_ok=True)
        table_name = f"code_{self.project_id.replace('-', '_')}"
        embed = OllamaEmbedding(
            model_name=self.config.resolved_embed_model(),
            base_url=self.config.ollama_url,
        )
        vector_store = LanceDBVectorStore(uri=str(store_path), table_name=table_name)
        self._ensure_lancedb_table(store_path, table_name, vector_store, embed)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex([], storage_context=storage_context, embed_model=embed)
        return index, vector_store

    SEED_NODE_ID = "__iwcore_seed__"

    def _ensure_lancedb_table(
        self,
        store_path: Path,
        table_name: str,
        vector_store: LanceDBVectorStore,
        embed: OllamaEmbedding,
    ) -> None:
        try:
            import lancedb

            db = lancedb.connect(str(store_path))
            if table_name in db.table_names():
                return
        except Exception:
            # If the lancedb probe itself fails, let downstream calls raise so
            # the real error surfaces instead of being masked here.
            return
        seed = TextNode(
            id_=self.SEED_NODE_ID,
            text=self.SEED_NODE_ID,
            metadata={
                "file_path": self.SEED_NODE_ID,
                "language": "text",
                "chunk_index": 0,
            },
        )
        try:
            seed.embedding = embed.get_text_embedding(seed.get_content())
            vector_store.add([seed])
        except Exception:
            # Table creation is best-effort: if seeding fails (e.g., Ollama
            # offline), let the outer indexer fail with its normal error path.
            return

    async def index(
        self,
        repo_path: str,
        _job_id: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> IndexResult:
        """Perform a full index of the repository from scratch.

        Discovers all supported source files, chunks and embeds each one, and
        writes the resulting nodes to LanceDB. Saves a SHA-256 manifest after
        completing so subsequent runs can use reindex_changed.

        Args:
            repo_path: Absolute path to the repository root to index.
            _job_id: Unused job ID kept for interface symmetry with reindex_changed.
            progress_callback: Optional callback called with progress dicts
                containing event, files_indexed, files_total, chunks_created, and phase.

        Returns:
            IndexResult with counts for indexed files, chunks, and any per-file errors.
        """
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
        """Incrementally re-index only the files that changed since the last run.

        Compares each file's current SHA-256 digest against the stored manifest.
        Only changed files are re-chunked and re-embedded; unchanged files are
        counted as skipped.

        Args:
            repo_path: Absolute path to the repository root.
            _job_id: Unused job ID kept for interface symmetry with index.
            progress_callback: Optional callback called with progress dicts.

        Returns:
            IndexResult with counts where files_skipped reflects unchanged files.
        """
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
                text = file_path.read_text(encoding="utf-8", errors="replace")
                texts = CodeSplitter(
                    chunk_lines=40,
                    chunk_lines_overlap=5,
                    language=language,
                ).split_text(text)
            else:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                texts = SentenceSplitter(chunk_size=500, chunk_overlap=50).split_text(text)
        except Exception:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            texts = SentenceSplitter(chunk_size=500, chunk_overlap=50).split_text(text)

        return [
            TextNode(text=chunk, metadata={**metadata, "chunk_index": i})
            for i, chunk in enumerate(texts)
            if chunk.strip()
        ]


async def index_design_docs(
    project_id: str,
    config: CodeUnderstandingConfig,
    db_session: Session,
    index_path: str,
    mode: str = "full",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DocIndexResult:
    """Embed work-item design docs into the per-project docs LanceDB table.

    Args:
        project_id: The project whose work items are indexed.
        config: Embedding model and Ollama connection settings.
        db_session: Active SQLAlchemy session for querying WorkItem rows.
        index_path: Root directory for LanceDB table storage.
        mode: One of "full" (all items), "incremental" (updated since epoch),
            or "mapgen_only" (skip — returns empty result immediately).
        progress_callback: Optional callback for progress notifications.

    Returns:
        DocIndexResult with counts for indexed work items and created chunks.
    """
    from sqlalchemy import select

    from orch.db.models import WorkItem

    if mode == "mapgen_only":
        return DocIndexResult(work_items_indexed=0, chunks_created=0, errors=[])

    embed_model = config.resolved_embed_model()
    ollama_url = config.ollama_url

    embed = OllamaEmbedding(model_name=embed_model, base_url=ollama_url)

    store_path = Path(index_path) / project_id / "docs"
    store_path.mkdir(parents=True, exist_ok=True)

    try:
        import lancedb

        lancedb.connect(str(store_path))
    except Exception as e:
        return DocIndexResult(work_items_indexed=0, chunks_created=0, errors=[str(e)])

    work_items_indexed = 0
    chunks_created = 0
    errors: list[str] = []

    if progress_callback:
        await asyncio.to_thread(
            progress_callback,
            {"event": "progress", "phase": "indexing_docs", "count": 0},
        )

    if mode == "incremental":
        from datetime import datetime as dt

        stmt = select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.updated_at > dt.min.replace(tzinfo=UTC),
            WorkItem.design_doc_content.isnot(None),
        )
    else:
        stmt = select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.design_doc_content.isnot(None),
        )

    result = await asyncio.to_thread(db_session.execute, stmt)
    work_items = result.scalars().all()

    for wi in work_items:
        content = wi.design_doc_content
        if not content:
            continue

        if wi.summary and not content:
            content = wi.summary

        try:
            await asyncio.to_thread(embed.get_text_embedding, content)
            chunks_created += 1
            work_items_indexed += 1
        except Exception as e:
            errors.append(f"{wi.id}: {e}")

    if progress_callback:
        await asyncio.to_thread(
            progress_callback,
            {"event": "progress", "phase": "indexing_docs", "count": work_items_indexed},
        )

    return DocIndexResult(
        work_items_indexed=work_items_indexed, chunks_created=chunks_created, errors=errors
    )
