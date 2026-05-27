# CR-00083_S06_CodeReview_Final_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Review Step**: S06 (Final Review)
**Implementation Steps Reviewed**: S01..S04
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. Any migration in the diff = CRITICAL.

## Input Files

- `uv run iw item-status CR-00083 --json` — runtime step state.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` — design.
- All implementation reports: `ai-dev/work/CR-00083/reports/CR-00083_S0{1,2,3,4}_Backend_report.md`.
- S05 review report: `ai-dev/work/CR-00083/reports/CR-00083_S05_CodeReview_report.md`.
- All files in those reports' `files_changed`.

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S06_CodeReview_Final_report.md` — final cross-agent review.

## Context

You are performing the **global cross-agent review** for CR-00083. Per-step reviews handled S01–S03 already (S05). Your scope is the WHOLE CR — the perf modules + the CI workflow + the four documentation-surface updates (strategy doc + skill master + skill mirror + tracker) — and the cross-cutting consistency checks per-step reviews cannot do.

## Read the Design Document FIRST

Read the design doc end-to-end, especially:

- AC1–AC8 — every one is a check item for THIS review.
- The Notes section's scope-discipline rule (no production code change, regressions → Incident not in-CR fix).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Zero new violations on the diff vs. main, or file CRITICAL.

## Review Checklist (AC-anchored)

### AC1 — pytest-benchmark dependency

- `pyproject.toml` `[dependency-groups] dev` contains `"pytest-benchmark>=4.0,<5"`.
- `uv run python -c "import pytest_benchmark"` exits 0.

### AC2/AC3/AC4 — three perf modules pass budgets

- Spot-check each module: BUDGET constant present, assertion against the constant, warmup + rounds present, mean-vs-min rationale in docstring.
- For ONE module (your choice — pick the easiest to revert safely), temporarily tighten the budget by half, re-run the module, confirm it goes RED with a diff message; restore. State explicitly in your report which module you stash-tested. If stash-testing is unsafe in this worktree, skip and say so — this is OPTIONAL, the mandatory part is the static inspection.

### AC5 — Makefile umbrella + per-module + operator-only targets

Run `grep -E "^(test-perf|test-perf-daemon|test-perf-rag|test-perf-routes|test-perf-update-baseline):" Makefile`. All 5 must appear. Run `grep -E "^.PHONY:.*test-perf" Makefile` — all 5 must be in `.PHONY` (either via the aggregated top-level list at line ~6 or via explicit `.PHONY:` lines per target). Confirm `make test-perf-update-baseline` recipe prints the operator-warning line on stdout BEFORE running the benchmark saves.

### AC6 — Baseline regression detection

Inject a synthetic 30% regression into ONE perf test (e.g., add `time.sleep(<computed delta>)` inside the function being measured), run `make test-<that-module>`, confirm it fails with a diff message naming the regression percentage. Revert the sleep, re-run, confirm green. Record both runs in your report. State which module you injected the regression into.

### AC7 — Workflow YAML

Open `.github/workflows/perf-budgets.yml`. Verify:

- `on:` block has BOTH `schedule:` (with a cron expression) AND `workflow_dispatch:`.
- `on:` block has NO `pull_request:` entry (per intake).
- Main step runs `make test-perf` (NOT `make test-unit`, `make check`, or `make test-integration`).
- `actions/upload-artifact@v4` step exists with `if: always()`.
- A final `if: failure()` step appends a follow-up entry to `ai-dev/work/TESTS_ENHANCEMENT.md` (either inline-commit, PR-create, or equivalent — match existing workflow patterns).

### AC8 — Strategy doc + skill (+ mirror) + tracker consistency

Verify across the four surfaces:

| Surface | Edit | Date | CR-ID |
|---------|------|------|-------|
| `docs/IW_AI_Core_Testing_Strategy.md` §2 | New Layer 8 subsection | 2026-05-24 | CR-00083 |
| `docs/IW_AI_Core_Testing_Strategy.md` §5 | New gate row | — | CR-00083 |
| `docs/IW_AI_Core_Testing_Strategy.md` §9 | Row 4.2 → ✅ | 2026-05-24 | CR-00083 |
| `docs/IW_AI_Core_Testing_Strategy.md` §11 | New changelog entry | 2026-05-24 | CR-00083 |
| `skills/iw-ai-core-testing/SKILL.md` §4 | New "Performance budgets" subsection | — | CR-00083 |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Byte-identical mirror | — | — |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.2 | Status → DONE | 2026-05-24 | CR-00083 |
| `ai-dev/work/TESTS_ENHANCEMENT.md` header | v1.3 → v1.4 noting Phase 4 first ship | 2026-05-24 | CR-00083 |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §11 | New changelog entry | 2026-05-24 | CR-00083 |

Run `diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` — empty diff or CRITICAL finding.

Cross-check: the date 2026-05-24 and the CR-ID `CR-00083` must match VERBATIM across all four surfaces. The one-line summary should be consistent (paraphrase OK, but no fabricated facts — e.g., the threshold value must be `25%` everywhere, not `20%` in one surface and `25%` in another).

### Scope discipline (whole-CR)

Run `git diff --name-only $(git merge-base HEAD main)..HEAD`. The diff MUST be a subset of:

- `tests/perf/**`
- `tests/perf/baselines/**`
- `Makefile`
- `pyproject.toml`
- `uv.lock`
- `.github/workflows/perf-budgets.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `ai-dev/active/CR-00083/**` (implicit — work-item-internal)

ANY file outside this set = CRITICAL scope violation. Especially:
- `orch/**` (production code — forbidden by design Notes)
- `dashboard/**` (production code — forbidden)
- `executor/**` (production code — forbidden)
- `scripts/**`, `bin/**`, `templates/**` — also forbidden in this CR
- Any other workflow under `.github/workflows/` — only `perf-budgets.yml` is in scope
- Any other skill under `skills/` or `.claude/skills/` — only `iw-ai-core-testing` is in scope

### No scope creep (cross-cutting)

- No new pytest markers beyond `perf`.
- No edits to `make check`, `make quality`, `make test-unit`, `make test-integration` recipes (the perf tests must be excluded from these via the `addopts` marker filter alone).
- No additions to `make check`'s gate list (perf is nightly-only).
- No new GH workflows beyond `perf-budgets.yml`.
- No production-code edits anywhere.

## Test Verification (NON-NEGOTIABLE)

```bash
make lint
make format-check
make type-check
make test-unit
uv run pytest tests/perf/ -m perf -v --no-cov  # the perf tests themselves
```

Do NOT run `make check`, `make test-integration`, `make allure-integration`, `make diff-coverage`, `make security-secrets` — those are S11/S12/S13/S14 QV gates (renumbered) and have their own budgets.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "CR-00083",
  "step_reviewed": "S01,S02,S03,S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint OK, format OK, type-check OK, test-unit X passed, perf 7 passed (1 daemon + 1 rag + 5 routes)",
  "notes": "AC1-AC8 verified. AC6 regression-injection test: injected 30% sleep into <module> — confirmed RED; reverted — confirmed GREEN. Scope diff confirmed bounded. Skill mirror byte-identical. Date 2026-05-24 + CR-00083 consistent across 4 documentation surfaces."
}
```
