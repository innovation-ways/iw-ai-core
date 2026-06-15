"""Unit tests for brand-asset distribution (orch.skills.sync_assets).

Covers recursive copy with structure preservation, idempotency (byte-identical
skip), check-only mode (no writes), the platform-repo self no-op, and the
missing-source error path.
"""

from __future__ import annotations

from pathlib import Path

from orch.skills.sync_assets import sync_assets


def _make_assets_src(root: Path) -> Path:
    """Create a small nested ai-dev/iw-assets master tree under ``root``.

    Args:
        root: Directory to treat as the platform repo root.

    Returns:
        The created ``ai-dev/iw-assets`` source directory.
    """
    src = root / "ai-dev" / "iw-assets"
    (src / "svg").mkdir(parents=True)
    (src / "png").mkdir(parents=True)
    (src / "README.md").write_text("brand assets\n", encoding="utf-8")
    (src / "svg" / "iw-mark.svg").write_text("<svg>mark</svg>", encoding="utf-8")
    (src / "png" / "favicon-16.png").write_bytes(b"\x89PNG-16")
    return src


def test_sync_copies_tree_preserving_structure(tmp_path: Path) -> None:
    """Verifies every source file lands at the matching nested project path."""
    src = _make_assets_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_assets(project, src)

    assert sorted(result.copied) == ["README.md", "png/favicon-16.png", "svg/iw-mark.svg"]
    assert (
        project / "ai-dev" / "iw-assets" / "svg" / "iw-mark.svg"
    ).read_text() == "<svg>mark</svg>"
    assert (
        project / "ai-dev" / "iw-assets" / "png" / "favicon-16.png"
    ).read_bytes() == b"\x89PNG-16"
    assert result.errors == []


def test_sync_is_idempotent(tmp_path: Path) -> None:
    """Verifies a second sync reports files up-to-date and copies nothing."""
    src = _make_assets_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    sync_assets(project, src)
    second = sync_assets(project, src)

    assert second.copied == []
    assert sorted(second.up_to_date) == [
        "README.md",
        "png/favicon-16.png",
        "svg/iw-mark.svg",
    ]


def test_sync_recopies_changed_file(tmp_path: Path) -> None:
    """Verifies a drifted target file is re-copied on the next sync."""
    src = _make_assets_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()
    sync_assets(project, src)

    target = project / "ai-dev" / "iw-assets" / "svg" / "iw-mark.svg"
    target.write_text("STALE", encoding="utf-8")

    result = sync_assets(project, src)

    assert "svg/iw-mark.svg" in result.copied
    assert target.read_text() == "<svg>mark</svg>"


def test_check_only_does_not_write(tmp_path: Path) -> None:
    """Verifies check_only reports would-copy files without writing them."""
    src = _make_assets_src(tmp_path / "platform")
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_assets(project, src, check_only=True)

    assert "svg/iw-mark.svg" in result.copied
    assert not (project / "ai-dev" / "iw-assets").exists()


def test_self_sync_is_noop(tmp_path: Path) -> None:
    """Verifies syncing the platform repo onto itself copies nothing (no self-clobber)."""
    platform = tmp_path / "platform"
    src = _make_assets_src(platform)

    result = sync_assets(platform, src)

    assert result.copied == []
    assert len(result.up_to_date) == 3


def test_missing_source_returns_error(tmp_path: Path) -> None:
    """Verifies a missing source directory yields an error, not an exception."""
    project = tmp_path / "proj"
    project.mkdir()

    result = sync_assets(project, tmp_path / "does-not-exist")

    assert result.copied == []
    assert len(result.errors) == 1
    assert result.errors[0].lower().find("not found") != -1
