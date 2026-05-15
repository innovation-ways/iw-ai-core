# CR-00052: Allure reporting recipes + curated smoke layer with SLA (P1-CR-E)

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase-1 P1-CR-E from `ai-dev/work/TESTS_ENHANCEMENT.md`. Bundles items 1.8 (Allure `make` targets — currently `.PHONY` stubs with no recipes) and 1.11 (curated smoke layer with documented SLA). Phase 1's last grouping CR. The third bit of P1-CR-E's original scope (the `integration-tests` no-op-gate fix) already landed as a direct change on 2026-05-14 (`a4e9ac8a`), so this CR is the smaller "tidy-up" subset.
**Created**: 2026-05-14
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR only touches the Makefile, configs, tests/markers, and docs. No new Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

(a) Replace 6 empty Allure `.PHONY` stubs in `Makefile` (`allure-unit`/`-integration`/`-all`/`-report`/`-serve`/`-clean`) with real recipes that write Allure results to `$(ALLURE_RESULTS)` and produce/serve HTML reports — ported from InnoForge's `iw-doc-plan/main/iw-doc-plan/Makefile:318–348` pattern. (b) Audit the existing 16 smoke-marked tests against the plan's 5 critical paths, trim/re-mark to land at **≤15 tests covering all 5 paths**, measure and document the wall-clock SLA (**<60 s**), and write that SLA into `tests/CLAUDE.md` + `docs/IW_AI_Core_Testing_Strategy.md` as **prose only** (no `make smoke-sla` enforcement target — operator's call to keep the CR small; mechanical enforcement is a future follow-up if drift happens).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `tests/CLAUDE.md` for testing conventions (you will extend §7-ish with the smoke SLA subsection). Read `docs/IW_AI_Core_Testing_Strategy.md` for the existing structure (the SLA goes alongside the existing §5/§6 prose). Read `iw-doc-plan/main/iw-doc-plan/Makefile:318–348` for the InnoForge Allure pattern this CR ports.

## Current Behavior

**Allure (item 1.8):**

- `allure-pytest>=2.15.3` is in `[project] dependencies` (`pyproject.toml:87`). Already installed.
- The Makefile's `.PHONY` declaration (top of file, line 5–10ish) lists 6 allure targets: `allure-unit`, `allure-integration`, `allure-all`, `allure-report`, `allure-serve`, `allure-clean`.
- **None of them has a recipe.** `grep -nA 2 "^allure-" Makefile` returns nothing for any of those names.
- Make treats them as `.PHONY` targets that always succeed trivially (exit 0). This is why the `integration-tests` QV gate that pointed at `make allure-integration` from CR-00046's introduction through 2026-05-14 was a silent no-op — flagged HIGH by CR-00046's self-assess, tracked in §10, and fixed as a direct change on 2026-05-14 (`a4e9ac8a` — canonical gate command flipped to `make test-integration`).

**Smoke (item 1.11):**

- The `smoke` marker is registered in `pyproject.toml:152`: `"smoke: fast critical-path tests; ~10 covering core flows; run via 'make smoke'"`. Note the "~10" — aspirational, not enforced.
- `make smoke` target at `Makefile:107–108`: `uv run pytest -m smoke --strict-markers --no-cov -v`.
- **Currently 16 smoke-marked tests** across 7 files (count verified 2026-05-14 via `grep -rc "@pytest.mark.smoke" tests/`):
  - `tests/unit/test_smoke.py` (7)
  - `tests/integration/test_db_identity_integration.py` (3)
  - `tests/integration/test_dashboard_remaining.py` (2)
  - `tests/integration/test_dashboard_pages.py` (1)
  - `tests/integration/test_cli_batches.py` (1)
  - `tests/unit/test_daemon_core.py` (1)
  - `tests/unit/dashboard/test_coverage_service.py` (1)
- **No written SLA.** No documented count cap. No documented wall-clock cap. The implicit "~10" in the marker description has already drifted to 16 — exactly the kind of soft-drift this CR codifies a contract around.
- The plan §5 row for item 1.11 lists 5 critical paths the smoke layer should cover: daemon starts a worktree; dashboard serves main pages; `iw next-id` works; a work item can be queued; `/healthz` sane. **No verification today that all 5 are represented**, and no audit table mapping the existing 16 tests to those paths.

## Desired Behavior

**Allure (item 1.8):**

- A `Makefile` variable `ALLURE_RESULTS := tests/output/allure-results` defined near the existing `SECURITY_DIR :=` / similar variables. Sits alongside `tests/output/coverage/` (the existing CR-00047 pattern).
- `tests/output/allure-results/` listed in `.gitignore` (it's an artefact dir).
- Each of the 6 stubs gets a real recipe, following the InnoForge pattern at `iw-doc-plan/main/iw-doc-plan/Makefile:318–348`:
  - `allure-unit`: cleans + makes `$(ALLURE_RESULTS)`, runs `uv run pytest tests/unit/ -v --alluredir=$(ALLURE_RESULTS)`, prints "Run `make allure-serve` to view".
  - `allure-integration`: same shape, against `tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser` (matches the canonical `make test-integration` invocation flipped in 2026-05-14).
  - `allure-all`: combined — both suites' results written into the same `$(ALLURE_RESULTS)` dir.
  - `allure-report`: runs `allure generate $(ALLURE_RESULTS) -o tests/output/allure-report --clean` (requires the `allure` CLI binary; recipe includes a `command -v allure` install-check matching the existing security-target convention).
  - `allure-serve`: runs `allure serve $(ALLURE_RESULTS)` — opens the dashboard locally.
  - `allure-clean`: `rm -rf $(ALLURE_RESULTS) tests/output/allure-report`.
- All 6 remain in `.PHONY`.
- The recipes are **local developer tools** — not run in CI as part of this CR (artefact upload is a future Phase-4 enhancement). They just need to work locally.

**Smoke (item 1.11):**

- The smoke marker covers **≤15 tests** that together cover all 5 plan paths. S01 audits each of the current 16 tests, classifies it as "covers path X" or "redundant" or "out-of-scope (re-mark non-smoke)", and lands at a curated ≤15. Audit table goes in S01's step report (and is summarised in §11 changelog).
- **No new test files** — S01 may *remove* a `@pytest.mark.smoke` decorator from a redundant test, or *add* one to an existing test that covers an under-represented plan path, but **does not create new test files**.
- `pyproject.toml`'s smoke marker description is updated from `"~10 covering core flows"` to match the new SLA — e.g. `"≤15 fast critical-path tests covering the 5 paths documented in tests/CLAUDE.md; wall-clock <60 s"`.
- `make smoke` wall-clock measured on a clean dev environment is **<60 s**. The measurement is recorded in S01's report and in §11 changelog (e.g. `"make smoke: 13 tests, 42.3 s"`).
- `tests/CLAUDE.md` gets a new "Smoke layer SLA" subsection. Contents: the ≤15/`<`60s contract, the 5 critical paths listed by name, the rule that adding a new `@pytest.mark.smoke` decorator requires re-auditing the SLA (which means trimming if the count goes over, or re-measuring if a test is slow).
- `docs/IW_AI_Core_Testing_Strategy.md` §5 (or §6 — wherever the smoke layer is already mentioned) gets the same SLA prose.
- **No `make smoke-sla` enforcement target.** Operator's call (prose-only) to keep this CR small. If drift happens, a follow-up CR adds enforcement.

**Plan + changelog:**

- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 P1-CR-E row → **SHIPPED (CR-00052, YYYY-MM-DD)** with the audit summary (count after curation + wall-clock measurement).
- Items 1.8 + 1.11 → **DONE (CR-00052, YYYY-MM-DD)**.
- §11 changelog entry: Allure recipes ported (6 stubs filled); smoke audit (16 → N tests, M removed as redundant, K re-marked) covering all 5 plan paths; wall-clock measurement; SLA prose in `tests/CLAUDE.md` + strategy doc.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `Makefile` allure-* targets (6) | `.PHONY` stubs, no recipes → silent exit 0 | 6 real recipes following the InnoForge pattern; `ALLURE_RESULTS` variable defined |
| `Makefile` `.PHONY` line | already lists the 6 allure targets | unchanged |
| `.gitignore` | (likely doesn't list `tests/output/allure-results/`) | `tests/output/allure-results/` and `tests/output/allure-report/` added |
| `pyproject.toml` `smoke` marker description | `"smoke: fast critical-path tests; ~10 covering core flows; run via 'make smoke'"` | `"smoke: fast critical-path tests; ≤15 covering the 5 critical paths documented in tests/CLAUDE.md; wall-clock <60 s; run via 'make smoke'"` (or similar) |
| `tests/**` `@pytest.mark.smoke` decorators | 16 markers across 7 files | ≤15 markers (some removed as redundant, some possibly re-added to cover a missing path); same files or near-same files. Audit table in step report. |
| `tests/CLAUDE.md` | no smoke SLA subsection | new "Smoke layer SLA" subsection naming the contract + the 5 paths + the audit-on-change rule |
| `docs/IW_AI_Core_Testing_Strategy.md` §5/§6 | smoke mentioned without SLA | smoke SLA subsection added with the same contract |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §5 + §11 | P1-CR-E row open, items 1.8/1.11 TODO | P1-CR-E SHIPPED, items 1.8/1.11 DONE, new §11 changelog entry |

### Breaking Changes

**None.** Additive Makefile recipes. The smoke marker re-balancing is test-only (no behavioural test changes — just toggling which tests get the `@pytest.mark.smoke` decorator).

### Data Migration

**None.** No DB tables, rows, or migrations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Allure recipes + smoke audit + SLA docs + plan/changelog. 2400 s timeout. | — |
| S02 | `code-review-impl` | Audit table completeness, recipe correctness, no scope creep | — |
| S03 | `code-review-final-impl` | Independent re-run of `make smoke` + `make allure-unit` + audit-table internal consistency | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S09 | `qv-gate` (`integration-tests`) | `make test-integration` — **the gate that was flipped from no-op on 2026-05-14**; this CR is the first to exercise it for real | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` | — |
| S11 | `qv-gate` (`security-secrets`) | `make security-secrets` (CR-00050) | — |
| S12 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project `self_assess = true`) | — |

Agent slugs verified against `skills/iw-workflow/SKILL.md`'s canonical agent table and `executor/step_executor_lib.sh`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migrations.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None
- `browser_verification` = **false** (no UI surface).

## File Manifest

All files for this work item live under `ai-dev/active/CR-00052/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00052_CR_Design.md` | Design | This document |
| `CR-00052_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00052_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `prompts/CR-00052_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00052_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review |
| `prompts/CR-00052_S12_SelfAssess_prompt.md` | Prompt | S12 self-assess |

(S04–S11 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00052/reports/`.

## Acceptance Criteria

### AC1: Allure recipes produce real output

```
Given the patched Makefile
When `make allure-unit` is run on a clean dev environment
Then it executes `uv run pytest tests/unit/ -v --alluredir=$(ALLURE_RESULTS)`
And $(ALLURE_RESULTS) (= tests/output/allure-results/) contains the expected *-result.json files from the run
And the recipe exits 0
And the recipe prints a hint pointing at `make allure-serve`
```

### AC2: Allure integration recipe matches the canonical gate scope

```
Given the patched Makefile
When `make allure-integration` is run
Then it executes against `tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser` (the same scope as `make test-integration`)
And produces results in $(ALLURE_RESULTS)
```

### AC3: Remaining Allure recipes work

```
Given the patched Makefile
When each of `make allure-all`, `make allure-report`, `make allure-serve`, `make allure-clean` is invoked
Then `allure-all` runs both suites and writes to $(ALLURE_RESULTS)
And `allure-report` runs `allure generate $(ALLURE_RESULTS) -o tests/output/allure-report --clean` (requires `allure` CLI; recipe has `command -v allure` install-check that prints a clear error if missing)
And `allure-serve` runs `allure serve $(ALLURE_RESULTS)` (interactive — verified by inspection of the recipe, not by running)
And `allure-clean` removes both $(ALLURE_RESULTS) and tests/output/allure-report/
```

### AC4: Smoke wall-clock SLA

```
Given the patched repo on a clean dev environment
When `make smoke` is run
Then it completes in <60 s wall clock
And the measurement is recorded in S01's report and in §11 changelog as "make smoke: N tests, T s"
```

### AC5: Smoke count + critical-path coverage

```
Given the audit table in S01's step report
When the table is examined
Then it has one row per @pytest.mark.smoke decorator that exists in the patched tree
And the count is ≤15
And each of the 5 plan-listed critical paths (daemon worktree start; dashboard main pages; `iw next-id`; work item queue; /healthz) has ≥1 smoke test mapped to it
And every smoke-marked test in the audit table maps to ≥1 critical path (no orphans)
```

### AC6: SLA documentation

```
Given the patched repo
When `tests/CLAUDE.md` and `docs/IW_AI_Core_Testing_Strategy.md` are read
Then both have a "Smoke layer SLA" subsection naming:
  - the ≤15/`<`60s contract (with the actual measured wall-clock from AC4 quoted)
  - the 5 critical paths by name
  - the rule that adding a new @pytest.mark.smoke decorator requires re-auditing (trim if over count, re-measure if a slow test)
And pyproject.toml's smoke marker description matches the SLA
And the prose in the three locations (tests/CLAUDE.md, strategy doc, pyproject.toml comment) is consistent — same count, same wall-clock, same paths
```

### AC7: .gitignore covers Allure artefacts

```
Given the patched .gitignore
When `git status` is run after `make allure-unit`
Then no Allure files appear as untracked
And both `tests/output/allure-results/` and `tests/output/allure-report/` are gitignored
```

### AC8: Plan + changelog updated

```
Given S01's edits
When ai-dev/work/TESTS_ENHANCEMENT.md is read
Then §5 P1-CR-E row is SHIPPED (CR-00052, YYYY-MM-DD)
And items 1.8 and 1.11 are DONE (CR-00052) with one-liner status
And §11 has a new dated changelog entry with the audit summary (16 → N tests, M removed, K re-marked) and the wall-clock measurement
And no follow-up rows are added beyond the pre-existing P1-CR-A-followup (assertion-baseline scrub); specifically, no P1-CR-E-followup-sla-enforcement row is filed unless drift emerges — that's a future operator decision
```

### AC9: QV chain passes (note: S09 is the real integration-tests gate now)

```
Given the patched worktree at S01 completion
When the daemon runs S04–S11
Then S04 (lint), S05 (assertions), S06 (format-check), S07 (typecheck), S08 (test-unit), S09 (test-integration), S10 (diff-coverage), S11 (security-secrets) all exit 0
And S09 in particular is exercised for real (the post-2026-05-14 flip) — this is the first CR whose `integration-tests` gate actually runs tests; any pre-existing latent integration failure that the no-op gate hid must be surfaced here
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the squash-merge commit. The 6 Allure recipes return to empty `.PHONY` stubs; smoke markers return to 16 tests across the original 7 files; `pyproject.toml` smoke marker description returns to "~10 covering core flows"; `tests/CLAUDE.md` and `docs/IW_AI_Core_Testing_Strategy.md` lose their SLA subsections. No data loss possible.
- **Data**: No data loss possible (tooling/docs-only CR).

## Dependencies

- **Depends on**: nothing hard. Builds on (but does not require) the 2026-05-14 direct change that flipped `integration-tests` to `make test-integration` — this CR is the first to exercise that gate for real in its own QV chain.
- **Blocks**: nothing. After P1-CR-E lands, the only Phase-1 remnants are CR-00049 (still drafted but unrun) and P1-CR-A-followup (low-urgency assertion-baseline scrub). Phase 2 begins.

## Impacted Paths

- `Makefile`
- `.gitignore`
- `pyproject.toml`
- `tests/**`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **RED-first evidence**: deliverable 0 captures the *current* state — the empty Allure stubs (proof by running `make allure-unit` and observing it exits 0 with no output) and the current smoke wall-clock measurement (proof by running `make smoke` and recording the timer). These are this CR's RED anchors: empty recipes → no-op; "~10" aspiration → 16 reality with no audit. The GREEN evidence is deliverables 1-4: real Allure recipes producing real output; smoke count ≤15 covering all 5 paths; measured wall-clock <60 s.
- **Unit tests**: None new. The Allure recipes are themselves the assertion — they run, they write files, they exit 0.
- **Integration tests**: None new. The smoke layer is being *curated*, not *expanded*.
- **Updated tests**: Only the `@pytest.mark.smoke` decorators on existing tests are touched — no behavioural changes, no weakened assertions.

## Notes

- **S09 is the moment of truth.** This CR is the first whose `integration-tests` QV gate actually runs the suite (post-2026-05-14 flip from `make allure-integration` → `make test-integration`). If the integration suite has latent failures that the silent no-op gate has been hiding, S09 will surface them. S01 should be aware that an unexpected S09 failure here is a *real* finding, not a flaky CI issue. If S09 fails, the fix path is: (a) if it's a real test-side bug, file as a separate incident; (b) if it's the suite's well-known order-dependence under randomisation (CR-00048 fallback context), confirm `-p no:randomly` is still active (CR-00049 hasn't merged yet); (c) if neither, escalate via blockers.

- **The audit table is the deliverable, not just a side-effect.** Operator's bar (strict ≤15 + all 5 plan paths) means S01 must produce a transparent, line-by-line classification of the existing 16 smoke decorators. Reviewers in S02/S03 use this table to verify the curation is honest. Don't skip the table; it's how the change is auditable.

- **No `make smoke-sla` enforcement target.** Operator's call — keep this CR small. If smoke drift happens later (e.g., a future CR adds a slow smoke test that pushes wall-clock over 60 s), the response is either: (i) tighten reviewer discipline, (ii) file `P1-CR-E-followup-sla-enforcement` to add the mechanical target. Today, drift is caught by the explicit rule in `tests/CLAUDE.md` that adding `@pytest.mark.smoke` requires re-auditing.

- **The "~10" in the existing marker description is aspirational drift.** When this CR rewrites the marker description, it codifies the contract: the count cap, the wall-clock cap, and the audit-on-change rule. Future agents writing tests get the contract directly from the marker description — no excuse for adding a smoke test without re-auditing.

- **`allure` CLI binary is not always installed.** The recipe for `allure-report` and `allure-serve` needs a `command -v allure` install-check (matching the existing pattern at `Makefile:180–189`'s `security-deps` and `Makefile:200–204`'s `security-iac`) that prints a clear install hint and exits 1 if missing. `allure-pytest` (the pytest plugin) IS installed via `pyproject.toml:87`; the Java-based `allure` CLI is a separate binary the developer needs locally. Don't pretend it's installed; gate behind a clear error.

- **Sibling repos** (`iw-doc-plan`/`podforger`/`cv`) already have their own Allure recipes — InnoForge's are the reference. This CR doesn't port to or sync with sibling projects; each picks up changes via their own `iw sync-skills` cadence. Out of scope.
