"""Data classes for the work-item-aware RAG evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orch.db.models import WorkItem


@dataclass
class CodeChunk:
    """A retrieved code chunk from the code LanceDB index."""

    file_path: str
    text: str
    score: float | None = None


@dataclass
class DocChunk:
    """A retrieved doc chunk from the docs LanceDB index."""

    work_item_id: str
    work_item_type: str
    work_item_title: str
    text: str
    score: float | None = None


@dataclass
class EvidenceBundle:
    """Container for all retrieval evidence for work-item-aware answering."""

    question: str
    code_chunks: list[CodeChunk] = field(default_factory=list)
    doc_chunks: list[DocChunk] = field(default_factory=list)
    fts_items: list[WorkItem] = field(default_factory=list)
    git_log_items: list[WorkItem] = field(default_factory=list)
    work_items: list[WorkItem] = field(default_factory=list)
    retrieval_cutoff: datetime = field(default_factory=datetime.utcnow)

    @property
    def allowed_ids(self) -> set[str]:
        """Set of all work-item IDs from every retrieval source, not just the ranked top-5.

        This is the union of IDs from doc_chunks (LanceDB semantic), fts_items (Postgres FTS),
        and git_log_items (git-log resolver), plus the ranked work_items.
        The citation allowlist must be a superset of all retrieved evidence so that
        a valid work-item ID from any source is never stripped from the answer.
        """
        ids: set[str] = set()
        for chunk in self.doc_chunks:
            if hasattr(chunk, "work_item_id") and chunk.work_item_id:
                ids.add(chunk.work_item_id)
        for wi in self.fts_items:
            ids.add(wi.id)
        for wi in self.git_log_items:
            ids.add(wi.id)
        for wi in self.work_items:
            ids.add(wi.id)
        return ids

    @property
    def code_file_paths(self) -> list[str]:
        """Unique file paths from code chunks."""
        return list({chunk.file_path for chunk in self.code_chunks})
