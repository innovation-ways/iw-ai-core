# CR-00047: Coverage gates — raise the floor, ratchet it, and gate diff-coverage on PRs

**Type**: Change Request
**Priority**: Medium
**Reason**: The `fail_under = 46` coverage floor is so far below actual coverage that the suite can rot ~30 points before anything fires, and nothing checks that *new* code is covered. This is the coverage half of Phase-1's cheap-gate story (the assertion scanner, CR-00046, was the structural half).
**Created**: 2026-05-12
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies. This CR touches no Docker/compose state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. **This CR adds no migration and modifies none** — no `orch/db/migrations/versions/**` changes.

## Description

Three things: (1) raise `[tool.coverage.report] fail_under` from **46** to a value a few points below the *measured* current branch coverage (S01 measures it), and document the floor + the "ratchet up, never down" rule; (2) add `diff-cover` as a dev dep, a `make diff-coverage` target (self-contained combined-coverage run → `diff-cover --compare-branch=origin/main --fail-under≈90`), a new `diff-coverage` daemon QV gate (after the test gates; canon → 7 gates), and a `pull_request`-conditional `diff-coverage` step in `.github/workflows/test-quality.yml`'s `unit` job; (3) the 1.10 coverage-plumbing audit — add `relative_files = true` to `[tool.coverage.run]` (it's missing) and confirm the other known gotchas. This is **P1-CR-B** of the testing-enhancement plan ([`ai-dev/work/TESTS_ENHANCEMENT.md`](../../work/TESTS_ENHANCEMENT.md) items 1.2 + 1.3 + the 1.10 audit).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Standards in place: [`docs/IW_AI_Core_Testing_Strategy.md`](../../../docs/IW_AI_Core_Testing_Strategy.md) (§1 "coverage is a floor on what's exercised, not a measure of quality"; §5 the gate table with `fail_under = 46`; §8 the assertion scanner; §9 the gaps table), [`skills/iw-ai-core-testing/SKILL.md`](../../../skills/iw-ai-core-testing/SKILL.md), `skills/iw-workflow/SKILL.md` (canonical 6-gate set: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests`), CR-00045's `tdd_red_evidence` contract, CR-00046's assertion scanner + `assertions` gate. InnoForge has a `fail_under` gate (89% branch) but **no diff-cover** — design the diff-cover part from `diff-cover`'s own docs, not from a port.

## Current Behavior

- `[tool.coverage.run]` in `pyproject.toml`: `source = ["orch", "dashboard", "executor"]`, `omit = [...]`, `branch = true`. **No `relative_files`.**
- `[tool.coverage.report]`: `fail_under = 46`, `skip_covered = true`, `show_missing = true`. So the coverage gate fires only if total coverage drops below 46% — far below the real number; ~30 points of silent rot are possible. `pytest --cov` (via `addopts`) enforces it at end of each test run.
- Nothing checks *diff* coverage. An agent can add a file with uncovered new branches and no gate fires (as long as overall coverage stays ≥ 46%).
- `make test-unit` writes `tests/output/coverage/coverage.xml` = unit coverage; `make test-integration` writes the same file = integration+dashboard coverage, overwriting it. There is no combined-coverage artefact.
- `.github/workflows/test-quality.yml`'s `unit` job runs `make test-unit` then uploads `tests/output/coverage/coverage.xml` as the `coverage-xml` artefact. Its `integration` job runs `make test-integration`. Neither does anything with the XML beyond uploading it.
- `skills/iw-workflow/SKILL.md` lists 6 canonical QV gates (`lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests`); the `integration-tests` gate runs `make allure-integration`, which is currently a `.PHONY` stub with no recipe → a silent no-op (flagged HIGH by CR-00046's self-assess; deliberately left for P1-CR-E).

## Desired Behavior

- **`[tool.coverage.report] fail_under`** is raised to a value a few points below the S01-measured branch coverage — enough headroom that a normal CR can't trip it, tight enough that real rot is caught (e.g. measured 73% → set 70). The value is chosen in S01 from the measurement (recorded in this design's Notes once known) — **not guessed at design time**. `docs/IW_AI_Core_Testing_Strategy.md` §5 (gate table) and §1 (principle) document the chosen floor and the rule: **never let it drop; ratchet it up over time as coverage improves.**
- **`diff-cover`** is a dev dependency (`pyproject.toml` + `uv.lock`).
- **`make diff-coverage`** target exists. It is **self-contained**: it produces its own combined unit+integration coverage (e.g. `coverage run`/`pytest --cov` with `--cov-append`/parallel + `coverage combine` + `coverage xml`, or runs `make test-unit` then `make test-integration --cov-append`-style — implementer picks the mechanism), then runs `uv run diff-cover <combined-coverage.xml> --compare-branch=origin/main --fail-under=<N>` where N ≈ 90 (new/changed Python lines must be ≥90% covered). It does **not** depend on a `coverage.xml` left behind by a preceding step or on the (currently no-op) `integration-tests` gate — so it stays correct when P1-CR-E fixes that gate. Exit non-zero if changed-line coverage < N.
- **A `diff-coverage` daemon QV gate** exists in `skills/iw-workflow/SKILL.md`'s canonical set, positioned **after `integration-tests`** (so it runs once the test gates have done their thing) — canon now lists **7** gates: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests` → `diff-coverage`. The "N canonical QV gates" prose is updated. `iw sync-skills` propagates the change to `.claude/skills/iw-workflow/SKILL.md`. Future Feature/CR/Incident manifests pick up the new gate.
- **`.github/workflows/test-quality.yml`** — the `unit` job gets a `Run diff coverage` step after `make test-unit` (and the coverage-XML artefact upload), **conditional on `pull_request` events** (`if: github.event_name == 'pull_request'`), comparing to the PR base. On `push` to main there's no diff, so the step is skipped. (For the GH step it's acceptable to diff against the *unit* `coverage.xml` already produced — the daemon gate is the authoritative combined-coverage one; note this in the strategy doc.)
- **1.10 audit fixes** — `[tool.coverage.run] relative_files = true` is added (it was missing; needed so coverage paths align across worktrees/CI). The other gotchas are confirmed and documented in this design's Notes: `addopts` uses `pytest --cov` (correct, not the `coverage run -m pytest` xdist-bypass footgun); no GH workflow uploads the raw `.coverage` file (only `coverage.xml`), so `include-hidden-files` is N/A; subprocess coverage (`COVERAGE_PROCESS_START`) — the `iw` CLI and daemon subprocesses don't currently contribute coverage; documenting as a known limitation, not fixing here.
- **`docs/IW_AI_Core_Testing_Strategy.md`** — §1 principle line on coverage reflects the new floor + ratchet rule; §5 gate table's Coverage row updated (new `fail_under`, plus a `diff-coverage` row); §9 gaps table rows for "Coverage failure floor" and "Diff/patch coverage on PRs" flipped to ✅; a short paragraph (near the coverage discussion, e.g. §5 or a §8 sibling) describing the `diff-coverage` gate — what it checks, the `--fail-under` value, `make diff-coverage` to run locally, and the coverage-source caveat (daemon gate = combined; GH step = unit).
- **`skills/iw-ai-core-testing/SKILL.md`** §8 (Quality gates) — the gate list adds `diff-coverage` and notes the `fail_under` floor; `.claude/skills/` copy re-synced.
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** — items 1.2, 1.3, and the 1.10 audit ticked DONE with `(CR-00047)` link; §5 grouping table marks P1-CR-B SHIPPED and moves "*(start here)*" to P1-CR-C; changelog entry.
- **Optional `tests/unit/test_coverage_gate_config.py`** — if a meaningful RED-first behavioural test exists: assert `pyproject.toml`'s `[tool.coverage.report] fail_under` is ≥ the chosen floor, `diff-cover` is in the dev dependency group, and the `make diff-coverage` target is present in the `Makefile`. Write it RED-first; record `tdd_red_evidence`. If the implementer judges no meaningful behavioural test exists for what is fundamentally config + a Makefile target + a skill edit + a dependency add, record `tdd_red_evidence: "n/a — config / Makefile / skill / workflow edits + dependency add; no production logic"` (the legitimate `"n/a"` form per CR-00045's contract) — **do not contrive a test just to have one**.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[tool.coverage.report]` | `fail_under = 46` | `fail_under = <S01-measured branch % minus headroom>` |
| `pyproject.toml` `[tool.coverage.run]` | no `relative_files` | adds `relative_files = true` |
| `pyproject.toml` dev deps + `uv.lock` | no `diff-cover` | adds `diff-cover` (latest) |
| `Makefile` | no `diff-coverage` target | adds `diff-coverage:` (self-contained combined-coverage run + `diff-cover`); added to `.PHONY` |
| `skills/iw-workflow/SKILL.md` (+ `.claude/` copy via sync) | 6 canonical QV gates | 7 — adds `diff-coverage` after `integration-tests`; "N canonical gates" prose updated |
| `.github/workflows/test-quality.yml` | `unit` job: `make test-unit` + upload `coverage.xml` | adds a `pull_request`-conditional `Run diff coverage` step after `make test-unit` |
| `docs/IW_AI_Core_Testing_Strategy.md` | §5 Coverage row says `fail_under = 46` (low); §9 rows for coverage-floor + diff-coverage are ⚠️/❌ | §5 Coverage row = new floor + ratchet note + `diff-coverage` row; §9 rows → ✅; new diff-coverage paragraph |
| `skills/iw-ai-core-testing/SKILL.md` (+ `.claude/` copy via sync) | §8 gate list = 6 gates, no coverage-floor mention | adds `diff-coverage` + the `fail_under` floor |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | items 1.2/1.3/1.10-audit TODO; P1-CR-B = "*(start here)*" | items DONE (CR-00047); P1-CR-B = SHIPPED; "*(start here)*" → P1-CR-C; changelog entry |
| `tests/unit/test_coverage_gate_config.py` | does not exist | new (optional) — content/config assertions guard |

### Breaking Changes

- **None.** Raising `fail_under` *below* the measured coverage cannot break a normal CR (and S01 verifies `make quality` still passes with the new value). `diff-coverage` is a new gate — future work items get one extra QV step (intended). Adding `diff-cover` mutates `uv.lock` (a normal dependency add). No schema change, no workflow-manifest schema change. The strategy doc and skills get additive updates.

### Data Migration

- **None.** No database changes. Reversible by `git revert` of the merge commit + `iw sync-skills` to regenerate the in-project skill copies.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | (1) `make test` to measure current line + branch coverage — record both in the step report. (2) Set `[tool.coverage.report] fail_under` to a value just below measured branch coverage; add `[tool.coverage.run] relative_files = true`. (3) Add `diff-cover` dev dep (regenerates `uv.lock`). (4) Add `make diff-coverage` (self-contained combined-coverage run → `diff-cover --compare-branch=origin/main --fail-under=<N≈90>`); add to `.PHONY`. (5) Add the `diff-coverage` gate to `skills/iw-workflow/SKILL.md` canon (after `integration-tests`; update the "N canonical gates" prose). (6) Add a `pull_request`-conditional `diff-coverage` step to `test-quality.yml`'s `unit` job. (7) Confirm the rest of the 1.10 audit; write findings into a `## Notes` addition in this design (or the step report). (8) Update `docs/IW_AI_Core_Testing_Strategy.md` §1/§5/§9 + the diff-coverage paragraph; `skills/iw-ai-core-testing/SKILL.md` §8. (9) `iw sync-skills`. (10) Tick items 1.2/1.3/1.10-audit + §5 grouping + changelog in `ai-dev/work/TESTS_ENHANCEMENT.md`. (11) Optional guard test (RED-first if added). Record `tdd_red_evidence` (the guard-test RED run, or `"n/a — …"`). (12) `make quality` + `make check` must still pass. | — |
| S02 | `code-review-impl` | Review S01: `fail_under` value is sensible (below measured, with headroom — cross-check against the recorded measurement); `make diff-coverage` is correct (combined coverage source, right `--compare-branch`, right `--fail-under`, exits non-zero on shortfall); `diff-coverage` QV gate placement + prose update; the GH step's `pull_request` conditional; `relative_files` added; `uv.lock` updated; docs/plan/skill updates; `iw sync-skills` ran (diff `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` vs masters); no out-of-scope edits (no integration-gate fix, no other Phase-1 deps, no baseline scrub). | — |
| S03 | `code-review-final-impl` | Global review: coverage-config ↔ Makefile ↔ skill canon ↔ GH workflow ↔ docs chain is internally consistent; `diff-coverage` wired into both CI surfaces with the right coverage source for each; `.claude/skills/` copies in sync; the cov-plumbing audit findings are recorded; `make quality`/`make check` pass; no scope creep. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S09 | `qv-gate` (`integration-tests`) | `make allure-integration` (timeout 900; still a no-op stub — P1-CR-E) | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` — **the new gate, dogfooded on its own CR.** This CR's diff is ≈0 new production Python lines; if the optional guard test is added, its own lines are covered when it runs — so the gate should pass. | — |
| S11 | `self-assess-impl` | Self-assessment of the just-completed item via the `iw-item-analyze` skill (project has `self_assess = true`). | — |

Fix cycles (`code-review-fix-impl`, `code-review-fix-final-impl`, per-`qv-gate` fixes) are dynamic and not listed in the manifest.

### Database Changes

- **New tables**: None · **Modified tables**: None · **Migration notes**: None — no Alembic migration; no `migration-check` gate needed.

### API Changes

- **New endpoints**: None · **Modified endpoints**: None · **Removed endpoints**: None

### Frontend Changes

- **New components**: None · **Modified components**: None · **Removed components**: None — `browser_verification: false`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/CR-00047/CR-00047_CR_Design.md` | Design | This document |
| `ai-dev/active/CR-00047/CR-00047_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `ai-dev/active/CR-00047/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/CR-00047/prompts/CR-00047_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `ai-dev/active/CR-00047/prompts/CR-00047_S02_CodeReview_prompt.md` | Prompt | S02 review instructions |
| `ai-dev/active/CR-00047/prompts/CR-00047_S03_CodeReview_Final_prompt.md` | Prompt | S03 final review instructions |
| `ai-dev/active/CR-00047/prompts/CR-00047_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment instructions |

Files **changed** by the implementation (mirrored to `workflow-manifest.json:scope.allowed_paths`):
`pyproject.toml` · `uv.lock` · `Makefile` · `skills/iw-workflow/SKILL.md` · `.claude/skills/iw-workflow/SKILL.md` · `skills/iw-ai-core-testing/SKILL.md` · `.claude/skills/iw-ai-core-testing/SKILL.md` · `.github/workflows/test-quality.yml` · `docs/IW_AI_Core_Testing_Strategy.md` · `ai-dev/work/TESTS_ENHANCEMENT.md` · `tests/unit/test_coverage_gate_config.py` (only if the optional guard test is added).

Reports are created during execution under `ai-dev/work/CR-00047/reports/`.

## Acceptance Criteria

### AC1: the coverage floor is raised and documented

```
Given pyproject.toml after this CR
When you read [tool.coverage.report] fail_under
Then it is a value at or just below the branch coverage measured by S01 (recorded in the step report), and strictly greater than 46
And docs/IW_AI_Core_Testing_Strategy.md §5 and §1 state the chosen floor and the "never let it drop; ratchet up over time" rule
And `make quality` still passes with the new value
```

### AC2: diff-coverage exists and is self-contained

```
Given the Makefile and pyproject.toml after this CR
When you read the `diff-coverage` target
Then `diff-cover` is a dev dependency (present in pyproject.toml's dev group and uv.lock)
And `make diff-coverage` produces its own combined unit+integration coverage XML and runs `diff-cover <that xml> --compare-branch=origin/main --fail-under=<N>` with N >= 80 (≈90 intended)
And the target does NOT rely on a coverage.xml left behind by a preceding step or on the `integration-tests` QV gate
And it exits non-zero if changed-line coverage is below N
```

### AC3: diff-coverage is wired into both CI surfaces

```
Given skills/iw-workflow/SKILL.md
When you read the canonical QV-gate list
Then there are 7 gates: lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage
And the `diff-coverage` gate uses agent `qv-gate`, gate name `diff-coverage`, command `make diff-coverage`
And the "N canonical QV gates" prose says 7
And .claude/skills/iw-workflow/SKILL.md matches (iw sync-skills ran)

Given .github/workflows/test-quality.yml
When you read the `unit` job
Then there is a `Run diff coverage` step after `make test-unit`, conditional on `github.event_name == 'pull_request'`, comparing to the PR base
```

### AC4: the cov-plumbing audit fixes are applied

```
Given pyproject.toml after this CR
When you read [tool.coverage.run]
Then it includes relative_files = true

Given this CR's design document
When you read the Notes section (or the S01 step report)
Then it records the audit findings for: pytest --cov vs coverage run -m pytest (confirmed correct), raw-.coverage-artefact / include-hidden-files (N/A — only coverage.xml is uploaded), subprocess coverage (documented as a known limitation, not fixed here)
```

### AC5: this CR's own diff-coverage QV gate passes (dogfood)

```
Given S10 is the new `diff-coverage` QV gate running `make diff-coverage`
When it executes after S01's implementation has landed
Then it exits 0 (this CR's diff is ≈0 new production Python lines; any optional guard-test lines are covered when the test runs)
```

### AC6: the plan and strategy doc are updated

```
Given ai-dev/work/TESTS_ENHANCEMENT.md
When you read the Phase 1 item rows, the §5 grouping table, and the changelog
Then items 1.2, 1.3, and the 1.10 audit are DONE (CR-00047); P1-CR-B is marked SHIPPED; "*(start here)*" has moved to P1-CR-C; a changelog entry exists

Given docs/IW_AI_Core_Testing_Strategy.md
When you read §1, §5, §9
Then §1's coverage principle reflects the new floor + ratchet rule
And §5's gate table has the updated Coverage row + a diff-coverage row, and a paragraph describing the diff-coverage gate (what it checks, --fail-under, `make diff-coverage`, the daemon-gate=combined / GH-step=unit coverage-source caveat)
And §9's "Coverage failure floor" and "Diff/patch coverage on PRs" rows are ✅
```

### AC7: the testing skill is updated

```
Given skills/iw-ai-core-testing/SKILL.md §8 (Quality gates)
When you read the gate list
Then it includes `diff-coverage` and notes the `fail_under` floor
And .claude/skills/iw-ai-core-testing/SKILL.md matches (iw sync-skills ran)
```

### AC8: tdd_red_evidence is honest

```
Given the S01 step report's Subagent Result Contract
When you read tdd_red_evidence
Then it is either a real RED-run snippet for tests/unit/test_coverage_gate_config.py (if a meaningful guard test was added), or the form "n/a — config / Makefile / skill / workflow edits + dependency add; no production logic"
And it is NOT a contrived/vacuous test added solely to populate the field
```

## Rollback Plan

- **Database**: Not applicable — no schema or data changes.
- **Code**: `git revert` the squash-merge commit (reverts the `fail_under` change, `relative_files`, the `diff-cover` dep + `uv.lock` change, the `make diff-coverage` target, the skill-canon + GH-workflow + docs changes, and the optional guard test). Then run `iw sync-skills` to regenerate `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` from the reverted masters.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00045 (`tdd_red_evidence` contract), CR-00046 (the `assertions` gate / canon shape). Both merged.
- **Blocks**: Nothing hard. P1-CR-C / P1-CR-D / P1-CR-E are independent. P1-CR-E (which fixes the `integration-tests` no-op gate) interacts: once that lands, the strategy-doc note about the `diff-coverage` coverage source can drop the "the `integration-tests` gate is currently a no-op" caveat — but `make diff-coverage` itself is already self-contained, so nothing breaks.

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `skills/iw-workflow/SKILL.md`
- `.claude/skills/iw-workflow/SKILL.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md`
- `.github/workflows/test-quality.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `tests/unit/test_coverage_gate_config.py`

## TDD Approach

- **Unit tests**: optional `tests/unit/test_coverage_gate_config.py` — config/content assertions (`fail_under` ≥ chosen floor; `diff-cover` in dev deps; `make diff-coverage` target present). Written RED-first if added (it fails before the `pyproject.toml`/`Makefile` edits, passes after) — and it must have *real* assertions on the actual parsed values, not `assert config is not None` (the assertion scanner would catch that anyway). If the implementer judges this contrived, skip it and use the `"n/a — …"` `tdd_red_evidence` form — that's the legitimate config-only case.
- **Integration tests**: None — there's no runtime behaviour to integration-test. The `diff-coverage` mechanics are exercised end-to-end by S10 (the dogfood gate).
- **Updated tests**: None — no existing test is modified by this CR.

## Notes

- **Measure first.** S01's first action is `make test` (unit + integration + dashboard) to get the real current branch coverage %. Until that number is known the `fail_under` value and the headroom are placeholders. **S01 records the measured line % and branch % in its step report**, and uses the branch % minus a few points of headroom as the new `fail_under`. (Headroom rule of thumb: floor = measured branch % rounded down to the nearest 5, minus 0–5 more if the measurement felt noisy. Aim for a floor that a routine CR's coverage wobble won't cross.)
- **`make diff-coverage` coverage source** — option (a): self-contained combined coverage. The implementer picks the mechanism (`pytest --cov ... --cov-append` across the unit + integration runs into one `.coverage`, then `coverage xml`; or `coverage run -p` parallel + `coverage combine`; whatever is cleanest given the existing `addopts`). It must NOT depend on the preceding QV step's `coverage.xml` or on the `integration-tests` gate. This is slower than reusing an existing XML, but it's robust to the `integration-tests` no-op-gate state and to its eventual fix (P1-CR-E). In the GH `unit` job, it's fine for the `Run diff coverage` step to use the unit `coverage.xml` already produced (cheaper; the daemon gate is the authoritative combined one) — note this asymmetry in the strategy-doc paragraph.
- **GH step is `pull_request`-only** — `diff-cover` needs a base to compare against; on `push` to main there's no diff. Use `if: github.event_name == 'pull_request'`. Fetch depth may need bumping (`fetch-depth: 0` on the checkout, or fetch the base ref) so `origin/main` (or `${{ github.event.pull_request.base.sha }}`) is available — the implementer handles this.
- **1.10 audit findings (to confirm + record in the step report):** `relative_files = true` — **missing, add it**. `pytest --cov` (not `coverage run -m pytest`) — already correct (the `addopts` use `--cov`). Raw `.coverage` artefact / `include-hidden-files` — N/A (only `coverage.xml` is uploaded). Subprocess coverage (`COVERAGE_PROCESS_START`) — the `iw` CLI and daemon subprocesses don't contribute coverage today; document as a known limitation; **do not** wire it up here (out of scope).
- **`iw sync-templates` is NOT needed** — no `templates/design/*.md` edits. `iw sync-skills` IS needed (for `iw-workflow` and `iw-ai-core-testing`). Confirm in the step report.
- **Cross-repo skill propagation** — `skills/iw-workflow/` is a shared workflow skill; the sibling repos (iw-doc-plan/podforger/cv) will pick up the new `diff-coverage` gate at their next `iw sync-skills` — not done from this worktree (post-merge operator step, same pattern as CR-00046). `skills/iw-ai-core-testing/` is project-specific — not propagated. Note this in the step report.
- **Dogfood S10** — the new `diff-coverage` gate runs on this very CR. This CR adds ≈0 new production Python lines (it's config + Makefile + skill + workflow + docs + maybe one config-assertion test). `diff-cover` only looks at Python files in the coverage data, so it should report "no lines to cover" → exit 0, or (if the guard test was added) the test's own lines as covered. If S10 fails, something unexpected happened — investigate, don't paper over it.
- **Scope discipline** — do not fix the `integration-tests` no-op gate (P1-CR-E); do not add `mutmut`/`vulture`/`deptry`/`gitleaks`/`semgrep`/`pytest-randomly` (subsequent CRs); do not scrub the assertion baseline (P1-CR-A-followup); do not raise `fail_under` to the *measured* value (leave headroom); do not change the workflow-manifest schema; do not restructure the existing `--cov-report` config beyond adding `relative_files`.
- **Why `backend-impl`** — it's `pyproject.toml`/`uv.lock` config, a Makefile target, a skill-canon edit, a GH-workflow edit, a dependency add, doc updates, and `iw sync-skills` — squarely `backend-impl`'s comfort zone. `tdd_red_evidence` is the `"n/a"` form unless a meaningful guard test is added.
