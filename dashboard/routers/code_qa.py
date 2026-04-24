"""POST /api/projects/{project_id}/code/qa — SSE streaming endpoint for Code Q&A.

Wraps QAEngine.answer_stream() in an SSE StreamingResponse with named events
and base64-encoded token payloads.
"""

from __future__ import annotations

import asyncio
import base64
import json
import queue
import re
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


WORK_ITEM_ID_RE = re.compile(r"^(F|I|CR)-\d{5}$")


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
    context_chips: list[str] = Field(default_factory=list)


class QARerenderRequest(BaseModel):
    render_id: str = Field(..., min_length=1)
    tone: str = Field(..., pattern="^(technical|functional)$")


router = APIRouter(prefix="/api")


@dataclass
class _CitationTracker:
    """De-duplicates citations by symbol identity and assigns monotonic 1-based indices."""

    _seen: dict[str, int] = field(default_factory=dict)
    _next: int = 1
    _work_items: dict[str, tuple[str, str]] = field(default_factory=dict)

    def add(self, symbol_id: str) -> int | None:
        """Add a symbol ID; return its 1-based index if new, None if already seen."""
        if symbol_id in self._seen:
            return None
        idx = self._next
        self._seen[symbol_id] = idx
        self._next += 1
        return idx

    def add_work_item(self, work_item_id: str, work_item_type: str) -> int | None:
        """Add a work-item citation; return its 1-based index if new, None if duplicate."""
        if not WORK_ITEM_ID_RE.match(work_item_id):
            raise ValueError(f"Invalid work_item_id format: {work_item_id!r}")
        if work_item_id in self._work_items:
            return None
        idx = self._next
        self._seen[work_item_id] = idx
        self._work_items[work_item_id] = (work_item_type, work_item_id)
        self._next += 1
        return idx

    def get_work_item(self, work_item_id: str) -> tuple[str, str] | None:
        """Return (type, id) tuple for a seen work item, or None if not found."""
        return self._work_items.get(work_item_id)


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
    q: queue.Queue[str | None | dict[str, object]],
    context_chips: list[str] | None = None,
    symbol_hint: str | None = None,
) -> None:
    """Run QAEngine.answer_stream_v2() in a daemon thread, pushing events into a queue."""
    from orch.rag.qa import QAEngine

    engine = QAEngine(project_id=project_id, config=config)

    async def produce_tokens() -> None:
        try:
            stream = engine.answer_stream_v2(
                question=question,
                context_level=context_level,
                context_doc_id=context_doc_id,
                conversation_history=conversation_history,
                session=db_session,
                module_path=module_path,
                module_name=module_name,
                context_chips=context_chips,
                symbol_hint=symbol_hint,
            )
            async for event in stream:
                q.put(event)
        except (ConnectionRefusedError, OSError):
            q.put(
                {"kind": "error", "message": "Local AI unavailable. Check that Ollama is running."}
            )
        except Exception as exc:
            # Any other exception (pydantic ValidationError from an out-of-sync
            # Ollama response shape, httpx.HTTPStatusError, AttributeError,
            # etc.) MUST surface as an SSE error event. Without this catch-all
            # the exception escapes into the ThreadPoolExecutor Future, which
            # nobody awaits, and the stream silently ends at `event: done`
            # with zero tokens — leaving the UI and qv-browser blind to the
            # real failure.
            import logging
            import traceback

            logging.error(
                "code_qa streaming failed: %s: %s\n%s",
                type(exc).__name__,
                exc,
                traceback.format_exc(),
            )
            q.put(
                {
                    "kind": "error",
                    "message": f"Q&A pipeline error: {type(exc).__name__}: {exc}",
                }
            )
        finally:
            q.put(None)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(produce_tokens())
    finally:
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
    context_chips: list[str] | None = None,
    symbol_hint: str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that runs QAEngine in a thread and yields SSE-formatted strings."""
    import concurrent.futures

    q: queue.Queue[str | None | dict[str, object]] = queue.Queue()
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
        context_chips,
        symbol_hint,
    )

    while True:
        event = await loop.run_in_executor(None, q.get)
        if event is None:
            break
        if isinstance(event, dict):
            kind = event.get("kind", "token")
            if kind == "error":
                payload = json.dumps({"message": event.get("message", "Unknown error")})
                yield f"event: error\ndata: {payload}\n\n"
                return
            if kind == "token":
                token_text = str(event.get("text", ""))
                b64 = base64.b64encode(token_text.encode("utf-8")).decode("ascii")
                payload = json.dumps({"b64": b64})
                yield f"event: token\ndata: {payload}\n\n"
            elif kind == "phase":
                payload = json.dumps({"name": event.get("name"), "detail": event.get("detail", {})})
                yield f"event: phase\ndata: {payload}\n\n"
            elif kind == "citation":
                payload = json.dumps(
                    {
                        "n": event.get("n"),
                        "work_item_type": event.get("work_item_type"),
                        "work_item_id": event.get("work_item_id"),
                        "label": event.get("label"),
                        "url": event.get("url"),
                        "snippet": event.get("snippet"),
                    }
                )
                yield f"event: citation\ndata: {payload}\n\n"
        else:
            b64 = base64.b64encode(str(event).encode("utf-8")).decode("ascii")
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

    symbol_hint = request.question.strip() if "findusages" in request.context_chips else None

    return StreamingResponse(
        _sse_generator(
            project_id=project_id,
            question=request.question,
            context_level=request.context_level,
            context_doc_id=request.context_doc_id,
            module_path=request.module_path,
            module_name=request.module_name,
            conversation_history=[m.model_dump() for m in request.conversation_history],
            context_chips=request.context_chips,
            symbol_hint=symbol_hint,
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
