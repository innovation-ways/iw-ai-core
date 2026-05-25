# CR-00082_S04_CodeReview_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
**Step Being Reviewed**: S01 + S02 + S03 (all three implementation steps)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy — see S01 prompt for full text.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. Any new file under `orch/db/migrations/versions/**` is a **CRITICAL** finding.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00082 --json`
- `ai-dev/work/CR-00082/CR-00082_CR_Design.md` — Design document
- `ai-dev/work/CR-00082/reports/CR-00082_S01_Backend_report.md`
- `ai-dev/work/CR-00082/reports/CR-00082_S02_Backend_report.md`
- `ai-dev/work/CR-00082/reports/CR-00082_S03_Backend_report.md`
- All files listed in those reports' `files_changed` arrays

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_S04_CodeReview_report.md`

## Context

You are reviewing the **three backend implementation steps** of CR-00082 in one pass. The three steps are cohesive — they collectively deliver the visual-regression layer — so a single per-agent review covers them.

Read the design document first. Read all three implementation reports. Then review all changed files.

## Read the Design Document FIRST

Read these sections in full before opening any code:

- `## Acceptance Criteria` (AC1–AC8) — every criterion is a mandatory check.
- `## TDD Approach` — note that this CR's "RED" evidence is the deliberate-regression demonstration described in S01 and S02 prompts (not a conventional new unit test).
- `## Impacted Paths` — every modified file MUST match this list. Any out-of-list file is a **CRITICAL** scope-creep finding.
- `## Notes` — pixel-tolerance discipline, Playwright CLI rules, baseline-management discipline.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format-check
```

If either reports NEW violations in this CR's changed files (i.e., violations not on `main`), classify each as a **CRITICAL** finding (`category: conventions`).

## Review Checklist

### 1. Scope discipline (AC8)

- Diff between this branch and `main` MUST touch ONLY paths inside `scope.allowed_paths` in `workflow-manifest.json`. Specifically: `tests/visual/**`, `tests/e2e/playwright_wrapper.py`, `Makefile`, `pyproject.toml`, `uv.lock`, `.github/workflows/visual-regression.yml`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`, `ai-dev/active/CR-00082/**`.
- Any file under `orch/`, `dashboard/` (except its templates — but this CR shouldn't touch those either), `executor/`, `scripts/`, `bin/`, `orch/db/migrations/versions/**` is a **CRITICAL** scope-creep finding.

### 2. Playwright CLI compliance (AC6)

- `tests/visual/test_html_visual_regression.py` and the extended `tests/e2e/playwright_wrapper.py` MUST contain ZERO occurrences of `chromium.launch`, `agent-browser`, or `npx playwright install`.
- No edits to `.playwright/cli.config.json`.
- All browser entry points go through `playwright-cli` subprocess wrappers.

Any violation is **CRITICAL**.

### 3. Pixel-tolerance discipline (Design Notes)

- S01 picked a single pixel-tolerance constant. S02 MUST reuse that constant (import or shared helper) — NOT pick its own. A second hardcoded tolerance value is **HIGH**.
- S01's report `notes` records the chosen value + rationale. Verify it is present and plausible.

### 4. Baseline-management discipline (AC4, Design Notes)

- Total baseline count is between 8 and 15 (count PDFs + HTML).
- Each editorial category in `doc-system/` has at least one representative baseline.
- No auto-accept logic — the test code does NOT contain a branch that overwrites baseline files on regression. Search for write-paths into `tests/visual/baselines/**` in the test sources. If any test code writes there, **CRITICAL**.

### 5. CI workflow correctness (AC5)

- `.github/workflows/visual-regression.yml` has all three triggers: cron, `workflow_dispatch`, `pull_request` with the exact path filters from S03's requirements.
- On failure, the job uploads `tests/output/visual-diff/**` as an artefact.
- Burn-in comment names the flip date (2026-06-01) and `continue-on-error: true` for the burn-in window.

### 6. Docs / skill / tracker correctness (AC7)

- `docs/IW_AI_Core_Testing_Strategy.md` §2 has a "Layer 8 — visual regression" subsection.
- §5 has a new gate row for `make visual-regression`.
- §9's visual-regression row is ✅ with CR-00082 + 2026-05-24.
- `skills/iw-ai-core-testing/SKILL.md` has the new section.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-equal to the master copy (verify via `diff`).
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.1 = DONE; v1.4 header entry dated 2026-05-24 present.

### 7. Failure path (AC3)

- Failure messages in both test modules MUST include the absolute path to the `*-diff.png` file. Read the `pytest.fail(...)` or equivalent calls and verify.
- Both S01 and S02 `tdd_red_evidence` show a deliberate-regression run with a `*-diff.png` path captured, AND a confirmation that the deliberate regression was reverted (target green again).

### 8. RED evidence (TDD §5a)

Verify `tdd_red_evidence` in S01 + S02 reports describes the deliberate-regression run. S03's `tdd_red_evidence` should be `"n/a — CI yaml + docs + skill + tracker edits only, no behavioural production logic"`. Anything else is a **HIGH** finding.

### 9. Dependency / lockfile correctness

- `pyproject.toml` adds `Pillow` and `pixelmatch` to `[dependency-groups] dev`. Both pins resolve. `uv.lock` is regenerated and consistent.

### 10. Project conventions

- Read `CLAUDE.md`, `tests/CLAUDE.md`, and `skills/iw-ai-core-testing/SKILL.md` for project-specific testing conventions. Verify the new modules follow them.

## Test Verification (NON-NEGOTIABLE)

```bash
make visual-regression
uv run pytest tests/visual/ -v
```

Both must pass. Report results accurately. Do NOT run the full unit/integration suites — those are S10/S11 QV gates.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope creep, security vulnerability, Playwright-rule violation |
| **HIGH** | Significant bug, missing requirement, architectural violation, second hardcoded pixel tolerance |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation |
| **MEDIUM (suggestion)** | Design improvement, better pattern available |
| **LOW** | Nitpick, style preference |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00082",
  "step_reviewed": "S01+S02+S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make visual-regression: PASS",
  "notes": ""
}
```
