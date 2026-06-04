"""POST /api/projects/{project_id}/code/qa — SSE streaming endpoint for Code Q&A.

Wraps QAEngine.answer_stream() in an SSE StreamingResponse with named events
and base64-encoded token payloads.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from dashboard.dependencies import get_db, get_session_id
from orch.db.models import Project
from orch.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


WORK_ITEM_ID_RE = re.compile(r"^(F|I|CR)-\d{5}$")

_FENCED_BLOCK_RE = re.compile(r"```(mermaid|d2)\n(.*?)```", re.DOTALL)


def _find_new_diagram_blocks(
    text: str,
    processed: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return (lang, dsl) pairs for newly completed fenced mermaid/d2 blocks.

    Never raises — returns empty list on any error.
    """
    try:
        results = []
        for m in _FENCED_BLOCK_RE.finditer(text):
            lang = m.group(1)
            dsl = m.group(2).strip()
            key = (lang, dsl)
            if key not in processed:
                results.append((lang, dsl))
        return results
    except Exception:
        return []


try:
    from orch.diagram.render import render_d2, render_mermaid

    _DIAGRAM_RENDER_AVAILABLE = True
except ImportError:
    _DIAGRAM_RENDER_AVAILABLE = False

    def render_mermaid(dsl: str) -> str | None:  # noqa: ARG001
        return None

    def render_d2(dsl: str) -> str | None:  # noqa: ARG001
        return None


class ConversationMessage(BaseModel):
    """A single message in a conversation history (deprecated — kept for backward compatibility).

    Attributes:
        role: Speaker role ('user' or 'assistant').
        content: Message text content.
    """

    role: str
    content: str


class QARequest(BaseModel):
    """Request body for the Code Q&A streaming endpoint.

    Attributes:
        question: The user's question (1–1000 characters).
        context_level: Either 'architecture' or 'module'.
        context_doc_id: Optional doc ID to use as context.
        module_path: Relative path of the focused module when context_level='module'.
        module_name: Human-readable name of the focused module.
        conversation_id: ID of the existing conversation to continue, or None to start a new one.
        conversation_history: Deprecated; ignored server-side.
        context_chips: Active UI chips that modify retrieval behaviour (e.g. 'findusages').
    """

    question: str = Field(..., min_length=1, max_length=1000)
    context_level: str = Field(..., pattern="^(architecture|module)$")
    context_doc_id: str | None = None
    module_path: str | None = None
    module_name: str | None = None
    conversation_id: str | None = Field(default=None)
    # Deprecated — server-side DB is the source of truth; this field is
    # accepted for backwards compatibility but ignored.
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    context_chips: list[str] = Field(default_factory=list)


class QARerenderRequest(BaseModel):
    """Request body for re-rendering a previously generated Q&A response.

    Attributes:
        render_id: Identifier of the response to re-render.
        tone: Target tone — 'technical' or 'functional'.
    """

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
    """Fetch a project by ID or raise HTTP 404.

    Args:
        project_id: The project identifier to look up.
        db: Active database session.

    Returns:
        The matching Project ORM row.

    Raises:
        HTTPException: With status 404 if the project does not exist.
    """
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
    db_session_factory: Callable[[], Session],
    config: CodeUnderstandingConfig,
    q: queue.Queue[str | None | dict[str, object]],
    context_chips: list[str] | None = None,
    symbol_hint: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """Run QAEngine.answer_stream_v2() in a daemon thread, pushing events into a queue."""
    from orch.rag.qa import QAEngine

    engine = QAEngine(project_id=project_id, config=config)

    async def produce_tokens() -> None:
        try:
            # Use session from factory (fresh session per thread)
            session = db_session_factory()
            stream = engine.answer_stream_v2(
                question=question,
                context_level=context_level,
                context_doc_id=context_doc_id,
                conversation_history=[],  # Deprecated — server-side DB is source
                session=session,
                module_path=module_path,
                module_name=module_name,
                context_chips=context_chips,
                symbol_hint=symbol_hint,
                conversation_id=conversation_id,
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
    conversation_id: str,
    session_factory: Callable[[], Session],
    config: CodeUnderstandingConfig,
    context_chips: list[str] | None = None,
    symbol_hint: str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that runs QAEngine in a thread and yields SSE-formatted strings.

    On the leading `event: meta` frame is emitted before any token events.
    On __DONE__ the assistant message is persisted and summarization is enqueued.
    On exception during streaming, partial content is persisted with metadata.error=true.
    """
    import concurrent.futures

    q: queue.Queue[str | None | dict[str, object]] = queue.Queue()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    loop = asyncio.get_event_loop()
    accumulated_text = ""
    processed_diagram_blocks: set[tuple[str, str]] = set()
    emit_counts: dict[str, int] = {"mermaid": 0, "d2": 0}

    # Emit meta event BEFORE any token — client must capture conversation_id
    meta_payload = json.dumps({"conversation_id": conversation_id})
    yield f"event: meta\ndata: {meta_payload}\n\n"

    executor.submit(
        _run_qa_in_thread,
        project_id,
        question,
        context_level,
        context_doc_id,
        module_path,
        module_name,
        session_factory,
        config,
        q,
        context_chips,
        symbol_hint,
        conversation_id,
    )

    assistant_content = ""
    try:
        while True:
            event = await loop.run_in_executor(None, q.get)
            if event is None:
                break
            if isinstance(event, dict):
                kind = event.get("kind", "token")
                if kind == "error":
                    error_message = event.get("message", "Unknown error")
                    if assistant_content:
                        db = session_factory()
                        try:
                            from orch.rag import chat_repo

                            chat_repo.append_message(
                                db,
                                conversation_id=conversation_id,
                                role="assistant",
                                content=assistant_content,
                                metadata={"error": True, "error_reason": str(error_message)},
                            )
                            db.commit()
                        except Exception:
                            logging.exception(
                                "Failed to persist partial assistant message on stream error",
                            )
                        finally:
                            if db is not None:
                                db.close()
                    payload = json.dumps({"message": error_message})
                    yield f"event: error\ndata: {payload}\n\n"
                    return
                if kind == "token":
                    token_text = str(event.get("text", ""))
                    b64 = base64.b64encode(token_text.encode("utf-8")).decode("ascii")
                    payload = json.dumps({"b64": b64})
                    yield f"event: token\ndata: {payload}\n\n"
                    accumulated_text += token_text
                    assistant_content += token_text
                    if _DIAGRAM_RENDER_AVAILABLE:
                        new_blocks = _find_new_diagram_blocks(
                            accumulated_text, processed_diagram_blocks
                        )
                        for lang, dsl in new_blocks:
                            processed_diagram_blocks.add((lang, dsl))
                            render_func = render_mermaid if lang == "mermaid" else render_d2
                            svg = await loop.run_in_executor(None, render_func, dsl)
                            if svg:
                                svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
                                img_payload = json.dumps(
                                    {
                                        "svg_b64": svg_b64,
                                        "alt": "Diagram",
                                        "source_type": lang,
                                        "block_index": emit_counts[lang],
                                    }
                                )
                                yield f"event: image\ndata: {img_payload}\n\n"
                            emit_counts[lang] += 1
                elif kind == "phase":
                    payload = json.dumps(
                        {"name": event.get("name"), "detail": event.get("detail", {})}
                    )
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
                accumulated_text += str(event)
                assistant_content += str(event)
                if _DIAGRAM_RENDER_AVAILABLE:
                    new_blocks = _find_new_diagram_blocks(
                        accumulated_text, processed_diagram_blocks
                    )
                    for lang, dsl in new_blocks:
                        processed_diagram_blocks.add((lang, dsl))
                        render_func = render_mermaid if lang == "mermaid" else render_d2
                        svg = await loop.run_in_executor(None, render_func, dsl)
                        if svg:
                            svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
                            img_payload = json.dumps(
                                {
                                    "svg_b64": svg_b64,
                                    "alt": "Diagram",
                                    "source_type": lang,
                                    "block_index": emit_counts[lang],
                                }
                            )
                            yield f"event: image\ndata: {img_payload}\n\n"
                        emit_counts[lang] += 1

    except Exception as exc:
        # Stream interrupted — persist partial assistant content with error flag
        logging.warning(
            "code_qa stream interrupted: %s: %s\n%s",
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
        # Persist partial assistant message with error flag
        db = session_factory()
        try:
            from orch.rag import chat_repo

            chat_repo.append_message(
                db,
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                metadata={"error": True, "error_reason": str(exc)},
            )
            db.commit()
        except Exception:
            logging.exception("Failed to persist partial assistant message during stream error")
        finally:
            if db is not None:
                db.close()
        # Re-raise so the error event is also yielded
        raise

    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    # __DONE__ sentinel reached — persist the complete assistant message
    if assistant_content:
        db = session_factory()
        if db is None:
            logging.warning("session_factory returned None, skipping assistant message persistence")
        else:
            try:
                from orch.rag import chat_repo

                chat_repo.append_message(
                    db,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_content,
                    metadata={},
                )
                db.commit()

                # Enqueue summarization if hard budget exceeded
                from orch.rag.qa import HISTORY_HARD_BUDGET_TOKENS

                job = chat_repo.enqueue_summarization_if_needed(
                    db,
                    conversation_id=conversation_id,
                    hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
                )
                if job:
                    logging.info(
                        "Enqueued ChatSummarizationJob %s for conversation %s",
                        job.id,
                        conversation_id,
                    )
                db.commit()
            except Exception:
                logging.exception("Failed to persist assistant message after __DONE__")
            finally:
                if db is not None:
                    db.close()

    done_payload = json.dumps({"ok": True})
    yield f"event: done\ndata: {done_payload}\n\n"


@router.post("/projects/{project_id}/code/qa")
async def code_qa(
    project_id: str,
    request: QARequest,
    fastapi_request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    SSE streaming endpoint for Code Q&A.

    Validates the project exists and that a LanceDB index exists on disk,
    then streams tokens from QAEngine.answer_stream().

    On first turn (conversation_id=None), creates a new ChatConversation
    and persists the user message before spawning the worker thread.
    Emits a leading `event: meta` frame with the conversation_id.
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

    session_id = get_session_id(fastapi_request)

    # Resolve or create conversation; persist user message synchronously
    # before the worker thread is spawned.
    from orch.rag import chat_repo

    conv = chat_repo.get_or_create_conversation(
        db,
        project_id=project_id,
        session_id=session_id,
        conversation_id=request.conversation_id,
        module_path=request.module_path,
        context_level=request.context_level,
        first_question=request.question,
    )
    db.commit()  # Ensure row exists before thread spawns

    # Persist user message BEFORE thread spawn (so row exists if thread crashes)
    chat_repo.append_message(
        db,
        conversation_id=conv.id,
        role="user",
        content=request.question,
    )
    db.commit()

    symbol_hint = request.question.strip() if "findusages" in request.context_chips else None

    return StreamingResponse(
        _sse_generator(
            project_id=project_id,
            question=request.question,
            context_level=request.context_level,
            context_doc_id=request.context_doc_id,
            module_path=request.module_path,
            module_name=request.module_name,
            conversation_id=conv.id,
            session_factory=lambda: SessionLocal(),
            context_chips=request.context_chips,
            symbol_hint=symbol_hint,
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
