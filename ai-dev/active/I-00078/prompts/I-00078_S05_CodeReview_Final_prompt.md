# I-00078_S05_CodeReview_Final_prompt

**Work Item**: I-00078 — Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema. Flag any migration/schema change as out of scope (CRITICAL).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00078 --json`.
- `ai-dev/active/I-00078/I-00078_Issue_Design.md` — design document
- All step reports: `ai-dev/active/I-00078/reports/I-00078_S01_*`, `..._S02_*`, `..._S03_*`, `..._S04_*`
- All files in every implementation report's `files_changed` (expected union: `dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html`, `tests/dashboard/test_i00078_layout.py`, possibly `dashboard/static/tailwind.src.css` / `dashboard/templates/components/step_pipeline.html` / `dashboard/static/theme-toggle.js`)

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S05_CodeReview_Final_report.md` — final review report

## Context

You are performing the final cross-agent review of all I-00078 work — looking at the whole picture, not individual steps. Per-agent reviews (S02, S04) are done; catch what they couldn't.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1–AC5) — every criterion must be satisfied by the combined work.
- Read `## TDD Approach` / `## Test to Reproduce` — `tests/dashboard/test_i00078_layout.py` must exist (in S03's `files_changed`) and cover all five ACs. A missing/uncovered AC is a CRITICAL finding.
- Read the design's **Notes** — the htmx-poll-vs-theme-toggle hazard and the `make css` / plain-CSS guidance.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on all changed files, fix nothing, report only:

```bash
make lint          # ruff + node --check + scripts/check_templates.py
make format        # ruff format --check
```

New violations → CRITICAL (`"category":"conventions"`). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design

- All four fixes implemented (dark scrollbars + hover + Firefox; pipeline-strip padding; dvh-shell single-scrollbar; full-width footer with the theme toggle moved in)?
- Any AC with no corresponding code or test? → CRITICAL.
- Any TODO / placeholder / commented-out fragment left behind in `base.html`?

### 2. Cross-cutting integration

- `base.html` ↔ `llm_usage_footer.html`: the `hx-get`/`hx-swap` is on the inner meters `<div>`, not `<footer>`; the fragment renders only the meters and still pins the version label right; a poll refresh does NOT remove the theme toggle. **Re-trace this path end-to-end** — it's the highest-risk integration point.
- `base.html` ↔ `theme-toggle.js` / the `<head>` pre-paint script: exactly one `id="theme-icon"`; `toggleDarkMode()` still toggles `.dark` on `<html>` and persists; the relocated button works on first paint and after htmx swaps anywhere on the page.
- `base.html` ↔ `toggleSidebar()` and the mobile sidebar transform/backdrop: still functional inside the new `[sidebar + content]` row.
- `base.html` ↔ `{% block %}` consumers: `title`, `head`, `page_help_slug`, `oss_status_anchor`, `breadcrumb`, `content`, `scripts` all still present and in a sensible place. Spot-check that a couple of real pages still render (e.g. the `client` fixture GET on `/` and `/system/status` in your test run below).
- `theme.css` / `styles.css`: if `make css` was run, the regenerated `styles.css` diff is sane (additions only, no dropped rules); if plain CSS was appended, it's valid and the scrollbar/`100dvh`/pipeline rules are actually being applied (not shadowed by an earlier rule).
- The stale-DB banner branch still renders and now fits inside the dvh column without re-introducing a body scrollbar.

### 3. Architecture / conventions

- Read `dashboard/CLAUDE.md` and `CLAUDE.md`. Tailwind classes follow project idioms; no dynamic class construction; Jinja2 `format` filter stays `%`-style (only if `step_pipeline.html` was touched).

### 4. Test coverage (holistic)

- Does `tests/dashboard/test_i00078_layout.py` pin every structural invariant (footer is a full-width sibling of the sidebar; toggle in footer, not sidebar; toggle outside the htmx-swap sub-tree; dvh shell, old `flex h-screen` wrapper gone; `<main>` is the scroller; `.iw-pipeline-strip` non-zero `padding-bottom`; `::-webkit-scrollbar-thumb` not `var(--border)` with `:hover` + Firefox fallback; single `id="theme-icon"`)? Are the assertions semantic, not shape-only? Are class checks attribute-scoped?

### 5. Security

- No hardcoded secrets/URLs/ports introduced anywhere. (None expected.)

## Test Verification (NON-NEGOTIABLE)

Run the **full** suite:

```bash
make test-unit
make test-integration
uv run pytest tests/dashboard/test_i00078_layout.py -v
```

Report results accurately. Integration-test failure → CRITICAL.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Missing AC/requirement; htmx poll wipes the toggle; two scrollbars remain; footer not full-width; migration sneaked in; integration tests fail; lint/format violation | Must fix |
| HIGH | Significant integration bug / architectural violation | Must fix |
| MEDIUM (fixable) | Code-quality / shape-only test / minor convention issue | Should fix |
| MEDIUM (suggestion) / LOW | Optional / informational | — |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00078",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "completeness|consistency|integration|testing|architecture|security", "file": "path", "line": 0, "description": "...", "suggestion": "...", "cross_cutting": true}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z dashboard passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
- `missing_requirements`: any design requirement with no implementation — each is automatically CRITICAL.
