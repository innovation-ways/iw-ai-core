"""On-demand archive extraction for the dashboard Full Artifacts view."""

from __future__ import annotations

import shutil
import tarfile
import time
from pathlib import Path

import zstandard as zstd

_VIEW_DIR = "iw-archive-view"


def extract_archive(
    project_id: str,
    item_id: str,
    archive_dir: Path | str,
    tmp_dir: Path | str,
) -> Path:
    """Extract a .tar.zst archive to a temporary directory.

    Reuses an existing extraction if the directory exists (within TTL — caller
    should run cleanup_expired periodically). Resets TTL by touching the dir on reuse.

    Args:
        project_id: Project identifier.
        item_id: Work item identifier.
        archive_dir: Directory containing project archives.
        tmp_dir: Base temporary directory for extractions.

    Returns:
        Path to the extracted directory (contains the item_id/ subfolder from the archive).

    Raises:
        FileNotFoundError: If the archive file does not exist.
    """
    archive_dir = Path(archive_dir)
    tmp_dir = Path(tmp_dir)

    archive_path = archive_dir / project_id / f"{item_id}.tar.zst"
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    extraction_path = tmp_dir / _VIEW_DIR / project_id / item_id

    if extraction_path.exists():
        extraction_path.touch()
        return extraction_path

    extraction_path.mkdir(parents=True, exist_ok=True)

    dctx = zstd.ZstdDecompressor()
    with (
        archive_path.open("rb") as f_in,
        dctx.stream_reader(f_in) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,
    ):
        tar.extractall(extraction_path, filter="data")

    return extraction_path


def cleanup_expired(tmp_dir: Path | str, ttl_seconds: int) -> int:
    """Delete extraction directories that have not been accessed within ttl_seconds.

    Scans {tmp_dir}/iw-archive-view/{project_id}/{item_id}/ directories and
    removes those whose mtime is older than ttl_seconds. Called by the daemon
    on each poll cycle.

    Args:
        tmp_dir: Base temporary directory containing iw-archive-view/.
        ttl_seconds: Seconds before an idle extraction is considered expired.

    Returns:
        Number of item directories deleted.
    """
    tmp_dir = Path(tmp_dir)
    view_root = tmp_dir / _VIEW_DIR
    if not view_root.exists():
        return 0

    now = time.time()
    deleted = 0

    for project_dir in view_root.iterdir():
        if not project_dir.is_dir():
            continue
        for item_dir in project_dir.iterdir():
            if not item_dir.is_dir():
                continue
            if now - item_dir.stat().st_mtime > ttl_seconds:
                shutil.rmtree(item_dir)
                deleted += 1
        # Remove empty project dirs
        if not any(project_dir.iterdir()):
            project_dir.rmdir()

    return deleted


def list_artifacts(extraction_path: Path | str) -> list[dict[str, object]]:
    """List all files and directories in an extracted archive.

    Args:
        extraction_path: Path to the extracted directory (as returned by extract_archive).

    Returns:
        List of dicts sorted by path, each with keys:
            name (str), relative_path (str), size (int), type ('file' | 'dir').
    """
    extraction_path = Path(extraction_path)
    results: list[dict[str, object]] = []

    for entry in sorted(extraction_path.rglob("*")):
        rel = entry.relative_to(extraction_path)
        if entry.is_dir():
            results.append(
                {"name": entry.name, "relative_path": str(rel), "size": 0, "type": "dir"}
            )
        else:
            results.append(
                {
                    "name": entry.name,
                    "relative_path": str(rel),
                    "size": entry.stat().st_size,
                    "type": "file",
                }
            )

    return results
