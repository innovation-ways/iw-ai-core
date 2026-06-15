"""Unit tests for doc-system distribution (orch.skills.sync_doc_system).

Covers recursive copy with structure preservation, idempotency (byte-identical
skip), check-only mode (no writes), the platform-repo self no-op, the
missing-source error path, and the critical catalog-exclusion guarantee — a
project's own ``catalog/`` is never overwritten or created by a sync.
"""

from __future__ import annotations

from pathlib import Path

from orch.skills.sync_doc_system import sync_doc_system


def _make_doc_system_src(root: Path) -> Path:
    """Create a small ai-dev/doc-system master tree under ``root``.

    Includes a project-specific ``catalog/`` subtree to exercise the exclusion.

    Args:
        root: Directory to treat as the platform repo root.

    Returns:
        The created ``ai-dev/doc-system`` source directory.
    """
    src = root / "ai-dev" / "doc-system"
    (src / "brand").mkdir(parents=True)
    (src / "editorial").mkdir(parents=True)
    (src / "catalog").mkdir(parents=True)
    (src / "CLAUDE.md").write_text("system instructions\n", encoding="utf-8")
    (src / "brand" / "brand.json").write_text('{"name": "Innovation Ways"}', encoding="utf-8")
    (src / "editorial" / "_default.md").write_text("default editorial\n", encoding="utf-8")
    (src / "catalog" / "index.json").write_text('{"documents": []}', encoding="utf-8")
    return src


def test_sync_copies_shared_tree_preserving_structure(tmp_path: Path) -> None:
    """Verifies brand/editorial/top-level files land at the matching project paths."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_doc_system(project, src)

    assert sorted(result.copied) == ["CLAUDE.md", "brand/brand.json", "editorial/_default.md"]
    assert (
        project / "ai-dev" / "doc-system" / "brand" / "brand.json"
    ).read_text() == '{"name": "Innovation Ways"}'
    assert result.errors == []


def test_sync_never_touches_project_catalog(tmp_path: Path) -> None:
    """Verifies the project-specific catalog/ is skipped and never written."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_doc_system(project, src)

    assert result.skipped == ["catalog/index.json"]
    assert not (project / "ai-dev" / "doc-system" / "catalog").exists()


def test_sync_preserves_existing_project_catalog(tmp_path: Path) -> None:
    """Verifies a pre-existing project catalog is left byte-for-byte unchanged."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    catalog = project / "ai-dev" / "doc-system" / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "index.json").write_text('{"documents": ["PROJECT-OWNED"]}', encoding="utf-8")

    sync_doc_system(project, src)

    assert (catalog / "index.json").read_text() == '{"documents": ["PROJECT-OWNED"]}'


def test_sync_is_idempotent(tmp_path: Path) -> None:
    """Verifies a second sync reports files up-to-date and copies nothing."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    sync_doc_system(project, src)
    second = sync_doc_system(project, src)

    assert second.copied == []
    assert sorted(second.up_to_date) == [
        "CLAUDE.md",
        "brand/brand.json",
        "editorial/_default.md",
    ]


def test_sync_recopies_changed_file(tmp_path: Path) -> None:
    """Verifies a drifted target file is re-copied on the next sync."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()
    sync_doc_system(project, src)

    target = project / "ai-dev" / "doc-system" / "brand" / "brand.json"
    target.write_text("STALE", encoding="utf-8")

    result = sync_doc_system(project, src)

    assert "brand/brand.json" in result.copied
    assert target.read_text() == '{"name": "Innovation Ways"}'


def test_check_only_does_not_write(tmp_path: Path) -> None:
    """Verifies check_only reports would-copy files without writing them."""
    src = _make_doc_system_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_doc_system(project, src, check_only=True)

    assert "brand/brand.json" in result.copied
    assert not (project / "ai-dev" / "doc-system").exists()


def test_self_sync_is_noop(tmp_path: Path) -> None:
    """Verifies syncing the platform repo onto itself copies nothing (no self-clobber)."""
    platform = tmp_path / "platform"
    src = _make_doc_system_src(platform)

    result = sync_doc_system(platform, src)

    assert result.copied == []
    assert sorted(result.up_to_date) == ["CLAUDE.md", "brand/brand.json", "editorial/_default.md"]
    assert result.skipped == ["catalog/index.json"]


def test_missing_source_returns_error(tmp_path: Path) -> None:
    """Verifies a missing source directory yields an error, not an exception."""
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_doc_system(project, tmp_path / "does-not-exist")

    assert result.copied == []
    assert len(result.errors) == 1
    assert result.errors[0].lower().find("not found") != -1
