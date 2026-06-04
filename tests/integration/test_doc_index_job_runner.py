"""Integration tests for DocIndexJobRunner + JOB_REGISTRY_DOC (orch/rag/doc_job.py).

Mirrors test_code_index_pipeline.py for the doc indexing side.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

from orch.db.models import DocIndexJob, Project, WorkItem, WorkItemType
from orch.rag.config import CodeUnderstandingConfig
from orch.rag.doc_indexer import DocIndexer
from orch.rag.doc_job import (
    JOB_REGISTRY_DOC,
    DocIndexJobRunner,
    JobAlreadyRunningError,
    start_doc_index_job,
)

MOCK_EMBED_MODEL = "test-embed-model"


def mock_embed(text: str) -> list[float]:
    vec = [0.0] * 8
    h = sum(text.encode()[:4])
    vec[h % 8] = 0.5 + (h % 10) * 0.05
    return vec


class MockOllamaEmbedding:
    model_name = MOCK_EMBED_MODEL

    def __init__(self, **kwargs: object) -> None:
        pass

    def get_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)


def create_doc_indexer(
    project_id: str,
    index_path: str,
    db_session_factory: sessionmaker,
) -> DocIndexer:
    config = CodeUnderstandingConfig(
        provider="local",
        embed_model=MOCK_EMBED_MODEL,
        ollama_url="http://localhost:11434",
        index_path=index_path,
    )
    return DocIndexer(
        project_id=project_id,
        config=config,
        index_path=index_path,
        db_session_factory=db_session_factory,
    )


def create_project_with_items(
    session: Session,
    project_id: str,
    item_ids: list[str],
) -> Project:
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    for wid in item_ids:
        item = WorkItem(
            project_id=project.id,
            id=wid,
            title=f"Item {wid}",
            type=WorkItemType.Feature,
            functional_doc_content=f"Functional doc content for {wid}.",
            updated_at=now,
        )
        session.add(item)
    session.flush()
    return project


def create_project_with_items_and_job(
    session_factory: sessionmaker,
    project_id: str,
    item_ids: list[str],
) -> tuple[str, str]:
    with session_factory() as session:
        project = Project(
            id=project_id,
            display_name=f"Test Project {project_id}",
            repo_root="/repos/test",
            config={},
        )
        session.add(project)
        session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        for wid in item_ids:
            item = WorkItem(
                project_id=project.id,
                id=wid,
                title=f"Item {wid}",
                type=WorkItemType.Feature,
                functional_doc_content=f"Functional doc content for {wid}.",
                updated_at=now,
            )
            session.add(item)

        job = DocIndexJob(project_id=project.id, status="queued")
        session.add(job)
        session.flush()
        session.commit()
        return job.id, project.id


class TestDocIndexJobRunnerBasic:
    def test_runner_status_transitions(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Runner enqueue + execute → status transitions queued → running → completed."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-runner-status"
        job_id, _ = create_project_with_items_and_job(
            test_session_factory, project_id, ["WI-RUNNER-1"]
        )

        index_path = str(tmp_path / "index")

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )

        runner = DocIndexJobRunner(
            job_id=job_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            asyncio.run(runner.run())

        with test_session_factory() as session:
            refreshed_job = session.get(DocIndexJob, job_id)
            assert refreshed_job is not None
            assert refreshed_job.status == "completed", (
                f"Expected status=completed, got {refreshed_job.status}"
            )
            assert refreshed_job.started_at is not None
            assert refreshed_job.completed_at is not None
            assert refreshed_job.items_indexed == 1
            assert refreshed_job.chunks_created > 0

    def test_second_register_raises_job_already_running(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Second register() for same project raises JobAlreadyRunningError."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-dup-runner"

        with test_session_factory() as session:
            project = Project(
                id=project_id,
                display_name=f"Test Project {project_id}",
                repo_root="/repos/test",
                config={},
            )
            session.add(project)
            session.flush()

            now = datetime.now(UTC).replace(tzinfo=None)
            item = WorkItem(
                project_id=project.id,
                id="WI-DUP-1",
                title="Item WI-DUP-1",
                type=WorkItemType.Feature,
                functional_doc_content="Functional doc content for WI-DUP-1.",
                updated_at=now,
            )
            session.add(item)

            job1 = DocIndexJob(project_id=project.id, status="queued")
            job2 = DocIndexJob(project_id=project.id, status="queued")
            session.add(job1)
            session.add(job2)
            session.flush()
            session.commit()
            job1_id = job1.id
            job2_id = job2.id

        index_path = str(tmp_path / "index")

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )

        runner1 = DocIndexJobRunner(
            job_id=job1_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )
        start_doc_index_job(job1, config=config, runner=runner1)

        try:
            runner2 = DocIndexJobRunner(
                job_id=job2_id,
                project_id=project_id,
                config=config,
                index_path=index_path,
                db_session_factory=test_session_factory,
            )
            with pytest.raises(JobAlreadyRunningError) as exc_info:
                start_doc_index_job(job2, config=config, runner=runner2)
            assert exc_info.value.project_id == project_id
        finally:
            JOB_REGISTRY_DOC.pop(project_id, None)

    def test_runner_counts_persisted(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Counters (items_discovered, items_indexed, chunks_created) are written to DB."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-counts"
        job_id, _ = create_project_with_items_and_job(
            test_session_factory, project_id, ["WI-COUNT-1", "WI-COUNT-2", "WI-COUNT-3"]
        )

        index_path = str(tmp_path / "index")

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )

        runner = DocIndexJobRunner(
            job_id=job_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            asyncio.run(runner.run())

        with test_session_factory() as session:
            refreshed_job = session.get(DocIndexJob, job_id)
            assert refreshed_job is not None
            assert refreshed_job.items_discovered == 3
            assert refreshed_job.items_indexed == 3
            assert refreshed_job.chunks_created > 0

    def test_error_on_missing_embed_model(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """If embedding fails, job status → failed and error_message is set."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-err"
        job_id, _ = create_project_with_items_and_job(
            test_session_factory, project_id, ["WI-ERR-1"]
        )

        index_path = str(tmp_path / "index")

        class FailingOllamaEmbedding:
            model_name = "fail-model"

            def __init__(self, **kwargs: object) -> None:
                pass

            def get_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError("Ollama is unreachable")

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model="fail-model",
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )

        runner = DocIndexJobRunner(
            job_id=job_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", FailingOllamaEmbedding):
            asyncio.run(runner.run())

        with test_session_factory() as session:
            refreshed_job = session.get(DocIndexJob, job_id)
            assert refreshed_job is not None
            assert refreshed_job.status == "failed"
            assert refreshed_job.error_message is not None
            assert (
                "Ollama" in refreshed_job.error_message
                or "unreachable" in refreshed_job.error_message.lower()
            )


class TestDocIndexJobRunnerWatermark:
    def test_watermark_skips_already_indexed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Re-index uses watermark to skip unchanged items."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-wm"

        with test_session_factory() as session:
            project = Project(
                id=project_id,
                display_name=f"Test Project {project_id}",
                repo_root="/repos/test",
                config={},
            )
            session.add(project)
            session.flush()

            now = datetime.now(UTC).replace(tzinfo=None)
            items = [
                WorkItem(
                    project_id=project.id,
                    id="WI-WM-1",
                    title="Item 1",
                    type=WorkItemType.Feature,
                    functional_doc_content="Content for item 1.",
                    updated_at=now,
                ),
                WorkItem(
                    project_id=project.id,
                    id="WI-WM-2",
                    title="Item 2",
                    type=WorkItemType.Issue,
                    functional_doc_content="Content for item 2.",
                    updated_at=now,
                ),
            ]
            for item in items:
                session.add(item)

            job = DocIndexJob(project_id=project.id, status="queued")
            session.add(job)
            session.flush()
            session.commit()
            job_id = job.id

        index_path = str(tmp_path / "index")

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )

        runner = DocIndexJobRunner(
            job_id=job_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            asyncio.run(runner.run())

        with test_session_factory() as session:
            job2 = DocIndexJob(project_id=project_id, status="queued")
            session.add(job2)
            session.flush()
            session.commit()
            job2_id = job2.id

        runner2 = DocIndexJobRunner(
            job_id=job2_id,
            project_id=project_id,
            config=config,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            asyncio.run(runner2.run())

        with test_session_factory() as session:
            refreshed_job2 = session.get(DocIndexJob, job2_id)
            assert refreshed_job2 is not None
            assert refreshed_job2.items_indexed == 0, (
                f"Expected 0 new items (all unchanged), got {refreshed_job2.items_indexed}"
            )
