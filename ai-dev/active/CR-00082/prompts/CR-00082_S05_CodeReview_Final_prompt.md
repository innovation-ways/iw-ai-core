# CR-00082_S05_CodeReview_Final_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

(Standard policy — see S01 prompt for full text.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. Any new file under `orch/db/migrations/versions/**` is a **CRITICAL** finding.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00082 --json`
- `ai-dev/work/CR-00082/CR-00082_CR_Design.md`
- All implementation step reports: `ai-dev/work/CR-00082/reports/CR-00082_S0{1,2,3}_Backend_report.md`
- S04 review report: `ai-dev/work/CR-00082/reports/CR-00082_S04_CodeReview_report.md`
- All files listed in all implementation reports' `files_changed` arrays

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_S05_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of CR-00082. Per-step review (S04) has already covered each backend step's internal quality. Your job is to catch cross-cutting issues:

- Do S01's PDF module and S02's HTML module share the same diff helper (DRY)?
- Does S03's CI workflow actually run the targets S01 + S02 produced (no name mismatch)?
- Are AC1–AC8 each satisfied by the combined work?
- Is the documentation set (strategy doc + skill + tracker) internally consistent on counts, dates, CR-IDs?

## Read the Design Document FIRST

Read these in full:

- `## Acceptance Criteria` (AC1–AC8) — every criterion is a final-review check.
- `## Impacted Paths` — every modified file MUST match.
- `## TDD Approach` — note the deliberate-regression evidence pattern.
- `## Notes` — pixel-tolerance discipline, baseline-management discipline, Playwright CLI rules.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

New violations in this CR's changed files are **CRITICAL**.

## Review Checklist

### 1. Completeness vs design

For each AC1–AC8, locate the exact line(s) in the implementation that satisfy it. Any AC without a clear satisfying implementation is a **CRITICAL** finding (`missing_requirements`).

### 2. Cross-step consistency

- S01's pixel-tolerance constant is imported / shared by S02 — verify by reading the source. A second hardcoded value is **HIGH**.
- S01's diff-helper code path is reused by S02 (single function or shared module). Copy-paste duplication is **MEDIUM (fixable)**.
- S03's `.github/workflows/visual-regression.yml` invokes `make visual-regression`, and that target exists in `Makefile` (S02 added it).

### 3. Integration

- Run `make visual-regression` end-to-end in this worktree. It MUST pass.
- Run `uv run pytest tests/visual/ -v`. It MUST pass.
- Run `make visual-regression-pdf` and `make visual-regression-html` independently. Both MUST pass.

### 4. Doc / skill / tracker internal consistency

- `docs/IW_AI_Core_Testing_Strategy.md` §9 row count for visual regression matches reality (8–15 baselines).
- `docs/IW_AI_Core_Testing_Strategy.md` §2 layer count is bumped to 8.
- `skills/iw-ai-core-testing/SKILL.md` master and `.claude/skills/iw-ai-core-testing/SKILL.md` are byte-equal (run `diff`).
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.1 status, v1.4 header date, and the CR-ID (CR-00082) all match.

### 5. Scope compliance (AC8)

```bash
git diff --name-only main...HEAD
```

Every line MUST match `scope.allowed_paths` in `workflow-manifest.json`. Any file outside is **CRITICAL** scope-creep.

### 6. Playwright CLI compliance (AC6)

Grep the full diff for `chromium.launch`, `agent-browser`, `npx playwright install`, `.playwright/cli.config.json`. Any match outside the original `tests/e2e/playwright_wrapper.py` lines is **CRITICAL**.

### 7. Security (cross-cutting)

- No hardcoded credentials, secrets, or API keys in CI yaml.
- No `pull_request_target` trigger (forbidden — it grants secrets to forks).
- The CI workflow does not check out submodules with secrets.

### 8. Architecture compliance

- The new test module is under `tests/visual/` (a new sibling of `tests/unit/`, `tests/integration/`, `tests/dashboard/`, `tests/e2e/`). It does NOT live under any of the existing test directories.
- `tests/visual/test_*.py` is NOT collected by `make test-unit` or `make test-integration` (verify the project's `pytest.ini` / `pyproject.toml` `[tool.pytest.ini_options]` `testpaths` config). If `tests/visual/` is accidentally included in those collections, the daemon QV gates will time out — **CRITICAL**.

## Test Verification (NON-NEGOTIABLE)

Run the FULL test suite:

```bash
make test-unit
make test-integration
make visual-regression
```

All three must pass. If `make test-unit` or `make test-integration` regress, it is **CRITICAL** (the new test module should be invisible to them).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope creep, security vulnerability, Playwright-rule violation, AC unsatisfied, daemon gate breakage |
| **HIGH** | Significant bug, integration failure, architectural violation, second hardcoded tolerance |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation, copy-paste duplication |
| **MEDIUM (suggestion)** | Design improvement, better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00082",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z visual-regression passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
