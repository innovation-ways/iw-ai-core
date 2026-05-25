# CR-00082 S02 Backend Report

- Step: S02 (backend-impl)
- Date: 2026-05-25

## What was done

1. Extended `tests/e2e/playwright_wrapper.py` with `screenshot_to_baseline(url: str, output_path: Path, *, session: str | None = None) -> Path`:
   - runs `playwright-cli kill-all`
   - opens URL (`open`, optional `-s=<session>`)
   - runs `playwright-cli screenshot`
   - resolves/moves latest `.playwright-cli/page-*.png` to target path (atomic rename fallback to copy2)
   - returns resolved output path

2. Added HTML visual-regression module: `tests/visual/test_html_visual_regression.py`:
   - discovers `tests/visual/baselines/html/<category>/source.html` + `baseline.png`
   - opens each source via `file://` URL with `PlaywrightWrapper` directly (no `base_url`/`pw` fixture dependency)
   - reuses S01 diff path by importing:
     - `__PIXEL_THRESHOLD__ = 0.1`
     - `__MAX_DIFF_FRACTION__ = 0.005`
     - `_compare_pixel_difference(...)`
   - writes AC3 failure artifacts under `tests/output/visual-diff/<doc>-{actual,baseline,diff}.png` with absolute paths in `pytest.fail(...)`
   - module skip guard for missing `playwright-cli` (`shutil.which`)

3. Populated HTML baselines and screenshots for 8 categories:
   - `architecture`, `blog`, `marketing`, `promo`, `release-notes`, `research`, `technical`, `user-guide`
   - each has `source.html` + committed `baseline.png`

4. Updated `Makefile`:
   - `visual-regression-html`
   - `visual-regression` umbrella target chaining PDF + HTML
   - added `--no-cov` to visual-regression pytest targets so the command is runnable standalone

5. Hardened shared diff helper in `tests/visual/test_pdf_visual_regression.py` for non-`page-NNN` baseline names (HTML reuse path).

## TDD RED evidence

Deliberate regression run:
- Mutated `tests/visual/baselines/html/architecture/baseline.png` (painted top rows black)
- Ran `make visual-regression-html`
- Expected failure observed:
  - `tests/visual/test_html_visual_regression.py::test_html_matches_baseline[architecture]`
  - `Failed: Pixel diff exceeded tolerance...`
  - Diff artifact path: `tests/output/visual-diff/architecture-diff.png`
- Reverted by recapturing the baseline screenshot from unchanged `source.html`
- Re-ran and confirmed green

## Verification

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/visual/test_html_visual_regression.py -v --no-cov` ✅ (8 passed)
- `make visual-regression` ✅ (PDF 4 passed + HTML 8 passed)

## Notes

- Shared pixel tolerance from S01: `max diff fraction = 0.005 (0.5%)`, `pixel threshold = 0.1`.
- Total baseline count (PDF + HTML): **12**.
- HTML coverage categories: architecture, blog, marketing, promo, release-notes, research, technical, user-guide.
