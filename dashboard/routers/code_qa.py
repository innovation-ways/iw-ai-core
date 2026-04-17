"""POST /api/projects/{project_id}/code/qa — SSE streaming endpoint for Code Q&A.

Wraps QAEngine.answer_stream() in an SSE StreamingResponse.
"""

from __future__ import annotations

import asyncio
import json
import queue
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import Project
from orch.rag.config import CodeUnderstandingConfig

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.orm import Session


class ConversationMessage(BaseModel):
    role: str
    content: str


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    context_level: str = Field(..., pattern="^(architecture|module)$")
    context_doc_id: str | None = None
    module_path: str | None = None
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


router = APIRouter(prefix="/api")


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
            async for token in engine.answer_stream(
                question=question,
                context_level=context_level,
                context_doc_id=context_doc_id,
                module_path=module_path,
                conversation_history=conversation_history,
                session=db_session,  # type: ignore[arg-type]
            ):
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
        conversation_history,
        db_session,
        config,
        q,
    )

    full_response_parts: list[str] = []

    while True:
        token = await loop.run_in_executor(None, q.get)
        if token is None:
            break
        if token.startswith("__ERROR__:"):
            error_msg = token[len("__ERROR__:") :]
            payload = json.dumps({"event": "error", "message": error_msg})
            yield f"data: {payload}\n\n"
            return
        full_response_parts.append(token)
        payload = json.dumps({"token": token})
        yield f"data: {payload}\n\n"

    executor.shutdown(wait=False, cancel_futures=True)

    full_response = "".join(full_response_parts)
    payload = json.dumps({"event": "done", "full_response": full_response})
    yield f"data: {payload}\n\n"


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

    code_cfg_dict = (project.config or {}).get("code_understanding", {})
    config = CodeUnderstandingConfig(**code_cfg_dict)

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
