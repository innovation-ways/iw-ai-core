# CR-00082_S01_Backend_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. You MUST NOT add any file under
`orch/db/migrations/versions/**`. If you think one is needed, STOP and
raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00082 --json`. The `workflow-manifest.json` file is a design-time snapshot.
- `ai-dev/work/CR-00082/CR-00082_CR_Design.md` — Design document (read AC1, AC3, AC4, AC8 carefully)
- `ai-dev/work/CR-00082/CR-00082_Functional.md` — Functional summary
- InnoForge precedent: `iw-doc-plan/main/iw-doc-plan/` — search this sibling repo for `visual-regression`, `pdftoppm`, `pixelmatch` to port patterns (reference only — do NOT directly import)
- `doc-system/` — read to enumerate editorial categories for baseline coverage

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_S01_Backend_report.md` — Step report

## Context

You are implementing the **PDF visual-regression module** for CR-00082.

Read the design document first (in particular AC1, AC3, AC4, AC8, and §"Pixel tolerance" of the Implementation Plan). Then read `CLAUDE.md` for project-specific patterns and conventions (especially the Playwright CLI rules and the docker / migration off-limits rules).

## Requirements

### 1. Add `Pillow` and `pixelmatch` to the dev dependency group

Edit `pyproject.toml` under `[dependency-groups] dev` to add `Pillow` and `pixelmatch`. Regenerate `uv.lock` via `uv lock`. Commit both files.

- **`Pillow`** is the standard PIL package (`pip install Pillow`); InnoForge pins `Pillow>=10.0`, port that pin.
- **`pixelmatch`** is the Python port of the JS `pixelmatch` library, published on PyPI under the name `pixelmatch` (NOT `pixelmatch-py`). The import alias is `from pixelmatch.contrib.PIL import pixelmatch`. Use the latest stable pin. InnoForge does NOT use this package — see §2 below for why this CR diverges from the InnoForge implementation.

### 2. Create the PDF visual-regression module

Create `tests/visual/__init__.py` (empty) and `tests/visual/test_pdf_visual_regression.py`.

Discovery: the module enumerates every PDF under `tests/visual/baselines/pdfs/<doc>/source.pdf` (one subdirectory per baseline doc). For each PDF, it shells out to `pdftoppm` (system binary; assume present in CI — if not, use `pytest.mark.skipif(not shutil.which("pdftoppm"), reason="poppler (pdftoppm) not installed")` at module level, mirroring the InnoForge `pytestmark` pattern). It produces one PNG per page into a per-test temp directory, then opens the matching committed baseline PNG at `tests/visual/baselines/pdfs/<doc>/page-NNN.png` and compares pixel-for-pixel via Pillow + `pixelmatch`.

**InnoForge precedent — what to port, what to diverge from**:

- InnoForge (`/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/tests/visual/test_invoice_regression.py`, `src/innoforge/services/pdf_to_image_converter.py`, `src/innoforge/services/regression_test_service.py`) uses the `pdf2image` Python package (which internally shells out to poppler/pdftoppm) and a custom Pillow-only pixel diff inside `RegressionTestService` — NOT `pixelmatch`.
- This CR deliberately diverges: use `pdftoppm` directly via `subprocess.run(["pdftoppm", ...])` (one fewer Python dep), and use `pixelmatch` for the diff (richer per-pixel diff PNG output for the failure path required by AC3).
- **PORT FROM INNOFORGE**: the `pytestmark = pytest.mark.skipif(not shutil.which("pdftoppm"), ...)` pattern (lines ~19–22 of `test_invoice_regression.py`), the per-page iteration shape, and the tolerance value (search `RegressionTestService` for the threshold the precedent uses).
- **DO NOT PORT FROM INNOFORGE**: `pdf2image`, `RegressionTestService`, the custom diff function, the `@allure.*` decorators (no allure in this repo), the `asyncio` shape (these tests are sync).

Failure path (AC3): on mismatch, write three PNGs to `tests/output/visual-diff/<doc>-page<N>-actual.png`, `tests/output/visual-diff/<doc>-page<N>-baseline.png`, and `tests/output/visual-diff/<doc>-page<N>-diff.png`. The test failure message MUST include the absolute path to the `*-diff.png` file so a reviewer can open it directly. Use `pytest.fail(...)` with that message — do NOT swallow the failure.

Pixel tolerance: pick the value from the InnoForge precedent. Read InnoForge's setup first. If InnoForge uses `maxDiffPixels` as an absolute count, port that. If InnoForge uses a per-channel threshold, port that. Record the chosen value and the rationale in the S01 report `notes`. Default fallback if InnoForge has no precedent: `maxDiffPixels` = 0.5 % of total page pixels, with a 0.1 per-pixel threshold passed to `pixelmatch`.

### 3. Populate the baseline set

Under `tests/visual/baselines/pdfs/<category>/` add one representative baseline PDF per editorial category enumerated from `doc-system/`. Target 8–15 baselines total across both modules (PDFs + HTML, the HTML half is S02's job — so pick 4–8 PDFs here). Categories likely include architecture, infrastructure, blog, pitch-deck, promo, research, release-notes, user-guide. The PDFs must be small, representative, and stable (committed under git LFS only if absolutely necessary — prefer plain git for files under ~500 KB each).

For each PDF, pre-rasterise the baseline PNGs into `tests/visual/baselines/pdfs/<category>/page-NNN.png` so the test compares like-for-like and does not need to call any production code path at run-time.

### 4. Add the `make visual-regression-pdf` target

Edit `Makefile` to add:

```
visual-regression-pdf:
	uv run pytest tests/visual/test_pdf_visual_regression.py -v
```

(Match the style of neighbouring targets — quoting, tab indentation, help string if other targets use them.)

### 5. RED-first evidence (AC3 demonstration)

After the module + baselines + target are in place, deliberately introduce a 1-pixel shift in one baseline PNG (e.g., overwrite one row with a different value) and re-run `make visual-regression-pdf`. Capture the failing output and the path to the produced `*-diff.png`. Then revert the deliberate shift and confirm the target passes again. Record both runs in the report as `tdd_red_evidence`.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Test organization and fixtures (`tests/conftest.py`, `tests/CLAUDE.md`)
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors on files you touched.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the new test file you wrote:

```bash
uv run pytest tests/visual/test_pdf_visual_regression.py -v
```

Do NOT run `make test-unit` or `make test-integration` — those are S10/S11 QV gates.

Do NOT run `make visual-regression` (umbrella) here — the HTML half does not exist yet (S02 owns it).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    "tests/visual/__init__.py",
    "tests/visual/test_pdf_visual_regression.py",
    "tests/visual/baselines/pdfs/<category-1>/source.pdf",
    "tests/visual/baselines/pdfs/<category-1>/page-001.png",
    "...",
    "Makefile"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/visual/test_pdf_visual_regression.py::test_pdf_matches_baseline[<doc>] — Failed: pixel diff exceeded tolerance; see tests/output/visual-diff/<doc>-page1-diff.png. Reverted deliberate shift; target now green.",
  "blockers": [],
  "notes": "Pixel tolerance chosen: <value> — rationale: <InnoForge precedent / fallback>. Categories covered: <list>."
}
```
