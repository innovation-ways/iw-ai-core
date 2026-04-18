"""POST /api/projects/{project_id}/code/qa — SSE streaming endpoint for Code Q&A.

Wraps QAEngine.answer_stream() in an SSE StreamingResponse with named events
and base64-encoded token payloads.
"""

from __future__ import annotations

import asyncio
import base64
import json
import queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


class ConversationMessage(BaseModel):
    role: str
    content: str


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    context_level: str = Field(..., pattern="^(architecture|module)$")
    context_doc_id: str | None = None
    module_path: str | None = None
    module_name: str | None = None
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


router = APIRouter(prefix="/api")


@dataclass
class _CitationTracker:
    """De-duplicates citations by symbol identity and assigns monotonic 1-based indices."""

    _seen: dict[str, int] = field(default_factory=dict)
    _next: int = 1

    def add(self, symbol_id: str) -> int | None:
        """Add a symbol ID; return its 1-based index if new, None if already seen."""
        if symbol_id in self._seen:
            return None
        idx = self._next
        self._seen[symbol_id] = idx
        self._next += 1
        return idx


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _run_qa_in_thread(
    project_id: str,
    question: str,
    context_level: str,
    context_doc_id: str | None,
    module_path: str | None,
    module_name: str | None,
    conversation_history: list[dict[str, str]],
    db_session: Session,
    config: CodeUnderstandingConfig,
    q: queue.Queue[str | None],
) -> None:
    """Run QAEngine.answer_stream() in a daemon thread, pushing tokens into a queue."""
    from orch.rag.qa import QAEngine

    engine = QAEngine(project_id=project_id, config=config)

    async def produce_tokens() -> None:
        try:
            stream = engine.answer_stream(
                question=question,
                context_level=context_level,
                context_doc_id=context_doc_id,
                module_path=module_path,
                module_name=module_name,
                conversation_history=conversation_history,
                session=db_session,  # type: ignore[arg-type]
            )
            async for token in stream:
                q.put(token)
        except (ConnectionRefusedError, OSError):
            q.put("__ERROR__:Local AI unavailable. Check that Ollama is running.")
        finally:
            q.put(None)
            loop.stop()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(produce_tokens())
    loop.run_forever()
    loop.close()


async def _sse_generator(
    project_id: str,
    question: str,
    context_level: str,
    context_doc_id: str | None,
    module_path: str | None,
    module_name: str | None,
    conversation_history: list[dict[str, str]],
    db_session: Session,
    config: CodeUnderstandingConfig,
) -> AsyncGenerator[str, None]:
    """Async generator that runs QAEngine in a thread and yields SSE-formatted strings."""
    import concurrent.futures

    q: queue.Queue[str | None] = queue.Queue()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    loop = asyncio.get_event_loop()
    executor.submit(
        _run_qa_in_thread,
        project_id,
        question,
        context_level,
        context_doc_id,
        module_path,
        module_name,
        conversation_history,
        db_session,
        config,
        q,
    )

    while True:
        token = await loop.run_in_executor(None, q.get)
        if token is None:
            break
        if token.startswith("__ERROR__:"):
            error_msg = token[len("__ERROR__:") :]
            payload = json.dumps({"message": error_msg})
            yield f"event: error\ndata: {payload}\n\n"
            return

        b64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
        payload = json.dumps({"b64": b64})
        yield f"event: token\ndata: {payload}\n\n"

    executor.shutdown(wait=False, cancel_futures=True)

    done_payload = json.dumps({"ok": True})
    yield f"event: done\ndata: {done_payload}\n\n"


@router.post("/projects/{project_id}/code/qa")
async def code_qa(
    project_id: str,
    request: QARequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    SSE streaming endpoint for Code Q&A.

    Validates the project exists and that a LanceDB index exists on disk,
    then streams tokens from QAEngine.answer_stream().
    """
    project = _get_project_or_404(project_id, db)

    from orch.config import load_config
    from orch.rag.config import build_code_config_from_project

    cfg = load_config()
    config = build_code_config_from_project(project.config, cfg.index_path)

    index_path = Path(config.index_path)
    if not (index_path / project_id / "vectors").exists():
        raise HTTPException(
            status_code=404,
            detail="No code index found for this project",
        )

    return StreamingResponse(
        _sse_generator(
            project_id=project_id,
            question=request.question,
            context_level=request.context_level,
            context_doc_id=request.context_doc_id,
            module_path=request.module_path,
            module_name=request.module_name,
            conversation_history=[m.model_dump() for m in request.conversation_history],
            db_session=db,
            config=config,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/projects/{project_id}/code/qa-with-image")
async def code_qa_with_image(
    project_id: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> StreamingResponse:
    """Multipart image attachment stub — returns 501 Not Implemented."""
    _ = project_id, db, file
    raise HTTPException(
        status_code=501,
        detail="Image attachments coming soon",
    )
