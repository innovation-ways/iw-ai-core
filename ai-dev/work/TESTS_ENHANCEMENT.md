# IW AI Core — Testing Enhancement Plan

> **Status**: living plan — v1.1 (2026-05-11)
> **Owner**: sergio
> **Source research**: [`docs/research/R-00068-ai-core-test-quality-strategy.md`](../../docs/research/R-00068-ai-core-test-quality-strategy.md) (R-00068)
> **Purpose**: the single place we track *what* we want to improve about IW AI Core's testing, *why*, and *how* — and the running status of each piece. We tackle items one at a time, each delivered either as a CR/Feature or as a direct change, decided at the time.
>
> **Current status (2026-05-11):** Phase 0 (the "constitution") is essentially done — 0.1 (strategy doc), 0.2 (`iw-ai-core-testing` skill), 0.3 (`tests/CLAUDE.md` updates) are committed (`db8f7b2`); **0.4 is CR-00045**, drafted + registered (status `draft`), under review, queued to run. Once CR-00045 merges, Phase 0 is complete and **Phase 1 begins — start with the assertion scanner (1.1)**; see the "proposed CR grouping & sequencing" at the top of §5.

---

## 1. Why we are doing this at all

IW AI Core has 413 test files (175 unit / 169 integration / 69 dashboard), strong DB-isolation discipline, and a decent quality pipeline. But the suite is **unvalidated** and **structurally incomplete**:

1. **Almost all production *and* test code is written by LLM agents.** AI-generated tests routinely pass while asserting nothing meaningful, asserting on their own mocks, or restating the implementation. Test *count* and *line coverage* are therefore weak quality signals for us specifically — we need instrumentation that measures whether a test would actually *fail* when the code regresses.
2. **There is no written definition of "a good test here."** No testing-strategy doc, no agent testing skill. So every `tests-impl` / `backend-impl` run re-derives conventions from scratch, and reviewers have no checklist. This is the biggest single leverage point.
3. **Coverage can silently rot.** Coverage is reported in `pytest` `addopts` but nothing *fails* on a drop. New code can ship with new branches uncovered.
4. **Whole classes of bug are untested.** Cross-project data leaks, a 5xx on a dashboard route, a broken `iw` exit code, a migration that doesn't round-trip, an SSRF/path-traversal in doc rendering, a daemon that doesn't recover from a worktree failure — nothing exercises these today.
5. **The sibling repos already solved most of this.** InnoForge (`iw-doc-plan/main/iw-doc-plan`) has mutation testing, an assertion scanner, Hypothesis property tests, a dedicated `innoforge-testing` skill, visual regression, contract sweeps, a testing-strategy doc, a TDD mandate. Podforger adds a per-domain Playwright E2E matrix and Trivy security scanning. Much of our work is **port + adapt, not invent** — see the port-inventory table in R-00068.

**Guiding principles** (these go verbatim into the testing-strategy doc and the testing skill once we write them):

- *Coverage is a floor on what's exercised; mutation score is the measure of whether exercising it matters.* Coverage alone is never the gate.
- *Every test must be able to fail.* If deleting the corresponding production line wouldn't fail the test, the test is worthless.
- *Tests assert on behaviour, not on their own mocks.*
- *Write the test first; confirm it fails before implementing (RED evidence recorded).*
- *Keep the pyramid.* AI lets us afford a slightly fatter integration band, but E2E stays thin and curated; the bulk of behaviour is pinned by integration tests against the testcontainer DB.
- *Cheap blocking gates on every PR; expensive checks run periodically and alert on regression.*

---

## 2. How we will work

- **One item at a time.** We pick the next item from the phase tables below, decide *then* whether it's a CR, a Feature, or a direct change, do it, mark it done here.
- **This document is the tracker.** Each item has: why, how/approach, likely delivery vehicle, status, and a link to its CR/Feature once it exists. Update the status column as we go. Don't let it drift.
- **Phases are an ordering hint, not a hard sequence.** Phase 0 (rules) should land first because later gates enforce those rules. Phase 1 gates can land incrementally and in parallel. Phase 2/3/4 items can interleave once Phase 0–1 are in place.
- **Skill/template sync.** Per project memory: any change to `skills/iw-ai-core-testing/` (when it exists) must be propagated to the IW-AI-DEV and InnoForge repos; any change under `templates/design/` or `ai-dev/templates/` must be copied to every project in `projects.toml`.
- **Status legend**: `TODO` · `IN PROGRESS` · `DONE` · `DEFERRED` · `DROPPED`.

---

## 3. The major phases at a glance

| Phase | Theme | One-line goal | Major gain |
|-------|-------|---------------|------------|
| **0 — Constitution** | Write the rules down | A testing-strategy doc + an agent testing skill + `tests/CLAUDE.md` updates that define what "good" means here | Every later gate has something to enforce; `tests-impl`/`backend-impl` immediately produce better tests; reviewers get a checklist. Highest leverage per unit of effort. |
| **1 — Stop the bleeding** | Cheap blocking gates | Assertion scanner, branch-coverage floor, diff-coverage, pytest-smell lints, secrets scan, dead-code/dep hygiene, Allure, randomized order, CI plumbing | The suite can no longer silently rot; new code can't ship uncovered; secrets can't leak; the most common AI test smells are blocked at CI — all at near-zero ongoing cost. |
| **2 — Prove the suite works** | Test-effectiveness validation | Mutation testing (changed-files PR gate + nightly full audit), property-based tests on the state machines, flaky/quarantine workflow | A real, trackable answer to "do our 413 tests actually catch regressions?"; the highest-risk logic (daemon / batch / work-item lifecycles, fix-cycle cap) gets fuzzed; flakiness gets a process instead of being ignored. |
| **3 — Test what we don't test at all** | Missing layers/modules | Structured dashboard E2E layer, contract route sweep + schemathesis, CLI-contract layer, cross-project isolation matrix, security test module, data-layer module (migrations/FTS/per-worktree DB), curated smoke w/ SLA | Each module closes a class of incident we've actually had or could have: cross-project leaks, route 5xx, broken `iw` exit codes, migration skew (I-00075/76), doc-render SSRF, etc. |
| **4 — Round it out & insure** | Higher-effort / specialised | Visual regression for HTML/PDF docs, performance budgets, daemon chaos/fault-injection, LLM-as-judge test review (experimental), DB-column doc gate, self-dashboarding of test health, regression-rate tracking | Long-tail risk reduction (layout breakage, perf regressions, daemon crashes) + the platform that runs other projects' tests starts reporting and dogfooding its own test health. |

---

## 4. Phase 0 — Constitution: write the rules down

**Why now**: Phases 1–4 are mostly *enforcement*. Enforcing rules nobody wrote down is arbitrary and won't stop agents repeating the same smells. This phase is doc + skill work, low effort, and pays back immediately on every subsequent agent run and review.

**Major gains**: a single source of truth for "what a good test looks like here"; immediately better `tests-impl`/`backend-impl` output; a reviewer checklist; a place the later gates point to ("this gate enforces rule X from the testing strategy").

| # | Item | Why | How / approach | Likely vehicle | Status | Link |
|---|------|-----|----------------|----------------|--------|------|
| 0.1 | `docs/IW_AI_Core_Testing_Strategy.md` | We have no written test strategy; InnoForge does and it's clearly worth it | Adapt InnoForge's `docs/testing-strategy.md`: philosophy (AI writes the tests), current layers (unit / integration / dashboard-TestClient / browser-playwright-cli) + accurate inventory + `make` targets, infrastructure (live-DB guard, testcontainers, fixtures, markers), conventions, current quality-gate table, known gaps, roadmap pointer. Link from `CLAUDE.md` (Quick Nav + Docs Reference) and `tests/CLAUDE.md`. | Direct (doc) | **DONE 2026-05-11** | `docs/IW_AI_Core_Testing_Strategy.md` |
| 0.2 | `skills/iw-ai-core-testing/SKILL.md` | The agent-facing rules; biggest lever on what gets generated | Adapt InnoForge's `innoforge-testing` skill: headline "the mutation-test question — would this test fail if the code regressed?"; anti-patterns (no `is not None`-only / mock-only / `pytest.raises(Exception)`-without-`match`); patterns (assert specific values, every dict field, error messages); IW-AI-Core infra rules (live-DB guard, the `dashboard.routers.*` collection-time gotcha, testcontainer fixtures, no `importlib.reload(orch.config)`, per-worktree-DB-vs-testcontainers); cross-project isolation; state-machine/property guidance; TDD + RED evidence; the red-flag checklist. `tests/CLAUDE.md` declares it MUST-read for agents writing/reviewing tests. **Still to do: sync to IW-AI-DEV + InnoForge repos** (per memory `feedback_skills_sync`). | Direct (skill) + sync | **DONE 2026-05-11** (sync to sibling repos still pending) | `skills/iw-ai-core-testing/SKILL.md` |
| 0.3 | `tests/CLAUDE.md` updates | The existing test doc should point at 0.1/0.2 and state the non-negotiables | Added: "Required reading" section (skill MUST-read, strategy doc, this plan); "TDD & test quality" section (RED-GREEN-REFACTOR + RED output recorded; "coverage is a floor, not the gate"; "every test must be able to fail"). The `pytest-randomly` reproduce recipe is deferred until item 1.4 lands. | Direct (doc) | **DONE 2026-05-11** | `tests/CLAUDE.md` |
| 0.4 | TDD-evidence requirement in `backend-impl` workflow | Agents do TDD well *if* required to; we should require and *verify* it | `backend-impl` (both mirrors) must run the new failing test, confirm it fails for the expected reason (assertion/`NotImplementedError`, not import/collection error), and record a `tdd_red_evidence` field in the result-contract JSON; the Implementation/SelfAssess/CodeReview prompt templates (+ `templates/design/` masters) get matching language; a guard test pins the contract strings; `iw sync-agents` afterward; cross-repo `iw sync-templates` is a post-merge operator step. | CR | **DONE 2026-05-11 (CR-00045)** | CR-00045 |

---

## 5. Phase 1 — Stop the bleeding: cheap blocking gates

**Why now**: these stop *new* test-quality regressions from landing, at near-zero ongoing cost, and most are direct ports from InnoForge.

**Major gains**: coverage can't silently rot; new code can't ship uncovered; secrets can't leak; the most common AI test smells (no-assert, tautology, mock-only) are blocked at CI; order-dependent pollution surfaces immediately; dead code and dep drift get flagged; we get an Allure report we already paid for.

### Phase 1 — proposed CR grouping & sequencing

Two things changed the picture: (a) recon (Phase 0) showed several "1.x" items are partly done already; (b) iw-ai-core has **two CI surfaces**, not one — see §9. So Phase 1 is best delivered as ~5 small CRs, done one at a time. Recommended order:

| CR | Bundles | What it does (high level) | Notes / open Qs |
|----|---------|---------------------------|-----------------|
| **P1-CR-A — Assertion scanner** *(start here)* | 1.1 | Port InnoForge's `scripts/check_test_assertions.py` (+ extend: tautology, mock-only, `pytest.raises` without `match`); `make test-assertions`; baseline file (`tests/assertion_free_baseline.txt`-style) so it blocks *new* violations while tracking existing; wire into both CI surfaces (a `qv-gate` in the workflow canon + a step in `.github/workflows/test-quality.yml`). | Decide where the daemon gate lives — fold into `make quality` (currently `lint format typecheck`), make it part of `lint`, or a new `assertions` qv-gate. Leaning a new `qv-gate` so failures are attributed cleanly. |
| **P1-CR-B — Coverage gates** | 1.2 + 1.3 + the 1.10 audit | Raise `fail_under` (from 46) to just below measured branch coverage and ratchet; add `diff-cover` dev dep + `make diff-cover` (`diff-cover coverage.xml --compare-branch=origin/main --fail-under=N`) as a `qv-gate` *and* a step in `test-quality.yml`'s `unit` job (which already uploads `coverage.xml`); audit the cov config for the known gotchas (`relative_files`, `pytest -n auto --cov` not `coverage run -m pytest`, `include-hidden-files` on the `.coverage` artefact). | Needs a one-off "measure current branch coverage" run first. Pick the starting `fail_under` and the diff-cover `--fail-under` (≈90). |
| **P1-CR-C — Test hygiene** | 1.4 + 1.5 + 1.7 | Add `pytest-randomly` (default) + budget a cleanup pass for whatever inter-test pollution it surfaces + document the reproduce recipe in `tests/CLAUDE.md`; make `--strict-markers` the default in `addopts`; add `vulture` + `deptry` dev deps + `make` targets, warn-first then gate after a burn-in. | `pytest-randomly` may surface a non-trivial cleanup (session-scoped fixtures + the live-DB guard). If it's big, split it out of this CR. |
| **P1-CR-D — Security gates** | 1.6 + 1.9 | Add `gitleaks` — a pre-commit hook (extend `.pre-commit-config.yaml`) **and** a job (extend `security-scan.yml` and/or a `qv-gate`); add **Semgrep** alongside `bandit` (today `make security-sast` is just a `bandit` alias) — extend `security-scan.yml` and the `security-sast` target. | Align `gitleaks` config with what the `iw-oss-publish` skill already uses. |
| **P1-CR-E — Allure + smoke SLA** | 1.8 + 1.11 | Fill in real recipes for the empty `allure-*` `.PHONY` stubs in the Makefile (model on InnoForge/Podforger); curate the `smoke` marker set to ≤15 tests / <60 s on the critical paths, document the SLA in `tests/CLAUDE.md` + the strategy doc, and keep `make smoke` running first in the daemon QV order and the `smoke` GH job. | Could split into two if the smoke curation grows. |

Sequencing rationale: A first (highest leverage, smallest, blocks the most common AI smell, pure port). B next (coverage is the other half of the cheap-gate story and the floor is dangerously low at 46). C/D/E in any order after — D is independent; C might need a cleanup detour; E is the lightest. Items can interleave with Phase 2 once A+B land.

| # | Item | Why | How / approach | Likely vehicle | Status | Link |
|---|------|-----|----------------|----------------|--------|------|
| 1.1 | AST assertion scanner (`scripts/check_test_assertions.py` + `make test-assertions`) | Cheapest high-yield AI-test-smell gate; catches no-assert/tautology/mock-only | Port InnoForge's script, extend heuristics: no `assert` at all; `assert True`/`assert x == x`; only-assertion-is-`mock.assert_called*`; `pytest.raises` with no type/message constraint. Wire into `make quality` and CI as a hard gate. | CR | **DONE 2026-05-11 (CR-00046)** | CR-00046 |
| 1.2 | Raise & ratchet the coverage floor | Branch coverage is already on (`[tool.coverage.run] branch = true`) and a floor already exists — but it's `fail_under = 46`, far below actual. Coverage can rot down to 46% silently. | Measure current branch coverage; set `fail_under` (and/or add `--cov-fail-under`) just below it; ratchet up, never down. Document the floor in the strategy doc §5. *(Note: `branch = true` and a `fail_under` gate already exist — this item is the ratchet, not the initial setup.)* | Direct (config) or small CR | TODO | |
| 1.3 | `diff-cover` PR gate | Best coverage gate for an AI workflow — forces new/changed lines to be covered without holding the repo hostage to legacy gaps | Add `diff-cover coverage.xml --compare-branch=origin/main --fail-under=90` as a CI step; consider `diff-quality` for changed-line lint too. | CR (CI) | TODO | |
| 1.4 | `pytest-randomly` as default | Surfaces inter-test pollution (which our session-scoped fixtures + live-DB guard invite) immediately instead of "sometimes in CI" | Add the plugin; expect it to find latent issues — budget a small cleanup pass; document `--randomly-seed=<n>` reproduce recipe in `tests/CLAUDE.md`. | CR (will include test fixes) | TODO | |
| 1.5 | `--strict-markers` default (PT rules already on) | Typo'd markers should fail fast | `ruff`'s `PT` rule set is **already enabled** in `pyproject.toml` `[tool.ruff.lint]` — the test-smell-lint half is done. Remaining: make `--strict-markers` the default in `addopts` (currently only `make smoke` passes it). `flake8-pytest-style` is largely redundant with ruff PT — skip unless a gap appears. | Direct (config) | TODO (mostly done) | |
| 1.6 | `gitleaks` secrets scan | `.env`-everywhere config makes an accidental commit a real risk; `iw-oss-publish` already does a one-off scan — make it always-on | Add `gitleaks` as a pre-commit hook *and* a CI job; align config with what `iw-oss-publish` uses. | CR | TODO | |
| 1.7 | `vulture` (dead code) + `deptry` (dep hygiene) in `make quality` | Cheap suite/codebase hygiene; often flags drifted test code | Add both as `make quality` steps — warnings first, gate after a burn-in period. | CR | TODO | |
| 1.8 | Allure reporting `make` targets | `allure-pytest` is already a dependency, and `allure-unit/integration/all/report/serve/clean` appear in the Makefile `.PHONY` line — **but have no recipes** (stale stubs). Pure quick win. | Add real recipes for the existing target names (model on InnoForge/Podforger). | Direct (Makefile) | TODO | |
| 1.9 | Semgrep SAST alongside `bandit` | Complementary SAST coverage (bandit = deep Python-specific; Semgrep = broader + custom rules) | Add a `security-sast` Semgrep step next to existing `bandit`; nightly first, gate after. | CR | TODO | |
| 1.10 | GitHub-native coverage CI plumbing | Avoid the known xdist/pytest-cov pitfalls; PR coverage comments without external services | Adopt `relative_files = true`, `pytest -n auto --cov` (not `coverage run -m pytest -n auto`), `include-hidden-files: true` on the `.coverage` artifact, fork-PR two-workflow split (per Daniel Nouri's 2025 writeup). | CR (CI) | TODO | |
| 1.11 | Curated smoke layer with an SLA | We have a `smoke` marker + `make smoke` but no defined contract | Define: ≤15 tests, <60 s total, critical paths only (daemon starts a worktree, dashboard serves main pages, `iw next-id` works, a work item can be queued, `/healthz` sane). Run first in CI as fail-fast. Document the SLA in `tests/CLAUDE.md`. | CR (or direct curation) | TODO | |

---

## 6. Phase 2 — Prove the suite works: effectiveness validation

**Why now**: Phase 0–1 catch *structural* test smells but not *weak oracles*. Mutation testing is the only direct measure; property tests find the edge cases LLMs miss on our highest-risk logic; flakiness needs a process, not denial.

**Major gains**: a trackable mutation score per module; confidence the 413 tests catch regressions; the daemon / batch / work-item lifecycles and fix-cycle cap get fuzzed by Hypothesis; flaky tests get quarantined and tracked instead of silently rerun.

| # | Item | Why | How / approach | Likely vehicle | Status | Link |
|---|------|-----|----------------|----------------|--------|------|
| 2.1 | Mutation testing — `mutmut` config + `make mutation-*` targets | Only direct measure of assertion strength; InnoForge already standardised on mutmut | Port `mutation-check` / `mutation-audit` / `mutation-results` / `mutation-show`; config with `mutate_only_covered_lines = true`, `max_stack_depth`. **Spike first**: run once over `orch/daemon/` to measure cost. PR gate = mutation score on **changed files only** (cache-warmed from `main`), start **non-blocking**. Nightly/weekly full `mutation-audit` over `orch/`, tracked over time. | CR (then a follow-up CR to make it blocking) | TODO | |
| 2.2 | Property-based tests (Hypothesis) on the state machines | State machines + parsers are the textbook PBT target; LLM tests under-explore edge cases here | Add `tests/unit/properties/` with `ci`/`dev`/`deep` profiles (few examples on PRs, exhaustive nightly). Targets: work-item lifecycle (`RuleBasedStateMachine` + invariants: never terminal with open fix cycle, never exceed cap, merged never re-queued); batch lifecycle (status = pure function of items'; held launches nothing); doc-diff round-trips; RAG chunking partitions; `iw next-id` atomicity (needs testcontainer). | Feature (sizable; multiple modules) | TODO | |
| 2.3 | Flaky / quarantine workflow | Flakiness in a session-scoped-fixture world is inevitable; needs a process | Add a `quarantine` (or `flaky`) marker; `pytest -m "not quarantine"` is the merge gate; quarantined tests run informationally so we see when they recover; quarantining a test files an incident. Use `pytest-rerunfailures` only as a *detector* in a nightly job, never as an auto-fix. | CR | TODO | |
| 2.4 | (Optional) `pytest-testmon` affected-test selection on draft PRs | Speeds up draft-PR feedback once the suite is big enough that full runs hurt | Add `pytest-testmon` (or a path→test map) for draft PRs; full suite on "ready for review". Not urgent at 413 files — revisit when CI time becomes painful. | TBD | DEFERRED | |

---

## 7. Phase 3 — Test what we don't test at all: missing layers/modules

**Why now**: there are whole categories of bug nothing exercises today. Each module here closes a class of incident.

**Major gains**: cross-project isolation guaranteed; no route can 5xx unnoticed; every `iw` command's contract (exit code / stdout / DB effect) is pinned; migration skew (the I-00075/76 class) is caught early; doc-render SSRF/path-traversal is tested; the live-DB-guard outage class (I-00041) has a regression net; a real, isolated browser E2E layer instead of ad-hoc `-m browser` tests.

| # | Item | Why | How / approach | Likely vehicle | Status | Link |
|---|------|-----|----------------|----------------|--------|------|
| 3.1 | Structured dashboard E2E layer | Current `-m browser` tests run against whatever's in the local DB — not a layer | New `tests/e2e/` (or `ai-dev`-style) **journey scripts via `playwright-cli`** (per `CLAUDE.md` — never `agent-browser`, never raw `chromium.launch()`, never `npx playwright install`): auth/session isolation, Queue→Batch→run→merge happy path, Code Q&A SSE stream renders+cites, Docs HTML/PDF export round-trip, Jobs filters, htmx fragments don't 5xx. Run against seeded data (`scripts/e2e_seed.py` fixtures or a dedicated E2E compose stack), never the live DB. A11y + no-console-error assertions per journey. `make test-e2e`. Adapt InnoForge's `e2e-test` skill / our `qv-browser` agent for the journey-script pattern. | Feature (largest item) | TODO | |
| 3.2 | Contract / no-5xx route sweep + `schemathesis` | Catches "a router import broke" before a human does; fuzzes JSON endpoints | Enumerate FastAPI `app.routes`; request each GET (+ representative POST/htmx fragment) against a seeded `TestClient`; assert status ∈ {2xx,3xx,expected-4xx}, never 5xx — for every project page + global `/docs`, `/healthz`, jobs, worktrees. Add `schemathesis` against the generated OpenAPI for the JSON endpoints (jobs API, runtime-overrides API, keep-alive). | CR | TODO | |
| 3.3 | `iw` CLI-contract layer | The CLI is the agent↔DB bridge; its contract is load-bearing and only piecemeal-tested | One test per command: exit code on success / each documented error; stdout shape; DB row(s) created/mutated; idempotence/atomicity where promised. Plus a spec-conformance check: parse `docs/IW_AI_Core_CLI_Spec.md`'s command table, assert every listed command has a test. Prioritise `step-done`, `register`, `doc-update`, `approve`, `next-id`, evidence-ingestion hooks. | CR | TODO | |
| 3.4 | Cross-project isolation matrix | Multi-project is our tenancy axis; InnoForge has the analogous cross-tenant matrix | Two registered projects, each with items/batches/docs/code-index/jobs. Matrix asserts: every project-scoped dashboard route for B never shows A's data (items, batches, docs, jobs, worktrees, RAG answers); `iw` project-scoped commands never touch the other project's rows; global `/docs` & `/jobs` *do* aggregate; per-worktree DB (`IW_CORE_DB_*`) ↔ orch DB (`IW_CORE_ORCH_DB_*`) stay separated (F-00062 rules). | CR | TODO | |
| 3.5 | Security test module | We have scan *targets* but no organised, asserted security *tests*; no secrets scanner in the suite | Named module: live-DB write-guard regression net (the I-00041 class); authz/negative-path tests (extend `test_chat_security` family); doc-render SSRF/path-traversal (assert the doc system can't read arbitrary local files or hit internal URLs); agent-context env-var handling. (Tool-side `gitleaks`/Semgrep land in Phase 1.) | CR | TODO | |
| 3.6 | Data-layer module — migrations / FTS / per-worktree DB | Hard-won lessons (I-00075/76) are rules in `CLAUDE.md` but not all asserted | Migration round-trip **already exists** (`tests/integration/test_migrations_round_trip.py`, `make migration-check`) — extend it / formalise the module: FTS-trigger invariant (insert/update updates the tsvector); per-worktree-DB-revision-skew detection (simulate "worktree DB at rev X, repo lacks rev X", assert detected early); fold in DB-identity (`orch/db/identity.py`) checks. | CR | TODO (partly done) | |

---

## 8. Phase 4 — Round it out & insure

**Why now**: lower frequency / higher cost, but each insures against a specific failure mode, and the last few close the meta-loop (the platform reports its own test health).

**Major gains**: rendered-doc layout regressions caught; perf regressions alerted; the daemon (our riskiest component — it merges to `main`) tested for recovery; an experimental second pair of eyes on AI-written tests; the schema doc kept honest; test health visible on the dashboard; reverts/incidents traced back to the merge that caused them.

| # | Item | Why | How / approach | Likely vehicle | Status | Link |
|---|------|-----|----------------|----------------|--------|------|
| 4.1 | Visual regression for rendered HTML/PDF docs | A CSS/template change can silently wreck layout; nothing tests it | PDF: `pdftoppm` → PNG per page → pixel-diff (Pillow/`pixelmatch`) vs committed baselines, small tolerance (InnoForge's approach). HTML: Playwright `toHaveScreenshot()` with `maxDiffPixels`/`maxDiffPixelRatio`, or `pytest-playwright-visual-snapshot`. Small representative set (one per editorial category). `make visual-regression`; baseline updates are reviewable diffs, never auto-accepted. Nightly + on doc-system changes. | CR | TODO | |
| 4.2 | Performance budgets | Catch perf regressions before users do | Lightweight `pytest-benchmark`-style assertions with generous budgets: daemon poll-loop iteration < N ms, RAG query < N s, key dashboard routes < N ms. Nightly; alert on regression vs baseline, not absolute numbers. Heavy load testing (Locust) out of scope unless a bottleneck warrants it. | CR | TODO | |
| 4.3 | Daemon chaos / fault-injection | The daemon is the riskiest component — it merges to `main` | Deterministic fault-injection integration tests: worktree-setup failure mid-way, fix-cycle exhausts the cap, agent stalls past `IW_CORE_STALL_THRESHOLD`, squash-merge conflict, `migration_rebase.py` failure. Assert the daemon recovers (marks the item, doesn't poison the batch, doesn't leave a half-merged `main`). "Chaos in the small" — not random kill -9. | CR | TODO | |
| 4.4 | LLM-as-judge test review (experimental) | Automated first-pass on assertion strength / behaviour-vs-mock / edge coverage | A *stronger* model than the one that wrote the test scores new tests against a rubric in the review step; advisory only (gate only on a low score). **Validate the judge against a labelled set first** — research is explicit that no judge is uniformly reliable. Try small; don't over-invest until proven. | CR (small spike first) | TODO | |
| 4.5 | DB-column documentation gate | Keeps `docs/IW_AI_Core_Database_Schema.md` honest (InnoForge has the analogue) | CI check: every SQLAlchemy model column has a description; fail on undocumented columns. | CR | TODO | |
| 4.6 | Self-dashboarding of test health | The platform runs other projects' tests — it should report its own | Surface mutation score + coverage trend + flaky count in the dashboard's existing Tests/Quality view (it already has a `coverage_service`). Feed into the Jobs/Quality view. | CR | TODO | |
| 4.7 | Regression-rate tracking | METR-style insight: throughput without a regression metric is misleading | Correlate filed incidents back to the merge that introduced them; report as a quality KPI alongside throughput. | Feature (data + UI) | TODO | |
| 4.8 | Tighten mutation gate to blocking | Once we trust the changed-files mutation score, make it block | Flip the Phase-2 non-blocking PR gate to blocking; expand audit cadence. | Direct (config) | TODO (after 2.1 burn-in) | |

---

## 9. CI gate matrix (target end-state)

**Two CI surfaces** — every Phase-1+ gate should be considered for both:

1. **Daemon QV gates** — run per work item, in the worktree, before squash-merge. Defined in each item's `workflow-manifest.json`; the canonical set lives in `skills/iw-workflow/SKILL.md` (today: `lint` → `make lint`, `format` → `make format-check`, `typecheck` → `make type-check`, `unit-tests` → `make test-unit`, `integration-tests` → `make allure-integration` [note: that target is a no-op stub right now — see 1.8]). Adding a gate here means adding it to the skill's canon **and** to the design templates so new items pick it up.
2. **GitHub Actions** — run on PR/push to `main` (and some on a weekly cron). Already present: `test-quality.yml` (jobs: `lint-typecheck`, `unit` [uploads `coverage.xml`], `integration` [real postgres service], `smoke`), `security-scan.yml` (pip-audit + bandit + trivy), `codeql.yml`, `scorecard.yml`, `compliance-scan.yml`, `schema-validation.yml`. Plus `.pre-commit-config.yaml` hooks (trailing-whitespace, end-of-file, ruff, mypy, …) — the place for `gitleaks`.

A gate isn't "done" until it's wired into whichever of these surfaces makes sense (most cheap gates: both — `qv-gate` for the merge gate, GH workflow step for the PR view).

- **Blocking on every PR**: assertion scanner · `--cov-fail-under` floor · `diff-cover --fail-under` · `ruff PT` + `--strict-markers` · `gitleaks` · smoke (fail-fast, first) · unit + integration + dashboard tests · contract route sweep · CLI-contract · cross-project isolation · security module · data-layer module · Hypothesis `ci` profile · `vulture`/`deptry` (after burn-in) · mutation score on changed files (after non-blocking burn-in) · daemon chaos subset.
- **Periodic (nightly/weekly, informational → alert on regression)**: full `mutation-audit` · Hypothesis `deep` profile · `schemathesis` full run · full E2E matrix · visual regression · perf budgets · `pytest-rerunfailures` flaky sweep · `security-all` + Semgrep + Trivy + image scan · LLM-as-judge experiment.
- **One-time / on-change**: testing-strategy doc · testing skill · `tests/CLAUDE.md` updates · Allure targets · CI plumbing.

---

## 10. Open questions / decisions to make as we go

- ~~Phase 0 first, or Phase-1 quick wins in parallel?~~ **Resolved** — Phase 0 first; 0.1/0.2/0.3 done, 0.4 = CR-00045 in flight.
- **Where does the assertion-scanner daemon gate live?** Fold into `make quality` (currently `lint format typecheck`), make it part of `lint`, or a dedicated `assertions` qv-gate? Leaning a dedicated gate (clean attribution). Decide in P1-CR-A.
- **Coverage floor starting value** — needs a one-off "measure current branch coverage" run; set `fail_under` just below it, ratchet. And the `diff-cover --fail-under` value (≈90?). Decide in P1-CR-B.
- **`pytest-randomly` cleanup size** — unknown until we turn it on; if it surfaces a large inter-test-pollution backlog, split the cleanup out of P1-CR-C into its own item.
- **Mutation testing cost** — unknown until the 2.1 spike. If a changed-files run is too slow even cache-warmed, fall back to nightly-only for a while.
- **E2E runner** — `playwright-cli` only (per `CLAUDE.md`). InnoForge's raw `@playwright/test` TypeScript package can't be ported verbatim; the *structure* (named projects, saved auth state, journey scripts, Allure output) ports, the *runner* must be `playwright-cli`. Decide whether journeys live as bash scripts (like the existing browser checks) or a thin Python harness.
- **What's a CR vs a direct change** — decided per item at pickup time; the "Likely vehicle" column is a hint, not a commitment.

---

## 11. Changelog

- **2026-05-11** — v1 draft created from research R-00068; phases 0–4 outlined.
- **2026-05-11** — Phase 0 started. **Items 0.1 / 0.2 / 0.3 done** (committed `db8f7b2`): `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md` (synced to `.claude/skills/` via `iw sync-skills`), `tests/CLAUDE.md` updates; `CLAUDE.md` Quick-Nav + Docs-Reference link them. Recon corrected several Phase-1/3 assumptions: branch coverage (`branch = true`) and a `fail_under` gate already exist (floor is low at 46 — item 1.2 becomes ratchet-only); `ruff` `PT` rules already enabled (item 1.5 reduces to `--strict-markers`); Allure `make` targets are `.PHONY` stubs with no recipes; `security-sast` is currently just a `bandit` alias (no Semgrep); migration round-trip test + `make migration-check` already exist (item 3.6 partly done); `factory-boy` is a dependency but unused (no `tests/factories.py`). Clarified: the `iw-ai-core-testing` skill is **project-specific** (the iw-ai-core analog of InnoForge's `innoforge-testing`) — it lives only in iw-ai-core, not propagated to the other managed projects (only shared `iw-*` workflow skills are).
- **2026-05-11** — **Item 0.4 → CR-00045 merged (CR-00045).** Full implementation: `backend-impl` agent definitions (both `agents/claude/` and `agents/opencode/`) now mandate running the new failing test with targeted run + confirm-reason + capture; `tdd_red_evidence` field added to Subagent Result Contract with the two documented forms; Implementation template gains the run-and-confirm-reason wording in TDD section and `tdd_red_evidence` in contract JSON; SelfAssess template gains TDD RED evidence checklist item (scoped to behaviour-implementing steps, tests-impl exempt); CodeReview template gains section 5a TDD RED Evidence review check (mandatory reason-check + optional stash-recheck); all three template pairs now byte-identical between `templates/design/` and `ai-dev/templates/`; guard test `tests/unit/test_tdd_red_evidence_contract.py` written RED-first (fails before edits, passes after); `iw sync-agents` ran to regenerate `.claude/agents/backend-impl.md` and `.opencode/agents/backend-impl.md`. Phase 0 complete — Phase 1 begins. `iw sync-templates` to be run by operator post-merge (not from this worktree).
- **2026-05-11** — Planned **Phase 1 as ~5 CRs** (P1-CR-A … P1-CR-E — see §5) and recorded the **two CI surfaces** (daemon QV gates + GitHub Actions workflows incl. `test-quality.yml` / `security-scan.yml` / `.pre-commit-config.yaml` — see §9). Recommended next item: **P1-CR-A, the assertion scanner.**
- **2026-05-11** — **Item 1.1 → CR-00046 shipped (P1-CR-A, AST assertion scanner).** New `scripts/check_test_assertions.py` flags four categories (no-assert / tautology / mock-only / `pytest.raises(Exception)` without `match=`); committed `tests/assertion_free_baseline.txt` (621 entries — predominantly tautology) admits the existing cleanup backlog so the gate fires only on **new** violations; new `make test-assertions` target folded into `make quality` (now `lint format typecheck test-assertions`); new `assertions` daemon QV gate added to `skills/iw-workflow/SKILL.md` right after `lint` (canon now lists 6 gates) and synced to `.claude/skills/iw-workflow/SKILL.md`; new `- run: make test-assertions` step in `.github/workflows/test-quality.yml`'s `lint-typecheck` job; cross-reference in `skills/iw-ai-core-testing/SKILL.md` §1 (and synced `.claude/skills/` copy) noting the bans are now statically enforced; strategy-doc §8 paragraph + §9 row flipped to ✅. RED-first unit tests in `tests/unit/test_assertion_scanner.py` (29 cases). Out-of-scope cleanup of baseline entries deferred to a follow-up. Sibling repos (iw-doc-plan/podforger/cv) will pick up the new `assertions` gate at their next `iw sync-skills` — not done from this worktree.
