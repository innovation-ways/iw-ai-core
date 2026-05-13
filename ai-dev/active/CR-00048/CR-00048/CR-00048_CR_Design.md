# CR-00048: Test hygiene — randomized test order, strict markers, dead-code & dep-hygiene gates

**Type**: Change Request
**Priority**: Medium
**Reason**: Three latent test-quality holes (fixed test order hides inter-test pollution; typo'd markers are silent warnings; dead code & dep drift have no check) plus a concrete env-leak test bug surfaced by CR-00047. Phase-1 items 1.4 + 1.5 + 1.7.
**Created**: 2026-05-12
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies. This CR touches no Docker/compose state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. **This CR adds no migration and modifies none** — no `orch/db/migrations/versions/**` changes.

## Description

Add `pytest-randomly` (test-order randomization, default-on) and make the suite robust to it (fix or quarantine the order-dependent failures it surfaces); add `--strict-markers` to `pytest` `addopts` (and fix any typo'd markers); add `vulture` (dead code) and `deptry` (dependency hygiene) as **warn-only** `make` targets wired into `make quality` and the GH `lint-typecheck` job; and fix the 2 pre-existing `tests/unit/test_safe_migrate.py` agent-context tests that fail inside an agent worktree because a leaked `IW_CORE_PER_WORKTREE_DB=true` flips `apply()`/`rollback()` out of the "refuse" path. This is **P1-CR-C** of the testing-enhancement plan ([`ai-dev/work/TESTS_ENHANCEMENT.md`](../../work/TESTS_ENHANCEMENT.md) items 1.4 + 1.5 + 1.7).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Standards in place: [`docs/IW_AI_Core_Testing_Strategy.md`](../../../docs/IW_AI_Core_Testing_Strategy.md), [`skills/iw-ai-core-testing/SKILL.md`](../../../skills/iw-ai-core-testing/SKILL.md), `skills/iw-workflow/SKILL.md` (canonical 7-gate set: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests` → `diff-coverage`), CR-00045's `tdd_red_evidence` contract, CR-00046's assertion scanner, CR-00047's `make diff-coverage` + `fail_under = 50` + `relative_files = true`. InnoForge has `make dead-code` (`vulture src/innoforge/ --min-confidence 80`) and `make dep-check` (`deptry .`) with `[tool.vulture]` / `[tool.deptry]` config sections in its `pyproject.toml` — port that structure. InnoForge's R29 audit had "No flaky test detection (pytest-randomly)" as Deferred — no port for that part; design it from `pytest-randomly`'s docs.

## Current Behavior

- `[tool.pytest.ini_options] addopts` = `--import-mode=importlib --cov=... --cov-report=... -m 'not browser'`. **No `--strict-markers`** (only `make smoke` passes it). A typo'd or unregistered `@pytest.mark.<x>` is a warning, not an error — so a mistyped marker silently mismarks/deselects a test.
- Registered markers: `integration`, `smoke`, `slow`, `browser`.
- Tests run in **fixed file order** (alphabetical, pytest default). Inter-test pollution — state leaked between tests, a real risk given the session-scoped testcontainer (`pg_container`) and the live-DB write guard armed in `tests/conftest.py` — only manifests "sometimes in CI" rather than every run. `pytest-randomly` is not installed.
- No dead-code detector (`vulture`) and no dependency-hygiene check (`deptry`). Unused functions, declared-but-unused / used-but-undeclared deps accumulate silently. `make quality` = `lint format typecheck test-assertions`.
- `.github/workflows/test-quality.yml`'s `lint-typecheck` job runs `make lint`, `make test-assertions`, `make format-check || make format`, `make typecheck`. No dead-code / dep-hygiene step.
- `tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `::TestRollback::test_rollback_refuses_in_agent_context` do `with patch.dict("os.environ", {"IW_CORE_AGENT_CONTEXT": "true"}, clear=False), pytest.raises(AgentContextForbiddenError): apply(...)` — expecting `apply()`/`rollback()` to refuse when `IW_CORE_AGENT_CONTEXT=true`. They pass in CI and locally, but **fail inside an agent worktree** because that environment exports `IW_CORE_PER_WORKTREE_DB=true`, which `clear=False` lets leak into the patched env, and a leaked per-worktree-DB flag flips `apply()` out of the "refuse" branch (the per-worktree DB is a context where migrations *are* allowed). So the `pytest.raises` block gets no exception and the test fails. This is a test-isolation bug, not a production bug.
- `make test-assertions` (CR-00046) currently passes; `make diff-coverage` (CR-00047) builds combined coverage and runs `diff-cover --fail-under=90`; `fail_under = 50`.

## Desired Behavior

- **`pytest-randomly` is a dev dependency** (in `uv.lock`). It's default-on once installed — randomizes test-file/class/function order and seeds `random` / `os.urandom`-consuming code / `numpy` with a per-run seed printed at the top of every run. **The suite is robust to it**: S01 runs a **bounded multi-seed sweep** — `make test-unit` 3× (different seeds) + `make test-integration` 1× (one more seed); the cheap unit suite is where most order-dependence surfaces, and the downstream QV gates (S08 `make test-unit`, S10 `make diff-coverage` which re-runs unit+integration+dashboard) give two more seeds for free, so S01 must **not** re-run the integration suite repeatedly (that would blow the step timeout — the I-00073 lesson). S01 then either (a) fixes every surfaced order-dependent failure (the usual fixes: a test mutating module/global state without restoring it; a test depending on another's side effect; an autouse fixture missing cleanup; a direct `app.state.x = …` that should be `monkeypatch.setattr(app.state, …)`), or (b) fixes the easy ones and **quarantines** the rest with a registered `order_dependent` marker (added to `pyproject.toml`'s `markers`) plus a tracking comment, files a `P1-CR-C-followup` item in the plan's §5, and documents it. Either way `make test-unit` / `make test-integration` end **green under randomization**. **Fallback** (only if the cleanup is too large even to quarantine cleanly): keep the dep but add `-p no:randomly` to `addopts` (off by default), document why, and the follow-up flips it on — the design and acceptance both name this fallback explicitly.
- **The reproduce/disable recipe is documented** in `tests/CLAUDE.md` (and `skills/iw-ai-core-testing/SKILL.md` §2/§7): `pytest -p no:randomly …` disables it; `pytest --randomly-seed=<N> …` reproduces a failure; the seed is printed at the top of every run.
- **`--strict-markers` is in `addopts`.** Any typo'd/unregistered marker the suite then surfaces is fixed (register a legitimate new marker or fix the typo).
- **`vulture` and `deptry` are dev dependencies.** A `make dead-code` target runs `vulture` over `orch dashboard executor scripts` with `--min-confidence` ≥ 70 and a whitelist file (`vulture_whitelist.py` at repo root, or `--ignore-decorators`/`--ignore-names`) for the unavoidable false positives (FastAPI route handlers, pytest fixtures, dynamically-referenced names, `__all__` exports, Click commands). A `make dep-check` target runs `deptry .` with a `[tool.deptry]` config in `pyproject.toml` for false positives (optional imports, plugin discovery). **Both warn-only this CR**: wired into `make quality` as non-failing (`… || true`) with a comment that they flip to hard gates after a burn-in (a follow-up); added to `.PHONY`; added to `.github/workflows/test-quality.yml`'s `lint-typecheck` job as a non-failing/informational step (`continue-on-error: true` or `… || true`). **Not** added as daemon QV gates (warn-only doesn't need a gate; a later item adds them as gates when they flip).
- **`tests/unit/test_safe_migrate.py`'s `test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context` pass both inside an agent worktree and in CI/locally.** The fix: control the leaking env var(s) — explicitly set `IW_CORE_PER_WORKTREE_DB` (and any other guard vars `apply()`/`rollback()` consult) in the test's `env` dict, or `clear=True` with the full required env, or pop the leaking vars before the `pytest.raises` block — whatever matches the surrounding test conventions in that file. **Read `orch/db/safe_migrate.py` first** to identify exactly which env vars flip the refuse path. Do **not** change production code in `orch/db/safe_migrate.py` unless the test reveals a genuine production bug (it almost certainly doesn't).
- **Plan / strategy doc / skill updates** — `ai-dev/work/TESTS_ENHANCEMENT.md`: items 1.4 / 1.5 / 1.7 ticked DONE (or "partial — cleanup follow-up filed" if the `pytest-randomly` cleanup is descoped) with `(CR-00048)` link; §5 grouping table marks **P1-CR-C SHIPPED** (or "SHIPPED — cleanup follow-up filed") and moves "*(start here)*" to **P1-CR-D**; if a `pytest-randomly` cleanup follow-up was filed, add it to the §5 table near `P1-CR-A-followup`; changelog entry (the dep adds, the order-dependent failures found + fixed/quarantined **with counts**, the marker fixes, the `vulture`/`deptry` setup + warn-only status, the `test_safe_migrate` fix, any fallback used). `docs/IW_AI_Core_Testing_Strategy.md`: §3 (test infrastructure) — `pytest-randomly` is default-on + the reproduce recipe; §5 (gate table) — add `dead-code` (vulture, warn-only) and `dep-check` (deptry, warn-only) rows; §6 (conventions) — `--strict-markers` is default; §9 (gaps table) — flip "Test-order randomisation (`pytest-randomly`)", "`vulture` dead-code / `deptry` dep-hygiene" rows to ✅ (and "Flaky/quarantine workflow" to ⚠️ if an `order_dependent` marker was introduced). `skills/iw-ai-core-testing/SKILL.md`: §2/§7 — the reproduce recipe; §8 — `dead-code`/`dep-check` (warn-only). Run `iw sync-skills` (for `iw-ai-core-testing`; also `iw-workflow` only if a new marker needs documenting there); `.claude/skills/` copies in sync. **`iw sync-templates` is NOT needed** (no `templates/design/*.md` edits) — confirm in the report.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[dependency-groups] dev` + `uv.lock` | no `pytest-randomly`/`vulture`/`deptry` | adds all three |
| `pyproject.toml` `[tool.pytest.ini_options] addopts` | no `--strict-markers` | adds `--strict-markers` (and, only in the fallback, `-p no:randomly`) |
| `pyproject.toml` `[tool.pytest.ini_options] markers` | `integration`/`smoke`/`slow`/`browser` | adds `order_dependent` **only if** the quarantine path is taken |
| `pyproject.toml` | no `[tool.vulture]` / `[tool.deptry]` | adds both config sections (whitelist path / min-confidence; deptry ignores) |
| `vulture_whitelist.py` | does not exist | new (only if the whitelist-file approach is chosen over `--ignore-*` flags) |
| `Makefile` | `quality: lint format typecheck test-assertions`; no `dead-code`/`dep-check` | adds `dead-code:` + `dep-check:` (warn-only); `quality:` appends them; `.PHONY` updated |
| `.github/workflows/test-quality.yml` | `lint-typecheck` job: lint + test-assertions + format + typecheck | adds a non-failing/informational `dead-code` + `dep-check` step |
| `tests/unit/test_safe_migrate.py` | `test_apply_refuses_in_agent_context` / `test_rollback_refuses_in_agent_context` fail in an agent worktree | fixed — control the leaking guard env var(s) |
| `tests/**` (various) | order-fragile in places | order-dependent failures fixed (test-isolation fixes only) or quarantined with `@pytest.mark.order_dependent` |
| `tests/CLAUDE.md` | no `pytest-randomly` recipe | adds the disable/reproduce recipe |
| `docs/IW_AI_Core_Testing_Strategy.md` | §3/§5/§6/§9 don't mention randomization, dead-code/dep-hygiene, strict markers | updated as above |
| `skills/iw-ai-core-testing/SKILL.md` (+ `.claude/` copy) | §2/§7/§8 don't mention these | updated; re-synced |
| `skills/iw-workflow/SKILL.md` (+ `.claude/` copy) | n/a | unchanged unless a new marker needs documenting there (unlikely) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | items 1.4/1.5/1.7 TODO; P1-CR-C = "*(start here)*" | items DONE (CR-00048); P1-CR-C = SHIPPED; "*(start here)*" → P1-CR-D; changelog; maybe a `P1-CR-C-followup` row |

### Breaking Changes

- **None.** `pytest-randomly` is additive — and the suite is made robust to it (or it's off-by-default in the fallback), so the daemon's `unit-tests`/`integration-tests` QV gates and the GH test jobs don't start flaking. `--strict-markers` only turns already-broken markers into errors — those are fixed in S01. `vulture`/`deptry` are warn-only — they print, they don't block. The `test_safe_migrate` fix makes a currently-broken test pass. Adding 3 deps mutates `uv.lock`. No DB schema change, no API change, no workflow-manifest schema change.

### Data Migration

- **None.** No database changes. Reversible by `git revert` of the merge commit + `iw sync-skills` to regenerate the in-project skill copies.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | **(0) RED-first**: reproduce the `test_safe_migrate` failure mode (run the 2 tests with `IW_CORE_PER_WORKTREE_DB=true` in the env; confirm `AssertionError`/`Failed: DID NOT RAISE`); capture the RED line. **(1)** Add `pytest-randomly`, `vulture`, `deptry` to `[dependency-groups] dev`; regen `uv.lock`. **(2)** Bounded multi-seed sweep — `make test-unit` 3× (different `--randomly-seed`) + `make test-integration` 1× (one more seed); **no more** (the integration suite is slow; downstream QV gates re-run it); catalogue failures; **fix or quarantine** each per the triage in Desired Behavior; if descoping, file the `P1-CR-C-followup` and add it to §5; if even quarantine is impractical, use the off-by-default fallback. **(3)** Add `--strict-markers` to `addopts`; run; fix any typo'd/unregistered markers. **(4)** Add `[tool.vulture]` (whitelist/min-confidence) + `[tool.deptry]` (ignores) config; create `vulture_whitelist.py` if used; add `make dead-code` + `make dep-check` (warn-only) + append to `quality:` + `.PHONY`; add a non-failing step to `.github/workflows/test-quality.yml`'s `lint-typecheck` job. **(5)** Fix `tests/unit/test_safe_migrate.py`'s 2 agent-context tests (read `orch/db/safe_migrate.py` to find the exact env var(s); control them in the test). **(6)** Document the `pytest-randomly` recipe in `tests/CLAUDE.md`; update `docs/IW_AI_Core_Testing_Strategy.md` §3/§5/§6/§9 and `skills/iw-ai-core-testing/SKILL.md` §2/§7/§8. **(7)** `iw sync-skills`. **(8)** Tick items 1.4/1.5/1.7 + §5 grouping + changelog in `ai-dev/work/TESTS_ENHANCEMENT.md`. **(9)** `make quality` must pass (the warn-only steps must not fail it); targeted re-run of touched test files. Do **not** also run `make check` / the full suites again — that's the QV gates' job. Record `tdd_red_evidence` = the `test_safe_migrate` RED run. S01 carries an extended `timeout` (≈2400s) for the bounded sweep + `uv lock`/`uv sync` + `make quality`. | — |
| S02 | `code-review-impl` | Review S01: the order-dependent failures are genuinely fixed (test-isolation only, no behavioral changes) or correctly quarantined + a follow-up filed; `--strict-markers` added + markers clean; `vulture`/`deptry` warn-only (do **not** block `make quality`/CI); the `test_safe_migrate` fix is correct (passes in agent worktree *and* CI; no production-code change); `uv.lock` updated for all 3 deps; doc/plan/skill updates present; `iw sync-skills` ran (diff `.claude/skills/iw-ai-core-testing/SKILL.md` vs master); the `pytest-randomly` recipe is documented; no out-of-scope edits (no integration-gate fix, no hard-gate flip, no broad dead-code deletion pass). | — |
| S03 | `code-review-final-impl` | Global review: the suite is robust to randomization (or off-by-default with a filed follow-up — design states which); `make quality` includes the warn-only steps without failing on them; `.claude/skills/` in sync; `make check` passes; no scope creep. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` — **now with `pytest-randomly` enabled** (the dep landed in S01); exercises the randomization on this very CR's run. If it flakes, the suite isn't robust yet → S01 must fix more. | — |
| S09 | `qv-gate` (`integration-tests`) | `make allure-integration` (timeout 900; still the no-op stub — P1-CR-E) | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` (timeout 1800) — runs against this CR's diff (mostly config/Makefile/docs + a few test-file fixes; test code is covered when it runs) — should pass. | — |
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
| `ai-dev/active/CR-00048/CR-00048_CR_Design.md` | Design | This document |
| `ai-dev/active/CR-00048/CR-00048_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `ai-dev/active/CR-00048/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/CR-00048/prompts/CR-00048_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `ai-dev/active/CR-00048/prompts/CR-00048_S02_CodeReview_prompt.md` | Prompt | S02 review instructions |
| `ai-dev/active/CR-00048/prompts/CR-00048_S03_CodeReview_Final_prompt.md` | Prompt | S03 final review instructions |
| `ai-dev/active/CR-00048/prompts/CR-00048_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment instructions |

Files **changed** by the implementation (mirrored to `workflow-manifest.json:scope.allowed_paths`):
`pyproject.toml` · `uv.lock` · `Makefile` · `vulture_whitelist.py` (if used) · `.github/workflows/test-quality.yml` · `tests/**` (the `test_safe_migrate` fix + any order-dependent test-isolation fixes — scope intentionally broad on `tests/`; the reviewer must verify the diff is only test-isolation fixes) · `tests/CLAUDE.md` · `docs/IW_AI_Core_Testing_Strategy.md` · `skills/iw-ai-core-testing/SKILL.md` · `.claude/skills/iw-ai-core-testing/SKILL.md` · `skills/iw-workflow/SKILL.md` (only if a new marker is documented there) · `.claude/skills/iw-workflow/SKILL.md` (ditto) · `ai-dev/work/TESTS_ENHANCEMENT.md`.

Reports are created during execution under `ai-dev/work/CR-00048/reports/`.

## Acceptance Criteria

### AC1: pytest-randomly is in, and the suite is robust to it

```
Given pyproject.toml and uv.lock after this CR
Then `pytest-randomly` is in the dev dependency group and uv.lock

Given `make test-unit` and `make test-integration` run with pytest-randomly enabled (the default once installed)
When `make test-unit` is run with 3 different --randomly-seed values and `make test-integration` with one more (S01's bounded sweep; the downstream QV gates S08/S10 supply further seeds)
Then all those runs end with 0 failures
And every order-dependent failure S01 surfaced is either fixed (a test-isolation fix, no behavioral change) or marked @pytest.mark.order_dependent (registered) with a P1-CR-C-followup filed
OR (fallback) addopts contains `-p no:randomly`, the design/changelog explain why, and a follow-up to flip it on is filed
```

### AC2: --strict-markers is default and markers are clean

```
Given pyproject.toml's [tool.pytest.ini_options] addopts after this CR
Then it contains --strict-markers
And `make test-unit` / `make test-integration` pass (no unregistered/typo'd markers; any found were fixed)
And any legitimately-new marker (e.g. order_dependent) is registered in the markers list
```

### AC3: dead-code and dep-check exist, warn-only

```
Given the Makefile after this CR
Then there is a `dead-code:` target running `vulture` over orch/dashboard/executor/scripts with --min-confidence >= 70 and a whitelist (file or --ignore-* flags) for false positives
And there is a `dep-check:` target running `deptry .` (with [tool.deptry] config for false positives)
And `quality:` invokes both as non-failing (e.g. `... || true`)
And `.github/workflows/test-quality.yml`'s lint-typecheck job runs both as non-failing/informational steps
And neither causes `make quality` or the GH job to fail in this CR

Given `make quality` is run
Then it exits 0 (lint + format-check + typecheck + test-assertions all pass; dead-code/dep-check print findings but don't fail it)
```

### AC4: the test_safe_migrate env-leak is fixed

```
Given tests/unit/test_safe_migrate.py after this CR
When `test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context` are run with IW_CORE_PER_WORKTREE_DB=true in the environment (simulating an agent worktree)
Then they pass
And they also pass when run in CI / locally (no env pollution)
And the fix is in the test (controlling the leaking guard env var(s)) — not in orch/db/safe_migrate.py
And the S01 step report's tdd_red_evidence shows these tests failing (DID NOT RAISE / AssertionError) before the fix
```

### AC5: the recipe is documented

```
Given tests/CLAUDE.md and skills/iw-ai-core-testing/SKILL.md after this CR
Then both describe: pytest-randomly is default-on; the per-run seed is printed; `pytest -p no:randomly` disables it; `pytest --randomly-seed=<N>` reproduces a failure
And .claude/skills/iw-ai-core-testing/SKILL.md matches (iw sync-skills ran)
```

### AC6: the plan and strategy doc are updated

```
Given ai-dev/work/TESTS_ENHANCEMENT.md
Then items 1.4, 1.5, 1.7 are DONE (CR-00048) — or "partial — cleanup follow-up filed" if the pytest-randomly cleanup was descoped
And §5's grouping table marks P1-CR-C SHIPPED (or "SHIPPED — cleanup follow-up filed") and "*(start here)*" has moved to P1-CR-D
And a changelog entry exists with the order-dependent-failure counts, the marker fixes, the vulture/deptry setup, the test_safe_migrate fix, and any fallback used

Given docs/IW_AI_Core_Testing_Strategy.md
Then §3 notes pytest-randomly is default-on + the recipe; §5's gate table has dead-code (warn-only) and dep-check (warn-only) rows; §6 notes --strict-markers is default; §9's "Test-order randomisation" and "vulture/deptry" rows are ✅
```

### AC7: this CR's own QV gates pass under randomization

```
Given S08 (`unit-tests`, `make test-unit`) and S09 (`integration-tests`) run with pytest-randomly active
Then they pass — i.e. the suite S01 left behind is genuinely robust to randomization (or off-by-default per the fallback)

Given S10 (`diff-coverage`, `make diff-coverage`)
Then it passes (this CR's diff is mostly config/Makefile/docs + test-file fixes whose own lines are covered when they run)
```

## Rollback Plan

- **Database**: Not applicable — no schema or data changes.
- **Code**: `git revert` the squash-merge commit (reverts the 3 dep adds + `uv.lock`, the `addopts`/marker changes, the `[tool.vulture]`/`[tool.deptry]` config + whitelist, the `make` targets + `quality:` change, the GH-workflow step, the test fixes/quarantine markers, the doc/plan/skill changes). Then `iw sync-skills` to regenerate `.claude/skills/iw-ai-core-testing/SKILL.md` (and `.claude/skills/iw-workflow/SKILL.md` if it changed) from the reverted masters.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00045 (`tdd_red_evidence` contract), CR-00046 (assertion scanner / canon shape), CR-00047 (`make diff-coverage` / `fail_under = 50`). All merged.
- **Blocks**: Nothing hard. P1-CR-D (security gates) and P1-CR-E (Allure + smoke SLA + the `integration-tests` no-op-gate fix) are independent. A `P1-CR-C-followup` (order-dependent backlog) and the existing `P1-CR-A-followup` (assertion-baseline scrub) run in the background.

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `vulture_whitelist.py`
- `.github/workflows/test-quality.yml`
- `tests/**`
- `tests/CLAUDE.md`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md`
- `skills/iw-workflow/SKILL.md`
- `.claude/skills/iw-workflow/SKILL.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **Unit tests**: the behavioural test fix is `tests/unit/test_safe_migrate.py`'s 2 agent-context tests — RED-first (reproduce the `IW_CORE_PER_WORKTREE_DB`-leak failure, capture it, then fix the test isolation). Any order-dependent test fixes are also test-side (no production change). No *new* test files are required by this CR (the `pytest-randomly` work is configuration + fixing existing tests; `vulture`/`deptry` are tooling, not testable logic).
- **Integration tests**: None added — the new behaviour (random order, strict markers, dead-code/dep checks) is exercised by the QV gates themselves (S08/S09 run under randomization; S04 runs lint with the new config).
- **Updated tests**: `tests/unit/test_safe_migrate.py` (the env-leak fix) + whatever order-dependent tests S01 surfaces (test-isolation fixes only).

## Notes

- **`pytest-randomly` blast radius is the wildcard.** S01's first substantive action (after the RED reproduction and adding the deps): a **bounded** multi-seed sweep — `make test-unit` 3× (different seeds) + `make test-integration` 1× (one more seed) — then catalogue the failures. **Bounded on purpose:** the integration suite is slow, S01 carries a finite timeout, and the QV gates downstream (S08, S10) re-run the suites under further seeds anyway — so S01 must not re-run `make test-integration` repeatedly (that's exactly the I-00073 timeout failure mode). **In all cases the suite must end green under randomization** — fixed, quarantined (with a registered marker + a filed follow-up), or (last resort) `-p no:randomly` off-by-default with a filed follow-up to flip it on. The design deliberately leaves the fix-vs-quarantine choice to S01 based on what it finds, but the *end state* (green under randomization, or explicitly off-by-default) is mandatory — do not merge with the suite failing under random order.
- **This is a testing-infrastructure CR — a bounded full-suite exception applies.** The general rule ("an implementation step never runs the full suite, never touches `make test-integration` — that's the QV gates' job"; I-00073/S03) is *relaxed* here because making the suite robust to randomization is the deliverable and can only be proven by running it under multiple seeds. The relaxation is bounded: deliverable 2's sweep (`make test-unit` ×3 + `make test-integration` ×1) is the *only* full-suite run S01 may do — no `make check`, no extra integration runs, targeted runs only otherwise. S01 also gets an extended `timeout` (≈2400s) in the manifest to absorb the sweep + `uv lock`/`uv sync` + `make quality`. Reviewers should treat the deliverable-2 sweep as expected, not as scope creep.
- **`vulture` is noisy** — expect dozens of false positives (FastAPI handlers, pytest fixtures, dynamically-referenced names, `__all__`, Click commands). The whitelist file / `--ignore-decorators` / `--ignore-names` config is mandatory; `--min-confidence` ≥ 70; warn-only is mandatory for this CR. Do not let `vulture` block anything.
- **`deptry`** — will flag transitive-but-imported / dev-deps-used-in-prod / etc. Some IW patterns (optional imports, plugin discovery, the `iw` CLI's lazy command loading) need `[tool.deptry] ignore_*` entries. Warn-only for this CR.
- **Do NOT do a dead-code *deletion* pass** — `vulture` warn-only just *reports*. Actually deleting flagged dead code is a separate, riskier effort; if `vulture`'s output is enlightening, note candidates for a follow-up in the step report, but delete nothing here.
- **`scope.allowed_paths` is intentionally broad on `tests/**`** — the order-dependent fixes can't be predicted (they could be in any test file or any `conftest.py`). The reviewer must verify the diff under `tests/` is *only* test-isolation fixes + the `test_safe_migrate` fix + quarantine markers — no behavioral test changes, no new assertions weakened, etc.
- **`iw sync-templates` is NOT needed** — no `templates/design/*.md` edits. `iw sync-skills` IS needed (for `iw-ai-core-testing`; also `iw-workflow` only if a new marker is documented there). Confirm in the step report. Sibling repos (iw-doc-plan/podforger/cv) pick up any shared-skill (`iw-workflow`) change at their next `iw sync-skills` — not done from this worktree; `iw-ai-core-testing` is project-specific (not propagated).
- **Scope discipline** — do not fix the `integration-tests` no-op gate (P1-CR-E); do not add `mutmut`/`gitleaks`/`semgrep` (subsequent CRs / Phase 2); do not flip `vulture`/`deptry` to hard gates yet (warn-first; a follow-up flips them); do not scrub the assertion baseline (P1-CR-A-followup); do not change the workflow-manifest schema; do not modify production code beyond what the `test_safe_migrate` fix genuinely requires (it shouldn't require any).
- **Why `backend-impl`** — config (`pyproject.toml`/`uv.lock`), Makefile targets, test-isolation fixes (the `test_safe_migrate` fix + any order-dependent fixes), a whitelist file, doc updates, a GH-workflow edit, `iw sync-skills`. `tdd_red_evidence` = the RED run for the `test_safe_migrate` fix.
