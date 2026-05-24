# CR-00080: Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking

**Type**: Change Request
**Priority**: Medium
**Reason**: Tracker follow-up from CR-00059. The first spike measured 0:17:17 wall-clock on `orch/daemon/` but generated 0 mutants because every module-level mutmut invocation tripped pytest's `coverage fail-under` threshold before any mutant could execute. Item 2.1 in `ai-dev/work/TESTS_ENHANCEMENT.md` stays IN PROGRESS until mutmut (a) measures the full `orch/` package and (b) actually blocks PRs/merges. This CR closes both the §5 `P2-CR-A-followup-mutation-block` row and the §8 Phase-4 item 4.8 "Tighten mutation gate to blocking".
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. No live-container changes are needed for this CR — the mutmut runner shells out to `uv run pytest`, which uses testcontainers via existing fixtures.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This CR adds, modifies, or removes ZERO migrations.** It is a CI/tooling/docs-only change. No `orch/db/migrations/versions/**` files are in scope.

## Description

CR-00059 (merged 2026-05-18) shipped the mutmut foundation: `mutmut>=2.5,<3.0` dep, a `[tool.mutmut]` block scoped to `orch/daemon/`, four `make mutation-{check,audit,results,show}` targets, a RED-first guard test (`tests/unit/test_mutmut_setup.py`), and a spike. The spike measured **0:17:17 wall-clock** but generated **0 mutants** because every module-level mutmut invocation hit `FAIL Required test coverage of 50.0% not reached` from pytest before mutant execution started. This CR (a) fixes the coverage-fail-under interaction so mutants actually run, (b) widens `paths_to_mutate` from `orch/daemon/` to `orch/`, (c) measures a **second spike** to get real per-mutant cost and total wall-clock numbers, (d) wires the gate as a **blocking nightly GitHub Actions workflow** (daemon-QV is impractical at the measured cost — see Notes), (e) picks a blocking mutation-score threshold a few points below measured **subject to a viability guard** (mirroring the CR-00047 coverage-floor ratchet pattern; refusing to wire if the spike data is too thin), and (f) flips the gate from "non-existent" to blocking. Tracker, strategy doc, and the testing skill are updated to reflect the new state.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Specifically relevant here: the canonical QV-gate chain documented in `skills/iw-workflow/SKILL.md`, the daemon's quality-validation step model in `docs/IW_AI_Core_Daemon_Design.md`, the gate matrix and gap rows in `docs/IW_AI_Core_Testing_Strategy.md`, and the testing skill at `skills/iw-ai-core-testing/SKILL.md`. The CR-00047 (diff-coverage ratchet) and CR-00050 (gitleaks secret-scanning gate) precedents define the "blocking floor a few points below measured, ratchet up over time" pattern reused here.

## Current Behavior

- `pyproject.toml` lines 248-257 carry the `[tool.mutmut]` block with `paths_to_mutate = "orch/daemon/"` and a CR-00059 comment that explicitly flags this CR as the follow-up that will widen scope. `tests_dir = "tests/"` and `runner = "uv run pytest tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q"`.
- `Makefile` lines ~245-316 define `mutation-check`, `mutation-audit`, `mutation-results`, `mutation-show`. The audit loop iterates every `orch/daemon/*.py` file, runs mutmut per module, and tails the results. The runner passes `tests/unit/daemon/` + `tests/integration/daemon/` but does **not** override pytest's coverage gate; pytest reads `[tool.coverage.report] fail_under` from `pyproject.toml` (currently `50`) and fails the first test run before any mutant executes. This is the bug that produced "0 mutants" in the CR-00059 spike.
- `skills/iw-workflow/SKILL.md` documents the canonical 8-gate QV chain: `lint`, `assertions`, `format`, `typecheck`, `unit-tests`, `integration-tests`, `diff-coverage`, `security-secrets`. `mutation-check` is **NOT** in the list. There is no `qv-gate` in any item's manifest that runs mutmut.
- `tests/unit/test_mutmut_setup.py` is the RED-first guard test from CR-00059. It currently asserts that `paths_to_mutate` is `"orch/daemon/"`. Widening the scope requires updating this assertion (or making it broader).
- `docs/IW_AI_Core_Testing_Strategy.md` §5 (gate table) lists mutmut as "on-demand, not gated"; §8 (mutation-testing section) explains the spike approach; §9 (gap row) tracks the open follow-up.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 lists `P2-CR-A-followup-mutation-block` as IN PROGRESS; §6 item 2.1 ("Adopt mutation testing in CI") is IN PROGRESS; §8 item 4.8 ("Tighten mutation gate to blocking") is OPEN; §10 carries the "mutation testing cost" open question.
- `skills/iw-ai-core-testing/SKILL.md` mutmut section reflects CR-00059's scope (daemon-only, on-demand).
- No `.github/workflows/mutation.yml` exists today; mutmut never runs in CI.

## Desired Behavior

- `pyproject.toml` `[tool.mutmut].paths_to_mutate` reads `"orch/"`, the runner override prevents the coverage-fail-under interaction from blocking mutant execution (either via a `--cov-fail-under=0` flag in the runner string or via a mutmut-specific pyproject override), and the comment block above the `[tool.mutmut]` table is rewritten to reference CR-00080 with the new spike numbers.
- `Makefile` `mutation-audit` loops over `orch/**/*.py` (the wider scope) and passes the cov-fail-under override on the inner pytest invocation.
- A new spike measurement file is committed at `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt`. It records: total wall-clock, number of mutants generated, number killed, number surviving, mutation score (killed / generated), and per-module breakdown.
- **The gate surface is a nightly GitHub Actions workflow** (`.github/workflows/mutation.yml`) — committed up-front rather than chosen at runtime. Rationale: CR-00059's daemon-only spike already measured 1037s wall-clock with 0 mutants actually executing (cov-fail-under killed each run immediately). The widened `orch/` scope with a fixed runner that actually executes mutants will materially exceed any reasonable per-batch QV budget. Per-batch enforcement is therefore impractical; the nightly workflow runs the audit once per day and fails when the score drops below threshold. Per-PR runs see the result from the latest nightly via the workflow's status badge / `gh run list` query.
- A blocking mutation-score threshold is chosen **subject to a viability guard** (see AC3): if measured score `M >= 20%` AND `(killed + survived) >= 30`, `T = round_down(M) − margin` (margin 5/3/2 per band, mirroring the CR-00047 diff-coverage ratchet). If either viability condition fails, S02 reports `completion_status: blocked` with a recommended next step (expand test coverage in the most-mutated modules, or run a longer manual spike), and the gate is NOT wired. A non-viable spike does not silently produce a `T <= 0` "blocking" gate.
- The gate is **blocking** (no `|| true`, no `continue-on-error: true`) once wired.
- Trackers and docs reflect DONE: `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P2-CR-A-followup-mutation-block` → DONE, §6 item 2.1 → DONE, §8 item 4.8 → DONE, §9 gate matrix updated, §10 mutation-cost question answered with the second-spike numbers; `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table, §8 mutation section, §9 gap row all updated; `skills/iw-ai-core-testing/SKILL.md` mutmut section updated; master copy is synced via `iw sync-skills --force iw-ai-core-testing`. (The canonical QV-gate chain in `skills/iw-workflow/SKILL.md` is NOT touched — mutmut lives on the nightly surface, not in the per-item QV chain.)
- `tests/unit/test_mutmut_setup.py` is extended (or its assertion broadened) so it accepts the new `"orch/"` value.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[tool.mutmut]` | `paths_to_mutate = "orch/daemon/"`; runner does not override cov-fail-under | `paths_to_mutate = "orch/"`; runner / config override prevents cov-fail-under from killing mutant runs |
| `Makefile` mutation targets | Audit loop iterates `orch/daemon/*.py`; runner does not override cov-fail-under | Audit loop iterates `orch/**/*.py`; runner passes `--cov-fail-under=0` |
| `tests/unit/test_mutmut_setup.py` | Asserts `paths_to_mutate == "orch/daemon/"` | Asserts `paths_to_mutate == "orch/"` (or equivalent broader check) |
| Spike evidence file | None for widened scope; CR-00059 file is daemon-only | New `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` records the widened-scope spike |
| GH workflow (nightly surface — chosen up-front) | None | `.github/workflows/mutation.yml` runs `make mutation-audit` nightly, parses score, fails the workflow if `score < T` (only if the viability guard passes in S02) |
| `docs/IW_AI_Core_Testing_Strategy.md` | mutmut on-demand, not gated | mutmut blocking on nightly GH workflow with documented threshold + ratchet rule + viability guard |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §5 row IN PROGRESS; item 2.1 IN PROGRESS; item 4.8 OPEN; §10 mutation-cost question open | §5 row DONE (CR-00080); item 2.1 DONE; item 4.8 DONE; §10 question answered with second-spike data |
| `skills/iw-ai-core-testing/SKILL.md` | mutmut section says daemon-only, on-demand | Updated to reflect widened scope + blocking gate + threshold |

### Breaking Changes

- **None for production code.** No `orch/` / `dashboard/` / `executor/` runtime behaviour changes.
- **Behavioural change for CI**: the new nightly GH workflow can fail and block downstream automation if mutation score drops below the chosen threshold. This is the **intended** effect — that's what "flip from informational to blocking" means.

### Data Migration

- **None.** No DB schema changes, no data backfill, no alembic revision.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md`. The spike (S01) is the riskiest piece — wall-clock is unknown until measured. The gate-wiring (S02) depends on S01's numbers passing the viability guard. Docs / tracker / skill sync (S03) is separate so a docs-only fix-cycle does not need to re-run the spike.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Fix the pytest cov-fail-under interaction; widen `paths_to_mutate` to `orch/`; run the second spike; commit measurements under `evidences/pre/`; extend `tests/unit/test_mutmut_setup.py` for the new scope | — |
| S02 | backend-impl | Apply AC3 viability guard to S01's measurements (`M >= 20%` AND `killed + survived >= 30`); if viable, pick threshold `T = round_down(M) − margin` (5/3/2 per band) and create `.github/workflows/mutation.yml` (blocking nightly); if not viable, report `completion_status: blocked` with recommended next step | — |
| S03 | backend-impl | Update `docs/IW_AI_Core_Testing_Strategy.md` (§5 / §8 / §9); update `ai-dev/work/TESTS_ENHANCEMENT.md` (§5 row / §6 item 2.1 / §8 item 4.8 / §9 gate matrix / §10 mutation-cost answer); update `skills/iw-ai-core-testing/SKILL.md` mutmut section; run `iw sync-skills --force iw-ai-core-testing` to propagate the skill change to the project copy | — |
| S04 | code-review-impl | Per-agent review of S01 (spike + scope widen) | — |
| S05 | code-review-final-impl | Global cross-agent review of S01..S04 | — |
| S06 | qv-gate (lint) | `make lint` | — |
| S07 | qv-gate (assertions) | `make test-assertions` | — |
| S08 | qv-gate (format) | `make format-check` | — |
| S09 | qv-gate (typecheck) | `make type-check` | — |
| S10 | qv-gate (unit-tests) | `make test-unit` | — |
| S11 | qv-gate (integration-tests) | `make test-integration` | — |
| S12 | qv-gate (diff-coverage) | `make diff-coverage` | — |
| S13 | qv-gate (security-secrets) | `make security-secrets` | — |
| S14 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

S01 requires a generous timeout (3600s) because the spike's wall-clock cost is the unknown the spike is measuring. The prior CR-00059 spike already took 1037s on the narrow daemon-only scope before any mutants actually executed; the widened scope with a working runner is expected to be materially longer.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None
- **Browser visibility**: None. This is a CI/tooling/docs change with no dashboard or UI surface. `browser_verification: false`.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00080/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00080_CR_Design.md` | Design | This document |
| `CR-00080_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00080_S01_Backend_prompt.md` | Prompt | S01 spike + scope-widen instructions |
| `prompts/CR-00080_S02_Backend_prompt.md` | Prompt | S02 gate-wiring instructions |
| `prompts/CR-00080_S03_Backend_prompt.md` | Prompt | S03 docs + tracker + skill sync instructions |
| `prompts/CR-00080_S04_CodeReview_prompt.md` | Prompt | Per-agent review of S01..S03 |
| `prompts/CR-00080_S05_CodeReview_Final_prompt.md` | Prompt | Global cross-agent review |
| `prompts/CR-00080_S14_SelfAssess_prompt.md` | Prompt | Self-assessment via iw-item-analyze |
| `evidences/pre/cr-00080-spike-measurements.txt` | Evidence | Second-spike numbers (written by S01) |

Reports are created during execution in `ai-dev/work/CR-00080/reports/`.

## Acceptance Criteria

### AC1: Scope widened and second spike runs end-to-end

```
Given pyproject.toml at the start of CR-00080 has paths_to_mutate = "orch/daemon/"
  And the CR-00059 spike measured 0 mutants because pytest cov-fail-under tripped first
When S01 widens paths_to_mutate to "orch/", patches the runner to override cov-fail-under,
     and runs the second spike (cold cache — fresh worktree)
Then the spike completes without the FAIL Required test coverage error
  And the measurement file at ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt
      records: total wall-clock, mutants generated (> 0), killed, surviving, mutation score,
      AND the viability inputs M (mutation score) and K (killed + survived) needed for AC3
  And tests/unit/test_mutmut_setup.py asserts the new "orch/" scope
```

### AC2: Gate runs as a blocking nightly GitHub Actions workflow

```
Given S01's evidence file passes the AC3 viability guard
When S02 creates .github/workflows/mutation.yml
Then the workflow triggers on `schedule: cron '0 6 * * *'` AND `workflow_dispatch: {}`
 And the workflow runs `make mutation-audit`, parses the mutation score,
     and exits non-zero when mutation_score < T
 And the workflow has NO `continue-on-error: true`, NO `|| true`, NO `if: failure()`
     swallowing — it is blocking
 And `skills/iw-workflow/SKILL.md` and the canonical per-item QV-gate chain are NOT modified
     (mutmut lives on the nightly surface only — it is not a per-batch gate)
```

### AC3: Blocking mutation-score threshold chosen and enforced — with viability guard

```
Given the spike's measured mutation score is M and (killed + survived) is K
When S02 picks the threshold T
Then S02 FIRST applies the viability guard:
        - if M < 20%  OR  K < 30: S02 reports completion_status=blocked with the
          measured M, K, and a recommended next step (expand test coverage in the
          most-mutated modules, or extend the spike with a longer manual run).
          The gate is NOT wired in this case — a non-viable spike must not silently
          produce a T <= 0 "blocking" gate.
 And  if the guard passes:
        T = round_down(M) - margin
            where margin = 5 for M >= 70, 3 for 50 <= M < 70, 2 for 20 <= M < 50.
 And the chosen value of T is documented in docs/IW_AI_Core_Testing_Strategy.md §8
 And the gate fails (non-zero exit) when measured mutation_score drops below T
 And the ratchet rule (raise T over time as more tests are added) is documented
```

### AC4: Tracker + strategy doc + skill all reflect DONE

```
Given the tracker states P2-CR-A-followup-mutation-block IN PROGRESS, item 2.1 IN PROGRESS,
      item 4.8 OPEN, and the §10 mutation-cost question open
When S03 updates the tracker
Then ai-dev/work/TESTS_ENHANCEMENT.md §5 row P2-CR-A-followup-mutation-block reads DONE (CR-00080)
 And §6 item 2.1 reads DONE (CR-00080)
 And §8 item 4.8 reads DONE (CR-00080)
 And §9 gate matrix shows mutmut on the nightly GH workflow with threshold T (or DEFERRED if the viability guard fired)
 And §10 mutation-cost answer cites the wall-clock + per-mutant cost from the measurement file
 And docs/IW_AI_Core_Testing_Strategy.md §5 / §8 / §9 are consistent with the tracker
 And skills/iw-ai-core-testing/SKILL.md mutmut section reflects widened scope + blocking gate
 And .claude/skills/iw-workflow/SKILL.md is byte-for-byte identical to its master copy
 And .claude/skills/iw-ai-core-testing/SKILL.md is byte-for-byte identical to its master copy
```

### AC5: No production code or migration touched

```
Given the CR's allowed_paths list excludes orch/**, dashboard/**, executor/**, orch/db/migrations/**
When the merge-time scope gate runs on the squash commit
Then git diff origin/main..HEAD shows zero files under orch/ (except docs in this manifest)
 And zero files under dashboard/, executor/, orch/db/migrations/
 And the qv-gate chain (lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets) passes
```

## Rollback Plan

- **Database**: Not applicable — no schema change.
- **Code**:
  - Delete `.github/workflows/mutation.yml`. The next nightly trigger is silently skipped (no workflow file = no run).
  - Revert `pyproject.toml` `[tool.mutmut].paths_to_mutate` back to `"orch/daemon/"` and revert the Makefile audit loop / runner override.
  - Revert `tests/unit/test_mutmut_setup.py` assertion to `"orch/daemon/"`.
- **Data**: No data loss on rollback. The measurement file is historical evidence and can stay in `evidences/pre/` even after rollback.

## Dependencies

- **Depends on**: CR-00059 (shipped the mutmut foundation — `mutmut>=2.5,<3.0` dep, the four make targets, the guard test, and the daemon-only spike).
- **Blocks**: `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P2-CR-A-followup-mutation-block`, §6 item 2.1, §8 item 4.8.

## Impacted Paths

```
pyproject.toml
Makefile
skills/iw-ai-core-testing/SKILL.md
.claude/skills/iw-ai-core-testing/SKILL.md
docs/IW_AI_Core_Testing_Strategy.md
ai-dev/work/TESTS_ENHANCEMENT.md
.github/workflows/mutation.yml
ai-dev/active/CR-00080/**
tests/unit/test_mutmut_setup.py
```

Note: if the AC3 viability guard fails, `.github/workflows/mutation.yml` is NOT created — S02 reports `blocked` and the gate is not wired. The merge-time scope gate's enforcement is "no modification outside this list" — listing a path that is not touched is not a violation.

## TDD Approach

- **Unit tests** (S01): extend `tests/unit/test_mutmut_setup.py` to assert the new `paths_to_mutate == "orch/"` value. RED-first: change the assertion first, run targeted (`uv run pytest tests/unit/test_mutmut_setup.py -v`), confirm `AssertionError`, then change `pyproject.toml` to make it GREEN.
- **Integration tests**: none added. The spike itself is the integration evidence — it is a one-shot measurement, not a recurring test. The spike measurement file is committed as evidence under `evidences/pre/`.
- **Existing tests that may need updating**: only `tests/unit/test_mutmut_setup.py`. No other test is coupled to the `[tool.mutmut].paths_to_mutate` value.
- **Gate-wiring verification**: the `workflow_dispatch: {}` trigger on `.github/workflows/mutation.yml` lets a manual test invocation prove the threshold-comparison logic works before the nightly schedule fires for the first time. If `gh` CLI access is available in the worktree, the test invocation result should be linked from the S02 report (optional — S02's contract is "wire the gate", not "prove the gate works in the GH UI"). If S02 reports `blocked` (viability guard fired), no gate exists to verify, and this section is N/A.

## Notes

- **Why nightly GH workflow up-front (not "decide at runtime")**: CR-00059's daemon-only spike took 1037s (17:17) wall-clock and produced 0 mutants — the runtime was spent on cov-fail-under failures, not actual mutation. With the runner fix landed, mutants will actually execute, which means the widened `orch/` scope will be **strictly slower**. Per-batch enforcement is impractical at this cost; the nightly surface is the only viable option until per-mutant cost drops materially (e.g., diff-scoped mutation that mutates only changed lines). A future CR can revisit the daemon-QV surface after measurements demonstrate sub-minute per-batch cost. Choosing the surface up-front avoids a fragile data-dependent branch in S02 (and the dead AC2 daemon-QV branch).
- **Cost-of-spike risk**: The widened spike on the whole of `orch/` is expected to take longer than CR-00059's daemon-only run once mutants actually execute. S01 gets a **3600s timeout** to accommodate this. If the spike still exceeds 3600s, S01 reports `completion_status: partial` and quotes the measured-so-far numbers. The S01 prompt **does not** instruct the agent to "prime cache" with `make test-unit` / `make test-integration` — those duplicate the S10 / S11 QV gates and do not populate `.mutmut-cache` (which is mutmut's own cache, built by `mutmut run`, not by pytest). The first spike on a fresh worktree is always cold; cache-warm-from-main only becomes available once the workflow persists `.mutmut-cache` via GH Actions cache (out of scope here — a future optimisation for the nightly workflow).
- **Viability guard rationale (AC3)**: A spike that times out early or kills very few mutants produces an unreliable `M` value. The formula `T = round_down(M) − margin` then yields a near-zero or negative threshold — a "blocking" gate that never actually blocks. The guard (`M >= 20%` AND `killed + survived >= 30`) refuses to wire such a gate; the operator must either (a) extend test coverage to reach the floor, or (b) re-run the spike with a longer manual budget before re-running this CR.
- **Why a separate S03 docs/skill-sync step**: bundling docs with the gate-wiring (S02) violates the step-granularity rule and risks a docs-only fix-cycle re-running the spike. Keeping S03 isolated means a docs-only review-fix is cheap.
- **Why not parallel S01/S02/S03**: S02's content (threshold choice, viability decision) depends on S01's measured numbers. S03's content (tracker / strategy-doc / skill updates) depends on both. They are strictly serial.
- **Threshold ratchet precedent**: CR-00047 chose `diff-cover --fail-under≈90`. CR-00050 chose `gitleaks` exit-non-zero. This CR follows the same "blocking floor a few points below measured, ratchet up over time" pattern, with the viability guard added as a safety rail.
- **Skill-sync rule**: `iw sync-skills` for project-override skills requires `--force` (see CR-00049 precedent). Only `iw-ai-core-testing` is touched in S03 (not `iw-workflow` — the canonical QV chain is unchanged).
- **No browser visibility**: This is CI/tooling/docs only. `browser_verification: false` in the manifest. No `qv-browser` step.
- **No self-assess override**: `iw-ai-core` has `self_assess = true` in `projects.toml`, so S14 self-assess is injected per the workflow rule.
