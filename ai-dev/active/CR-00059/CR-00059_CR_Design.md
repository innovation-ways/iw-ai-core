# CR-00059: Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase-2 item 2.1 from `ai-dev/work/TESTS_ENHANCEMENT.md`. Coverage and the assertion scanner (CR-00046) catch *structural* test smells but cannot tell a strong assertion from `assert x is not None`. Mutation testing — introducing a small bug ("mutant") into production code and checking that some test fails — is the only direct measure of whether our ~4,420 tests would actually catch a regression. This is the highest-leverage item left in the plan, and the daemon is our highest-risk module (it merges to `main`).
**Created**: 2026-05-17
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. The mutmut runner re-uses the same testcontainer fixtures the regular test suite already uses (via `tests/integration/conftest.py`'s `pg_container` / `db_engine` / `db_session`). No new Docker invocations. No `docker compose` calls.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Land the permanent **mutmut** surface in IW AI Core — `[tool.mutmut]` config block in `pyproject.toml`, four `make mutation-{check,audit,results,show}` recipes ported from InnoForge's `iw-doc-plan/main/iw-doc-plan/Makefile:444–500` pattern — and **run a one-shot spike on `orch/daemon/`** during S01 to measure (a) total runtime on a typical dev box, (b) raw mutation score, (c) per-mutant runtime distribution, (d) any infrastructure blockers (testcontainer startup per worker, FTS trigger replay, the live-DB write guard). The spike output is a measurement table in the S01 report — it is **not** yet a permanent PR gate. A follow-up CR (`P2-CR-A-followup-mutation-block`) will use those numbers to decide between a daemon QV gate vs a GH workflow step and flip to blocking after burn-in.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `docs/IW_AI_Core_Testing_Strategy.md` — especially §8 ("Mutation testing awareness") which today says *"It is not yet set up — it's roadmap item 2.1"*; this CR makes that section concrete. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.1 for the original spec. Read `iw-doc-plan/main/iw-doc-plan/Makefile:444–500` for the InnoForge mutmut Makefile pattern and `iw-doc-plan/main/iw-doc-plan/pyproject.toml:256–262` for the `[tool.mutmut]` config block being ported.

## Current Behavior

- **No mutmut dependency.** `grep -n mutmut pyproject.toml` returns nothing in `[dependency-groups] dev` (lines 76–104).
- **No `[tool.mutmut]` config block.** `grep -n "tool.mutmut" pyproject.toml` is empty.
- **No `make mutation-*` targets.** `grep -nE "^mutation-" Makefile` returns nothing; the `.PHONY` line (lines 5–13) does not list any mutation-* targets.
- **No `.mutmut-cache` in `.gitignore`** (because there's nothing producing one yet). `tests/output/` itself is already gitignored (`.gitignore:26`), so any mutmut cache placed under `tests/output/mutmut/` is implicitly covered.
- **Strategy doc §8** ("Mutation testing awareness", `docs/IW_AI_Core_Testing_Strategy.md:273–279`) explicitly states:
  > Mutation testing (introduce a small bug — a "mutant" — into production code; check that some test fails) is the only direct measure of whether our tests catch regressions: line coverage cannot tell a strong assertion from `assert x is not None`. **It is not yet set up** — it's roadmap item 2.1 …
- **TESTS_ENHANCEMENT.md** §6 item 2.1 row status: `TODO`. §9 row "Mutation testing": `❌ (2.1)`.
- Consequence: every "improving test quality" claim we make rests on the assertion scanner (CR-00046) catching *structural* smells. We have **no** measurement of whether the surviving non-vacuous tests would actually fail when production code regresses.

## Desired Behavior

**Dependency + config (permanent, lands regardless of spike outcome):**

- `mutmut>=2.5,<3.0` added to `[dependency-groups] dev` in `pyproject.toml` (pin matches InnoForge's `iw-doc-plan/main/iw-doc-plan/pyproject.toml:102`). `uv.lock` regenerated.
- `[tool.mutmut]` block added to `pyproject.toml` (after `[tool.deptry]` at line ~213):
  ```toml
  # Mutation testing (CR-00059, P2-CR-A) — runs on-demand, NOT in CI yet.
  # Usage: make mutation-check MODULE=orch/daemon/auto_merge.py
  #        make mutation-audit (currently scoped to orch/daemon/; expand in follow-up CR)
  [tool.mutmut]
  paths_to_mutate = "orch/daemon/"
  tests_dir = "tests/unit/daemon/ tests/integration/daemon/"
  runner = "uv run pytest tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q"
  ```
  - `paths_to_mutate` scoped to `orch/daemon/` — the spike target and the default `mutation-audit` scope. Follow-up CR widens to all of `orch/` after the spike informs cost.
  - `tests_dir` scoped to the matching test directories so mutmut doesn't run the entire ~4,420-test suite per mutant.
  - `runner` uses `-x --tb=no -q` (mutmut convention: stop on first failure, no traceback, quiet — each mutant only needs a binary "killed/survived" verdict, not full output).
  - `mutate_only_covered_lines = true` is set per-target on the `mutmut run` invocations in the Makefile (mutmut respects it via the `--simple-output` + cache interaction; the explicit flag goes on the CLI, not in `[tool.mutmut]`, because the InnoForge reference pattern controls it at recipe time).

**Makefile recipes (permanent — ported from InnoForge `Makefile:444–500`):**

Four new targets, all added to the existing `.PHONY` line:

- `mutation-check` — single-module mutation test (default usage during development):
  ```
  make mutation-check MODULE=orch/daemon/auto_merge.py
  ```
  Recipe: validates `MODULE` is set; auto-derives a matching test path (`tests/unit/daemon/test_auto_merge.py` and `tests/integration/daemon/test_auto_merge.py` — try unit first, fall back to broader `tests/unit/daemon/ tests/integration/daemon/` if no matching file found); deletes `.mutmut-cache`; runs `uv run mutmut run --paths-to-mutate $(MODULE) --runner "<resolved test path>" --tests-dir tests/unit/daemon/ tests/integration/daemon/ --simple-output`; prints results.
- `mutation-audit` — bulk audit (currently scoped to `orch/daemon/`):
  ```
  make mutation-audit
  ```
  Recipe: walks `find orch/daemon/ -name "*.py" -not -name "__init__.py"`, runs the same mutation-check shape per module; prints a per-module summary at the end. **This is the slow one** — the spike measures its actual runtime. Expected to run nightly or weekly, not per-PR.
- `mutation-results` — show results from the last cached run: `uv run mutmut results`.
- `mutation-show ID=N` — inspect a specific surviving mutant: `uv run mutmut show $(ID)`.

All four recipes **do NOT** go into `make quality` or `make check` (mutation testing is on-demand, not blocking). No new daemon QV gate, no GH workflow step — deferred to follow-up CR per the operator decision.

**Documentation:**

- `docs/IW_AI_Core_Testing_Strategy.md` §8 rewritten to reflect: mutmut now installed; spike measurement (count of mutants, runtime, score); the four `make` targets; what's still missing (PR gate, broader scope) and the named follow-up CR.
- `docs/IW_AI_Core_Testing_Strategy.md` §5 quality-gate table gets a new "Mutation testing" row labelled "on-demand (not in CI)" with the `make mutation-audit` command.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 known-gaps row "Mutation testing" flipped from `❌ (2.1)` to `⚠️ (CR-00059, 2026-MM-DD) — config + Makefile + orch/daemon/ spike landed; broader scope and PR-gate flip deferred to follow-up CR P2-CR-A-followup-mutation-block`.

**Plan + changelog:**

- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.1 row: `TODO` → `IN PROGRESS — CR-00059 shipped foundation + spike; follow-up CR for broader scope and blocking gate`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11 changelog gets a new dated entry summarising: spike numbers (mutants, runtime, score, blockers), targets added, doc updates, follow-up CR filed.
- New follow-up row in §5 (or a new sub-section near Phase 2): `P2-CR-A-followup-mutation-block` — drives mutation-check scope wider (all of `orch/`) and flips to a blocking PR gate (daemon QV or GH workflow, choice informed by spike runtime).

**Spike (S01 deliverable — measurement only, NOT a permanent gate):**

- S01 runs `make mutation-audit` against `orch/daemon/` exactly once, **after** the Makefile/config are in place.
- Captures into `evidences/pre/cr-00059-spike-measurements.txt` (and inline in S01's report):
  | Metric | Value |
  |---|---|
  | Total mutants generated | _N_ |
  | Killed | _K_ |
  | Survived | _S_ |
  | Timeout | _T_ |
  | Suspicious | _Sus_ |
  | Mutation score | _K / (K + S) × 100_% |
  | Wall-clock | _hh:mm:ss_ |
  | Modules covered | _list of orch/daemon/*.py files mutated_ |
  | Top 5 surviving mutants (file:line + brief diff) | _list_ |
  | Infrastructure blockers encountered | _free-text_ — e.g. "testcontainer cold-start on every mutant adds ~2s × N", "FTS trigger drops/re-creates per session not per test", "live-DB write guard fires on subprocess inside mutmut runner" |
- The surviving-mutant list is **the deliverable** — it's the queue of "tests that don't actually test what they look like they test". The follow-up CR will mine this list to strengthen specific tests.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[dependency-groups] dev` | no mutmut | `mutmut>=2.5,<3.0` added |
| `pyproject.toml` `[tool.mutmut]` | missing | new block (paths_to_mutate, tests_dir, runner) |
| `Makefile` `.PHONY` line | no mutation-* targets | adds `mutation-check mutation-audit mutation-results mutation-show` |
| `Makefile` recipes | no mutation-* recipes | 4 new recipes ported from InnoForge pattern |
| `uv.lock` | no mutmut | regenerated with mutmut + transitive deps |
| `docs/IW_AI_Core_Testing_Strategy.md` §8 | "not yet set up" prose | factual description of installed tooling + spike numbers + named follow-up |
| `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table | no mutation row | new "Mutation testing" row (on-demand, not in CI) |
| `docs/IW_AI_Core_Testing_Strategy.md` §9 known-gaps | "❌ (2.1)" | "⚠️ (CR-00059) — foundation + spike done; PR gate deferred" |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §5 + §6 item 2.1 + §11 | TODO | IN PROGRESS + changelog entry + follow-up CR row |
| `evidences/pre/cr-00059-spike-measurements.txt` | (doesn't exist) | spike measurement table |

### Breaking Changes

**None.** New dev dependency, new Makefile targets, doc updates. The `make` targets are opt-in; `make quality`, `make check`, `make test`, and every existing QV gate are unchanged. No CI behaviour change. No test re-balancing. No production code touched.

### Data Migration

**None.** No DB tables, rows, or migrations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | (a) **RED-first**: write `tests/unit/test_mutmut_setup.py` asserting the not-yet-present config (parse `pyproject.toml`, assert `[tool.mutmut]` block exists with the three expected keys; assert all 4 `mutation-*` targets exist in `Makefile` via `make -n`); run it, confirm failure, capture RED evidence. (b) Add `mutmut>=2.5,<3.0` to dev deps; `uv lock`; `[tool.mutmut]` config; 4 Makefile recipes. (c) Re-run RED test → GREEN. (d) Run `make mutation-audit` against `orch/daemon/` (single shot — **3600 s timeout**); capture measurement table to `evidences/pre/cr-00059-spike-measurements.txt` and inline in step report. (e) Update strategy doc §5/§8/§9 with spike numbers; update TESTS_ENHANCEMENT.md §5/§6/§11 and file follow-up CR row. | — |
| S02 | `code-review-impl` | Review S01: `[tool.mutmut]` config matches InnoForge precedent and CR design; Makefile recipes are syntactically correct (`make -n mutation-*` parses); `mutation-check` correctly auto-derives test paths; `mutation-audit` walks `orch/daemon/` and not `orch/`; the spike measurement table is populated with real numbers (not placeholders or `TBD`); strategy-doc §8 prose matches recorded spike numbers; the `P2-CR-A-followup-mutation-block` row is filed; **no production code under `orch/` was touched**; no new daemon QV gate added to `skills/iw-workflow/SKILL.md`; no GH workflow step added; RED-first guard test `tests/unit/test_mutmut_setup.py` exists and is in the diff. | — |
| S03 | `code-review-final-impl` | Global cross-agent review: independently re-run `make mutation-check MODULE=<one daemon file>` (any small daemon file) to confirm the recipe works end-to-end; independently re-run `make mutation-results` to confirm cache reads back; spot-check that surviving-mutant IDs in S01's report still resolve via `make mutation-show ID=<n>`; verify the spike measurement table's mutation-score arithmetic (K / (K+S)); cross-doc consistency (strategy doc §8 numbers ↔ S01 evidence file ↔ §11 changelog entry — same wall-clock, same mutant count, same score). Confirm `make quality` still passes. No scope creep. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` (includes the new `test_mutmut_setup.py`) | — |
| S09 | `qv-gate` (`integration-tests`) | `make test-integration` | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` | — |
| S11 | `qv-gate` (`security-secrets`) | `make security-secrets` (CR-00050) | — |
| S12 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project `self_assess = true`). Phase 2 inaugural CR — surface what the spike taught us about Phase-2 cost-per-CR and whether P2-CR-B (Hypothesis) should follow the same spike-then-setup shape. | — |

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

All files for this work item live under `ai-dev/active/CR-00059/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00059_CR_Design.md` | Design | This document |
| `CR-00059_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00059_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `prompts/CR-00059_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00059_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review |
| `prompts/CR-00059_S12_SelfAssess_prompt.md` | Prompt | S12 self-assess |
| `evidences/pre/cr-00059-spike-measurements.txt` | Evidence | Spike measurement table (written by S01) |

(S04–S11 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00059/reports/`.

## Acceptance Criteria

### AC1: mutmut dependency installed

```
Given the patched pyproject.toml
When `uv sync` is run and `uv run mutmut --version` is invoked
Then mutmut prints a 2.x version string
And `uv.lock` contains a mutmut entry
```

### AC2: [tool.mutmut] config block present and parses

```
Given the patched pyproject.toml
When `python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['mutmut'])"` is run
Then it prints a dict containing keys `paths_to_mutate`, `tests_dir`, `runner`
And `paths_to_mutate` equals "orch/daemon/"
And `tests_dir` equals "tests/unit/daemon/ tests/integration/daemon/"
```

### AC3: Four `make mutation-*` targets exist and parse

```
Given the patched Makefile
When `make -n mutation-check MODULE=orch/daemon/auto_merge.py`, `make -n mutation-audit`, `make -n mutation-results`, and `make -n mutation-show ID=1` are run
Then each prints a parseable recipe (no "No rule to make target" error)
And `mutation-check` without MODULE prints the usage message and exits non-zero
And `mutation-show` without ID prints the usage message and exits non-zero
```

### AC4: Spike measurement table is populated with real numbers

```
Given S01 has completed
When `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` is read
Then it contains a table with rows: Total mutants, Killed, Survived, Timeout, Suspicious, Mutation score, Wall-clock, Modules covered, Top 5 surviving mutants, Infrastructure blockers
And every numeric cell is a real number (not "TBD", not "—", not "$VAR")
And Mutation score = Killed / (Killed + Survived) × 100 (within ±0.5 % rounding)
And Wall-clock is a real duration (h:mm:ss or m:ss format)
And Modules covered lists at least one file from orch/daemon/*.py
```

### AC5: RED-first guard test exists and passes

```
Given the patched repo
When `uv run pytest tests/unit/test_mutmut_setup.py -v` is run
Then it passes (post-implementation GREEN)
And the test would have failed before S01 added the [tool.mutmut] block AND the Makefile recipes (S01 must capture this RED evidence per backend-impl contract)
```

### AC6: Strategy doc §8 updated with spike numbers

```
Given S01 has updated docs/IW_AI_Core_Testing_Strategy.md
When §8 ("Mutation testing awareness") is read
Then it no longer says "It is not yet set up"
And it names the four `make mutation-*` targets
And it quotes the spike's mutation score and wall-clock from AC4
And it points at `P2-CR-A-followup-mutation-block` for next steps
And §5's gate table has a new "Mutation testing" row labelled on-demand (not in CI)
And §9's known-gaps row "Mutation testing" is flipped from ❌ to ⚠️ with the CR number
```

### AC7: Plan and changelog updated

```
Given S01 has updated ai-dev/work/TESTS_ENHANCEMENT.md
When the file is read
Then §6 item 2.1 status is "IN PROGRESS — CR-00059 shipped foundation + spike; follow-up for broader scope and blocking"
And §5 has a new row for `P2-CR-A-followup-mutation-block`
And §11 has a new dated changelog entry with the spike summary (mutant count, score, wall-clock, blockers) and follow-up filed
And §9 "Mutation testing" row matches §9 in the strategy doc
```

### AC8: No production code or CI surface touched

```
Given the diff of this CR
When the file list is inspected
Then no files under `orch/` (except the [tool.mutmut] block in pyproject.toml? — pyproject.toml is root) are modified
And no files under `dashboard/`, `executor/`, `skills/`, `.claude/skills/`, `.github/workflows/`, `.pre-commit-config.yaml` are modified
And no Alembic migration is added
And no new daemon QV gate appears in `skills/iw-workflow/SKILL.md`
```

### AC9: QV chain passes

```
Given the patched worktree at S01 completion
When the daemon runs S04–S11
Then S04 (lint), S05 (assertions), S06 (format-check), S07 (typecheck), S08 (test-unit — exercises the new test_mutmut_setup.py), S09 (test-integration), S10 (diff-coverage), S11 (security-secrets) all exit 0
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the squash-merge commit. `mutmut` leaves dev deps; `[tool.mutmut]` block disappears; 4 Makefile recipes disappear; `tests/unit/test_mutmut_setup.py` disappears; strategy doc §8 returns to "not yet set up"; TESTS_ENHANCEMENT.md item 2.1 returns to `TODO`. No production behaviour change → trivially safe to revert.
- **Data**: No data loss possible (tooling/docs-only CR).

## Dependencies

- **Depends on**: nothing hard. Builds on the existing test-quality infrastructure (testcontainers, the `tests/unit/daemon/` + `tests/integration/daemon/` test dirs).
- **Blocks**: nothing hard. `P2-CR-A-followup-mutation-block` (the eventual blocking-gate flip) consumes this CR's spike numbers but is filed only as a row in `TESTS_ENHANCEMENT.md` — not as a real CR with an ID yet. Compatible to batch-run in parallel with P2-CR-B (item 2.2 Hypothesis) and P2-CR-C (item 2.3 quarantine) — disjoint scopes.

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `tests/unit/test_mutmut_setup.py`

(The spike artefact `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` is implicitly allowed — `ai-dev/active/{ID}/**` is always in scope.)

## TDD Approach

- **RED-first evidence**: `tests/unit/test_mutmut_setup.py` is written **before** the `[tool.mutmut]` block and the Makefile recipes exist, run, and observed to fail with a real `AssertionError` (config block missing / `make -n mutation-check` reports "No rule"). The captured failure is recorded in `tdd_red_evidence` per the backend-impl contract (CR-00045). After S01's implementation, the same test passes (GREEN).
- **Unit tests**: `tests/unit/test_mutmut_setup.py` — pins `[tool.mutmut]` keys and the existence of the 4 `make` targets. Protects against silent drift in future edits.
- **Integration tests**: None new. mutmut itself is the integration test — its `runner` command exercises the existing daemon tests against mutated code.
- **Updated tests**: None. The existing test suite is mutmut's *input*, not its *target*.
- **Note on the spike's mutation-score deliverable**: the spike's numbers (e.g. "78 % of daemon mutants killed") are themselves a *measurement of test quality*, not a test result. They are recorded in S01's evidence file and the strategy doc. They are not asserted as a threshold by any test in this CR — that's the follow-up CR's job.

## Notes

- **Why `orch/daemon/` for the spike, not `orch/`.** The plan §6 explicitly says "spike first: run once over `orch/daemon/` to measure cost". The daemon is the highest-risk module (it merges to `main`); the mutant count is bounded (~26 source files); and the matching tests live in two well-defined directories (`tests/unit/daemon/` + `tests/integration/daemon/`). A spike over all of `orch/` would risk exceeding the 3600 s timeout and burying the measurement signal in noise.

- **Why no PR gate in this CR.** Operator decision (recorded at GO time): "spike informs *thresholds*, not whether to land the surface". If we wire a `make mutation-check` daemon QV gate now, we'd ship dead infrastructure if the spike reveals mutmut is impractical at PR time for our codebase. Cleaner: measure first, wire the gate in `P2-CR-A-followup-mutation-block` once we know the numbers.

- **Why `mutmut>=2.5,<3.0`.** Same pin as InnoForge (`iw-doc-plan/main/iw-doc-plan/pyproject.toml:102`). Major version 2 is the stable line; 3.x is a different CLI surface (released 2024) — porting to 3.x is a separate decision, not bundled here.

- **The runner uses `-x --tb=no -q`.** Per InnoForge's `Makefile:462` and mutmut's docs: each mutant only needs a binary killed/survived verdict. `-x` stops on the first failing test (the kill), `--tb=no` skips the traceback, `-q` quiets the output. This is what makes per-mutant runs fast enough to be tractable.

- **Spike infrastructure blockers we expect to see.** (a) testcontainer startup cost — each pytest invocation pays ~2 s for the session-scoped Postgres container; mutmut serialises mutants, so this is amortised across the run, but if mutmut spawns one pytest subprocess per mutant, we pay it per mutant. The spike measurement will tell us which. (b) FTS trigger replay — `tests/integration/conftest.py` runs `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` once at session start. If mutmut bypasses the session conftest, the FTS trigger is missing and any test that depends on it fails on the *test*, not on the *mutant* — a false "killed". S01's spike report must call this out if it happens. (c) live-DB write guard — `tests/conftest.py` hijacks `IW_CORE_DB_*` to unreachable. mutmut subprocesses must inherit those env vars or the guard fires correctly anyway. The spike confirms this.

- **The surviving-mutant list is the long-term value.** Even after this CR, the most valuable artefact is the list of surviving mutants (file:line + diff). That list is the queue for `P2-CR-A-followup-mutation-block`: each surviving mutant is a test that needs strengthening. Treat the spike output not as a one-shot measurement but as the seed of an iterative quality-improvement loop.

- **No sibling-repo sync.** mutmut already lives in InnoForge; podforger and cv pick up changes via their own cadence. This CR doesn't touch `skills/iw-ai-core-testing/` (the per-project skill — adding a "mutation testing" section happens after the spike informs what to write) or any agent definitions.
