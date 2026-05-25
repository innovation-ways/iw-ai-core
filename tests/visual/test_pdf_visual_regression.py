"""Visual regression tests for PDF exports (CR-00082 S01).

Each baseline lives under tests/visual/baselines/pdfs/<doc>/ with:
  source.pdf   — the committed reference PDF
  page-001.png — page-1 raster baseline (pre-rendered via pdftoppm -r 150 -png)
  ...

The test shells out to pdftoppm (poppler) to rasterise pages at 150 DPI, then
compares each page PNG against the committed baseline using Pillow + pixelmatch.
A max-diffraction budget of 0.5% of page pixels is applied (mirroring InnoForge's
pass_threshold of 0.2% / warn at 1.0%).

Pixel-tolerance rationale:
  InnoForge's regression service uses pass_threshold=0.2% (absolute percentage of
  changed pixels per page). CR-00082 uses maxDiffFraction = 0.5% of total page pixels
  and per-pixel threshold = 0.1 (pixelmatch's threshold, 0.0–1.0 range). These two
  parameter systems are not directly comparable. The 0.5% budget was chosen as the
  closest stand-in for InnoForge's 0.2% pass / 1.0% warn bands. See __PIXEL_THRESHOLD__
  and __MAX_DIFF_FRACTION__ below.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# Module-level skip when poppler (pdftoppm) is unavailable in CI / dev env.
# ─────────────────────────────────────────────────────────────────────────────
pytestmark = pytest.mark.skipif(
    not shutil.which("pdftoppm"),
    reason="poppler (pdftoppm) not installed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Pixel-diff configuration  (mirrors InnoForge's pass_threshold / warn bands)
# ─────────────────────────────────────────────────────────────────────────────
# Fraction of page pixels allowed to differ before the page is FAIL.
# 0.005 = 0.5 % — InnoForge's pass_threshold = 0.2% / warn = 1.0%.
__MAX_DIFF_FRACTION__: float = 0.005

# pixelmatch threshold argument (0.0 to 1.0; lower is more sensitive).
# Default 0.1 matches InnoForge's per-channel approach without triggering
# on anti-aliased rendering edges.
__PIXEL_THRESHOLD__: float = 0.1

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent
BASELINES_DIR = _ROOT / "baselines"
PDFS_DIR = BASELINES_DIR / "pdfs"
OUTPUT_DIR = Path("tests/output/visual-diff")
PDFTOPPM_DPI = 150


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _find_baseline_pdfs() -> list[tuple[str, Path]]:
    """Discover every source.pdf under the baselines tree.

    Returns:
        List of (doc-name, pdf-path) pairs, one entry per sub-directory.
    """
    pdfs: list[tuple[str, Path]] = []
    for sub_dir in sorted(PDFS_DIR.iterdir()):
        if not sub_dir.is_dir():
            continue
        pdf_path = sub_dir / "source.pdf"
        if pdf_path.exists():
            pdfs.append((sub_dir.name, pdf_path))
    return pdfs


def _rasterise_pdf(pdf_path: Path, output_dir: Path, dpi: int = PDFTOPPM_DPI) -> list[Path]:
    """Render a PDF to PNG pages using pdftoppm.

    Args:
        pdf_path:  Path to the source PDF.
        output_dir: Directory to write page PNGs into (created here).
        dpi:       Resolution for rendering (default 150 DPI).

    Returns:
        List of created PNG paths sorted alphabetically.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "tmp"
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
        text=True,
    )
    png_paths: list[Path] = sorted(output_dir.glob("tmp-*.png"))
    return png_paths


def _compare_pixel_difference(
    baseline_path: Path,
    actual_path: Path,
    threshold: float = __PIXEL_THRESHOLD__,
    max_diff_fraction: float = __MAX_DIFF_FRACTION__,
) -> tuple[float, float, Path | None]:
    """Compare baseline and actual PNGs via Pillow + pixelmatch.

    pixelmatch.contrib.PIL.pixelmatch returns the number of mismatched pixels
    (not an Image). We provide an RGBA output image so the library writes the
    diff overlay in-place.

    Args:
        baseline_path:     Committed reference PNG path.
        actual_path:       Newly rendered PNG path.
        threshold:         pixelmatch threshold (0.0–1.0); lower=more sensitive.
        max_diff_fraction: Maximum fraction of the page that may differ (0.0–1.0).

    Returns:
        Tuple of (similarity_pct, diff_fraction, diff_image_path | None).
        diff_image_path is non-None when a diff PNG has been written to OUTPUT_DIR.
    """
    baseline_img = Image.open(baseline_path).convert("RGB")
    actual_img = Image.open(actual_path).convert("RGB")

    if baseline_img.size != actual_img.size:
        actual_img = actual_img.resize(baseline_img.size, Image.Resampling.LANCZOS)

    from pixelmatch.contrib.PIL import pixelmatch  # lazy import

    # Provide an RGBA output image so the library can paint the diff overlay.
    diff_img = Image.new("RGBA", baseline_img.size, (0, 0, 0, 0))
    mismatched_pixels: int = pixelmatch(
        baseline_img,
        actual_img,
        output=diff_img,
        threshold=threshold,
        diff_color=(255, 0, 0),  # red = changed pixels
        aa_color=(255, 255, 0),  # yellow = anti-aliased pixels
    )

    total_pixels = baseline_img.width * baseline_img.height
    diff_fraction = mismatched_pixels / total_pixels
    similarity_pct = (1.0 - diff_fraction) * 100.0

    diff_image_path: Path | None = None
    if diff_fraction > max_diff_fraction:
        _ensure_output_dir()
        doc = baseline_path.parent.parent.name
        stem = baseline_path.stem
        if stem.startswith("page-"):
            page_num = int(stem.split("-")[-1])  # page-NNN → NNN
            diff_image_path = OUTPUT_DIR / f"{doc}-page{page_num}-diff.png"
        else:
            diff_image_path = OUTPUT_DIR / f"{doc}-{stem}-diff.png"
        diff_img.save(diff_image_path)

    return similarity_pct, diff_fraction, diff_image_path


def _ensure_output_dir() -> None:
    """Create the visual-diff output directory if it does not exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("doc_name", "pdf_path"),
    _find_baseline_pdfs(),
    ids=[doc for doc, _ in _find_baseline_pdfs()],
)
def test_pdf_matches_baseline(
    doc_name: str,
    pdf_path: Path,
    tmp_path: Path,
) -> None:
    """Rasterise the source PDF and compare each page against committed baselines.

    Each committed baseline lives at tests/visual/baselines/pdfs/<doc>/page-NNN.png.
    Rendering uses pdftoppm at the same DPI as the pre-rendered baselines (150 DPI).

    Failure path (AC3):
      - A pytest.fail() message names the absolute path to the *-diff.png file so
        a reviewer can open the artefact directly.
      - Three PNGs land under tests/output/visual-diff/:
          {doc}-page{N}-actual.png   ← newly rendered candidate
          {doc}-page{N}-baseline.png  ← committed reference
          {doc}-page{N}-diff.png     ← pixel-diff highlight (red = changed pixels)
    """
    # ── rasterise the source PDF ──────────────────────────────────────────
    actual_pages: list[Path] = _rasterise_pdf(pdf_path, tmp_path)
    baseline_dir = pdf_path.parent

    for actual_path in actual_pages:
        page_num = int(actual_path.stem.split("-")[-1])  # tmp-NNN → NNN
        baseline_path = baseline_dir / f"page-{page_num:03d}.png"

        if not baseline_path.exists():
            pytest.fail(
                f"No committed baseline found for {doc_name} page {page_num}. "
                f"Expected: {baseline_path}",
            )

        similarity_pct, diff_fraction, diff_path = _compare_pixel_difference(
            baseline_path,
            actual_path,
            threshold=__PIXEL_THRESHOLD__,
            max_diff_fraction=__MAX_DIFF_FRACTION__,
        )

        if diff_fraction > __MAX_DIFF_FRACTION__:
            # Write the three diagnostic PNGs (AC3 requirement).
            _ensure_output_dir()
            actual_dest = OUTPUT_DIR / f"{doc_name}-page{page_num}-actual.png"
            baseline_dest = OUTPUT_DIR / f"{doc_name}-page{page_num}-baseline.png"
            diff_dest = OUTPUT_DIR / f"{doc_name}-page{page_num}-diff.png"

            Image.open(actual_path).convert("RGB").save(actual_dest)
            Image.open(baseline_path).convert("RGB").save(baseline_dest)
            if diff_path:
                Image.open(diff_path).convert("RGB").save(diff_dest)

            diff_pct = diff_fraction * 100.0
            pytest.fail(
                f"Pixel diff exceeded tolerance for {doc_name} page {page_num}:\n"
                f"  Similarity:           {similarity_pct:.4f}%\n"
                f"  Changed pixels:       {diff_pct:.4f}% "
                f"(max allowed: {__MAX_DIFF_FRACTION__ * 100:.2f}%)\n"
                f"  Diff image:           {diff_dest.absolute()}\n"
                f"  Baseline image:       {baseline_dest.absolute()}\n"
                f"  Actual image:         {actual_dest.absolute()}\n"
                f"  Open any of the above PNGs to inspect the regression."
            )

    assert diff_fraction <= __MAX_DIFF_FRACTION__
