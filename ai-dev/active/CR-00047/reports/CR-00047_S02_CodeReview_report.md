# CR-00047 — S02 (CodeReview) report

**Work item**: CR-00047 — Coverage gates — raise the floor, ratchet it, and gate diff-coverage on PRs (P1-CR-B)
**Step**: S02 (`code-review-impl`) — reviewing S01 (`backend-impl`)
**Verdict**: **pass** — 0 CRITICAL, 0 HIGH, 0 MEDIUM(fixable)

---

## What was reviewed

Read the design doc (`ai-dev/active/CR-00047/CR-00047_CR_Design.md`) — Acceptance Criteria AC1–AC8, TDD Approach, Notes — and the S01 report + run-log result contract. Then reviewed every file in `files_changed` against the design, `CLAUDE.md`, and `tests/CLAUDE.md`.

Design's TDD section names exactly one (optional) test file: `tests/unit/test_coverage_gate_config.py`. It is present in `files_changed`. ✔

## Pre-review lint & format gate

- `make lint` → **All checks passed!** (ruff + `check_templates.py` + `lint-js`)
- `make format` (`ruff format --check .`) → **676 files already formatted** — no drift.

No new `conventions` violations in the changed files.

## Acceptance-criteria check

| AC | Result |
|----|--------|
| AC1 — floor raised & documented | ✔ `pyproject.toml [tool.coverage.report] fail_under = 50` (> 46; just below the *lower* measured slice — unit 51.84 %, integration+dashboard 61.23 %). Strategy doc §1 + §5 state the floor + the "ratchet up, never down" rule. `make test-unit` passes the new floor (re-verified: 51.82 % ≥ 50). `make quality` passes. |
| AC2 — diff-coverage self-contained | ✔ `diff-cover>=9` in `[dependency-groups] dev`; `uv.lock` regenerated → `diff-cover==10.2.0`. `make diff-coverage` runs its own `pytest tests/unit/ --cov-fail-under=0` → `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser --cov-append --cov-fail-under=0` → `coverage xml -o …/coverage-combined.xml` → `diff-cover …/coverage-combined.xml --compare-branch=origin/main --fail-under=90`. Does not reuse a leftover `coverage.xml` or depend on the `integration-tests` gate. Exits non-zero on shortfall (diff-cover's `--fail-under`). Added to `.PHONY`. |
| AC3 — wired into both CI surfaces | ✔ `skills/iw-workflow/SKILL.md` canon now lists **7** gates `lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage`; the `diff-coverage` entry is `{"agent": "qv-gate", "gate": "diff-coverage", "command": "make diff-coverage", "timeout": 1800}`; the "N canonical QV gates" prose says 7; `.claude/skills/iw-workflow/SKILL.md` is byte-identical (sync ran). `.github/workflows/test-quality.yml` `unit` job has a `Run diff coverage` step after `make test-unit`, `if: github.event_name == 'pull_request'`, comparing to `origin/${{ github.base_ref }}`, with `fetch-depth: 0` on the checkout. |
| AC4 — cov-plumbing audit fixes | ✔ `[tool.coverage.run] relative_files = true` added. Audit findings recorded in the design's `## Notes` and in the S01 report §2 + `TESTS_ENHANCEMENT.md` item 1.10: `pytest --cov` already correct; raw-`.coverage`-artefact / `include-hidden-files` N/A; subprocess coverage documented as a known limitation, not wired. |
| AC5 — dogfood diff-coverage gate | ✔ Ran `make diff-coverage` end-to-end in this worktree: combined coverage 75 %; `diff-cover` → "No lines with coverage information in this diff." → **exit 0** (this CR's only changed `.py` is `tests/…` which is in `[tool.coverage.run] omit`). |
| AC6 — plan & strategy doc | ✔ `TESTS_ENHANCEMENT.md`: items 1.2/1.3/1.10-audit → DONE (CR-00047); P1-CR-B → SHIPPED; "*(start here)*" → P1-CR-C; sequencing rationale + top status blurb + open-Q resolved; changelog entry added. `IW_AI_Core_Testing_Strategy.md`: §1 principle row, §5 Coverage row + new Diff-coverage row + new "Coverage floor & diff-coverage" sub-section (incl. the daemon=combined / GH-step=unit caveat), §9 both rows → ✅. |
| AC7 — testing skill | ✔ `skills/iw-ai-core-testing/SKILL.md` §8 adds `diff-coverage`, the 7-gate canon line, and the `fail_under` floor/ratchet note; `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical (sync ran). |
| AC8 — tdd_red_evidence honest | ✔ The contract's `tdd_red_evidence` is a real RED snippet for `tests/unit/test_coverage_gate_config.py` (`AssertionError: assert 46 == 50`), not a contrived/vacuous test — it pins actual parsed `pyproject.toml`/`Makefile` values. |

## TDD RED evidence (§5a)

1. `tdd_red_evidence` present and plausible — `AssertionError: assert 46 == 50` (a real assertion failure, not an Import/Syntax/collection error). ✔
2. Would the test fail against pre-change code? Yes — `test_coverage_fail_under_is_the_raised_floor` asserts `fail_under == 50`; pre-change `pyproject.toml` had `fail_under = 46`. Genuine RED-first for that assertion. ✔
3. Stash-recheck: **not performed** (git stash mid-workflow in the daemon worktree is risky; the optional step is not mandatory).

## Test verification

- `make test-unit` → **2800 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed**; coverage gate: `Required test coverage of 50.0% reached. Total coverage: 51.82%`. ✔ (The 2 `test_safe_migrate.py` failures the S01 report flags did **not** reproduce here — they only surface when `IW_CORE_PER_WORKTREE_DB=true` leaks into the env, which is not set in this run.)
- `make diff-coverage` → **exit 0** (2261 integration+dashboard passed; combined coverage XML written; `diff-cover` → no changed lines to judge).
- `make test-assertions` → "No new assertion-scanner violations (419 files scanned)."
- `make type-check` → "Success: no issues found in 240 source files."
- `make lint`, `make format`, `make quality` → pass.

## Findings

| # | Severity | Category | File:line | Issue | Suggestion |
|---|----------|----------|-----------|-------|------------|
| 1 | MEDIUM (suggestion) | code_quality | `.github/workflows/test-quality.yml:77` | The `Run diff coverage` step's `if: github.event_name == 'pull_request'` overrides GitHub Actions' implicit `success()`, so the step also runs when `make test-unit` failed (adds a second, possibly confusing, failure annotation — or a "file not found" if `coverage.xml` wasn't produced because of a collection error). | `if: success() && github.event_name == 'pull_request'`. Low practical impact (the job is already red), so the author can decide. |
| 2 | LOW | code_quality | `pyproject.toml:163` | `fail_under = 50` leaves only ~1.84 pts of headroom over the measured unit slice (51.82–51.84 %). It is the design's rule-of-thumb value (lower slice rounded down to the nearest 5) and within AC1, but a routine CR's coverage wobble on the unit slice could trip the S08 `unit-tests` QV gate (no fix cycle). | Informational. Per the ratchet rule the correct response if it ever fires is to add coverage, not lower the floor — already documented. A more conservative 48–49 was also acceptable per the design. |
| 3 | LOW | testing | `tests/unit/test_coverage_gate_config.py` | The RED run reported "1 failed, 3 passed" — the `relative_files` / `diff-cover` / `Makefile` prod changes were already in place when the RED run was taken, so only the `fail_under` assertion was RED. Strict TDD would run the test before *any* prod change. | Acceptable for an explicitly-optional config guard test (the design's `"n/a"` path was the alternative); the `assert 46 == 50` RED is genuine. No action required. |

**Out-of-scope edits**: none. `git diff --stat` + the untracked `tests/unit/test_coverage_gate_config.py` are all within `workflow-manifest.json:scope.allowed_paths`. No `integration-tests` no-op-gate fix, no other Phase-1 deps, no assertion-baseline scrub, no workflow-manifest schema change. ✔

**Note (not a finding against this CR)**: the S01 report's flagged 2 pre-existing failures in `tests/unit/test_safe_migrate.py` (`IW_CORE_PER_WORKTREE_DB=true` leaking into a `patch.dict(..., clear=False)`) — confirmed pre-existing (clean tree at `main` shows the same; not reproduced in an env without that var). `test_safe_migrate.py` is not in this CR's scope; a follow-up incident scoped to that file is warranted, as the report says. Also: untracked nested-dup dir `ai-dev/active/CR-00047/CR-00047/` predates this step — flag for orchestrator cleanup, not touched here.

## Result contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00047",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "code_quality",
      "file": ".github/workflows/test-quality.yml",
      "line": 77,
      "description": "The `Run diff coverage` step uses `if: github.event_name == 'pull_request'`, which overrides GitHub Actions' implicit `success()` — the step runs even if `make test-unit` failed, adding a redundant failure annotation (or a coverage.xml-not-found error on a collection failure).",
      "suggestion": "Use `if: success() && github.event_name == 'pull_request'`."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "pyproject.toml",
      "line": 163,
      "description": "fail_under = 50 leaves only ~1.84 points of headroom over the measured unit-suite branch coverage (51.82-51.84%); a routine coverage wobble on the unit slice could trip the S08 unit-tests QV gate (no fix cycle for QV gates).",
      "suggestion": "Informational — within the design's rule-of-thumb range and AC1. If it ever fires, add coverage per the ratchet rule rather than lowering the floor (already documented)."
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/unit/test_coverage_gate_config.py",
      "line": 34,
      "description": "RED evidence shows '1 failed, 3 passed' — the relative_files / diff-cover / Makefile production changes were already applied before the RED run, so only the fail_under assertion was RED. Strict TDD would run the test before any production change.",
      "suggestion": "Acceptable for an explicitly-optional config guard test; the `assert 46 == 50` RED is genuine. No action required."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: 2800 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed (coverage 51.82% >= 50%). make diff-coverage: exit 0 (2261 integration+dashboard passed; diff-cover: no changed lines). make lint / make format / make test-assertions / make type-check / make quality: all pass.",
  "notes": "All 8 acceptance criteria met. .claude/skills/ copies byte-identical to masters (iw sync-skills ran). diff-coverage gate dogfooded end-to-end (exit 0). Cov-plumbing audit findings recorded. No out-of-scope edits. The S01-flagged 2 pre-existing test_safe_migrate.py failures only surface when IW_CORE_PER_WORKTREE_DB leaks into the env (not set here) — out of scope for CR-00047, warrants a follow-up incident. Untracked nested-dup dir ai-dev/active/CR-00047/CR-00047/ predates this step — flag for orchestrator cleanup."
}
```
