# CR-00052_S03_CodeReview_Final_prompt

**Work Item**: CR-00052 -- Allure reporting recipes + curated smoke layer with SLA (P1-CR-E)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands except read-only or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration in `files_changed` as a CRITICAL scope violation.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status CR-00052 --json` — runtime step state.
- `ai-dev/active/CR-00052/CR-00052_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00052/reports/CR-00052_S0[12]_*_report.md` -- S01 + S02 reports
- All files in S01's `files_changed`
- `ai-dev/active/CR-00052/evidences/pre/cr-00052-smoke-baseline.txt` -- the RED baseline

## Output Files

- `ai-dev/active/CR-00052/reports/CR-00052_S03_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of CR-00052. Single implementation step (S01) + S02 per-agent review; your job is the cross-cutting view. Specifically:

1. **Independent re-verification** of the Allure recipes (do they actually work?) and the smoke audit (do all 5 plan paths really have ≥1 keeper?).
2. **Internal consistency check** — the audit table in S01's report must match the actual `git diff` for `@pytest.mark.smoke` decorators. If the table says "remove test_X" but the diff doesn't show that removal, the report is lying.
3. **The 60-second SLA holds** — re-measure independently. If S01 reported 42 s but you measure 65 s, that's a CRITICAL discrepancy.
4. **No latent issues from the integration-tests-gate flip** — CR-00052's S09 is the first real run of `make test-integration` post-2026-05-14 flip. Anticipate it by running it independently here. If it fails, that's a CRITICAL — likely the CR-00048 fallback context (pytest-randomly off) is keeping it green but S09 might still hit something.

## Read the Design Document FIRST

- AC1–AC9 are mandatory checks.
- "Impacted Paths" defines scope. Production code under `orch/dashboard/executor/` in `files_changed` = CRITICAL.
- "Notes" sections particularly: the audit table is the deliverable; `allure` CLI install-check; S09 is the first real run.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation = CRITICAL.

## Review Checklist

### 1. Completeness vs Design Document

- **AC1**: `make allure-unit` produces `*-result.json` files in `tests/output/allure-results/`. Run it.
- **AC2**: `make allure-integration` matches the `make test-integration` scope (`tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser`). Verify by reading the recipe.
- **AC3**: All 4 remaining Allure recipes have real bodies. `make allure-clean` exits 0. `make allure-all`, `make allure-report`, `make allure-serve` either run or have a clear `command -v` install-check that exits 1 with an install hint when `allure` CLI is missing.
- **AC4**: `time make smoke` — wall-clock <60s. Re-run twice; both must be under.
- **AC5**: `grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | awk -F: '{s+=$2} END {print s}'` ≤15. All 5 plan paths have ≥1 audit-table row with decision=keep (or add).
- **AC6**: SLA prose consistent across `tests/CLAUDE.md` + strategy doc + `pyproject.toml` smoke marker description (count, wall-clock, 5 paths).
- **AC7**: After `make allure-unit`, `git status --short` shows no allure-* files (gitignore works).
- **AC8**: `ai-dev/work/TESTS_ENHANCEMENT.md` §5 P1-CR-E SHIPPED, items 1.8 + 1.11 DONE, §11 has dated changelog entry with audit summary.
- **AC9**: Independent re-run of S04-S11 below.

### 2. Audit-table ↔ git-diff parity

Open S01's report. For each "remove" row in the audit table, verify `git diff` for that test file shows the `@pytest.mark.smoke` decorator was actually removed. For each "add" row, verify the decorator was actually added. For each "keep" row (the majority), verify the decorator is still present in the patched tree.

Any divergence = HIGH finding (the report is misleading). A "remove" claim with no corresponding diff hunk = CRITICAL (the audit didn't actually happen for that test).

### 3. Cross-doc consistency

The SLA prose in 3 locations must agree:

- `tests/CLAUDE.md` Smoke-SLA subsection
- `docs/IW_AI_Core_Testing_Strategy.md` Smoke-SLA section
- `pyproject.toml` smoke marker description (line 152-ish)

Check: same count cap, same wall-clock cap, same 5 path names, same measured wall-clock value. Any inconsistency = HIGH.

Also: the §11 changelog entry's counts must match S01's report counts (16 → N → M-removed + K-added).

### 4. Anticipate S09

Before the QV chain runs, do an independent smoke check on what S09 will do:

```bash
# This is what S09's gate will execute
make test-integration 2>&1 | tail -20
```

If this fails with errors or test failures, that's a CRITICAL — likely indicates either (a) the patched smoke marker re-balancing accidentally broke a previously-smoke test (HIGH-level finding in S01, route via fix cycles), or (b) latent integration-test issues that the no-op gate had been hiding (CRITICAL findings, escalate via the design's Notes section).

If `make test-integration` exits 0, you've pre-confirmed S09 will pass.

### 5. Scope discipline

`files_changed` review:
- No `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/` paths.
- No new test files. Compare against the 7 pre-existing smoke-marker files; the only test-file edits should be in those 7 (or in 1-2 additional files if S01 had to re-mark a non-smoke test for missing-path coverage — verify by reading the diff).
- Test-file diffs only touch `@pytest.mark.smoke` lines. Any non-decorator change = scope creep.
- No `make smoke-sla` target.
- No `.github/workflows/` changes beyond minimal.
- No sibling-project syncs.

### 6. Architecture / Security cross-cut

CI/tooling/docs-only CR. Neither surface applies.

## Test Verification (NON-NEGOTIABLE — definitive proof)

Run all of these. Any non-zero on 1-6 is CRITICAL.

```bash
# 1. Allure recipes (the linchpin for item 1.8)
make allure-clean
make allure-unit
ls tests/output/allure-results/ | head -3   # must show *-result.json files

# 2. Smoke SLA (the linchpin for item 1.11)
time make smoke                              # <60s, exit 0
grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | awk -F: '{s+=$2} END {print s}'   # ≤15

# 3. Lint + format
make lint
make format-check

# 4. Gitignore
git status --short | grep -E "allure-(results|report)"   # must be empty

# 5. S09 anticipation
make test-integration | tail -30             # must exit 0 (pre-confirms S09)

# 6. Daemon QV gates (the canonical chain)
make quality                                  # lint + format + typecheck + test-assertions + dead-code + dep-check
```

Do **NOT** run `make check` (would re-trigger the suites) — that's S08-S11's job.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | AC failure, missing path, broken recipe, wall-clock ≥60s, audit-table ↔ diff divergence, scope violation, S09 anticipation failure | Must fix |
| **HIGH** | Inconsistent SLA prose, audit row maps to wrong path, missing tracking detail | Must fix |
| **MEDIUM (fixable)** | Convention violation | Should fix |
| **MEDIUM (suggestion)** | Better pattern | Optional |
| **LOW** | Style | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00052",
  "steps_reviewed": ["S01", "S02"],
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
  "test_summary": "Allure recipes verified end-to-end (allure-unit produces results). make smoke: <N> tests, <T>s. make test-integration: exit 0 (S09 pre-confirmed). lint+format-check clean. Gitignore covers Allure artefacts.",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `missing_requirements`: any AC1–AC9 not met. Each is automatically CRITICAL.
- `cross_cutting`: set `true` on findings spanning multiple doc locations or affecting the consistency of the audit-table narrative.
