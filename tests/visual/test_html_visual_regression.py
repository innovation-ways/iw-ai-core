"""Visual regression tests for HTML document renders (CR-00082 S01)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from tests.e2e.playwright_wrapper import PlaywrightWrapper
from tests.visual.test_pdf_visual_regression import (
    __MAX_DIFF_FRACTION__,
    __PIXEL_THRESHOLD__,
    _compare_pixel_difference,
)

pytestmark = pytest.mark.skipif(
    not shutil.which("playwright-cli"),
    reason="playwright-cli not on PATH",
)

_ROOT = Path(__file__).parent
HTML_DIR = _ROOT / "baselines" / "html"
OUTPUT_DIR = Path("tests/output/visual-diff")


def _find_baseline_html() -> list[tuple[str, Path, Path]]:
    """Discover every source.html/baseline.png pair under the baselines/html tree.

    Returns:
        List of (doc-name, source-html-path, baseline-png-path) tuples.
    """
    docs: list[tuple[str, Path, Path]] = []
    for sub_dir in sorted(HTML_DIR.iterdir()):
        if not sub_dir.is_dir():
            continue
        source = sub_dir / "source.html"
        baseline = sub_dir / "baseline.png"
        if source.exists() and baseline.exists():
            docs.append((sub_dir.name, source, baseline))
    return docs


@pytest.mark.parametrize(
    ("doc_name", "source_html", "baseline_png"),
    _find_baseline_html(),
    ids=[doc for doc, _, _ in _find_baseline_html()],
)
def test_html_matches_baseline(
    doc_name: str,
    source_html: Path,
    baseline_png: Path,
    tmp_path: Path,
) -> None:
    """Screenshot the source HTML and assert pixel diff is within the committed baseline."""
    wrapper = PlaywrightWrapper(base_url="")
    actual_path = tmp_path / f"{doc_name}-actual.png"
    wrapper.screenshot_to_baseline(source_html.resolve().as_uri(), actual_path)

    similarity_pct, diff_fraction, diff_path = _compare_pixel_difference(
        baseline_png,
        actual_path,
        threshold=__PIXEL_THRESHOLD__,
        max_diff_fraction=__MAX_DIFF_FRACTION__,
    )

    if diff_fraction > __MAX_DIFF_FRACTION__:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        actual_dest = OUTPUT_DIR / f"{doc_name}-actual.png"
        baseline_dest = OUTPUT_DIR / f"{doc_name}-baseline.png"
        diff_dest = OUTPUT_DIR / f"{doc_name}-diff.png"

        Image.open(actual_path).convert("RGB").save(actual_dest)
        Image.open(baseline_png).convert("RGB").save(baseline_dest)
        if diff_path:
            Image.open(diff_path).convert("RGB").save(diff_dest)

        pytest.fail(
            f"Pixel diff exceeded tolerance for {doc_name}:\n"
            f"  Similarity:           {similarity_pct:.4f}%\n"
            f"  Changed pixels:       {diff_fraction * 100:.4f}% "
            f"(max allowed: {__MAX_DIFF_FRACTION__ * 100:.2f}%)\n"
            f"  Diff image:           {diff_dest.absolute()}\n"
            f"  Baseline image:       {baseline_dest.absolute()}\n"
            f"  Actual image:         {actual_dest.absolute()}"
        )

    assert diff_fraction <= __MAX_DIFF_FRACTION__
