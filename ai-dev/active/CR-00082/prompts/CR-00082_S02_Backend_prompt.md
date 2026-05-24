# CR-00082_S02_Backend_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
**Step**: S02
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

## ⛔ Playwright CLI rules (NON-NEGOTIABLE — from CLAUDE.md)

- Use `playwright-cli` EXCLUSIVELY. NEVER `agent-browser`. NEVER direct `chromium.launch()`. NEVER `npx playwright install`. NEVER edit `.playwright/cli.config.json`.
- Always run `playwright-cli kill-all` before starting a browser session.
- `playwright-cli screenshot` saves to `.playwright-cli/page-<ts>.png` — it does NOT accept a destination path as an argument. Move the file after capture.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00082 --json`.
- `ai-dev/work/CR-00082/CR-00082_CR_Design.md` — Design document (read AC2, AC3, AC4, AC6, AC8 carefully)
- `ai-dev/work/CR-00082/reports/CR-00082_S01_Backend_report.md` — Read S01's pixel-tolerance value and diff helper so this step uses the same tolerance and same helper code path.
- `tests/e2e/playwright_wrapper.py` — F-00088 wrapper you will extend
- `doc-system/` — read to enumerate editorial categories

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_S02_Backend_report.md` — Step report

## Context

You are implementing the **HTML visual-regression module** for CR-00082, plus the umbrella `make visual-regression` target.

Read the design document first. Then read `CLAUDE.md` for project-specific patterns (especially the Playwright CLI rules) and `tests/e2e/playwright_wrapper.py` for the F-00088 wrapper you will extend.

## Requirements

### 1. Extend `tests/e2e/playwright_wrapper.py`

Add a `screenshot_to_baseline(url: str, output_path: pathlib.Path, *, session: str | None = None) -> pathlib.Path` helper that:

1. Runs `playwright-cli kill-all` first (always, per CLAUDE.md).
2. Opens the URL via `playwright-cli open` (with `-s=<session>` if `session` is set).
3. Calls `playwright-cli screenshot` (no path argument — it saves to `.playwright-cli/page-<ts>.png`).
4. Moves the captured file to `output_path` (atomic rename when possible).
5. Returns the resolved `output_path`.

Use the existing subprocess-wrapper patterns already in the file. Do NOT introduce a second subprocess pattern. Do NOT call `chromium.launch()` directly. Do NOT use `agent-browser`.

### 2. Create the HTML visual-regression module

Create `tests/visual/test_html_visual_regression.py`. (The `tests/visual/__init__.py` already exists from S01.)

Discovery: enumerate baseline HTML docs under `tests/visual/baselines/html/<category>/source.html`. For each, start (or assume already-running) a dashboard test server — match the pattern used by existing dashboard E2E tests. Open the doc-view URL via the new `screenshot_to_baseline()` helper. Compare the captured PNG to the committed baseline at `tests/visual/baselines/html/<category>/baseline.png` using the **same Pillow + `pixelmatch` diff helper that S01 introduced** (DRY — import or share, do not copy-paste).

Failure path (AC3): same as S01 — write `tests/output/visual-diff/<doc>-actual.png`, `-baseline.png`, `-diff.png` and include the diff path in the failure message.

If `playwright-cli` is not on PATH, skip with a clear message naming the missing binary.

### 3. Populate the HTML baseline set

Under `tests/visual/baselines/html/<category>/` add one representative baseline HTML doc per editorial category from `doc-system/`. Target the remaining slots so the combined PDF + HTML baseline count lands between 8 and 15 (S01 added 4–8 PDFs; you add the rest). For each, pre-capture the baseline PNG and commit it.

### 4. Add `make visual-regression-html` and umbrella `make visual-regression`

Edit `Makefile` to add:

```
visual-regression-html:
	uv run pytest tests/visual/test_html_visual_regression.py -v

visual-regression: visual-regression-pdf visual-regression-html
```

Match the style of neighbouring targets (tab indentation, optional help string).

### 5. RED-first evidence (AC3 demonstration)

Deliberately introduce a 1-pixel shift in one HTML baseline PNG; re-run `make visual-regression-html`; capture the failing output and the produced `*-diff.png` path; revert; confirm green. Record both runs as `tdd_red_evidence`. Also run `make visual-regression` (umbrella) once at the end to confirm both halves wire together.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Test organization and fixtures (`tests/conftest.py`, `tests/CLAUDE.md`)
- Playwright CLI rules (binary, never `chromium.launch()`, screenshot path quirk)
- Build and run commands

Follow all rules defined there exactly.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. **`make format`**
2. **`make typecheck`** — zero errors on touched files
3. **`make lint`** — zero errors

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/visual/test_html_visual_regression.py -v
# and one umbrella run at the end:
make visual-regression
```

Do NOT run `make test-unit` or `make test-integration` — those are S10/S11 QV gates.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "CR-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/e2e/playwright_wrapper.py",
    "tests/visual/test_html_visual_regression.py",
    "tests/visual/baselines/html/<category-1>/source.html",
    "tests/visual/baselines/html/<category-1>/baseline.png",
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
  "tdd_red_evidence": "tests/visual/test_html_visual_regression.py::test_html_matches_baseline[<doc>] — Failed: pixel diff exceeded tolerance; see tests/output/visual-diff/<doc>-diff.png. Reverted; target now green.",
  "blockers": [],
  "notes": "Total baseline count (PDF + HTML): <N>. Categories covered: <list>. Pixel tolerance shared with S01: <value>."
}
```
