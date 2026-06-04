"""Integration tests for orch/evidences:ingest_phase_from_disk.

Uses a real PostgreSQL testcontainer so the ON CONFLICT upsert
can be exercised without mocking.  Tests are run with `make test-integration`.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from orch.db.models import EvidencePhase, WorkItemEvidence
from orch.evidences import EvidenceTooLargeError, ingest_phase_from_disk

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_work_item(session: Session, project_id: str, item_id: str) -> None:
    from orch.db.models import WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

    session.add(
        WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test {item_id}",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
    )
    session.flush()


def _setup_evidence_dirs(
    root: Path, item_id: str, pre_files: dict[str, bytes], post_files: dict[str, bytes]
) -> tuple[Path, Path]:
    pre_dir = root / "ai-dev" / "active" / item_id / "evidences" / "pre"
    post_dir = root / "ai-dev" / "active" / item_id / "evidences" / "post"
    pre_dir.mkdir(parents=True)
    post_dir.mkdir(parents=True)
    for name, data in pre_files.items():
        (pre_dir / name).write_bytes(data)
    for name, data in post_files.items():
        (post_dir / name).write_bytes(data)
    return pre_dir, post_dir


class TestIngestPhaseFromDiskHappyPath:
    def test_ingest_two_pngs_and_one_yaml(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99999"
        pre_dir, _ = _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={
                "a.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
                "b.png": b"\x89PNG\r\n\x1a\n" + b"\x01" * 50,
                "c.yaml": b"key: value\n",
            },
            post_files={},
        )
        _make_work_item(db_session, "test-proj", item_id)

        count = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
            step_id=None,
        )
        assert count == 3

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id=item_id, phase=EvidencePhase.pre)
            .all()
        )
        assert len(rows) == 3

        for row in rows:
            disk_file = pre_dir / row.filename
            assert row.size_bytes == disk_file.stat().st_size
            expected_sha = _sha256(disk_file.read_bytes())
            actual_sha = _sha256(row.content)
            assert actual_sha == expected_sha, f"SHA256 mismatch for {row.filename}"

        content_types = {r.filename: r.content_type for r in rows}
        assert content_types["a.png"] == "image/png"
        assert content_types["b.png"] == "image/png"
        assert content_types["c.yaml"] == "application/yaml"


class TestIngestPhaseFromDiskEdgeCases:
    def test_missing_dir_returns_0_no_exception(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99998"
        _make_work_item(db_session, "test-proj", item_id)

        count = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )
        assert count == 0

        rows = db_session.query(WorkItemEvidence).filter_by(work_item_id=item_id).all()
        assert len(rows) == 0

    def test_empty_dir_returns_0_no_rows(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99997"
        pre_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "pre"
        pre_dir.mkdir(parents=True)
        _make_work_item(db_session, "test-proj", item_id)

        count = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )
        assert count == 0

        rows = db_session.query(WorkItemEvidence).filter_by(work_item_id=item_id).all()
        assert len(rows) == 0

    def test_non_file_entries_ignored(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        if sys.platform != "linux":
            pytest.skip("symlink is_file behavior is platform-dependent")
        item_id = "X-99996"
        pre_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "pre"
        pre_dir.mkdir(parents=True)
        (pre_dir / "subdir").mkdir()
        (pre_dir / "file.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        (pre_dir / "link.png").symlink_to(pre_dir / "file.png")
        _make_work_item(db_session, "test-proj", item_id)

        count = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )
        assert count == 1, f"expected 1 (file.png only), got {count}"

        rows = db_session.query(WorkItemEvidence).filter_by(work_item_id=item_id).all()
        assert len(rows) == 1, f"expected 1 row for file.png, got {len(rows)}"
        assert rows[0].filename == "file.png"


class TestIngestPhaseFromDiskOversize:
    def test_oversize_raises_evidence_too_large_error_no_rows_inserted(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99995"
        pre_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "pre"
        pre_dir.mkdir(parents=True)
        (pre_dir / "large.png").write_bytes(b"\x00" * 101)
        _make_work_item(db_session, "test-proj", item_id)

        max_bytes = 100
        with pytest.raises(EvidenceTooLargeError) as exc_info:
            ingest_phase_from_disk(
                session=db_session,
                project_id="test-proj",
                work_item_id=item_id,
                phase=EvidencePhase.pre,
                root=tmp_path,
                max_bytes=max_bytes,
            )

        assert exc_info.value.filename == "large.png"
        assert exc_info.value.size == 101
        assert exc_info.value.max_bytes == 100

        db_session.rollback()

        rows = db_session.query(WorkItemEvidence).filter_by(work_item_id=item_id).all()
        assert len(rows) == 0


class TestIngestPhaseFromDiskIdempotentUpsert:
    def test_ingest_twice_overwrites_content_and_size_bytes(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99994"
        pre_dir, _ = _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={"screenshot.png": b"version-A"},
            post_files={},
        )
        _make_work_item(db_session, "test-proj", item_id)

        count1 = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )
        assert count1 == 1

        (pre_dir / "screenshot.png").write_bytes(b"version-B-overwritten")

        count2 = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )
        assert count2 == 1

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                filename="screenshot.png",
            )
            .all()
        )
        assert len(rows) == 1
        assert rows[0].content == b"version-B-overwritten"
        assert rows[0].size_bytes == len(b"version-B-overwritten")

    def test_upsert_updates_step_id_when_step_id_changes(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99993"
        _, post_dir = _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={},
            post_files={"post1.png": b"post-bytes-1"},
        )
        _make_work_item(db_session, "test-proj", item_id)

        ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.post,
            root=tmp_path,
            step_id="S01",
        )

        row = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                filename="post1.png",
            )
            .one()
        )
        assert row.step_id == "S01"

        ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.post,
            root=tmp_path,
            step_id="S02",
        )

        db_session.refresh(row)
        assert row.step_id == "S02"


class TestIngestPhaseFromDiskMimeTypes:
    def test_unknown_extension_defaults_to_octet_stream(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99992"
        _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={"weird.bin": b"some bytes"},
            post_files={},
        )
        _make_work_item(db_session, "test-proj", item_id)

        ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )

        row = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                filename="weird.bin",
            )
            .one()
        )
        assert row.content_type == "application/octet-stream"

    def test_yaml_extension_registered_as_application_yaml(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99991"
        _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={
                "evidence.yaml": b"key: value\n",
                "evidence.yml": b"key: value\n",
            },
            post_files={},
        )
        _make_work_item(db_session, "test-proj", item_id)

        ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
        )

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id=item_id)
            .all()
        )
        assert len(rows) == 2
        content_types = {r.filename: r.content_type for r in rows}
        assert content_types["evidence.yaml"] == "application/yaml"
        assert content_types["evidence.yml"] == "application/yaml"


class TestIngestPhaseFromDiskConfigOverride:
    def test_max_bytes_parameter_overrides_env(
        self, tmp_path: Path, db_session: Session, test_project: object
    ) -> None:
        item_id = "X-99990"
        pre_dir, _ = _setup_evidence_dirs(
            tmp_path,
            item_id,
            pre_files={"small.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 50},
            post_files={},
        )
        _make_work_item(db_session, "test-proj", item_id)

        count = ingest_phase_from_disk(
            session=db_session,
            project_id="test-proj",
            work_item_id=item_id,
            phase=EvidencePhase.pre,
            root=tmp_path,
            max_bytes=100,
        )
        assert count == 1

        (pre_dir / "oversize.png").write_bytes(b"\x00" * 101)

        with pytest.raises(EvidenceTooLargeError) as exc_info:
            ingest_phase_from_disk(
                session=db_session,
                project_id="test-proj",
                work_item_id=item_id,
                phase=EvidencePhase.pre,
                root=tmp_path,
                max_bytes=100,
            )

        assert exc_info.value.filename == "oversize.png"
        assert exc_info.value.size == 101
        assert exc_info.value.max_bytes == 100
