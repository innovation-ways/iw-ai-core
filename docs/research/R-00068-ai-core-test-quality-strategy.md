# R-00068 — Enhancing Test Quality & Coverage for IW AI Core in the AI-Agent Development Era

| Field | Value |
|-------|-------|
| ID | R-00068 |
| Date | 2026-05-11 |
| Mode | deep |
| Editorial category | functional |
| Status | draft |

**Primary question** — How should IW AI Core evolve its testing — *effectiveness validation*, *new test layers/modules*, and *AI-agent-specific process* — so that its mostly-LLM-generated test suite genuinely catches regressions, given 2025–2026 best practice and what the sibling repos InnoForge and Podforger already do?

---

## Executive Summary

IW AI Core has a respectable but **unvalidated** test suite: 413 test files (175 unit / 169 integration / 69 dashboard), strong DB-isolation discipline (testcontainers + a hardened live-DB write guard), but **no `--cov-fail-under` gate, no mutation testing, no assertion-quality scanner, no property-based tests, no structured E2E layer, and no testing-strategy document or agent testing skill**. The sibling InnoForge platform has already built most of this (~6,140 tests across 5 layers, 89 % branch coverage, mutmut audits, an AST assertion scanner, Hypothesis property tests, a dedicated `innoforge-testing` skill, visual regression, contract sweeps), and Podforger adds a granular Playwright E2E matrix and Trivy-based security scanning — so much of the work here is **porting and adapting, not inventing**.

The single highest-leverage insight from current research is that **test *count* and *line coverage* are nearly worthless as quality signals when an LLM writes the tests** — AI-generated tests routinely pass while asserting nothing meaningful, asserting on their own mocks, or restating the implementation ([Red Hat Research](https://research.redhat.com/blog/2025/04/21/choosing-llms-to-generate-high-quality-unit-tests-for-code/), [Do LLMs Generate Useful Test Oracles? — ASE 2025](https://www.lucadigrazia.com/papers/ase2025.pdf), [minware — Test Pyramid in AI-Assisted Dev](https://www.minware.com/blog/test-pyramid-ai-assisted-development)). The countermeasures with the best ROI are cheap and well-established: (1) an **AST assertion scanner** that fails CI on no-assert / mock-only tests; (2) **diff-coverage** + a **`--cov-fail-under` branch-coverage floor** so new code can't ship uncovered; (3) **mutation testing scoped to changed files** as a PR gate plus a periodic full audit; (4) **property-based tests on the state machines** (work-item / batch lifecycle, fix-cycle counters); (5) a **dedicated agent testing skill** that bans the known anti-patterns and a **TDD-evidence requirement** ("the test must fail before it passes"); and (6) **`pytest-randomly`** to surface the inter-test pollution that session-scoped fixtures invite. On top of that, IW AI Core should add the *missing test modules* it doesn't have at all: a structured dashboard E2E layer (auth/SSE/htmx, queue→batch→merge happy paths), visual-regression for the rendered HTML/PDF docs, a route + `iw`-CLI contract sweep, a **cross-project isolation matrix**, security testing as a first-class module (SAST + dep CVEs + secrets + the live-DB-guard regression net), curated smoke with an SLA, perf budgets, daemon chaos/fault-injection, migration round-trips, and `vulture`/`deptry` suite-health gates.

The recommendation is a **three-phase adoption roadmap**: Phase 1 = quick wins that are nearly all "port from InnoForge" (assertion scanner, coverage gates, Allure targets, testing skill, smoke SLA, `pytest-randomly`, `vulture`/`deptry`); Phase 2 = the effectiveness engine (mutation testing on changed files, property tests on state machines, structured E2E layer, contract sweep, cross-project isolation matrix, testing-strategy doc); Phase 3 = the higher-effort layers (visual regression, perf budgets, daemon chaos, LLM-as-judge test review, migration-invariant suite). This document is **analysis only** — no work items are created here.

---

## Part 1 — Test Effectiveness & Quality Validation

### 1.1 Why "413 tests, X % coverage" tells us almost nothing right now [HIGH]

Coverage measures *which lines executed*, not *whether a regression in those lines would fail a test*. That gap is the whole problem, and it is dramatically worse when an LLM writes the tests:

- Empirical work on LLM-generated test oracles found that a large fraction of generated assertions are weak or wrong — a 2025 study extracted 13,866 oracles from 135 post-2024 open-source projects across 10 LLMs and found oracle quality varies sharply with model, code difficulty and prompt, with many oracles failing to detect injected faults ([Do LLMs Generate Useful Test Oracles? — ASE 2025](https://www.lucadigrazia.com/papers/ase2025.pdf)).
- LLM-generated tests "often lack semantic diversity" — they cluster around the same happy path and miss edge cases ([Red Hat Research — Choosing LLMs to generate high-quality unit tests](https://research.redhat.com/blog/2025/04/21/choosing-llms-to-generate-high-quality-unit-tests-for-code/)).
- Even LLM-generated *property-based* tests tend to under-explore edge cases relative to what a careful human would write ([Understanding the Characteristics of LLM-Generated Property-Based Tests — arXiv 2510.25297](https://arxiv.org/html/2510.25297v1)).
- "Generative AI in testing just expanded the budget" — AI will happily produce thousands of redundant or vacuous tests if nothing constrains it; the structure (pyramid + gates) is what keeps the suite "efficient, relevant, and scalable" ([minware — Test Pyramid in AI-Assisted Development](https://www.minware.com/blog/test-pyramid-ai-assisted-development), [QAlified — Why the Test Pyramid Still Matters in 2025](https://qalified.com/blog/test-pyramid-for-engineering-teams/)).

Consequence for IW AI Core: the suite needs **effectiveness instrumentation** layered *on top of* the existing tests before the count is trustworthy. InnoForge already did this and treats the layers explicitly in `docs/testing-strategy.md` (repo inspection); IW AI Core has no such document.

### 1.2 Mutation testing — the only direct measure of assertion strength [HIGH]

Mutation testing makes small changes ("mutants") to production code and checks that some test fails ("kills" the mutant). A surviving mutant = code whose behaviour no test pins down. It is the closest thing to a ground-truth quality metric for a test suite.

**Tool choice — `mutmut` is the right default for IW AI Core.** A 2024–2025 academic comparison of Python mutation tools found `mutmut` and `cosmic-ray` are the only actively-maintained options, with `mutmut` the more active; `cosmic-ray` offers more operators (9 vs 6) and a test↔mutant "kill matrix" useful for deep analysis, while `mutmut` is faster (AST-based, no recompilation), hides killed mutants to keep the report focused on live ones, and persists state so runs are resumable/incremental ([An Analysis and Comparison of Mutation Testing Tools for Python — NSF/IEEE](https://par.nsf.gov/servlets/purl/10573281), [mutmut — GitHub](https://github.com/boxed/mutmut), [cosmic-ray docs](https://cosmic-ray.readthedocs.io/en/stable/)). InnoForge already standardised on `mutmut` with Makefile targets `mutation-check` / `mutation-audit` / `mutation-results` / `mutation-show` (repo inspection) — porting that is cheap.

**Making it tractable on a CI budget — scope to changed code, audit the rest periodically.** Full-suite mutation testing on a medium codebase is 30–60 min of CI per run and cannot be a per-PR blocker ([oneuptime — How to Handle Mutation Testing](https://oneuptime.com/blog/post/2026-01-24-mutation-testing/)). The accepted pattern is:
  - **PR gate**: mutate only files changed in the diff (mutmut supports targeting modules via wildcard, e.g. `mutmut run "orch/daemon/core*"`; `mutmut` also persists a cache so the first PR commit can warm from `main`'s cache) ([mutmut — GitHub](https://github.com/boxed/mutmut), [Automating Mutation Testing with Mutmut and GitHub Actions](https://blog.stackademic.com/automating-mutation-testing-with-mutmut-and-github-actions)). The diff-scoped, cache-warmed approach is the same one `cargo-mutants` documents for Rust PRs ("incremental tests of pull requests") and is the consensus model across ecosystems ([cargo-mutants — Incremental tests of pull requests](https://mutants.rs/pr-diff.html)).
  - **Enable `mutate_only_covered_lines = true`** so mutmut skips lines with zero coverage (no point mutating dead-to-tests code) and **`max_stack_depth`** to keep mutants tied to direct unit tests ([mutmut — GitHub](https://github.com/boxed/mutmut)).
  - **Periodic full audit**: a nightly or weekly `mutation-audit` over the whole `orch/` package, tracked over time (InnoForge runs a monthly per-service audit — repo inspection).
  - **Gate**: PR fails if the mutation score on *changed files* drops below a threshold (start non-blocking, then tighten — the standard rollout advice) ([oneuptime — How to Handle Mutation Testing](https://oneuptime.com/blog/post/2026-01-24-mutation-testing/)).

**Where to point it first in IW AI Core**: the daemon state machine (`orch/daemon/`), the work-item/batch state transitions, fix-cycle counting, `orch/cli/` exit-code logic, `orch/evidences.py`, `orch/doc_diff.py` / `orch/doc_sections.py` — the dense-logic modules where a flipped comparison or off-by-one is exactly the kind of bug a vacuous test misses.

### 1.3 Assertion-strength rules + an AST assertion scanner [HIGH]

The cheapest, highest-yield check against AI test-smells is a static scan for tests that *cannot* fail. InnoForge ships `scripts/check_test_assertions.py` (`make test-assertions`) — a fast AST walk that flags test functions with no `assert` (and can be extended to flag `assert True`, `assert mock.called` as the only assertion, etc.) and wires it into `make quality` (repo inspection). Podforger has the same idea via its `quality-engineer` skill (repo inspection).

Port this to IW AI Core and extend it for the patterns research keeps flagging:
- **No assertion at all** (the classic AI test smell).
- **Tautological assertions** — `assert x == x`, `assert result == result`.
- **Mock-only assertions** — the only assertion is `mock.assert_called*` / `assert mock.return_value == ...` (the test is asserting on the test's own setup, not on behaviour) — directly the "tests that assert on mocks" anti-pattern in scope. (Catching this perfectly is hard statically; a heuristic — "test body contains `Mock`/`AsyncMock` *and* the only `assert*` calls are on those names" — catches most of it.)
- **`pytest.raises` with no body / no message check** — `with pytest.raises(Exception): ...` that doesn't constrain the exception type or message.
- **Snapshot/golden-file tests with an empty or trivially-regenerated baseline.**

Complement with a **test-smell linter**: `flake8-pytest-style` / the `ruff` `PT` rule set (`ruff` already runs in `make lint`) catches structural smells (bare `assert` in `pytest.raises`, `pytest.mark` misuse, `assert` on a tuple — which is always truthy, etc.) — these are essentially free once enabled in `pyproject.toml`.

### 1.4 Coverage that actually matters — branch coverage, a floor, and diff-coverage [HIGH]

`coverage.py` line counts are wired into IW AI Core's `pytest` `addopts` today, but there is **no failure condition** — coverage can silently rot. Three additions, in order of value:

1. **Branch coverage + a `--cov-fail-under` floor.** Turn on `[tool.coverage.run] branch = true` and set `--cov-fail-under=<N>` so the suite *fails* below the floor. Pick a floor at or slightly below current measured branch coverage and ratchet it up; never let it drop. InnoForge holds 89 % branch coverage as a gate (repo inspection). This is the gatekeeper pattern current Python-CI guides recommend ([Coverage.py PyTest Plugin: Threshold Enforcement in CI](https://johal.in/coverage-py-pytest-plugin-threshold-enforcement-in-ci-2026/), [pytest-cov — GitHub](https://github.com/pytest-dev/pytest-cov)).
2. **Diff-coverage on PRs** — the single best coverage gate for an AI-agent workflow. `diff-cover coverage.xml --compare-branch=origin/main --fail-under=90` fails the PR if *new or modified* lines aren't ≥90 % covered, without holding the whole repo hostage to legacy gaps ([diff_cover — GitHub](https://github.com/Bachmann1234/diff_cover), [diff-cover — PyPI](https://pypi.org/project/diff-cover/), [Mathieu Lamiot — Diff coverage: a refined approach](https://mathieulamiot.com/diff-coverage-instead-of-code-coverage/)). This directly counters AI agents that touch a file and leave the new branch uncovered. (`diff-cover` also has a `diff-quality` sibling that can run a linter on changed lines only.)
3. **Coverage *contexts*** (`[tool.coverage.run] dynamic_context = "test_function"`) so the HTML report shows *which test* covered each line — invaluable when reviewing whether a line is covered *meaningfully* or just incidentally executed.

Caveat to bake into the testing-strategy doc: **100 % coverage with weak oracles is the failure mode, not the goal** — coverage is a *floor on what's exercised*, mutation score is the *measure of whether exercising it matters*. Modern coverage write-ups make exactly this point ([Daniel Nouri — Modern Python CI with Coverage in 2025](https://danielnouri.org/notes/2025/11/03/modern-python-ci-with-coverage-in-2025/) covers the GitHub-native plumbing — `relative_files = true`, `pytest -n auto --cov` vs `coverage run -m pytest` xdist gotcha, `include-hidden-files: true` for the `.coverage` artifact — which IW AI Core should adopt verbatim for its CI).

### 1.5 Property-based testing on the state machines [HIGH]

IW AI Core is full of state machines and parsers — the textbook targets for Hypothesis. `RuleBasedStateMachine` lets you declare *actions* (`@rule`), *invariants* (`@invariant` — checked after every step), *bundles* (values flowing rule→rule), and *preconditions* (`@precondition` — gate a rule on current state); Hypothesis then generates *sequences* of actions and shrinks any failing sequence to a minimal reproduction ([Hypothesis — Stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html), [hypothesis.works — Rule Based Stateful Testing](https://hypothesis.works/articles/rule-based-stateful-testing/)). InnoForge already runs ~250 Hypothesis property tests under `tests/unit/properties/` with `ci` / `dev` / `deep` profiles (fewer examples on PRs, exhaustive nightly) (repo inspection) — port that profile structure.

Concrete targets in IW AI Core:
- **Work-item lifecycle** — model legal transitions; invariant: never reach a terminal state with an open fix cycle; never exceed the fix-cycle cap (max 5); a merged item is never re-queued.
- **Batch lifecycle** — invariant: a batch's status is a pure function of its items' statuses; held/paused batches launch no new items (parity with the existing `test_batch_held_indicator` / `test_batches_progress_parity` dashboard tests, but as an invariant rather than a fixture).
- **`iw next-id`** — invariant: monotonic, never reuses an ID, atomic under concurrency (this one needs a real testcontainer DB, not pure Hypothesis).
- **Doc versioning / diff** (`orch/doc_diff.py`, `orch/doc_sections.py`) — round-trip and idempotence invariants on section split/merge.
- **RAG chunking** (`orch/rag/`) — invariant: chunk boundaries partition the source; re-chunking is stable.
- **`schemathesis`** for the dashboard's FastAPI surface doubles as property-testing the HTTP layer (see §2.4).

### 1.6 Flaky-test hygiene, test-order randomisation, inter-test pollution [HIGH]

IW AI Core's `tests/CLAUDE.md` already warns about session-scoped fixtures and the live-DB guard leaking state — that is *exactly* the soil flakiness grows in. "A flaky test indicates the test relies on system state that is not being appropriately controlled — the test environment is not sufficiently isolated" ([pytest — Flaky tests](https://docs.pytest.org/en/stable/explanation/flaky.html)). Actions:
- **`pytest-randomly`** — randomises test order every run (and seeds RNGs deterministically with a printed seed for reproduction). Order-dependent pollution surfaces immediately instead of "sometimes in CI". Adopt it as a default plugin ([Trunk — How to avoid and detect flaky tests in Pytest](https://trunk.io/blog/how-to-avoid-and-detect-flaky-tests-in-pytest)). Note: with the current session-scoped testcontainer/app fixtures this *will* find latent issues — that's the point; budget a small cleanup pass.
- **A `flaky` / `quarantine` marker** — when a test is provably flaky, mark it `@pytest.mark.flaky` (or a `quarantine` marker), keep running it in CI as non-blocking (so you can tell when it's actually fixed), and file an incident. The pattern: `pytest -m "not quarantine"` is the merge gate; `pytest -m quarantine` runs informationally ([pytest — Flaky tests](https://docs.pytest.org/en/stable/explanation/flaky.html), [Trunk](https://trunk.io/blog/how-to-avoid-and-detect-flaky-tests-in-pytest)). Avoid `pytest-rerunfailures` auto-retry as a *fix* — it hides flakiness; use it only as a *detector* in a nightly job.
- **`pytest -p no:randomly --randomly-seed=<n>`** documented in `tests/CLAUDE.md` as the way to reproduce a randomised failure.
- **Detecting over-mocking** beyond the assertion scanner: a periodic grep/AST pass for tests where the SUT's collaborators are *all* mocked (a sign the test exercises no real integration) — flag, don't fail, and surface in the testing-strategy doc as a known-debt list.

### 1.7 Test-smell & test-quality linting [MEDIUM]

Beyond `ruff PT` rules: `flake8-pytest-style` is the canonical pytest-smell linter; `pytest --strict-markers` (already used in `make smoke`) should be the default everywhere so a typo'd marker fails fast; and a small custom check for "test file imports a `dashboard.routers.*` module without a `db_session` in scope" would have caught the collection-time `LiveDbConnectionRefusedError` class of failure that `tests/CLAUDE.md` documents — worth adding to the existing `scripts/check_templates.py`-style local-rules family.

---

## Part 2 — New Test Modules / Layers IW AI Core Is Missing

IW AI Core today has unit, integration, dashboard (`TestClient`), and ad-hoc `-m browser` tests. Compared to InnoForge (unit / integration / property / E2E-API / E2E-smoke) and Podforger (a per-domain Playwright E2E matrix + Trivy security), it is missing several whole categories.

### 2.1 A structured E2E / browser layer for the dashboard [HIGH]

Today: a handful of `@pytest.mark.browser` tests run via `playwright-cli` against whatever data happens to be in the local DB (per `pyproject.toml` markers). That's not a layer — it's a few smoke checks with no isolation guarantee. InnoForge has a *separate* Playwright TypeScript package under `tests/e2e/` with named projects (`auth-setup`, `api`, `smoke`), saved `storageState` per role, and `allure-playwright` reporting; Podforger goes further with per-domain targets (`e2e-auth`, `e2e-critical`, `e2e-smoke`, `e2e-accessibility`, `e2e-mobile`, `e2e-visual`, `e2e-security`, `e2e-theme`, `e2e-health`, `e2e-stats`) (repo inspection).

For IW AI Core, given the `CLAUDE.md` rule that browser automation **must** use `playwright-cli` (never `agent-browser`, never `chromium.launch()` directly, never `npx playwright install`), the right shape is:
- A dedicated E2E directory with a small set of **journey scripts** driven through `playwright-cli` (open → snapshot → click → fill → screenshot), each captured into `evidences/`, organised by surface: **auth/session isolation** (cf. `test_F00077_session_isolation`), **Queue → Batch → run → merge happy path**, **Code Q&A SSE stream renders and cites**, **Docs export (HTML/PDF) round-trip**, **Jobs table filters**, **htmx fragment swaps don't 500**.
- Each journey runs against a **known data set** — either the existing `scripts/e2e_seed.py` fixtures (already the regression net `tests/integration/test_e2e_seed.py`) or a dedicated E2E compose stack — never "whatever's in the live DB".
- A11y and "no console errors / no 5xx" assertions baked into each journey (Podforger's `e2e-accessibility` pattern).

Note on the testing-pyramid debate: the consensus in 2025 is *not* "E2E first" — the pyramid (or "trophy", weighting integration heavily) still holds; AI just lets you afford a slightly fatter integration band ([QAlified — Test Pyramid Still Matters in 2025](https://qalified.com/blog/test-pyramid-for-engineering-teams/), [WireMock — Rethinking the Testing Pyramid](https://www.wiremock.io/post/rethinking-the-testing-pyramid), [minware](https://www.minware.com/blog/test-pyramid-ai-assisted-development)). IW AI Core's E2E layer should stay **thin and curated** — happy paths and critical guards only — with the bulk of behaviour pinned by integration tests against the testcontainer DB.

### 2.2 Visual regression for the rendered HTML / PDF doc-generation pipeline [MEDIUM]

IW AI Core renders branded HTML and PDF deliverables (`orch/doc_service.py`, the `iw-doc-system` / `iw-tech-doc-writer` skills). A CSS/template change can silently wreck layout, and nothing tests that today. InnoForge has `make visual-regression` (poppler-utils — rasterise PDF pages and pixel-diff against baselines); Podforger has `e2e-visual` (repo inspection). Options:
- **PDF**: `pdftoppm` (poppler) → PNG per page → pixel-diff (Pillow / `pixelmatch`) against committed baselines with a small tolerance — exactly InnoForge's approach.
- **HTML**: Playwright's built-in `toHaveScreenshot()` / snapshot comparison with `maxDiffPixels` / `maxDiffPixelRatio` tolerances, baselines stored next to the spec; or the `pytest-playwright-visual-snapshot` plugin if staying in pytest ([Playwright — Visual comparisons](https://playwright.dev/docs/test-snapshots), [pytest-playwright-visual-snapshot](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/)). Wire baseline-update into a `make` target and treat baseline churn as a reviewable diff.
- Keep it to a **handful of representative documents** (one of each editorial category) — full visual coverage is expensive and brittle.

### 2.3 Contract / "no server error" route sweep for the dashboard [HIGH]

InnoForge's `make contract-test` does a cheap, high-value thing: hit *every* route on the running dev stack and assert none returns 5xx (and `contract-test-full` does deeper assertions) (repo inspection). For IW AI Core, two complementary forms:
1. **Route-existence sweep** — enumerate the FastAPI `app.routes`, request each GET (and a representative POST/htmx fragment) against a seeded `TestClient` / E2E stack, assert status ∈ {2xx, 3xx, expected 4xx} and never 5xx, for *every* project page and the global `/docs`, `/healthz`, jobs, worktrees routes. This is the regression net that catches "a router import broke" before a human does.
2. **`schemathesis`** against the dashboard's generated OpenAPI — property-based fuzzing of every documented endpoint for 5xx crashes, schema-conformance violations, and validation bypasses, runnable as a CLI step in CI or via the pytest integration ([schemathesis — GitHub](https://github.com/schemathesis/schemathesis), [schemathesis docs](https://schemathesis.readthedocs.io/), [testdriven.io — Hypothesis & Schemathesis with FastAPI](https://testdriven.io/blog/fastapi-hypothesis/)). Caveat: much of the dashboard is HTML/htmx, not JSON APIs, so `schemathesis` mainly helps the JSON endpoints (jobs API, runtime-overrides API, keep-alive routes) — the route-existence sweep is the broader net.

### 2.4 A CLI-contract layer for the `iw` command surface [HIGH]

The `iw` CLI is the agent↔DB bridge — its contract (inputs, stdout/stderr shape, **exit codes**, DB side-effects) is load-bearing for every agent workflow, and `docs/IW_AI_Core_CLI_Spec.md` already specifies it. Today it's covered piecemeal under `tests/integration/cli/`. Make it a *named, exhaustive* layer:
- One test per command asserting: exit code on success / on each documented error; stdout shape (e.g. `iw next-id` prints exactly an ID); the DB row(s) it creates/mutates; idempotence/atomicity where promised.
- A **spec-conformance check**: parse `docs/IW_AI_Core_CLI_Spec.md`'s command table and assert every listed command has a corresponding test (the same "spec ↔ test" gate InnoForge uses for DB-column docs).
- This is also the right home for `iw step-done` / `iw register` / `iw doc-update` / `iw approve` / evidence-ingestion hooks — the commands agents call most.

### 2.5 A cross-PROJECT isolation matrix [HIGH]

InnoForge has a systematic *cross-tenant* isolation matrix (`tests/integration/api/test_cross_tenant_isolation.py`): two tenants, then a matrix asserting GET-by-ID returns 404 across tenants and list endpoints never overlap (repo inspection). IW AI Core's analogue is **multi-project**: does Project A's data leak into Project B's views? Build a matrix that, given two registered projects each with work items / batches / docs / code-index data / jobs:
- Asserts every project-scoped dashboard route for Project B never shows Project A's items, batches, docs, jobs, worktrees, RAG answers.
- Asserts `iw` commands scoped to a project never touch another project's rows.
- Asserts the global `/docs` / `/jobs` views *do* aggregate across projects (the inverse property).
- Asserts the per-worktree DB (`IW_CORE_DB_*`) and the global orch DB (`IW_CORE_ORCH_DB_*`) stay separated (cf. the F-00062 isolation rules in `CLAUDE.md`).

### 2.6 Security testing as a first-class module [HIGH]

IW AI Core already has `security-deps` (pip-audit), `security-iac`, `security-image-dashboard`, `security-sast` Makefile targets and `bandit` in dev deps — but security testing isn't organised as a *test module* with assertions, and there's no secrets scanner. Bring it together (Podforger uses Trivy for deps/secrets/IaC/image; InnoForge runs `bandit` + Semgrep `security-sast` — repo inspection):
- **SAST**: keep `bandit` (deep Python-specific checks) and add **Semgrep** (broader rule set, custom rules) — they're complementary, not redundant ([Semgrep — Bandit vs Semgrep](https://semgrep.dev/blog/2021/python-static-analysis-comparison-bandit-semgrep/)).
- **Dependency CVEs**: keep `pip-audit`; optionally add Trivy for parity with Podforger.
- **Secrets scanning**: add **`gitleaks`** as a pre-commit hook *and* a CI job (and consider `trufflehog` for validation-aware scanning of history) — IW AI Core's `.env`-everywhere config makes an accidental commit a real risk, and `CLAUDE.md` already mandates `.env`/`.iw/` in `.gitignore` ([gatlenculp — Pre-Commit Hooks Guide 2025](https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835), [trufflehog — GitHub](https://github.com/trufflesecurity/trufflehog)). Note this dovetails with the `iw-oss-publish` skill, which already does a secrets/history scan for OSS release — make the CI gate the always-on version of that.
- **Authz / negative-path tests as a module**: the live-DB write-guard regression net (the I-00041 outage class), the `tests/dashboard/test_chat_security.py` family, path-traversal / SSRF in doc rendering (the doc system fetches/renders content — assert it can't read arbitrary local files or hit internal URLs), and "agent context" env-var handling.

### 2.7 Curated smoke tests with an SLA [MEDIUM]

IW AI Core has a `smoke` marker and `make smoke` (browser-based, `--no-cov`), but it's a handful of tests with no defined contract. Promote it to a real layer: **≤15 tests, <60 s total, covering the critical paths** (daemon can start a worktree, dashboard serves the main pages, `iw next-id` works, a work item can be queued, `/healthz` reports a sane DB identity). Document the SLA in `tests/CLAUDE.md` (InnoForge documents its smoke layer; Podforger has `e2e-smoke` / `e2e-critical` / `e2e-health` as the fast tier — repo inspection). Run smoke first in CI as a fail-fast gate before the full suite.

### 2.8 Performance / load smoke [LOW–MEDIUM]

Lightweight, not a load-test rig: a few `pytest-benchmark`-style assertions with generous budgets — daemon poll-loop iteration under N ms, a RAG query under N s, key dashboard routes under N ms (the "dashboard route budgets" in scope). Run nightly, not per-PR; alert on *regression* (slowdown vs baseline), not absolute numbers. Heavier load testing (Locust against the dashboard) is out of scope unless a specific bottleneck warrants it.

### 2.9 Data-layer tests — Alembic round-trips & per-worktree / FTS invariants [MEDIUM]

`tests/CLAUDE.md` already mandates downgrading to a *specific revision* (never `-1`) in migration tests, and `CLAUDE.md` carries the hard-won I-00075/I-00076 lesson about uncommitted migrations. Codify as a module:
- **Migration round-trip**: `upgrade head` → `downgrade <base-ish revision>` → `upgrade head` on a fresh testcontainer; assert the schema matches `Base.metadata` (autogenerate-diff is empty).
- **FTS invariant**: after `create_all()` + `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`, inserting/updating a row updates the tsvector — the rule `tests/CLAUDE.md` already states, but as an assertion.
- **Per-worktree DB invariant**: the per-worktree DB (when `ai-dev/iw-config/` exists) is `pg_dump`-restored and `alembic upgrade head`-ed; a test that simulates "worktree DB at revision X, repo at commit lacking revision X" and asserts the failure mode is detected early (the exact I-00075 scenario).
- **DB identity** (`orch/db/identity.py`): already partly covered (`test_db_identity_integration`); make it part of the named data-layer module.

### 2.10 Daemon chaos / fault-injection [LOW–MEDIUM]

The daemon is the riskiest component (it merges to `main`). Add fault-injection integration tests: worktree creation fails mid-setup, a fix cycle exhausts the cap, an agent stalls past `IW_CORE_STALL_THRESHOLD`, a squash-merge hits a conflict, the migration-rebase step (`orch/daemon/migration_rebase.py`) fails. Assert the daemon recovers (marks the item, doesn't poison the batch, doesn't leave a half-merged `main`). This is "chaos" only in the small — deterministic fault injection, not random kill -9.

### 2.11 Suite-health gates — `vulture` (dead code) & `deptry` (dep hygiene) [LOW]

InnoForge has `make dead-code` (`vulture`) and `make dep-check` (`deptry`) (repo inspection). Cheap to port: `vulture` flags unused functions/vars (often *test* code that's drifted), `deptry` flags declared-but-unused / used-but-undeclared dependencies. Run in `make quality` as warnings first, then gates.

---

## Part 3 — Process, Tooling & AI-Agent-Specific Practices

### 3.1 Stopping AI agents from writing vacuous tests — the layered defence [HIGH]

No single control is sufficient; the research and the sibling repos converge on a *stack*:

1. **A dedicated agent testing skill** (port/adapt InnoForge's `innoforge-testing` SKILL.md → `iw-ai-core-testing`) that the `tests-impl` and `backend-impl` agents **must read before writing tests**, encoding the explicit anti-patterns ("never write `assert True`", "never make a mock-call the only assertion", "every test must be able to fail", "no logic in the Assert block", project-specific isolation rules) plus the positive patterns (AAA, `test_<unit>_<scenario>_<expected>` naming, factory usage, testcontainer rules). InnoForge's skill literally opens with "AI-generated tests frequently pass but catch nothing. Every test assertion must survive mutation testing" (repo inspection) — that framing should headline the IW AI Core skill too.
2. **TDD-evidence requirement** — "use TDD: write the tests first, confirm they fail before implementing" is now standard agentic-engineering guidance; agents do TDD *well* because a failing test is the clear binary goal they thrive on ([Simon Willison — Red/green TDD agentic pattern](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/), [alexop.dev — Forcing Claude Code to TDD](https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/)). Operationalise it: the `backend-impl` agent already follows RED-GREEN-REFACTOR; require it to **record the RED output** (the failing-test run) in its execution report, and have the review step check that the new tests *would* fail against the pre-change code (a `git stash` + run check, or a targeted mutmut run on the new code).
3. **The assertion scanner** (§1.3) as a hard CI gate — catches the smells the skill is supposed to prevent.
4. **Diff-coverage** (§1.4) as a hard CI gate — catches "touched a file, didn't cover the new branch".
5. **Mutation testing on changed files** (§1.2) as a PR gate (non-blocking → blocking) — catches the weak-oracle case the scanner can't.
6. **Coverage-gaming prevention** — because agents can hit a coverage number with empty tests, *coverage alone is never the gate*; the gate is `coverage floor` **AND** `diff-coverage` **AND** `assertion scanner` **AND** (eventually) `mutation score on changed files`. State this explicitly in `tests/CLAUDE.md` so future agents (and humans) don't "optimise" for the wrong metric — the minware/QAlified point that structure is what stops AI flooding the suite ([minware](https://www.minware.com/blog/test-pyramid-ai-assisted-development), [QAlified](https://qalified.com/blog/test-pyramid-for-engineering-teams/)).
7. **Regression rate as a first-class metric** — METR's finding that ~half of SWE-bench-passing agent patches wouldn't be merged by real maintainers, with CI failures a leading cause, argues for tracking *"did this merged change later get reverted / cause an incident"* alongside throughput (referenced via [the agentic-TDD literature](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)). IW AI Core already files incidents; correlating incidents back to the merge that introduced them would close the loop.

### 3.2 Review heuristics for AI-generated tests & LLM-as-judge [MEDIUM]

For the human/agent reviewing a test PR, a short checklist (put it in the testing skill): *Would this test fail if I deleted the corresponding production line? Does it assert on behaviour or on its own mocks? Is the assertion specific (value/shape/message) or vacuous (truthiness/“not None”)? Does it cover the error path, not just the happy path? Is it isolated (no order dependence, no shared `app.state` mutation)?*

**LLM-as-judge** can automate a first pass: a stronger model scores each new test on assertion strength / behaviour-vs-mock / edge coverage against a rubric, gating only on a low score (humans/scanners handle the rest). Caveats from the research: use a *different, stronger* model than the one that wrote the test (same-model self-grading has blind spots); judges are *not uniformly reliable* — validate the judge against a labelled set before trusting it; treat the score as advisory, not a hard gate ([Evidently AI — LLM-as-a-judge guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge), [Confident AI — DeepEval](https://github.com/confident-ai/deepeval), [Judge Reliability Harness — arXiv 2603.05399](https://arxiv.org/html/2603.05399v1)). Worth a small experiment in IW AI Core's review step; not worth building heavily until proven.

### 3.3 Test-data management for agents [MEDIUM]

IW AI Core already has `factory-boy` and `tests/fixtures/`. Recommendations: standardise a **`tests/factories.py`** (InnoForge's `EntityFactory` pattern — one place agents go to create a `Project` / `WorkItem` / `Batch` / `Doc`); add **`Faker`** for realistic-but-not-real strings; keep **golden files** for doc-rendering output but treat baseline updates as reviewable diffs (snapshot tests are a known AI footgun — agents will "fix" a failing snapshot by blessing the wrong output, so baseline changes must be reviewed, never auto-accepted — flagged in the LLM-test research ([Red Hat Research](https://research.redhat.com/blog/2025/04/21/choosing-llms-to-generate-high-quality-unit-tests-for-code/))).

### 3.4 CI orchestration — fast PR runs vs deep nightly runs [HIGH]

The shape every source converges on:
- **PR (fast, blocking)**: `make quality` (ruff + ruff PT + format + mypy + assertion scanner + `vulture`/`deptry` warnings) → `make smoke` (fail-fast) → `make test-unit` → `make test-integration` (testcontainers) → `make test-dashboard` → `diff-cover --fail-under` + `--cov-fail-under` → `gitleaks` → mutation testing on changed files (non-blocking at first) → contract route-sweep. Parallelise with `pytest -n auto` (mind the xdist/pytest-cov gotcha — use `pytest -n auto --cov`, not `coverage run -m pytest -n auto` ([Daniel Nouri — Modern Python CI with Coverage 2025](https://danielnouri.org/notes/2025/11/03/modern-python-ci-with-coverage-in-2025/))). Per-job `pytest-timeout` (already a dep) so a hung test fails instead of stalling CI.
- **Nightly / weekly (deep, informational)**: full `mutation-audit` over `orch/`; Hypothesis `deep` profile (many examples); `schemathesis` full run; perf budgets; `-m browser` / E2E full matrix; `pytest-rerunfailures`-based flaky detection; `security-all` + Semgrep + Trivy + image scan.
- **Affected-test selection** (optional, later) — `pytest-testmon` or a path→test map to run only tests touching changed code on draft PRs; full suite on "ready for review". Useful once the suite is big enough that full runs hurt; not urgent at 413 files.
- **Flaky quarantine** — `-m "not quarantine"` is the gate; quarantined tests run informationally so you see when they recover (§1.6).

### 3.5 A testing-strategy document & a testing skill for IW AI Core [HIGH]

The two structural gaps. **`docs/IW_AI_Core_Testing_Strategy.md`** (model on InnoForge's `docs/testing-strategy.md`): the layer model (unit / integration / property / contract / E2E / smoke / security / perf), the test inventory with counts and `make` targets, the quality-gate matrix (what's blocking on PR vs informational nightly), the mutation-audit cadence, the coverage floors, the known-debt list (over-mocked tests, quarantined tests). **`skills/iw-ai-core-testing/SKILL.md`**: the agent-facing rules (§3.1.1) — and per `MEMORY.md`'s `feedback_skills_sync` and `feedback_templates_sync`, propagate the skill to the IW-AI-DEV and InnoForge repos and keep `templates/design/` in sync. Also update `tests/CLAUDE.md` to (a) link both, (b) state the TDD mandate explicitly (RED output recorded), (c) state the "coverage is a floor, not the gate" rule.

### 3.6 Coverage / quality dashboards [LOW–MEDIUM]

`allure-pytest` is *already a dependency* but has **no Makefile targets** — pure quick win: add `allure-unit` / `allure-integration` / `allure-all` / `allure-serve` / `allure-clean` (InnoForge has them; Podforger has very granular per-domain ones — repo inspection). Surface coverage trend on the dashboard's existing Tests/Quality pages (it already has a `coverage_service` and `test_coverage_page`). Optionally feed the mutation score + coverage + flaky count into the Jobs/Quality view so the *platform that runs other projects' tests* also reports its own health.

---

## Benchmark — IW AI Core vs InnoForge vs Podforger vs best practice

| Capability | IW AI Core (today) | InnoForge | Podforger | Best-practice target |
|---|---|---|---|---|
| Unit / integration layers | ✅ (175 / 169) | ✅ (4,787 / 1,344) | ✅ | ✅ |
| Dashboard `TestClient` tests | ✅ (69) | ✅ (via integration `api/`) | ✅ | ✅ |
| Branch coverage measured | ⚠️ reported, no gate | ✅ 89 % gate | ✅ gate | ✅ floor + ratchet |
| `--cov-fail-under` gate | ❌ | ✅ | ✅ | ✅ |
| Diff / patch coverage on PRs | ❌ | (gate via `quality`) | — | ✅ `diff-cover --fail-under` |
| Mutation testing | ❌ | ✅ `mutmut` (4 `make` targets, monthly audit) | — | ✅ changed-files PR gate + periodic audit |
| Assertion-strength AST scanner | ❌ | ✅ `make test-assertions` | ✅ (`quality-engineer` skill) | ✅ CI gate |
| Property-based tests (Hypothesis) | ❌ | ✅ ~250, ci/dev/deep profiles | — | ✅ on state machines & parsers |
| `pytest-randomly` / order-rand | ❌ | (implied) | — | ✅ default |
| Flaky quarantine workflow | ❌ | ⚠️ partial | ⚠️ | ✅ marker + informational run |
| Structured E2E layer | ⚠️ ad-hoc `-m browser` | ✅ Playwright TS pkg (auth/api/smoke) | ✅ per-domain matrix | ✅ thin curated journeys |
| Visual regression (HTML/PDF) | ❌ | ✅ `make visual-regression` | ✅ `e2e-visual` | ✅ representative docs |
| Contract / no-5xx route sweep | ❌ | ✅ `contract-test` / `-full` | — | ✅ route sweep + `schemathesis` |
| CLI-contract layer | ⚠️ piecemeal | n/a | n/a | ✅ per-command + spec conformance |
| Cross-project / cross-tenant isolation matrix | ❌ | ✅ cross-tenant matrix | ✅ | ✅ cross-project matrix |
| SAST (bandit + semgrep) | ⚠️ `bandit` dep + `security-sast` target | ✅ bandit + Semgrep | ✅ (Trivy) | ✅ both |
| Dependency CVE scan | ✅ `pip-audit` | ✅ | ✅ Trivy | ✅ |
| Secrets scanning | ❌ (only in `iw-oss-publish` skill) | ✅ | ✅ Trivy secrets | ✅ `gitleaks` pre-commit + CI |
| IaC / image scanning | ✅ `security-iac` / `security-image-dashboard` | ✅ | ✅ Trivy | ✅ |
| Curated smoke layer w/ SLA | ⚠️ marker, no SLA | ✅ documented | ✅ `e2e-smoke`/`-critical`/`-health` | ✅ ≤15 tests <60 s |
| Perf budgets | ❌ | ⚠️ | ⚠️ `e2e-stats` | ✅ nightly regression alerts |
| Migration round-trip tests | ⚠️ rules in CLAUDE.md, partial tests | ✅ | ✅ `schema-check` | ✅ named module |
| Daemon chaos / fault-injection | ❌ | n/a (no daemon) | n/a | ✅ deterministic fault injection |
| `vulture` dead-code / `deptry` dep-hygiene | ❌ | ✅ | — | ✅ in `quality` |
| Allure reporting targets | ❌ (dep present, no targets) | ✅ | ✅ granular | ✅ |
| `arch-check` (import-linter) | ✅ | ✅ | — | ✅ |
| Testing-strategy doc | ❌ | ✅ `docs/testing-strategy.md` | ⚠️ | ✅ |
| Agent testing skill | ❌ | ✅ `innoforge-testing` | ✅ `quality-engineer`/`tdd-orchestrator` | ✅ |
| TDD mandate documented + RED evidence | ⚠️ in `backend-impl` agent only | ✅ in `tests/CLAUDE.md` | ✅ | ✅ |
| LLM-as-judge test review | ❌ | ❌ | ❌ | 🔬 experimental |

Legend: ✅ have/target · ⚠️ partial · ❌ absent · 🔬 emerging.

---

## Port inventory — what to take from InnoForge / Podforger

| Artifact (source) | Recommendation | Rationale | Rough effort |
|---|---|---|---|
| `scripts/check_test_assertions.py` + `make test-assertions` (InnoForge) | **Port as-is**, then extend (tautology / mock-only heuristics) | Cheapest high-yield AI-test-smell gate | S |
| `mutation-check` / `mutation-audit` / `mutation-results` / `mutation-show` `make` targets + `mutmut` config (InnoForge) | **Port + adapt** to changed-files PR gate + nightly audit | Only direct measure of assertion strength | M |
| Hypothesis `tests/unit/properties/` layout + ci/dev/deep profiles (InnoForge) | **Adapt** — same structure, IW-AI-Core-specific state-machine rules | State machines are the textbook target | M |
| `innoforge-testing` SKILL.md (InnoForge) | **Adapt** → `skills/iw-ai-core-testing/SKILL.md`; sync to IW-AI-DEV + InnoForge | Directly improves `tests-impl`/`backend-impl` output | S–M |
| `docs/testing-strategy.md` (InnoForge) | **Adapt** → `docs/IW_AI_Core_Testing_Strategy.md` | Missing structural document | S |
| `tests/CLAUDE.md` TDD mandate (InnoForge) | **Port** the RED-GREEN-REFACTOR + RED-evidence wording | Formalises what the agent already half-does | S |
| Allure `make` targets `allure-unit/integration/all/serve/clean` (InnoForge/Podforger) | **Port** — `allure-pytest` already a dep | Pure quick win | S |
| `make visual-regression` (poppler PDF rasterise + pixel-diff) (InnoForge) | **Adapt** to IW AI Core's HTML/PDF doc pipeline; small baseline set | Nothing tests rendered-doc layout today | M |
| `make contract-test` / `contract-test-full` route sweep (InnoForge) | **Adapt** → FastAPI `app.routes` no-5xx sweep + `schemathesis` for JSON endpoints | Catches "router import broke" before humans | M |
| Cross-tenant isolation matrix test (InnoForge) | **Adapt** → cross-**project** isolation matrix | Multi-project is IW AI Core's tenancy axis | M |
| `make dead-code` (`vulture`) / `make dep-check` (`deptry`) (InnoForge) | **Port** into `make quality` (warn → gate) | Cheap suite/codebase hygiene | S |
| `make security-sast` Semgrep step (InnoForge) | **Port** alongside existing `bandit` | Complementary SAST coverage | S |
| Trivy deps/secrets/IaC/image scanning (Podforger) | **Adapt** — keep `pip-audit`; add `gitleaks` for secrets (lighter than Trivy-secrets); Trivy optional | Secrets scanning is the real gap | S–M |
| Playwright E2E package `tests/e2e/` w/ `auth-setup`/`api`/`smoke` projects + `allure-playwright` (InnoForge) | **Adapt** — but driven via `playwright-cli` per `CLAUDE.md`, not raw `@playwright/test` | Replaces ad-hoc `-m browser` with a real layer | M–L |
| Per-domain E2E `make` targets `e2e-accessibility/-mobile/-visual/-security/-health/-stats` (Podforger) | **Cherry-pick** — `e2e-accessibility`, `e2e-health`, `e2e-critical` worth it; `-mobile`/`-theme` less relevant | Match scope to IW AI Core's actual surfaces | M |
| `e2e-test` skill (InnoForge) | **Adapt** → an `iw-ai-core` E2E journey skill (already partially covered by `qv-browser` agent) | Codifies the journey-script pattern | M |
| `us-test` skill (InnoForge — user-story acceptance testing) | **Skip** — IW AI Core uses Features/Incidents/CRs, not user stories | No user-story artifact to test against | — |
| `schema-docs` / `schema-check` (Podforger) / `docs-check` DB-column gate (InnoForge) | **Adapt** — IW AI Core has `docs/IW_AI_Core_Database_Schema.md`; a "every model column documented" gate is reasonable | Keeps schema doc honest | S |
| `test-code` skill — full-CI-pipeline-and-fix (InnoForge) | **Adapt** — IW AI Core's `quality-validation-impl` / `quality-fix-impl` agents already cover this; align prompts | Avoid duplicating existing agents | S |
| `tdd-orchestrator` / `quality-engineer` / `test-automator` skills (Podforger) | **Reference, mostly skip** — IW AI Core's `backend-impl` (TDD) + `tests-impl` + `tests-review` agents already fill these roles | Don't fork agent taxonomy unnecessarily | — |
| `import-linter` `arch-check` | **Already present** in IW AI Core | — | — |

Effort key: S ≈ ≤1 day · M ≈ 1–3 days · L ≈ ≥1 week (rough, single-agent-workflow units).

---

## Recommendations — phased adoption roadmap

> **Analysis only — no work items created.** Each row below is a candidate Feature/CR; sequencing assumes the existing batch-execution model and that Phase-1 items are independent enough to parallelise.

### Phase 1 — Quick wins, mostly "port from InnoForge" (low effort, immediate signal)

| Item | What | Gate type | Effort | Impact |
|---|---|---|---|---|
| P1-1 | AST **assertion scanner** (`scripts/check_test_assertions.py` + `make test-assertions`, extended for tautology/mock-only) → into `make quality` | **CI gate** | S | High |
| P1-2 | **Branch coverage** on + **`--cov-fail-under`** floor at current measured level | **CI gate** | S | High |
| P1-3 | **`diff-cover --fail-under=90`** on PRs (changed-lines coverage) | **CI gate** | S | High |
| P1-4 | **`pytest-randomly`** as a default plugin + reproduce-with-seed doc in `tests/CLAUDE.md` (+ small cleanup of whatever pollution it surfaces) | dev default | S–M | High |
| P1-5 | Enable **`ruff` `PT` rules** + `flake8-pytest-style` + `--strict-markers` everywhere | **CI gate** | S | Med |
| P1-6 | **`gitleaks`** pre-commit hook + CI job (secrets) | **CI gate** | S | High |
| P1-7 | **Allure** `make` targets (dep already present) | reporting | S | Med |
| P1-8 | **`vulture`** + **`deptry`** in `make quality` (warn → gate) | warn→gate | S | Med |
| P1-9 | **Semgrep** SAST step alongside `bandit` | nightly→gate | S | Med |
| P1-10 | **`docs/IW_AI_Core_Testing_Strategy.md`** + **`skills/iw-ai-core-testing/SKILL.md`** + `tests/CLAUDE.md` updates (TDD mandate, RED evidence, "coverage is a floor not the gate") + sync skill to sibling repos | docs/process | S–M | High |
| P1-11 | **Curated smoke layer w/ SLA** (≤15 tests, <60 s) — run first in CI as fail-fast | **CI gate** | S | Med |
| P1-12 | Adopt the **GitHub-native coverage CI plumbing** (`relative_files=true`, `pytest -n auto --cov`, `include-hidden-files`, fork-PR two-workflow split) | CI infra | S | Med |

### Phase 2 — The effectiveness engine + the missing core layers (medium effort, high payoff)

| Item | What | Gate type | Effort | Impact |
|---|---|---|---|---|
| P2-1 | **Mutation testing** (`mutmut` config + `make mutation-*` targets); PR gate = mutation score on **changed files** (start non-blocking) + **nightly full `mutation-audit`** over `orch/` | PR gate + nightly audit | M | High |
| P2-2 | **Property-based tests** (Hypothesis) on the state machines — work-item lifecycle, batch lifecycle, fix-cycle cap, `iw next-id` atomicity, doc-diff round-trips, RAG chunking; ci/dev/deep profiles | **CI gate** (ci profile) + nightly (deep) | M | High |
| P2-3 | **Structured E2E layer** — `tests/e2e/` journey scripts via `playwright-cli` (auth/session, queue→batch→merge, Code Q&A SSE, Docs export, Jobs filters, htmx no-5xx) against seeded data; a11y + no-console-error assertions; `make test-e2e` | nightly + `-m browser` | M–L | High |
| P2-4 | **Contract route sweep** — enumerate `app.routes`, assert no 5xx for every page; `schemathesis` for JSON endpoints | **CI gate** | M | High |
| P2-5 | **CLI-contract layer** — per-`iw`-command exit-code/stdout/DB-effect tests + spec-conformance check against `docs/IW_AI_Core_CLI_Spec.md` | **CI gate** | M | High |
| P2-6 | **Cross-project isolation matrix** — two projects, matrix of "B never sees A" + "global views aggregate" + per-worktree-DB ↔ orch-DB separation | **CI gate** | M | High |
| P2-7 | **Security test module** — live-DB-guard regression net, authz/negative-path tests, doc-render SSRF/path-traversal, agent-context env handling — as a named, asserted module | **CI gate** | M | High |
| P2-8 | **Data-layer module** — migration round-trip, FTS-trigger invariant, per-worktree-DB-revision-skew detection, DB-identity | **CI gate** | M | Med |
| P2-9 | **`flaky`/`quarantine` marker workflow** — `-m "not quarantine"` is the gate; quarantined run informationally; incident filed on quarantine | process | S | Med |
| P2-10 | **`pytest-testmon`** (or path→test map) for affected-test selection on draft PRs | CI infra | S–M | Low–Med |

### Phase 3 — Higher-effort / specialised layers (do after Phase 2 proves out)

| Item | What | Gate type | Effort | Impact |
|---|---|---|---|---|
| P3-1 | **Visual regression** for rendered HTML/PDF docs (poppler rasterise + pixel-diff; Playwright `toHaveScreenshot` for HTML); small representative baseline set; `make visual-regression` | nightly + on doc-system changes | M | Med |
| P3-2 | **Performance budgets** — daemon poll-loop, RAG query latency, dashboard route budgets; nightly; alert on regression vs baseline | nightly (informational) | M | Med |
| P3-3 | **Daemon chaos / fault-injection** — worktree-setup failure, fix-cycle exhaustion, stalled agent, merge conflict, migration-rebase failure; assert recovery | **CI gate** (subset) | M | Med |
| P3-4 | **LLM-as-judge test review** — stronger model scores new tests on a rubric in the review step; advisory only; validate the judge against a labelled set first | experimental | M | Med (if it works) |
| P3-5 | **Mutation gate tightened** — changed-files mutation score becomes *blocking* once the team trusts it; expand audit cadence | PR gate (blocking) | S | Med |
| P3-6 | **DB-column documentation gate** (`docs/IW_AI_Core_Database_Schema.md` ↔ model columns) | **CI gate** | S | Low–Med |
| P3-7 | **Self-dashboarding** — surface own mutation score / coverage trend / flaky count in the platform's Quality/Jobs view | reporting | S–M | Low–Med |
| P3-8 | **Regression-rate tracking** — correlate filed incidents back to the merge that introduced them; report as a quality KPI | metrics/process | M | Med |

### What becomes a CI gate vs a periodic audit (summary)

- **Blocking on every PR**: assertion scanner; `--cov-fail-under` floor; `diff-cover --fail-under`; `ruff PT` + `--strict-markers`; `gitleaks`; smoke (fail-fast); unit + integration + dashboard tests; contract route sweep; CLI-contract; cross-project isolation; security module; data-layer module; Hypothesis `ci` profile; `vulture`/`deptry` (after warn period); mutation score on changed files (after non-blocking period); daemon chaos subset.
- **Periodic (nightly/weekly, informational → alert on regression)**: full `mutation-audit`; Hypothesis `deep` profile; `schemathesis` full run; full E2E matrix; visual regression; perf budgets; `pytest-rerunfailures` flaky sweep; `security-all` + Semgrep + Trivy + image scan; LLM-as-judge experiment.
- **One-time / on-change**: testing-strategy doc; testing skill; `tests/CLAUDE.md` updates; Allure targets; CI plumbing.

---

## Limitations

- **No live-codebase deep dive in this research** — the IW AI Core / InnoForge / Podforger findings come from a structured but bounded inspection of `Makefile`s, `pyproject.toml`s, `tests/` trees, `CLAUDE.md`s and skill manifests, not a file-by-file audit. Test *counts* for the sibling repos are taken from their own docs (InnoForge's `docs/testing-strategy.md` states ~6,140); they were not re-counted here. Specific module paths suggested for IW AI Core (e.g. exact daemon files) should be confirmed against the current tree before scoping work items.
- **Effort estimates are rough** ("single-agent-workflow units") and assume the existing batch-execution model; real effort depends on how much pollution `pytest-randomly` surfaces and how heavy the E2E seed/compose work turns out to be.
- **Some sources are secondary or recent-blog quality** (e.g. johal.in, oneuptime, stackademic posts) and a few cited papers carry future-looking arXiv identifiers (e.g. 2510.25297, 2603.x) — treated as MEDIUM/LOW confidence and used only for direction, not load-bearing claims. The load-bearing claims (mutation testing's purpose, diff-coverage mechanics, Hypothesis stateful API, the LLM-test-quality gap, TDD-for-agents) are each backed by an official doc or a primary-author source.
- **Mutation-testing CI cost** for IW AI Core specifically is unknown until measured — the changed-files-only + cache-warmed approach is the de-risking strategy, but a spike (run `mutmut` once over `orch/daemon/`) should precede committing to a blocking gate.
- **LLM-as-judge for test review is genuinely experimental** — the reliability research is explicit that no judge is uniformly reliable; this is a "try small, validate, don't over-invest" item, not a recommendation to ship.
- **Browser/E2E tooling is constrained** by IW AI Core's hard `CLAUDE.md` rules (`playwright-cli` only; never `npx playwright install`; never modify `.playwright/cli.config.json`) — so InnoForge's raw `@playwright/test` TypeScript package can't be ported verbatim; the *structure* (named projects, saved auth state, journey scripts, Allure output) ports, the *runner* must be `playwright-cli`.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | mutmut — Mutation testing system (GitHub README) | High (primary, tool author) | https://github.com/boxed/mutmut |
| 2 | Cosmic Ray — mutation testing for Python (docs) | High (primary, tool author) | https://cosmic-ray.readthedocs.io/en/stable/ |
| 3 | An Analysis and Comparison of Mutation Testing Tools for Python (NSF/IEEE) | High (peer-reviewed) | https://par.nsf.gov/servlets/purl/10573281 |
| 4 | Hypothesis — Stateful testing (official docs) | High (primary) | https://hypothesis.readthedocs.io/en/latest/stateful.html |
| 5 | hypothesis.works — Rule Based Stateful Testing | High (primary author) | https://hypothesis.works/articles/rule-based-stateful-testing/ |
| 6 | diff_cover — Automatically find diff lines that need test coverage (GitHub) | High (primary) | https://github.com/Bachmann1234/diff_cover |
| 7 | diff-cover (PyPI) | High (primary) | https://pypi.org/project/diff-cover/ |
| 8 | Mathieu Lamiot — Diff coverage: a refined approach to the unpopular code coverage metric | Medium (practitioner) | https://mathieulamiot.com/diff-coverage-instead-of-code-coverage/ |
| 9 | Daniel Nouri — Modern Python CI with Coverage in 2025 | Medium–High (detailed practitioner) | https://danielnouri.org/notes/2025/11/03/modern-python-ci-with-coverage-in-2025/ |
| 10 | pytest-cov (GitHub) | High (primary) | https://github.com/pytest-dev/pytest-cov |
| 11 | Coverage.py PyTest Plugin: Threshold Enforcement in CI (johal.in) | Low–Medium (blog) | https://johal.in/coverage-py-pytest-plugin-threshold-enforcement-in-ci-2026/ |
| 12 | Schemathesis — Catch API bugs before your users do (GitHub) | High (primary) | https://github.com/schemathesis/schemathesis |
| 13 | Schemathesis documentation | High (primary) | https://schemathesis.readthedocs.io/ |
| 14 | testdriven.io — Using Hypothesis and Schemathesis to Test FastAPI | Medium (tutorial) | https://testdriven.io/blog/fastapi-hypothesis/ |
| 15 | Playwright — Visual comparisons (official docs) | High (primary) | https://playwright.dev/docs/test-snapshots |
| 16 | pytest-playwright-visual-snapshot (GitHub) | Medium (community plugin) | https://github.com/iloveitaly/pytest-playwright-visual-snapshot/ |
| 17 | pytest — Flaky tests (official docs) | High (primary) | https://docs.pytest.org/en/stable/explanation/flaky.html |
| 18 | Trunk — How to avoid and detect flaky tests in Pytest | Medium (vendor blog) | https://trunk.io/blog/how-to-avoid-and-detect-flaky-tests-in-pytest |
| 19 | minware — Why the Test Pyramid Matters More Than Ever in AI-Assisted Development | Medium (vendor blog) | https://www.minware.com/blog/test-pyramid-ai-assisted-development |
| 20 | QAlified — Why the Test Pyramid Still Matters in 2025 | Medium (practitioner) | https://qalified.com/blog/test-pyramid-for-engineering-teams/ |
| 21 | WireMock — The testing pyramid is an outdated economic model | Medium (vendor blog) | https://www.wiremock.io/post/rethinking-the-testing-pyramid |
| 22 | Red Hat Research — Choosing LLMs to generate high-quality unit tests for code (2025) | High (research blog) | https://research.redhat.com/blog/2025/04/21/choosing-llms-to-generate-high-quality-unit-tests-for-code/ |
| 23 | Do LLMs Generate Useful Test Oracles? An Empirical Study (ASE 2025) | High (peer-reviewed) | https://www.lucadigrazia.com/papers/ase2025.pdf |
| 24 | Understanding the Characteristics of LLM-Generated Property-Based Tests (arXiv 2510.25297) | Medium (preprint) | https://arxiv.org/html/2510.25297v1 |
| 25 | Simon Willison — Red/green TDD (Agentic Engineering Patterns) | Medium–High (recognised practitioner) | https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/ |
| 26 | alexop.dev — Forcing Claude Code to TDD: An Agentic Red-Green-Refactor Loop | Medium (practitioner) | https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/ |
| 27 | cargo-mutants — Incremental tests of pull requests | High (primary, tool docs) | https://mutants.rs/pr-diff.html |
| 28 | Joss Moffatt — Automating Mutation Testing with Mutmut and GitHub Actions | Medium (practitioner) | https://blog.stackademic.com/automating-mutation-testing-with-mutmut-and-github-actions-9767b4fc75b5 |
| 29 | oneuptime — How to Handle Mutation Testing | Low–Medium (blog) | https://oneuptime.com/blog/post/2026-01-24-mutation-testing/view |
| 30 | Evidently AI — LLM-as-a-judge: a complete guide | Medium–High (vendor, well-regarded) | https://www.evidentlyai.com/llm-guide/llm-as-a-judge |
| 31 | confident-ai/deepeval — The LLM Evaluation Framework (GitHub) | High (primary) | https://github.com/confident-ai/deepeval |
| 32 | Judge Reliability Harness: Stress Testing the Reliability of LLM Judges (arXiv 2603.05399) | Medium (preprint) | https://arxiv.org/html/2603.05399v1 |
| 33 | Semgrep — Python static analysis comparison: Bandit vs Semgrep | Medium–High (vendor, technical) | https://semgrep.dev/blog/2021/python-static-analysis-comparison-bandit-semgrep/ |
| 34 | trufflesecurity/trufflehog — Find, verify, and analyze leaked credentials (GitHub) | High (primary) | https://github.com/trufflesecurity/trufflehog |
| 35 | Gatlen Culp — The Ultimate Pre-Commit Hooks Guide for 2025 | Medium (practitioner) | https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835 |
| 36 | Repo inspection — InnoForge (`/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan`): `Makefile`, `docs/testing-strategy.md`, `tests/CLAUDE.md`, `.claude/skills/{innoforge-testing,e2e-test,us-test,test-code}`, `scripts/check_test_assertions.py` | High (direct source) | (local repo) |
| 37 | Repo inspection — Podforger (`/home/sergiog/dev/iw-doc-plan/main/podforger`): `Makefile`, `.claude/skills/{test-automator,webapp-testing,tdd-orchestrator,quality-engineer}`, `pytest.ini`, e2e targets | High (direct source) | (local repo) |
| 38 | Repo inspection — IW AI Core (`/home/sergiog/dev/iw-doc-plan/main/iw-ai-core`): `Makefile`, `pyproject.toml`, `tests/` tree, `tests/CLAUDE.md`, `CLAUDE.md` | High (direct source) | (local repo) |
