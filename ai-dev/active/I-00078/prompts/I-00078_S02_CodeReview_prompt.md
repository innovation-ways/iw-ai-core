# I-00078_S02_CodeReview_prompt

**Work Item**: I-00078 — Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema. Flag any alembic/migration change as out of scope.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00078 --json`.
- `ai-dev/active/I-00078/I-00078_Issue_Design.md` — design document
- `ai-dev/active/I-00078/reports/I-00078_S01_frontend-impl_report.md` — S01 report
- All files in S01's `files_changed` (expected: `dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html`, possibly `dashboard/static/tailwind.src.css` / `dashboard/templates/components/step_pipeline.html` / `dashboard/static/theme-toggle.js` / `tests/dashboard/test_i00078_layout.py`)

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S02_CodeReview_report.md` — review report

## Context

You are reviewing the dashboard layout fixes implemented in S01 for I-00078. Read the design doc first (Root Cause Analysis #1–#4, AC1–AC4, the Notes section), then the S01 report, then the changed files.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1–AC5) in full — each is a mandatory check.
- Read `## TDD Approach` and `## Test to Reproduce` — note the test file `tests/dashboard/test_i00078_layout.py` and the semantic checks it must contain. (The *full* test set is S03's job; S01 only needs a minimal RED→GREEN test. If S01 added zero tests *and* the design's RED test would not exist until S03, that's acceptable here — but note it; if S01 claimed `tests_passed: true` without any test file existing, that's a HIGH finding.)

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`, fix nothing, report only:

```bash
make lint          # ruff + node --check (dashboard JS) + scripts/check_templates.py (Jinja2)
make format        # ruff format --check
```

Any NEW violation in the changed files (not present on `main` pre-S01) → CRITICAL finding with `"category":"conventions"`, `file`, `line`, and the exact code/message. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Correctness vs the four fixes

- **Fix 1 (dark scrollbars)** — `::-webkit-scrollbar-thumb` no longer uses `var(--border)`; a `--scrollbar-thumb`/`--scrollbar-thumb-hover` pair (or equivalent high-contrast value) is defined in **both** `:root` and `.dark`; a `::-webkit-scrollbar-thumb:hover` rule exists; Firefox `scrollbar-width: thin` + `scrollbar-color: … transparent` is declared. Sanity-check the dark thumb colour actually contrasts with the dark background (`--background` in `.dark`).
- **Fix 2 (pipeline spacing)** — `.iw-pipeline-strip` declares a non-zero `padding-bottom` (or the spacing is added via a wrapper in `step_pipeline.html`). Pill/connector styling unchanged.
- **Fix 3 (single scrollbar)** — the app layout is sized with a dynamic-viewport unit (`h-dvh` / `100dvh`), `html, body` are pinned (`height:100%; overflow:hidden`), the body is a single flex column (`banner` shrink-0 → `[sidebar+content]` row flex-1 → `footer` shrink-0), and `<main>` is the only `overflow-y-auto`. The old `<div class="flex h-screen overflow-hidden">` wrapper is gone. There must NOT be two nested `overflow-y-auto` scrollers fighting (the sidebar's own `overflow-y-auto` is fine — it's a separate column).
- **Fix 4 (full-width footer + theme toggle)** — `<footer>` is a sibling of the `[sidebar+content]` row (not nested inside the content column), carries a full-width class, and is `flex-shrink-0`. The theme toggle (`onclick="toggleDarkMode()"`) is a **static** child of `<footer>`, on the left, *outside* the htmx-swapped sub-tree. The `hx-get="/api/usage/llm/fragment"` / `hx-trigger` / `hx-swap="innerHTML"` are on an inner `<div>` (the meters container), **not** on `<footer>` itself — if they're still on `<footer>`, the first poll wipes the toggle: that's a CRITICAL finding. The sidebar's old theme-toggle block is removed. Exactly one element has `id="theme-icon"`. `theme-toggle.js`, the `<head>` pre-paint script, and `toggleSidebar()` still work; the `{% block %}` names are intact.

### 2. Regression risks

- Mobile sidebar: `toggleSidebar()`, `#sidebar-backdrop`, the `-translate-x-full lg:translate-x-0 lg:static` classes — still functioning?
- The stale-DB banner branch (`{% if is_db_stale(request) %}`) — still renders, and now fits inside the dvh column without causing overflow?
- `llm_usage_footer.html` — still NOT extending `base.html`; still renders only the meters; `ml-auto` still pins the version label right within the wider footer.
- `make css` — if S01 ran it, is the regenerated `styles.css` diff sane (only the expected additions, no mass churn that drops existing rules)? If S01 appended plain CSS instead, is it valid and placed sensibly?

### 3. Project conventions

- Jinja2 `format` filter stays `%`-style (only relevant if S01 touched `step_pipeline.html` — it has a `"%dm%02ds"|format(...)`).
- Tailwind class idioms match the rest of `base.html`. No dynamically-constructed class strings that break JIT purging.
- Read `dashboard/CLAUDE.md` and `CLAUDE.md` for anything else.

### 4. Security

- No hardcoded secrets/URLs/ports introduced. (None expected for a CSS/template change.)

### 5. Testing

- If `tests/dashboard/test_i00078_layout.py` exists, do its assertions check **semantics** (footer is a full-width sibling of the sidebar, toggle in footer not sidebar, dvh shell, pipeline padding, non-`--border` thumb) — not just "the word footer appears"? Shape-only assertions are a MEDIUM (fixable) finding. CSS-class assertions on rendered HTML should use the attribute-scoped form (`class="…w-full…"`), not bare substring (I-00067).

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` (fast, no containers) to confirm no regression, and `uv run pytest tests/dashboard/test_i00078_layout.py -v` if that file exists. Report results accurately in the contract.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality (e.g. htmx poll wipes the toggle; footer still nested; two scrollbars remain) | Must fix before merge |
| HIGH | Significant bug / missing AC / convention violation | Must fix before merge |
| MEDIUM (fixable) | Code-quality / shape-only test / minor convention issue | Should fix in fix cycle |
| MEDIUM (suggestion) | Better pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00078",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "architecture|code_quality|conventions|security|testing", "file": "path", "line": 0, "description": "...", "suggestion": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable). Otherwise `fail`.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
