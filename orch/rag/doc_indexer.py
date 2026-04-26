"""DocIndexer — embeds functional_doc_content from work_items into LanceDB.

Mirrors the pattern of CodeIndexer but indexes work_items.functional_doc_content
rather than code files. Uses SentenceSplitter for prose chunking and Ollama
embeddings via the same CodeUnderstandingConfig.
"""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


@dataclass
class DocIndexResult:
    items_discovered: int = 0
    items_indexed: int = 0
    chunks_created: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


_MANIFEST_KEY = "embed_model"


class DocIndexer:
    def __init__(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
        index_path: str | Path,
        db_session_factory: Callable[[], Session],
    ) -> None:
        self.project_id = project_id
        self.config = config
        self.index_path = str(index_path)
        self._db_session_factory = db_session_factory

    def _table_name(self) -> str:
        return f"docs_{self.project_id.replace('-', '_')}"

    def _uri(self) -> str:
        return f"{self.index_path}/{self.project_id}/vectors/"

    def _sanitise(self, text: str) -> str:
        text = text.replace("\x00", "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _load_embed_model(self) -> str:
        return self.config.resolved_embed_model()

    def _embed(self, text: str) -> list[float]:
        from llama_index.embeddings.ollama import OllamaEmbedding

        embed = OllamaEmbedding(
            model_name=self._load_embed_model(),
            base_url=self.config.ollama_url,
        )
        return embed.get_text_embedding(text)

    def get_previous_job_watermark(self) -> datetime | None:
        from sqlalchemy import select

        from orch.db.models import DocIndexJob

        factory = self._db_session_factory
        with factory() as session:
            last_completed = session.scalar(
                select(DocIndexJob)
                .where(
                    DocIndexJob.project_id == self.project_id,
                    DocIndexJob.status == "completed",
                )
                .order_by(DocIndexJob.completed_at.desc())
                .limit(1)
            )
            if last_completed is None:
                return None
            return last_completed.completed_at

    def _fetch_work_items(
        self,
        watermark: datetime | None,
    ) -> list[tuple[str, str, str, str | None]]:
        from sqlalchemy import select

        from orch.db.models import WorkItem

        factory = self._db_session_factory
        with factory() as session:
            if watermark is None:
                stmt = select(
                    WorkItem.id,
                    WorkItem.type,
                    WorkItem.title,
                    WorkItem.functional_doc_content,
                ).where(
                    WorkItem.project_id == self.project_id,
                    WorkItem.functional_doc_content.isnot(None),
                )
            else:
                stmt = select(
                    WorkItem.id,
                    WorkItem.type,
                    WorkItem.title,
                    WorkItem.functional_doc_content,
                ).where(
                    WorkItem.project_id == self.project_id,
                    WorkItem.updated_at > watermark,
                    WorkItem.functional_doc_content.isnot(None),
                )
            result = session.execute(stmt)
            rows = result.tuples().all()
            return [
                (
                    str(r[0]),
                    r[1].value if hasattr(r[1], "value") else str(r[1]),
                    str(r[2]),
                    self._sanitise(r[3]) if r[3] else r[3],
                )
                for r in rows
            ]

    def _table_exists(self) -> bool:
        import lancedb  # type: ignore[import-untyped]

        uri = self._uri()
        try:
            db = lancedb.connect(uri)
            return self._table_name() in db.table_names()
        except Exception:
            return False

    def _read_manifest(self) -> dict[str, str]:
        path = Path(self._uri()) / "manifest.json"
        if not path.exists():
            return {}
        import json

        with path.open("r", encoding="utf-8") as f:
            result: dict[str, str] = json.load(f)
            return result

    def _write_manifest(self, manifest: dict[str, str]) -> None:
        path = Path(self._uri())
        path.mkdir(parents=True, exist_ok=True)
        import json

        with (path / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def _stored_embed_model(self) -> str | None:
        manifest = self._read_manifest()
        return manifest.get(_MANIFEST_KEY)

    def _drop_table(self) -> None:
        import lancedb

        uri = self._uri()
        with suppress(Exception):
            db = lancedb.connect(uri)
            if self._table_name() in db.table_names():
                db.drop_table(self._table_name())

    def _write_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> int:
        import lancedb

        uri = self._uri()
        table_name = self._table_name()

        Path(uri).mkdir(parents=True, exist_ok=True)

        if not chunks:
            manifest = self._read_manifest()
            manifest[_MANIFEST_KEY] = self._load_embed_model()
            self._write_manifest(manifest)
            return 0

        db = lancedb.connect(uri)

        import pyarrow as pa  # type: ignore[import-untyped]

        schema = pa.schema(
            [
                ("work_item_id", pa.string()),
                ("work_item_type", pa.string()),
                ("work_item_title", pa.string()),
                ("chunk_index", pa.int32()),
                ("text", pa.string()),
                ("embedding", pa.list_(pa.float32(), 8)),
            ]
        )

        if table_name in db.table_names():
            db.drop_table(table_name)

        tbl = db.create_table(table_name, schema=schema, mode="overwrite")

        import numpy as np

        records = []
        for chunk in chunks:
            records.append(
                {
                    "work_item_id": chunk["work_item_id"],
                    "work_item_type": chunk["work_item_type"],
                    "work_item_title": chunk["work_item_title"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "embedding": np.array(chunk["embedding"], dtype=np.float32).tolist(),
                }
            )

        tbl.add(records)

        manifest = self._read_manifest()
        manifest[_MANIFEST_KEY] = self._load_embed_model()
        self._write_manifest(manifest)

        return len(chunks)

    def index_all(
        self,
        progress_queue: Any | None = None,
    ) -> DocIndexResult:
        from llama_index.core.node_parser import SentenceSplitter

        embed_model = self._load_embed_model()

        if self._table_exists():
            stored = self._stored_embed_model()
            if stored is not None and stored != embed_model:
                self._drop_table()

        work_items = self._fetch_work_items(watermark=None)
        items_discovered = len(work_items)

        if progress_queue:
            progress_queue.put_nowait(
                {
                    "event": "progress",
                    "items_indexed": 0,
                    "chunks_created": 0,
                    "phase": "indexing",
                }
            )

        chunks: list[dict[str, Any]] = []
        items_indexed = 0
        errors: list[dict[str, Any]] = []
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)

        for work_item_id, work_item_type, work_item_title, content in work_items:
            if content is None:
                continue
            try:
                sanitised = self._sanitise(content)
                text_chunks = splitter.split_text(sanitised)
                for chunk_index, text_chunk in enumerate(text_chunks):
                    embedding = self._embed(text_chunk)
                    chunks.append(
                        {
                            "work_item_id": work_item_id,
                            "work_item_type": work_item_type,
                            "work_item_title": work_item_title,
                            "chunk_index": chunk_index,
                            "text": text_chunk,
                            "embedding": embedding,
                        }
                    )
                items_indexed += 1

                if progress_queue:
                    progress_queue.put_nowait(
                        {
                            "event": "progress",
                            "items_indexed": items_indexed,
                            "chunks_created": len(chunks),
                            "phase": "indexing",
                        }
                    )
            except Exception as e:
                errors.append({"work_item_id": work_item_id, "error": str(e)})

        chunks_created = self._write_chunks(chunks)

        return DocIndexResult(
            items_discovered=items_discovered,
            items_indexed=items_indexed,
            chunks_created=chunks_created,
            errors=errors,
        )

    def reindex_changed(
        self,
        watermark: datetime | None,
        progress_queue: Any | None = None,
    ) -> DocIndexResult:
        from llama_index.core.node_parser import SentenceSplitter

        embed_model = self._load_embed_model()

        if self._table_exists():
            stored = self._stored_embed_model()
            if stored is not None and stored != embed_model:
                self._drop_table()
                return self.index_all(progress_queue)

        if watermark is None:
            watermark = self.get_previous_job_watermark()

        work_items = self._fetch_work_items(watermark=watermark)
        items_discovered = len(work_items)

        if items_discovered == 0:
            return DocIndexResult(items_discovered=0, items_indexed=0, chunks_created=0)

        if progress_queue:
            progress_queue.put_nowait(
                {
                    "event": "progress",
                    "items_indexed": 0,
                    "chunks_created": 0,
                    "phase": "reindexing",
                }
            )

        import lancedb

        uri = self._uri()
        table_name = self._table_name()

        lancedb_uri = lancedb.connect(uri)
        existing_ids: set[str] = set()
        if table_name in lancedb_uri.table_names():
            tbl = lancedb_uri.open_table(table_name)
            existing_ids = set(tbl.to_pandas()["work_item_id"].tolist())

        chunks: list[dict[str, Any]] = []
        items_indexed = 0
        errors: list[dict[str, Any]] = []
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)

        for work_item_id, work_item_type, work_item_title, content in work_items:
            if content is None:
                continue

            if work_item_id in existing_ids:
                with suppress(Exception):
                    ldb_uri = lancedb.connect(uri)
                    if table_name in ldb_uri.table_names():
                        ldb_uri.open_table(table_name).delete(f"work_item_id = '{work_item_id}'")

            try:
                sanitised = self._sanitise(content)
                text_chunks = splitter.split_text(sanitised)
                for chunk_index, text_chunk in enumerate(text_chunks):
                    embedding = self._embed(text_chunk)
                    chunks.append(
                        {
                            "work_item_id": work_item_id,
                            "work_item_type": work_item_type,
                            "work_item_title": work_item_title,
                            "chunk_index": chunk_index,
                            "text": text_chunk,
                            "embedding": embedding,
                        }
                    )
                items_indexed += 1

                if progress_queue:
                    progress_queue.put_nowait(
                        {
                            "event": "progress",
                            "items_indexed": items_indexed,
                            "chunks_created": len(chunks),
                            "phase": "reindexing",
                        }
                    )
            except Exception as e:
                errors.append({"work_item_id": work_item_id, "error": str(e)})

        chunks_created = self._write_chunks(chunks)

        return DocIndexResult(
            items_discovered=items_discovered,
            items_indexed=items_indexed,
            chunks_created=chunks_created,
            errors=errors,
        )
