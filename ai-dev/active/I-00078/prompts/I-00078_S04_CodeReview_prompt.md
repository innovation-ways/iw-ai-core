# I-00078_S04_CodeReview_prompt

**Work Item**: I-00078 — Dashboard layout: invisible dark-mode scrollbars, double vertical scrollbar hiding the footer, and a full-width footer with the theme toggle inside it
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00078 --json`.
- `ai-dev/active/I-00078/I-00078_Issue_Design.md` — design document (`## Test to Reproduce`, `## Acceptance Criteria`, `## TDD Approach`)
- `ai-dev/active/I-00078/reports/I-00078_S03_tests-impl_report.md` — S03 report
- `tests/dashboard/test_i00078_layout.py` — the test file under review
- `ai-dev/active/I-00078/reports/I-00078_S01_frontend-impl_report.md` — to confirm the tests assert against what S01 actually built
- The S01-changed files (`dashboard/templates/base.html`, `dashboard/static/theme.css`, `dashboard/static/styles.css`, `dashboard/templates/fragments/llm_usage_footer.html`)

## Output Files

- `ai-dev/active/I-00078/reports/I-00078_S04_CodeReview_report.md` — review report

## Context

You are reviewing the test coverage S03 added for I-00078. The point of these tests is to (a) prove the bug existed (would FAIL pre-fix) and (b) lock the four fixes in place against regression.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1–AC5). Every AC must have a corresponding assertion in `tests/dashboard/test_i00078_layout.py`. If an AC has no test, that's a CRITICAL finding (missing required test).
- Read `## Test to Reproduce` and `## TDD Approach` — the design names `tests/dashboard/test_i00078_layout.py` and lists the mandatory semantic checks; confirm they're all present.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on `tests/dashboard/test_i00078_layout.py` (and any other file in S03's `files_changed`), fix nothing, report only:

```bash
make lint
make format
```

New violations → CRITICAL findings (`"category":"conventions"`). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Semantic correctness (the I003 lesson)

For each test function, confirm the assertion is **semantic**, not shape-only:

- ❌ `assert "footer" in html` / `assert "padding-bottom" in css` / `assert "h-dvh" in html` *alone* with no positional/structural context for the first two — flag as MEDIUM (fixable).
- ✅ `html.index("<footer") > html.index("</aside>")`; parsing the `.iw-pipeline-strip { ... }` block and asserting *that block* has non-zero `padding-bottom`; `"var(--border)" not in <the ::-webkit-scrollbar-thumb block>`; `"toggleDarkMode()" not in <sidebar slice>` and `in <footer slice>`; `html.count('id="theme-icon"') == 1`.

CSS-class assertions on rendered HTML must be attribute-scoped (`class="…w-full…"` regex), not bare substring (I-00067) — bare-substring class checks are a MEDIUM (fixable) finding.

### 2. AC coverage

| AC | Expected test |
|----|---------------|
| AC1 (dark scrollbars) | `::-webkit-scrollbar-thumb` not `var(--border)` + `:hover` rule + Firefox `scrollbar-color`/`scrollbar-width` present |
| AC2 (pipeline spacing) | `.iw-pipeline-strip` block declares non-zero `padding-bottom` |
| AC3 (single scrollbar / footer visible) | shell uses `h-dvh`/`100dvh`; old `flex h-screen overflow-hidden` wrapper absent; `<main>` is the `overflow-y-auto` scroller; footer comes after `</aside>` |
| AC4 (full-width footer + toggle inside) | footer has full-width class; `toggleDarkMode()` in footer, not sidebar; toggle is outside the `hx-swap="innerHTML"` sub-tree; single `id="theme-icon"`; `onclick="toggleDarkMode()"` still present |
| AC5 (regression test exists) | the file `tests/dashboard/test_i00078_layout.py` exists and the suite passes |

Any AC with no test → CRITICAL.

### 3. Test hygiene

- Tests live under `tests/dashboard/` (the `client` fixture lives there). A test using `client` placed elsewhere is a CRITICAL finding.
- Tests are isolated and deterministic — no reliance on live DB (port 5433), no network, no order dependence.
- CSS files opened with `encoding="utf-8"`.
- Test names clearly describe what they verify.
- No over-broad regex that would also match unrelated CSS/HTML and silently pass against the buggy code.

### 4. Conventions

Read `tests/CLAUDE.md`, `dashboard/CLAUDE.md`, `CLAUDE.md`. Match the style of existing `tests/dashboard/test_*.py`.

## Test Verification (NON-NEGOTIABLE)

Run the new test file and a quick unit sweep:

```bash
uv run pytest tests/dashboard/test_i00078_layout.py -v
make test-unit
```

Report results accurately. If `tests/dashboard/test_i00078_layout.py` fails against the *current* (post-S01) code, that's a CRITICAL finding (either the tests are wrong or S01 didn't actually fix something — diagnose which and say so).

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | An AC has no test; a `client` test placed outside `tests/dashboard/`; the test file fails on current code; lint/format violation | Must fix before merge |
| HIGH | A test asserts the wrong thing / would pass against the buggy code | Must fix before merge |
| MEDIUM (fixable) | Shape-only assertion; bare-substring class check; flaky/over-broad regex | Should fix in fix cycle |
| MEDIUM (suggestion) / LOW | Naming, extra coverage ideas | Optional / informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00078",
  "step_reviewed": "S03",
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

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
