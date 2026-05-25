# CR-00082: Visual-regression test layer for rendered HTML and PDF documents

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 4 of the testing initiative — `ai-dev/work/TESTS_ENHANCEMENT.md` §8 item 4.1 ("Round it out & insure"). Currently no gate detects CSS / template / markdown-pipeline regressions in the production-rendered HTML doc views or PDF exports. A single change to `dashboard/static/styles.css`, `dashboard/templates/pdf/doc_pdf.html`, or the markdown→HTML pipeline can silently wreck layout in shipped artefacts.
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds NO alembic migrations — tests/CI/docs only.

## Description

Introduce a new dedicated visual-regression test layer that pins the pixel output of every editorial-category-representative HTML doc view and PDF export against committed baselines. PDFs are rasterised by `pdftoppm` and pixel-diffed via Pillow + `pixelmatch`; HTML doc views are screenshotted via `playwright-cli` (extending the F-00088 wrapper). Surface is a new `make visual-regression` umbrella target plus a path-filtered + nightly GitHub Actions workflow. NOT a daemon QV gate (too slow for per-item).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Particularly relevant for this CR:

- The Playwright CLI rule: `playwright-cli` exclusively; never `agent-browser`, never direct `chromium.launch()`, never `npx playwright install`, never edit `.playwright/cli.config.json`.
- The doc-system layout: `doc-system/` holds editorial config (brand, catalog, guidelines); the dashboard's HTML doc-view and PDF-export routes live in `dashboard/routers/docs.py`; the PDF template is `dashboard/templates/pdf/doc_pdf.html`.
- The Tailwind / plain-CSS rule for `dashboard/static/styles.css` (I-00067 mitigation).

## Current Behavior

Today, the rendered output of the doc system is exercised only by:

1. **Contract tests** (`tests/dashboard/`, `tests/integration/test_route_sweep_contract.py`) that assert HTTP-status / route-shape / response-header properties but never look at the rendered pixels.
2. **F-00088 E2E tests** (`tests/e2e/`, via `tests/e2e/playwright_wrapper.py`) that drive the dashboard end-to-end but assert on DOM presence and accessible-name semantics, not on visual layout.
3. **`make test-dashboard` / `make test-route-sweep`** — route-level smoke that catches 5xx but not "the navbar is now overlapping the toolbar".

There is **no gate**, anywhere in the stack, that compares the actual rendered pixels of an HTML doc view or a PDF export against a previously-approved baseline. A regression in `dashboard/static/styles.css` (e.g., a Tailwind compile drift), `dashboard/templates/pdf/doc_pdf.html` (e.g., page-break CSS), or `orch/doc_service.py`'s markdown→HTML pipeline (e.g., heading-level renumbering) can ship to production and only be caught by a human noticing the broken layout.

## Desired Behavior

A new `tests/visual/` test module containing:

1. **PDF visual regression** (`tests/visual/test_pdf_visual_regression.py`) — for each baseline PDF under `tests/visual/baselines/pdfs/`, `pdftoppm` renders to PNG per page; Pillow + `pixelmatch` compares against committed baseline PNGs under `tests/visual/baselines/pdfs/<doc>/page-NNN.png`. Small pixel tolerance (see §"Implementation Plan / Backend / Pixel tolerance").
2. **HTML visual regression** (`tests/visual/test_html_visual_regression.py`) — for each baseline HTML doc under `tests/visual/baselines/html/`, the test extends `tests/e2e/playwright_wrapper.py` with a `screenshot_to_baseline()` helper that wraps `playwright-cli screenshot`. The captured PNG is compared against `tests/visual/baselines/html/<doc>/baseline.png` using the same Pillow + `pixelmatch` diff path as the PDF module.
3. **Baseline set** of 8–15 files total — one PDF + one HTML per editorial category (read from `doc-system/` config; categories include architecture, infrastructure, blog, pitch-deck, promo, research, release-notes, user-guide).
4. **`make visual-regression-pdf`**, **`make visual-regression-html`**, and **`make visual-regression`** (umbrella) targets. Failure produces `tests/output/visual-diff/<doc>-page<N>-{actual,baseline,diff}.png` reviewers can eyeball.
5. **`.github/workflows/visual-regression.yml`** — nightly cron + `workflow_dispatch` AND path-filtered PR trigger on `dashboard/static/styles.css`, `dashboard/templates/pdf/**`, `dashboard/templates/components/doc_*`, `doc-system/**`. After a burn-in nightly window, `continue-on-error: false` (blocking).
6. **Docs + skill + tracker updated** — `docs/IW_AI_Core_Testing_Strategy.md` §2 gains "Layer 8 — visual regression"; §5 gains a new gate row; §9 row flips to ✅. `skills/iw-ai-core-testing/SKILL.md` gains a new section on visual-regression patterns and baseline-management rules. `iw sync-skills --force iw-ai-core-testing` propagates the skill edit. `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.1 → DONE and v1.4 header entry added.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/visual/` | Does not exist | New test module with PDF + HTML visual-regression suites |
| `tests/visual/baselines/` | Does not exist | 8–15 baseline assets (PDFs, HTML reference renders, PNG baselines) committed to git |
| `tests/e2e/playwright_wrapper.py` | Wraps `playwright-cli` subprocess calls (F-00088) | Gains a `screenshot_to_baseline()` helper used by the HTML visual-regression module |
| `Makefile` | No visual-regression target | Adds `visual-regression-pdf`, `visual-regression-html`, and `visual-regression` umbrella targets |
| `pyproject.toml` | No Pillow / pixelmatch deps | Adds `Pillow` and `pixelmatch` to `[dependency-groups] dev` |
| `uv.lock` | No Pillow / pixelmatch | Regenerated by `uv lock` |
| `.github/workflows/visual-regression.yml` | Does not exist | New workflow: nightly cron + `workflow_dispatch` + path-filtered PR trigger |
| `docs/IW_AI_Core_Testing_Strategy.md` | §2 has Layers 1–7; §9 row "visual regression" = ❌ | §2 gains "Layer 8 — visual regression"; §5 gains a gate row; §9 row flipped to ✅ |
| `skills/iw-ai-core-testing/**` (and `.claude/skills/` copy) | No visual-regression guidance | New section on visual-regression patterns + baseline-management rules |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §8 row 4.1 = TODO | §8 row 4.1 = DONE; new v1.4 header entry |

### Breaking Changes

None. The CR adds new test files, new make targets, a new CI workflow, and new dependency entries. No production code under `orch/`, `dashboard/`, or `executor/` is touched. No existing test is rewritten.

### Data Migration

None. No alembic migrations.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern (one module or closely-related file group). Multi-concern work is split across multiple steps. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | PDF visual-regression module + baselines + `pdftoppm` / `pixelmatch` plumbing + `Pillow` + `pixelmatch` deps in `pyproject.toml` + `make visual-regression-pdf` target | — |
| S02 | backend-impl | HTML visual-regression module + baselines + `playwright_wrapper.py` `screenshot_to_baseline()` extension + `make visual-regression-html` + `make visual-regression` umbrella target | — (depends on S01 for the shared diff helper) |
| S03 | backend-impl | `.github/workflows/visual-regression.yml`; strategy doc + skill + tracker updates; `iw sync-skills --force iw-ai-core-testing` | — (depends on S01 + S02 for the make targets to exist) |
| S04 | code-review-impl | Per-agent review of S01 + S02 + S03 (single review pass — three cohesive backend deliverables in one CR) | — |
| S05 | code-review-final-impl | Global cross-agent review of the complete CR | — |
| S06..S13 | qv-gate | 8 standard QV gates: lint / assertions / format / typecheck / unit-tests / integration-tests / diff-coverage / security-secrets | — |
| S14 | self-assess-impl | `iw-item-analyze` self-assessment of the just-completed item | — |

Total: 14 steps. `browser_verification: false` — the tests use `playwright-cli` internally but the CR ships no UI feature.

### Pixel tolerance

The design picks an initial small `maxDiffPixels` budget per page (target: ≤ 0.5 % of page pixels, mirroring InnoForge's value in `iw-doc-plan/main/iw-doc-plan/`). S01 reads InnoForge's exact value and ports it; if InnoForge ships a different policy (per-channel threshold rather than pixel count), S01 picks the closer match and records the choice in the S01 report under `notes`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no alembic changes

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00082/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00082_CR_Design.md` | Design | This document |
| `CR-00082_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator (14 steps; `browser_verification: false`) |
| `prompts/CR-00082_S01_Backend_prompt.md` | Prompt | S01 — PDF visual-regression module |
| `prompts/CR-00082_S02_Backend_prompt.md` | Prompt | S02 — HTML visual-regression module + umbrella `make` target |
| `prompts/CR-00082_S03_Backend_prompt.md` | Prompt | S03 — CI workflow + docs + skill + tracker updates |
| `prompts/CR-00082_S04_CodeReview_prompt.md` | Prompt | S04 — per-agent code review of S01 + S02 + S03 |
| `prompts/CR-00082_S05_CodeReview_Final_prompt.md` | Prompt | S05 — final cross-agent review |
| `prompts/CR-00082_S14_SelfAssess_prompt.md` | Prompt | S14 — self-assessment via `iw-item-analyze` |

S06..S13 are QV gate steps and run from the `command` field declared in `workflow-manifest.json` — they do not need per-step prompt files.

Reports are created during execution under `ai-dev/work/CR-00082/reports/`.

## Acceptance Criteria

### AC1: PDF visual-regression module exists and passes against committed baselines

```
Given a fresh checkout of the worktree
And the dev dependencies are installed (`uv sync`)
When the operator runs `make visual-regression-pdf`
Then the target exits 0
And every baseline PDF under `tests/visual/baselines/pdfs/` is rasterised, pixel-diffed against its committed PNG, and reported as matching within the configured pixel tolerance
```

### AC2: HTML visual-regression module exists and passes against committed baselines

```
Given a fresh checkout of the worktree
And the dev dependencies are installed
And `playwright-cli` is available on PATH
When the operator runs `make visual-regression-html`
Then the target exits 0
And every baseline HTML doc under `tests/visual/baselines/html/` is screenshotted via `playwright-cli`, pixel-diffed against its committed PNG, and reported as matching within the configured pixel tolerance
```

### AC3: Diffs on failure are written to a reviewable artefact directory

```
Given a deliberate regression has been introduced (e.g., a CSS rule changed)
When the operator runs `make visual-regression`
Then the target exits non-zero
And for each failing comparison, three PNGs land under `tests/output/visual-diff/<doc>-page<N>-{actual,baseline,diff}.png`
And the test failure message names the path to the `*-diff.png` file
```

### AC4: Baseline coverage spans every editorial category

```
Given the editorial categories declared in `doc-system/`
When the baseline set under `tests/visual/baselines/` is enumerated
Then every category has at least one representative baseline (one PDF + one HTML)
And the total baseline count is between 8 and 15
```

### AC5: CI workflow runs nightly, on demand, and on relevant PR paths

```
Given a PR that modifies `dashboard/static/styles.css`, `dashboard/templates/pdf/**`, `dashboard/templates/components/doc_*`, or `doc-system/**`
When the PR is opened
Then `.github/workflows/visual-regression.yml` is triggered by the path filter
And the workflow also runs nightly via cron
And the workflow can be triggered ad-hoc via `workflow_dispatch`
```

### AC6: `playwright-cli` is the only browser-automation entry point

```
Given the HTML visual-regression module
When its source is searched
Then it contains zero calls to `chromium.launch`, `agent-browser`, or `npx playwright install`
And it never modifies `.playwright/cli.config.json`
And it drives the browser exclusively through `tests/e2e/playwright_wrapper.py`'s `playwright-cli` subprocess wrapper
```

### AC7: Documentation, skill, and tracker reflect the new layer

```
Given the CR has shipped S03
When `docs/IW_AI_Core_Testing_Strategy.md` is opened
Then §2 contains a "Layer 8 — visual regression" subsection
And §5 contains a new gate row for `make visual-regression`
And §9's visual-regression row is marked ✅

When `skills/iw-ai-core-testing/SKILL.md` is opened
Then it contains a new section documenting visual-regression patterns and baseline-management rules
And the same content lives at `.claude/skills/iw-ai-core-testing/SKILL.md` (synced via `iw sync-skills`)

When `ai-dev/work/TESTS_ENHANCEMENT.md` is opened
Then §8 row 4.1 status reads DONE
And a v1.4 header entry dated 2026-05-24 records the visual-regression delivery
```

### AC8: Scope discipline — no production code touched

```
Given the CR has shipped all three implementation steps
When `git diff main...HEAD --name-only` is inspected
Then no file under `orch/`, `dashboard/` (excluding the test-only `dashboard/templates/...` paths the CR explicitly leaves untouched), `executor/`, or `scripts/` appears
And no migration file under `orch/db/migrations/versions/**` appears
And every modified path matches `scope.allowed_paths` in `workflow-manifest.json`
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert the squash-merge commit. The new make targets, test module, baseline assets, dependency entries, and CI workflow disappear cleanly; nothing in production code depends on them.
- **Data**: No data loss on rollback. Baseline assets are committed to git, so re-introducing the layer later only requires re-applying the revert.

## Dependencies

- **Depends on**: F-00088 (the `tests/e2e/playwright_wrapper.py` infrastructure this CR extends). No active blocking dependency — F-00088 is shipped.
- **Blocks**: None. Leaf CR — independent of CR-00080, CR-00081, and of I-00109/110/111.

## Impacted Paths

```
tests/visual/**
tests/e2e/playwright_wrapper.py
Makefile
pyproject.toml
uv.lock
.github/workflows/visual-regression.yml
docs/IW_AI_Core_Testing_Strategy.md
skills/iw-ai-core-testing/**
.claude/skills/iw-ai-core-testing/**
ai-dev/work/TESTS_ENHANCEMENT.md
```

No production code under `orch/`, `dashboard/`, `executor/`. No migrations under `orch/db/migrations/versions/**`.

## TDD Approach

- **Unit tests**: N/A — the deliverables are test modules themselves. The "RED" evidence is the deliberate-regression demonstration (AC3): apply a 1-pixel CSS shift, observe the test fail, capture the failing-line output as `tdd_red_evidence` for the relevant Backend step, then revert the shift before reporting completion.
- **Integration tests**: N/A — the new tests run under `make visual-regression`, an out-of-band target NOT part of `make test-integration` (the latter is the daemon QV gate; visual-regression is too slow for per-item).
- **Updated tests**: None. No existing test is rewritten. `tests/e2e/playwright_wrapper.py` is extended with a new helper but its existing signatures are untouched.

## Notes

- **Why not a daemon QV gate?** Visual regression is wall-clock-heavy (PDF rasterisation + per-page diff + per-baseline browser screenshot). Adding it to the per-item daemon path would inflate every batch by minutes. Path-filtered PR triggers + nightly cron give the same regression coverage at a fraction of the cost.
- **InnoForge precedent — port selectively.** A similar layer ships at `iw-doc-plan/main/iw-doc-plan/tests/visual/test_invoice_regression.py` and `src/innoforge/services/regression_test_service.py`. The precedent uses `pdf2image` (Python wrapper for poppler) and a **custom Pillow-only diff inside `RegressionTestService`** — NOT `pixelmatch`. This CR diverges deliberately: `pdftoppm` directly (one fewer Python dep) plus `pixelmatch` (richer per-pixel diff PNG for AC3). PORT from InnoForge: the `pytest.mark.skipif(not shutil.which("pdftoppm"), ...)` module-level guard, the per-page iteration shape, and the tolerance value. DO NOT PORT: `pdf2image`, the `RegressionTestService` class, the custom diff function, the `@allure.*` decorators, or the `asyncio` shape (these tests are sync).
- **HTML rendering strategy — `file://` URLs, not the live dashboard.** Baseline `source.html` files are self-contained static snapshots (relatively-linking `dashboard/static/styles.css` so CSS regressions are caught). The HTML test opens each via `playwright-cli open file:///abs/path/...` — deterministic, no `IW_BROWSER_BASE_URL` dependency. The `tests/e2e/conftest.py` `base_url` / `pw` fixtures are NOT imported. Live-template regressions are caught at baseline-regeneration time, which is a deliberate review-gated PR (per the baseline-management discipline below).
- **Baseline-management discipline.** Baselines are committed to git. Updates are reviewable diffs (a PR that touches `tests/visual/baselines/**` must justify the diff). NEVER auto-accept on regression — the failure path produces `*-diff.png` artefacts so a human can decide whether the change is intentional.
- **Playwright CLI rules** (per `CLAUDE.md`): `playwright-cli` exclusively; NEVER `agent-browser`, NEVER direct `chromium.launch()`, NEVER `npx playwright install`, NEVER edit `.playwright/cli.config.json`.
