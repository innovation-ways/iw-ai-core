# CR-00052_S02_CodeReview_prompt

**Work Item**: CR-00052 -- Allure reporting recipes + curated smoke layer with SLA (P1-CR-E)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands except read-only introspection or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration in `files_changed` as a CRITICAL scope violation.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status CR-00052 --json` — runtime step state.
- `ai-dev/active/CR-00052/CR-00052_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00052/reports/CR-00052_S01_Backend_report.md` -- Impl step report (**must contain the audit table** — see Checklist 3)
- `ai-dev/active/CR-00052/evidences/pre/cr-00052-smoke-baseline.txt` — the RED baseline
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00052/reports/CR-00052_S02_CodeReview_report.md`

## Context

You are reviewing S01's implementation of **CR-00052 — Allure recipes + smoke SLA (P1-CR-E)**. The CR has two halves: (a) 6 Allure recipes ported from the InnoForge pattern; (b) a smoke audit that trims 16 → ≤15 tests covering all 5 plan-listed critical paths plus a documented SLA. The audit table in S01's step report is the most important deliverable — without an honest, line-by-line audit, AC5 can't be verified.

Read the design first. ACs are AC1–AC9. The single biggest CRITICAL risk: a smoke set that's claimed to cover all 5 paths but actually has a gap. The audit table is how you verify this.

## Read the Design Document FIRST

- AC1–AC9 are mandatory checks.
- "Impacted Paths" defines scope. Any file in `files_changed` outside that list = CRITICAL (especially production code under `orch/dashboard/executor/`).
- The "Notes" section explains: S09 is the first real `integration-tests` gate run; `allure` CLI is a separate binary that needs an install-check; the audit table is the deliverable (not a side-effect).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations = CRITICAL with `"category": "conventions"`.

## Review Checklist

### 1. Allure recipes work — exercise them

```bash
make allure-clean
make allure-unit
ls tests/output/allure-results/ | head -5
```

- The 3 commands above must exit 0 and the `ls` must show `*-result.json` files. If `make allure-unit` exits non-zero, that's a CRITICAL finding (AC1 fails). If `ls` is empty (no result files written), CRITICAL (the recipe is broken).
- Repeat the exit-0 check for `make allure-clean`, `make allure-integration`, `make allure-all`, `make allure-report` (the last requires `allure` CLI; if it's not installed locally, verify the recipe prints a clear install-hint error and exits 1 — that's the AC3-correct behaviour, not a fail).
- `make allure-serve` is interactive; verify by inspection that the recipe runs `allure serve $(ALLURE_RESULTS)` and has the same `command -v allure` install-check as `allure-report`.

### 2. `.gitignore` covers Allure artefacts

After `make allure-unit`:

```bash
git status --short | grep -E "allure-results|allure-report"
```

Must produce **no output** — meaning the dirs are gitignored. If output appears, that's a HIGH finding (AC7 fails). Verify `.gitignore` lists `tests/output/allure-results/` and `tests/output/allure-report/`.

### 3. The audit table is honest

This is the highest-stakes check in this review. Open S01's report and find the audit table.

For **each row** in the table:

- **Open the test file at the named test name** and read the test body. Does it actually exercise what the audit row claims it does? Spot-check at least 5 rows in detail; trust-but-verify the rest by sampling.
- For tests marked **keep**: does the test ACTUALLY exercise the claimed critical path? A row that says "covers `iw-next-id`" but tests an unrelated helper function is a HIGH finding.
- For tests marked **remove** (decorator removed): is the rationale plausible? An entry that says "redundant" but actually covers a still-needed path is HIGH.
- For tests marked **add** (decorator added): same scrutiny — does it actually cover the path it's now mapped to?

After the audit-table audit:

- Count the smoke markers in the patched tree:
  ```bash
  grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | awk -F: '{s+=$2} END {print s}'
  ```
  Must be **≤15**. >15 = CRITICAL (AC5 fails).
- Check each of the 5 plan paths has at least one test mapped to it in the final state. For each path, find ≥1 row in the audit table where the path appears in "Covers path(s)" AND the decision is "keep" (or "add"). If any path has 0 keepers, CRITICAL.

### 4. Wall-clock SLA verified

```bash
time make smoke
```

- Wall-clock must be **<60 s**. If ≥60 s, CRITICAL (AC4 fails).
- The recorded measurement in S01's report and §11 changelog must be within ±5 s of what you measure. Larger discrepancies = HIGH (the report is misleading).

### 5. SLA prose is consistent across all 3 locations

Read the SLA prose in:
- `tests/CLAUDE.md` (new "Smoke layer SLA" subsection)
- `docs/IW_AI_Core_Testing_Strategy.md` (§5 or §6 area)
- `pyproject.toml` (the smoke marker description)

Check:
- All three quote the same count cap (≤15), same wall-clock cap (<60 s), same 5 critical-path names.
- The actual measured wall-clock from AC4 appears in at least `tests/CLAUDE.md` (e.g. "measured 2026-05-14: 42.3s").
- Each location is plausibly written for its audience (tests/CLAUDE.md = test authors; strategy doc = broader; pyproject marker = test authors writing new tests).

Inconsistencies (e.g. one says "≤15" and another says "≤20") = HIGH finding.

### 6. Scope discipline

`grep` `files_changed` for any path under `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`. Any hit = CRITICAL scope violation.

Other out-of-scope flags:
- New test files (anything not in the existing 7 smoke files + possibly 1-2 new files if S01 added markers to existing-non-smoke tests) — only **existing** test files should have decorator changes.
- Test body changes — only `@pytest.mark.smoke` lines should be touched in test files. Use `git diff` on each tests/*.py file: should show only marker add/remove, no logic changes.
- `make smoke-sla` target (out of scope — operator's call to keep this CR small).
- CI changes to `.github/workflows/*.yml` (out of scope — the report is local-only).
- Sibling-project syncs (out of scope).

### 7. RED evidence

S01's `tdd_red_evidence` must record both halves: (a) the empty-allure-stub proof; (b) the 16-tests / no-SLA baseline. If `"n/a"` — HIGH (this CR has a real RED anchor by design).

### 8. The integration-tests gate is exercised for the first time post-flip

This isn't a check on S01 — it's a flag for S03 / the daemon: CR-00052's S09 will be the first run of the real `make test-integration` gate after the 2026-05-14 flip. If S01's changes happen to land on a worktree where the integration suite has latent failures (the CR-00048 pytest-randomly fallback context), S09 may surface them. Note in your review whether you saw any integration-test red flags during your spot-checks of the patched tree.

## Test Verification (NON-NEGOTIABLE)

Run these. Any non-zero exit on 1–4 is CRITICAL.

1. `make allure-clean && make allure-unit && ls tests/output/allure-results/ | head -3` — must produce result files.
2. `time make smoke` — exit 0, wall-clock <60s, count ≤15.
3. `make lint && make format-check` — clean.
4. `git status --short | grep -E "allure-(results|report)"` — must produce no output (verifies .gitignore).

Do NOT run `make check` / `make test-integration` / `make diff-coverage` — that's S08-S11's job.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | AC failure, missing-path-coverage in audit, broken recipe, count >15, wall-clock ≥60s, scope violation | Must fix |
| **HIGH** | Inconsistent SLA prose, dishonest audit row, missing tracking comment, measurement off by >5s | Must fix |
| **MEDIUM (fixable)** | Convention violation, minor inconsistency | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Style nit | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00052",
  "step_reviewed": "S01",
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
  "test_summary": "make allure-unit ok (results in tests/output/allure-results/). make smoke: <N> tests, <T>s. .gitignore covers artefacts. lint+format-check clean.",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
