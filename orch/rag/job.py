"""CodeIndexJobRunner + JOB_REGISTRY — asyncio background job for code indexing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal

from orch.db.models import CodeIndexJob, Project
from orch.rag.config import CodeUnderstandingConfig

JOB_REGISTRY: dict[str, CodeIndexJobRunner] = {}


class JobAlreadyRunningError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"A code index job is already running for project {project_id}")
        self.project_id = project_id


class CodeIndexJobRunner:
    def __init__(
        self,
        job_id: str,
        project_id: str,
        repo_path: str,
        config: CodeUnderstandingConfig,
        index_path: str,
        *,
        reindex: bool = False,
        mapgen_only: bool = False,
        db_session_factory: Any = None,
    ) -> None:
        self.job_id = job_id
        self.project_id = project_id
        self.repo_path = repo_path
        self.config = config
        self.index_path = index_path
        self.reindex = reindex
        self.mapgen_only = mapgen_only
        self._db_session_factory = db_session_factory
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._cancel_requested = False

    @property
    def progress_queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._queue

    def request_cancel(self) -> None:
        self._cancel_requested = True

    async def run(self) -> None:
        from orch.rag.indexer import CodeIndexer

        try:
            await self._db_set_status_async(self.job_id, "running")

            if self.mapgen_only:
                prev = await asyncio.to_thread(self._read_counters, self.job_id)
                self._queue.put_nowait(
                    {
                        "event": "progress",
                        "phase": "mapgen",
                        "files_indexed": prev["files_indexed"],
                        "files_total": prev["files_discovered"] or prev["files_indexed"],
                        "chunks_created": prev["chunks_created"],
                    }
                )
                if self._cancel_requested:
                    await self._handle_cancel()
                    return
                await self._run_mapgen(
                    prev["files_indexed"],
                    prev["chunks_created"],
                    prev["files_discovered"],
                    prev["languages_detected"],
                )
                await self._db_set_status_async(self.job_id, "completed", completed=True)
                self._queue.put_nowait({"event": "progress", "phase": "done"})
                return

            indexer = CodeIndexer(
                project_id=self.project_id,
                config=self.config,
                index_path=self.index_path,
            )

            def progress_callback(event: dict[str, Any]) -> None:
                self._queue.put_nowait(event)

            if self.reindex:
                result = await indexer.reindex_changed(
                    self.repo_path,
                    self.job_id,
                    progress_callback,
                )
            else:
                result = await indexer.index(
                    self.repo_path,
                    self.job_id,
                    progress_callback,
                )

            if self._cancel_requested:
                await self._handle_cancel()
                return

            await asyncio.to_thread(
                self._persist_counters,
                self.job_id,
                result.files_indexed,
                result.chunks_created,
                result.files_discovered,
                result.languages_detected,
                list(result.errors),
            )

            self._queue.put_nowait(
                {
                    "event": "progress",
                    "phase": "mapgen",
                    "files_indexed": result.files_indexed,
                    "files_total": result.files_discovered or result.files_indexed,
                    "chunks_created": result.chunks_created,
                }
            )

            await self._run_mapgen(
                result.files_indexed,
                result.chunks_created,
                result.files_discovered,
                list(result.languages_detected),
            )

            await self._db_set_status_async(self.job_id, "completed", completed=True)
            self._queue.put_nowait({"event": "progress", "phase": "done"})

            try:
                from orch.rag.index_gen import generate_index_page

                def do_index() -> None:
                    from orch.db import session as db_session_module

                    factory = self._db_session_factory or db_session_module.SessionLocal
                    with factory() as sess:
                        generate_index_page(project_id=self.project_id, session=sess)

                await asyncio.to_thread(do_index)
            except Exception as exc:
                import logging

                logging.warning(
                    "Index page generation failed for project %s (non-fatal): %s",
                    self.project_id,
                    exc,
                )

        except asyncio.CancelledError:
            await self._handle_cancel()
        except Exception as e:
            self._queue.put_nowait(
                {
                    "event": "progress",
                    "phase": "error",
                    "message": str(e),
                }
            )
            await self._db_set_status_async(self.job_id, "failed", error=str(e), completed=True)
        finally:
            JOB_REGISTRY.pop(self.project_id, None)

    async def _run_mapgen(
        self,
        files_indexed: int,
        chunks_created: int,
        files_discovered: int,
        languages_detected: list[str],
    ) -> None:
        from orch.rag.mapgen import MapGenerator

        def cancel_check() -> bool:
            return self._cancel_requested

        doc = await MapGenerator().generate_level1(
            self.project_id,
            self.config,
            cancel_check=cancel_check,
            db_session_factory=self._db_session_factory,
        )

        def do_update() -> None:
            from orch.db import session as db_session_module

            factory = self._db_session_factory or db_session_module.SessionLocal
            with factory() as session:
                job = session.get(CodeIndexJob, self.job_id)
                if job:
                    job.doc_id = doc.id if doc is not None else None
                    job.files_indexed = files_indexed
                    job.chunks_created = chunks_created
                    job.files_discovered = files_discovered
                    if languages_detected:
                        job.languages_detected = list(languages_detected)
                    session.commit()

        await asyncio.to_thread(do_update)

    def _persist_counters(
        self,
        job_id: str,
        files_indexed: int,
        chunks_created: int,
        files_discovered: int,
        languages_detected: list[str],
        errors: list[str],
    ) -> None:
        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal
        with factory() as session:
            job = session.get(CodeIndexJob, job_id)
            if job is None:
                return
            job.files_indexed = files_indexed
            job.chunks_created = chunks_created
            job.files_discovered = files_discovered
            if languages_detected:
                job.languages_detected = list(languages_detected)
            if errors:
                merged = list(job.errors) if job.errors else []
                merged.extend(errors)
                job.errors = merged
            session.commit()

    def _read_counters(self, job_id: str) -> dict[str, Any]:
        from sqlalchemy import select

        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal
        with factory() as session:
            last_completed = session.scalar(
                select(CodeIndexJob)
                .where(
                    CodeIndexJob.project_id == self.project_id,
                    CodeIndexJob.status == "completed",
                    CodeIndexJob.id != job_id,
                )
                .order_by(CodeIndexJob.triggered_at.desc())
                .limit(1)
            )
            if last_completed is None:
                return {
                    "files_indexed": 0,
                    "chunks_created": 0,
                    "files_discovered": 0,
                    "languages_detected": [],
                }
            return {
                "files_indexed": last_completed.files_indexed or 0,
                "chunks_created": last_completed.chunks_created or 0,
                "files_discovered": last_completed.files_discovered or 0,
                "languages_detected": list(last_completed.languages_detected or []),
            }

    async def _handle_cancel(self) -> None:
        await self._db_set_status_async(self.job_id, "cancelled", cancelled=True, completed=True)
        self._queue.put_nowait(
            {
                "event": "progress",
                "phase": "cancelled",
            }
        )

    async def _db_set_status_async(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        cancelled: bool = False,
        completed: bool = False,
    ) -> None:
        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal

        def do_update() -> None:
            with factory() as session:
                job = session.get(CodeIndexJob, job_id)
                if job is None:
                    return
                job.status = status
                if error:
                    errors = list(job.errors) if job.errors else []
                    errors.append(error)
                    job.errors = errors
                if cancelled:
                    errors = list(job.errors) if job.errors else []
                    errors.append("cancelled by user")
                    job.errors = errors
                now = datetime.now(UTC)
                job.updated_at = now
                if completed:
                    job.completed_at = now
                if status == "completed" and completed:
                    from orch.db.models import DaemonEvent

                    session.add(
                        DaemonEvent(
                            project_id=job.project_id,
                            event_type="code_map_completed",
                            entity_id=job.id,
                            entity_type="doc_job",
                            message=(
                                f"Code map generated — "
                                f"{job.files_indexed} files, "
                                f"{job.chunks_created} chunks"
                            ),
                            event_metadata={
                                "job_id": job.id,
                                "llm_model": job.llm_model,
                                "embed_model": job.embed_model,
                                "index_tier": job.index_tier,
                                "files_indexed": job.files_indexed,
                                "chunks_created": job.chunks_created,
                                "duration_seconds": (
                                    int((job.completed_at - job.triggered_at).total_seconds())
                                    if job.completed_at and job.triggered_at
                                    else None
                                ),
                            },
                        )
                    )
                session.commit()

        await asyncio.to_thread(do_update)

    def _db_set_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        cancelled: bool = False,
        completed: bool = False,
    ) -> None:
        from orch.db import session as db_session_module

        factory = self._db_session_factory or db_session_module.SessionLocal
        with factory() as session:
            job = session.get(CodeIndexJob, job_id)
            if job is None:
                return
            job.status = status
            if error:
                errors = list(job.errors) if job.errors else []
                errors.append(error)
                job.errors = errors
            if cancelled:
                errors = list(job.errors) if job.errors else []
                errors.append("cancelled by user")
                job.errors = errors
            now = datetime.now(UTC)
            job.updated_at = now
            if completed:
                job.completed_at = now
            session.commit()


def start_index_job(
    job: CodeIndexJob,
    project: Project,
    *,
    mode: Literal["full", "incremental", "mapgen_only"],
    db_session_factory: Any | None = None,
    runner: CodeIndexJobRunner | None = None,
) -> CodeIndexJobRunner:
    if project.id in JOB_REGISTRY:
        raise JobAlreadyRunningError(project.id)

    project_config: dict[str, Any] = project.config or {}
    code_config = project_config.get("code_understanding", {})

    if runner is None:
        from orch.config import load_config

        cfg = load_config()
        index_path = code_config.get("index_path") or cfg.index_path
    else:
        index_path = runner.index_path

    config = CodeUnderstandingConfig(
        provider=code_config.get("provider", "local"),
        llm_model=code_config.get("llm_model"),
        embed_model=code_config.get("embed_model"),
        index_tier=code_config.get("index_tier", "balanced"),
        ollama_url=code_config.get("ollama_url", "http://localhost:11434"),
        index_path=index_path,
    )

    if runner is None:
        runner = CodeIndexJobRunner(
            job_id=job.id,
            project_id=project.id,
            repo_path=project.repo_root,
            config=config,
            index_path=index_path,
            reindex=(mode == "incremental"),
            mapgen_only=(mode == "mapgen_only"),
            db_session_factory=db_session_factory,
        )

    JOB_REGISTRY[project.id] = runner
    return runner
