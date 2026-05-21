"""Unit tests for the archive system.

Uses tmp_path for all file operations. DB session is mocked — no container required.
Tests focus on file I/O behaviour and pure logic (compression, extraction, TTL).
"""

from __future__ import annotations

import os
import tarfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import zstandard as zstd

from orch.archive.archiver import _compress_to_zstd, archive_work_item
from orch.archive.extractor import cleanup_expired, extract_archive, list_artifacts
from orch.db.models import WorkItemPhase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item(
    project_id: str = "proj",
    item_id: str = "I-00001",
    *,
    design_doc_path: str | None = None,
    archived_at: object = None,
) -> MagicMock:
    wi = MagicMock()
    wi.id = item_id
    wi.project_id = project_id
    wi.design_doc_path = design_doc_path
    wi.archived_at = archived_at
    wi.archive_path = None
    wi.archive_size_bytes = None
    wi.design_doc_content = None
    return wi


def _make_project(repo_root: str) -> MagicMock:
    proj = MagicMock()
    proj.repo_root = repo_root
    return proj


def _make_session(wi: MagicMock, project: MagicMock, steps: list | None = None) -> MagicMock:
    if steps is None:
        steps = []
    db = MagicMock()
    db.get.side_effect = lambda _model, key: (
        wi if (isinstance(key, tuple) and len(key) == 2) else project
    )
    scalars = MagicMock()
    scalars.all.return_value = steps
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    db.execute.return_value = execute_result
    return db


# ---------------------------------------------------------------------------
# Tier 1 — design doc stored in DB
# ---------------------------------------------------------------------------


def test_tier1_stores_design_doc_content(tmp_path: Path) -> None:
    """archive_work_item reads design doc from disk and writes to wi.design_doc_content."""
    doc = tmp_path / "I001_Design.md"
    doc.write_text("# Design\nSome content here.", encoding="utf-8")

    wi = _make_work_item(design_doc_path="I001_Design.md")
    db = _make_session(wi, _make_project(str(tmp_path)))

    archive_work_item(db, "proj", "I-00001", archive_dir=None)

    assert wi.design_doc_content == "# Design\nSome content here."


def test_tier1_skips_missing_design_doc(tmp_path: Path) -> None:
    """archive_work_item does not fail if design doc file is missing."""
    wi = _make_work_item(design_doc_path="missing.md")
    db = _make_session(wi, _make_project(str(tmp_path)))

    archive_work_item(db, "proj", "I-00001", archive_dir=None)

    assert wi.design_doc_content is None


def test_tier1_stores_report_content_for_each_step(tmp_path: Path) -> None:
    """archive_work_item reads each step report and writes to step.report_content."""
    report_a = tmp_path / "report_a.md"
    report_b = tmp_path / "report_b.md"
    report_a.write_text("Report A content", encoding="utf-8")
    report_b.write_text("Report B content", encoding="utf-8")

    step_a = MagicMock()
    step_a.report_file = "report_a.md"
    step_a.report_content = None

    step_b = MagicMock()
    step_b.report_file = "report_b.md"
    step_b.report_content = None

    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path)), steps=[step_a, step_b])

    archive_work_item(db, "proj", "I-00001", archive_dir=None)

    assert step_a.report_content == "Report A content"
    assert step_b.report_content == "Report B content"


def test_tier1_sets_phase_done(tmp_path: Path) -> None:
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path)))

    archive_work_item(db, "proj", "I-00001", archive_dir=None)

    assert wi.phase == WorkItemPhase.done


def test_tier1_sets_archived_at(tmp_path: Path) -> None:
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path)))

    archive_work_item(db, "proj", "I-00001", archive_dir=None)

    assert wi.archived_at is not None


# ---------------------------------------------------------------------------
# Tier 2 — .tar.zst creation
# ---------------------------------------------------------------------------


def test_tier2_creates_tar_zst(tmp_path: Path) -> None:
    """archive_work_item creates a .tar.zst archive in the correct location."""
    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "file.txt").write_text("hello", encoding="utf-8")

    archive_dir = tmp_path / "archives"
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    expected = archive_dir / "proj" / "I-00001.tar.zst"
    assert expected.exists()
    assert expected.stat().st_size > 0


def test_tier2_records_archive_path_and_size(tmp_path: Path) -> None:
    """archive_work_item stores archive_path and archive_size_bytes in the DB."""
    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "doc.md").write_text("content", encoding="utf-8")

    archive_dir = tmp_path / "archives"
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    assert wi.archive_path == "proj/I-00001.tar.zst"
    assert isinstance(wi.archive_size_bytes, int)
    assert wi.archive_size_bytes > 0


def test_tier2_archive_contains_correct_files(tmp_path: Path) -> None:
    """The .tar.zst archive contains the expected files from the work item folder."""
    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "design.md").write_text("# Design", encoding="utf-8")
    sub = work_item_dir / "prompts"
    sub.mkdir()
    (sub / "prompt.txt").write_text("prompt content", encoding="utf-8")

    archive_dir = tmp_path / "archives"
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    archive_path = archive_dir / "proj" / "I-00001.tar.zst"
    dctx = zstd.ZstdDecompressor()
    with (
        archive_path.open("rb") as f_in,
        dctx.stream_reader(f_in) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,  # type: ignore[arg-type]
    ):
        names = tar.getnames()

    assert any("design.md" in n for n in names)
    assert any("prompt.txt" in n for n in names)


def test_tier2_cleanup_deletes_source_folder(tmp_path: Path) -> None:
    """When cleanup=True, the work item source folder is deleted after archiving."""
    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "file.txt").write_text("data", encoding="utf-8")

    archive_dir = tmp_path / "archives"
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=True)

    assert not work_item_dir.exists()


def test_tier2_no_cleanup_preserves_source_folder(tmp_path: Path) -> None:
    """When cleanup=False, the work item source folder is preserved."""
    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "file.txt").write_text("data", encoding="utf-8")

    archive_dir = tmp_path / "archives"
    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    assert work_item_dir.exists()
    assert (work_item_dir / "file.txt").exists()


# ---------------------------------------------------------------------------
# Tier 2 — work folder (ai-dev/work/<id>/) archiving + cleanup
# ---------------------------------------------------------------------------


def test_tier2_archives_work_folder(tmp_path: Path) -> None:
    """The .tar.zst captures the ai-dev/work/<id>/ tree (reports, logs, findings)."""
    repos = tmp_path / "repos"
    active_dir = repos / "ai-dev" / "active" / "I-00001"
    active_dir.mkdir(parents=True)
    (active_dir / "design.md").write_text("# Design", encoding="utf-8")
    reports = repos / "ai-dev" / "work" / "I-00001" / "reports"
    reports.mkdir(parents=True)
    (reports / "I-00001_S02_CodeReview_report.md").write_text("findings", encoding="utf-8")

    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(repos)))
    archive_work_item(db, "proj", "I-00001", archive_dir=tmp_path / "archives", cleanup=False)

    archive_path = tmp_path / "archives" / "proj" / "I-00001.tar.zst"
    dctx = zstd.ZstdDecompressor()
    with (
        archive_path.open("rb") as f_in,
        dctx.stream_reader(f_in) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,  # type: ignore[arg-type]
    ):
        names = tar.getnames()

    assert any(n.endswith("I-00001_S02_CodeReview_report.md") for n in names)


def test_tier2_cleanup_deletes_work_folder(tmp_path: Path) -> None:
    """cleanup=True removes ai-dev/work/<id>/, not only the active folder."""
    repos = tmp_path / "repos"
    active_dir = repos / "ai-dev" / "active" / "I-00001"
    active_dir.mkdir(parents=True)
    (active_dir / "design.md").write_text("# Design", encoding="utf-8")
    work_dir = repos / "ai-dev" / "work" / "I-00001"
    (work_dir / "reports").mkdir(parents=True)
    (work_dir / "reports" / "r.md").write_text("report", encoding="utf-8")

    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(repos)))
    archive_work_item(db, "proj", "I-00001", archive_dir=tmp_path / "archives", cleanup=True)

    assert not active_dir.exists()
    assert not work_dir.exists()


def test_tier2_archives_work_folder_when_active_folder_absent(tmp_path: Path) -> None:
    """The work folder is still archived and removed when no active folder exists."""
    repos = tmp_path / "repos"
    work_dir = repos / "ai-dev" / "work" / "I-00001"
    work_dir.mkdir(parents=True)
    (work_dir / "I-00001_self_assess_findings.json").write_text("{}", encoding="utf-8")

    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(repos)))
    archive_work_item(db, "proj", "I-00001", archive_dir=tmp_path / "archives", cleanup=True)

    archive_path = tmp_path / "archives" / "proj" / "I-00001.tar.zst"
    assert archive_path.exists()
    assert not work_dir.exists()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotent_second_call_skips_tier2(tmp_path: Path) -> None:
    """Second archive_work_item call (archived_at already set) skips Tier 2."""
    from datetime import UTC, datetime

    work_item_dir = tmp_path / "repos" / "ai-dev" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "file.txt").write_text("data", encoding="utf-8")

    archive_dir = tmp_path / "archives"

    wi = _make_work_item()
    db = _make_session(wi, _make_project(str(tmp_path / "repos")))
    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    first_size = wi.archive_size_bytes

    # Simulate already archived (archive_path set by first call)
    wi.archived_at = datetime.now(UTC)

    archive_work_item(db, "proj", "I-00001", archive_dir=archive_dir, cleanup=False)

    assert wi.archive_size_bytes == first_size


# ---------------------------------------------------------------------------
# extract_archive
# ---------------------------------------------------------------------------


def _make_archive(archive_path: Path, source_dir: Path, arcname: str) -> None:
    _compress_to_zstd([(source_dir, arcname)], archive_path)


def test_extract_archive_creates_extraction_path(tmp_path: Path) -> None:
    """extract_archive decompresses archive into expected path."""
    source = tmp_path / "source" / "I-00001"
    source.mkdir(parents=True)
    (source / "file.txt").write_text("hello", encoding="utf-8")

    archive_dir = tmp_path / "archives" / "proj"
    archive_dir.mkdir(parents=True)
    _make_archive(archive_dir / "I-00001.tar.zst", source, arcname="I-00001")

    result = extract_archive("proj", "I-00001", tmp_path / "archives", tmp_path / "tmp")

    assert result.exists()
    assert result == tmp_path / "tmp" / "iw-archive-view" / "proj" / "I-00001"


def test_extract_archive_file_contents_correct(tmp_path: Path) -> None:
    """Extracted archive contains original file with correct content."""
    source = tmp_path / "source" / "I-00001"
    source.mkdir(parents=True)
    (source / "design.md").write_text("# Hello", encoding="utf-8")

    archive_dir = tmp_path / "archives" / "proj"
    archive_dir.mkdir(parents=True)
    _make_archive(archive_dir / "I-00001.tar.zst", source, arcname="I-00001")

    extraction = extract_archive("proj", "I-00001", tmp_path / "archives", tmp_path / "tmp")

    extracted_file = extraction / "I-00001" / "design.md"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "# Hello"


def test_extract_archive_reuses_existing_within_ttl(tmp_path: Path) -> None:
    """Second extract_archive call reuses existing extraction and returns same path."""
    source = tmp_path / "source" / "I-00001"
    source.mkdir(parents=True)
    (source / "f.txt").write_text("x", encoding="utf-8")

    archive_dir = tmp_path / "archives" / "proj"
    archive_dir.mkdir(parents=True)
    _make_archive(archive_dir / "I-00001.tar.zst", source, arcname="I-00001")

    path1 = extract_archive("proj", "I-00001", tmp_path / "archives", tmp_path / "tmp")
    path2 = extract_archive("proj", "I-00001", tmp_path / "archives", tmp_path / "tmp")

    assert path1 == path2


def test_extract_archive_not_found_raises(tmp_path: Path) -> None:
    """extract_archive raises FileNotFoundError when archive is missing."""
    with pytest.raises(FileNotFoundError):
        extract_archive("proj", "MISSING", tmp_path / "archives", tmp_path / "tmp")


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------


def test_cleanup_expired_removes_old_extractions(tmp_path: Path) -> None:
    """cleanup_expired deletes directories older than ttl_seconds."""
    item_dir = tmp_path / "iw-archive-view" / "proj" / "I-00001"
    item_dir.mkdir(parents=True)

    old_time = time.time() - 7200
    os.utime(item_dir, (old_time, old_time))

    deleted = cleanup_expired(tmp_path, ttl_seconds=3600)

    assert deleted == 1
    assert not item_dir.exists()


def test_cleanup_expired_keeps_fresh_extractions(tmp_path: Path) -> None:
    """cleanup_expired does not delete directories within TTL."""
    item_dir = tmp_path / "iw-archive-view" / "proj" / "I-00001"
    item_dir.mkdir(parents=True)

    deleted = cleanup_expired(tmp_path, ttl_seconds=3600)

    assert deleted == 0
    assert item_dir.exists()


def test_cleanup_expired_no_view_dir_returns_zero(tmp_path: Path) -> None:
    """cleanup_expired returns 0 when iw-archive-view does not exist."""
    deleted = cleanup_expired(tmp_path, ttl_seconds=3600)
    assert deleted == 0


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


def test_list_artifacts_returns_file_tree(tmp_path: Path) -> None:
    """list_artifacts returns all files and dirs with correct metadata."""
    root = tmp_path / "extracted"
    root.mkdir()
    (root / "design.md").write_text("hello", encoding="utf-8")
    sub = root / "prompts"
    sub.mkdir()
    (sub / "prompt.txt").write_text("prompt", encoding="utf-8")

    results = list_artifacts(root)

    types = {r["relative_path"]: r["type"] for r in results}
    assert types["prompts"] == "dir"
    assert types["design.md"] == "file"
    assert types[str(Path("prompts") / "prompt.txt")] == "file"


def test_list_artifacts_file_size(tmp_path: Path) -> None:
    """list_artifacts reports correct file sizes."""
    root = tmp_path / "extracted"
    root.mkdir()
    content = "hello world"
    (root / "file.txt").write_text(content, encoding="utf-8")

    results = list_artifacts(root)

    file_entry = next(r for r in results if r["name"] == "file.txt")
    assert file_entry["size"] == len(content.encode("utf-8"))


def test_list_artifacts_dir_size_is_zero(tmp_path: Path) -> None:
    """list_artifacts reports size=0 for directories."""
    root = tmp_path / "extracted"
    sub = root / "subdir"
    sub.mkdir(parents=True)

    results = list_artifacts(root)

    dir_entry = next(r for r in results if r["type"] == "dir")
    assert dir_entry["size"] == 0


def test_list_artifacts_empty_dir(tmp_path: Path) -> None:
    """list_artifacts returns empty list for an empty directory."""
    root = tmp_path / "extracted"
    root.mkdir()

    results = list_artifacts(root)

    assert results == []
