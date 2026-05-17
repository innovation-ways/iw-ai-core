# CR-00060: Hypothesis property-based tests on the state machines (P2-CR-B)

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase-2 item 2.2 from `ai-dev/work/TESTS_ENHANCEMENT.md`. State machines + parsers are the textbook property-based-testing target, and LLM-generated tests under-explore edge cases here. The highest-risk lifecycles in this codebase — work-item state, batch state, fix-cycle cap, doc-diff round-trips, and `iw next-id` atomicity — currently rely on example-based tests written by the same agent that wrote the implementation. Hypothesis explores the space these examples miss.
**Created**: 2026-05-17
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. The `iw next-id` property test uses the existing `db_session` testcontainer fixture (Ryuk teardown); no new Docker invocations, no `docker compose` calls.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Add `hypothesis>=6.100,<7` as a dev dep; add a `[tool.hypothesis]` config block with named profiles `ci` (≤20 examples, fast — runs in `make test-unit`), `dev` (~200 examples — default for local invocation), and `deep` (~1000 examples + shrinking budget — on-demand, nightly later). Create `tests/unit/properties/` with one property module per state machine target — five total: **work-item lifecycle**, **batch lifecycle**, **fix-cycle cap**, **doc-diff round-trip**, **`iw next-id` atomicity**. Register a new `properties` pytest marker (auto-applied to anything under `tests/unit/properties/`). The `ci` profile is the merge gate; `deep` runs via a new `make test-properties-deep` target.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `docs/IW_AI_Core_Testing_Strategy.md` — especially §3 (test infrastructure rules), §4 (conventions), §9 row "Property-based tests (Hypothesis) on state machines" which today reads `❌ (2.2)`. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.2 for the spec. Read the InnoForge analogue at `iw-doc-plan/main/iw-doc-plan/tests/unit/properties/` (the sibling repo already standardised on this layout — adapt, don't reinvent). Read `orch/db/models.py` for `WorkItem`, `Batch`, `FixCycle` shapes; `orch/doc_diff.py` for the round-trip target; `orch/cli/id_commands.py` for the `iw next-id` atomicity contract; `tests/integration/conftest.py` for the testcontainer fixture conventions the next-id property test relies on.

## Current Behavior

- **No `hypothesis` dependency.** `grep -n hypothesis pyproject.toml` returns nothing under `[dependency-groups] dev`.
- **No `tests/unit/properties/` directory.** All property-style coverage is ad-hoc (specific input examples in regular unit tests).
- **No `properties` pytest marker.** Not in the `markers` list in `[tool.pytest.ini_options]`.
- **State machines exist but are tested with examples only:**
  - **Work-item lifecycle** — `WorkItem.status` transitions (`draft` → `approved` → `in_progress` → `merged`/`failed`/`cancelled`); the fix-cycle counter; the "never re-queue merged" invariant. Tested in `tests/integration/test_cli_items.py`, `tests/unit/test_work_item_state.py`, etc. — all example-based.
  - **Batch lifecycle** — `Batch.status` as a pure function of its items' statuses; "held launches nothing" invariant. Tested in `tests/integration/test_cli_batches.py` + scattered. Example-based.
  - **Fix-cycle cap** — `MAX_FIX_CYCLE` enforcement in `orch/daemon/fix_cycle.py`. Tested as "after N cycles, the step fails terminally". No invariant assertion that *the cap is never exceeded* across arbitrary failure sequences.
  - **Doc-diff round-trips** — `orch/doc_diff.py` parses a doc into sections, applies edits, serialises back. The round-trip is the textbook PBT target (parse(serialise(parse(x))) == parse(x)). Today tested with a handful of fixtures.
  - **`iw next-id` atomicity** — `allocate_next_id()` in `orch/db/models.py` uses a row-level lock to guarantee no two concurrent callers get the same ID. Tested with one concurrent-test case in `tests/integration/test_cli_items.py`. Hypothesis with a stateful machine can find the lost-update edge case if it exists.
- **Strategy doc §9** row "Property-based tests (Hypothesis) on state machines" status: `❌ (2.2)`.
- **TESTS_ENHANCEMENT.md** §6 item 2.2 row Status: `TODO`.
- Consequence: every "the work-item lifecycle is correct" claim rests on example tests written by an agent that knows the implementation. The classes of bug Hypothesis finds — un-considered orderings, off-by-one boundary cases, race conditions in the next-id allocator — are systematically undertested.

## Desired Behavior

**Dependency + config:**

- `hypothesis>=6.100,<7` added to `[dependency-groups] dev` in `pyproject.toml`. `uv.lock` regenerated.
- `[tool.hypothesis]` block added to `pyproject.toml`:
  ```toml
  # Hypothesis property-based testing (CR-00060, P2-CR-B)
  # Profiles selected via `--hypothesis-profile=<name>` on the pytest CLI.
  # ci    — merge gate; small example count, no shrinking budget.
  # dev   — local default; medium example count, modest shrinking.
  # deep  — nightly/on-demand; large example count + full shrinking.
  [tool.hypothesis]
  database_file = ".hypothesis/examples"
  ```
- Profile registration lives in `tests/unit/properties/conftest.py` (Hypothesis profiles are a runtime concept; toml-level config is limited to the example database). The conftest registers three profiles and picks the active one from the `IW_HYPOTHESIS_PROFILE` env var, defaulting to `ci`:
  ```python
  # tests/unit/properties/conftest.py
  from hypothesis import settings, HealthCheck
  import os

  settings.register_profile("ci",   max_examples=20,   deadline=2000, suppress_health_check=[HealthCheck.too_slow])
  settings.register_profile("dev",  max_examples=200,  deadline=5000)
  settings.register_profile("deep", max_examples=1000, deadline=None, derandomize=False)
  settings.load_profile(os.environ.get("IW_HYPOTHESIS_PROFILE", "ci"))
  ```
- `.hypothesis/` added to `.gitignore` (Hypothesis example DB lives here).
- `properties` marker registered in `pyproject.toml` `[tool.pytest.ini_options]` `markers` list. A `tests/unit/properties/conftest.py` `pytest_collection_modifyitems` hook auto-applies the marker to every test in the directory (no per-test decorator needed).

**Five property modules under `tests/unit/properties/`:**

- `test_work_item_lifecycle_properties.py` — `RuleBasedStateMachine` modelling `WorkItem`'s allowed transitions. Rules: `register`, `approve`, `claim`, `complete_step`, `fail_step` (increments cycle counter), `merge`, `cancel`. Invariants:
  1. A `WorkItem` in `merged` state never transitions to any other state (terminal).
  2. `fix_cycle_count` never exceeds `MAX_FIX_CYCLE`.
  3. A work item in a terminal state (`merged`, `failed`, `cancelled`) is never re-claimable.
  4. `current_step_index` only moves forward (monotonic) within a single non-rollback execution.
  - Targets the *invariant set*, not the *transitions* (the latter are pinned by example tests).
- `test_batch_lifecycle_properties.py` — pure-function properties (no state machine): given a list of (item-id, item-status) tuples, `compute_batch_status(items)` is:
  1. Deterministic (same input → same output, no time/ID dependence).
  2. `held` if any item is `held`.
  3. `completed` iff every item is in a terminal state AND at least one is `merged`.
  4. `failed` iff every item is in a terminal state AND none are `merged`.
  5. `in_progress` otherwise.
  - If batch-status computation lives in code (it does — `orch/daemon/batch_manager.py`), import and test it directly. If it's intertwined with DB queries, extract a pure helper first as part of S01 (minimal extraction — no behaviour change).
- `test_fix_cycle_cap_properties.py` — `RuleBasedStateMachine` exercising `orch/daemon/fix_cycle.py`'s cap enforcement. Rules: `record_pass`, `record_fail`. Invariant: cycle count never exceeds the configured cap regardless of any pass/fail interleaving; the step terminates in `failed` (not `in_progress`) exactly when count hits the cap and the latest record was a fail.
- `test_doc_diff_round_trip_properties.py` — `parse(serialise(d)) == d` and `serialise(parse(s)) == s` (within whitespace normalisation) over arbitrary documents. Uses Hypothesis's `@given(text())` with shaping strategies (e.g. `from_regex(MARKDOWN_HEADING_RE)` for headings, random body content). Targets `orch/doc_diff.py` and `orch/doc_sections.py`.
- `test_iw_next_id_atomicity_properties.py` — **only property test that touches a DB** (uses the existing testcontainer `db_session` fixture). `RuleBasedStateMachine` with N parallel "callers" (modelled as `ThreadPoolExecutor` invocations under the testcontainer DB) calling `allocate_next_id(prefix)` over arbitrary interleavings. Invariant: across all rules executed, no two `allocate_next_id` calls with the same prefix returned the same numeric suffix (the lost-update violation).
  - Lives in `tests/unit/properties/` (not `tests/integration/properties/`) per the GO decision: keep the property layout flat, single directory. The DB-backed property test conftest pulls in the testcontainer fixture explicitly via `pytest_plugins = ["tests.integration.conftest"]` (the existing pattern from `tests/unit/conftest.py:38–42`).

**Makefile + Makefile-adjacent:**

- New target `test-properties` — runs `tests/unit/properties/` with the `ci` profile (which is the conftest default; explicit for clarity):
  ```make
  test-properties:
      IW_HYPOTHESIS_PROFILE=ci uv run pytest tests/unit/properties/ -v --no-cov
  ```
- New target `test-properties-deep` — runs the same dir with the `deep` profile (a slower, more thorough sweep; on-demand):
  ```make
  test-properties-deep:
      IW_HYPOTHESIS_PROFILE=deep uv run pytest tests/unit/properties/ -v --no-cov
  ```
- Both added to `.PHONY`.
- The `ci` profile runs **as part of `make test-unit`** (since `tests/unit/properties/` is under `tests/unit/`). No changes to existing `make test-unit` recipe required — pytest discovers the new files naturally; the conftest defaults the profile to `ci` for the merge-gate path.
- The `deep` profile is NOT added to `make quality` / `make check` / any QV gate — it's on-demand, future nightly cron.

**Documentation:**

- `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table: new row "Property tests (`ci` profile)" — included in unit-tests gate via `make test-unit`; new row "Property tests (`deep` profile)" — on-demand, NOT in CI.
- `docs/IW_AI_Core_Testing_Strategy.md` §3 (test infrastructure): new sub-section "Property-based tests" naming the five targets, the three profiles, and the env-var profile selector.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Property-based tests (Hypothesis) on state machines" flipped from `❌ (2.2)` to `✅ (CR-00060, 2026-MM-DD) — five property modules under tests/unit/properties/; ci profile in make test-unit; deep profile on-demand`.
- `tests/CLAUDE.md` new sub-section "Property tests" naming the conventions: where new property tests go, how to add a new profile, when to use `assume()` vs explicit narrowing, the `properties` marker auto-application via the conftest hook, the rule that property tests MUST be deterministic-given-seed (Hypothesis's `derandomize=True` in `ci`).
- `skills/iw-ai-core-testing/SKILL.md` extended with a "Property-based tests" sub-section in the conventions section (when to add a new property module, how to choose between RuleBasedStateMachine and `@given`).

**Plan + changelog:**

- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.2 row Status: `TODO` → `DONE — CR-00060 (2026-MM-DD)`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11 changelog: new dated entry summarising the five property modules, the three profiles, the `make test-properties` / `make test-properties-deep` targets, and the new `properties` marker.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[dependency-groups] dev` | no hypothesis | `hypothesis>=6.100,<7` added |
| `pyproject.toml` `[tool.hypothesis]` | missing | new block (example DB path only) |
| `pyproject.toml` `[tool.pytest.ini_options]` `markers` | no `properties` marker | new `properties` marker registered |
| `pyproject.toml` `[tool.pytest.ini_options]` `addopts` | `--strict-markers -p no:randomly --cov ...` | unchanged (the `properties` marker is auto-applied by conftest; nothing else to add) |
| `uv.lock` | no hypothesis | regenerated |
| `.gitignore` | no `.hypothesis/` entry | added |
| `Makefile` `.PHONY` | no test-properties* targets | adds `test-properties test-properties-deep` |
| `Makefile` recipes | no test-properties* | 2 new recipes |
| `tests/unit/properties/` | doesn't exist | new dir with `__init__.py`, `conftest.py`, 5 property modules |
| `docs/IW_AI_Core_Testing_Strategy.md` §3/§5/§9 | no property-test content | new sub-section §3; 2 new rows §5; §9 row flipped ✅ |
| `tests/CLAUDE.md` | no property-test sub-section | new sub-section |
| `skills/iw-ai-core-testing/SKILL.md` | no property-test guidance | new sub-section + sync to `.claude/skills/` |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | mirror of the master | re-sync via `iw sync-skills` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §6/§11 | item 2.2 TODO | DONE + changelog |
| `orch/daemon/batch_manager.py` | possibly DB-coupled batch-status computation | **may need a minimal pure helper extraction** — see Notes |

### Breaking Changes

**None.** New dev dependency, new test directory, new Makefile targets, doc updates. No production behaviour change. The one risk: if `orch/daemon/batch_manager.py`'s batch-status computation is too DB-coupled to test as a pure function, S01 extracts a minimal pure helper. That extraction is a pure-refactor (call-site delegates to the helper; semantics unchanged) and is asserted by an existing example test before AND after.

### Data Migration

**None.** No DB tables, rows, or migrations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | (a) **RED-first** — write `tests/unit/test_hypothesis_setup.py` pinning `hypothesis` import, `[tool.hypothesis]` presence, `properties` marker registration, `tests/unit/properties/conftest.py` existence; run it; confirm RED. (b) Add `hypothesis>=6.100,<7` to dev deps; `uv lock`; `[tool.hypothesis]` block; `properties` marker registration; `.hypothesis/` to `.gitignore`. (c) Create `tests/unit/properties/{__init__.py, conftest.py}` (conftest registers ci/dev/deep profiles + marker auto-apply hook). (d) Write the 5 property modules — list above. (e) (If needed) extract a pure `compute_batch_status(items)` helper from `orch/daemon/batch_manager.py` and route the existing call-site through it (no behaviour change; minimal patch). (f) Add 2 Makefile targets. (g) Run `make test-properties` and `IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/ -v --no-cov` — both pass. Capture wall-clock for each profile per file into `evidences/pre/cr-00060-profile-wall-clock.txt` (used by reviewers to verify the `ci` profile is fast enough for merge-gate inclusion). (h) Re-run RED test → GREEN. (i) Update strategy doc + tests/CLAUDE.md + iw-ai-core-testing skill (+ sync). (j) Update TESTS_ENHANCEMENT.md §6 + §11. **3000 s timeout** (5 property modules × dev profile = ≤200 examples each + room for shrinking on any unexpected failures). | — |
| S02 | `code-review-impl` | Review S01: dep + config + marker registration correct; all 5 property modules present with the named invariants from "Desired Behavior"; each `RuleBasedStateMachine` has at least one `@invariant` and at least 2 `@rule`s; `@given` strategies are non-degenerate (e.g. not `sampled_from([fixed_value])`); doc-diff round-trip uses `assume()` to skip pathological inputs rather than silently passing; next-id atomicity test uses the testcontainer fixture (not a mocked engine); the `properties` marker is auto-applied via conftest hook (no per-test decoration); profile selection works (`IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/test_work_item_lifecycle_properties.py -v` should run more examples than the default `ci`); `.hypothesis/` in `.gitignore`; **wall-clock of the `ci` profile run is sane** (the `evidences/pre/cr-00060-profile-wall-clock.txt` file shows ci profile total wall-clock <30s on a typical dev box — CRITICAL if >60s because that would push `make test-unit` over its expected budget); strategy doc §3/§5/§9 + tests/CLAUDE.md + skill updated and synced. Scope: no production code changed except (potentially) one pure-helper extraction in `orch/daemon/batch_manager.py` — that extraction must be call-site-equivalent (existing example tests still pass). | — |
| S03 | `code-review-final-impl` | Global cross-agent review: independently run `make test-properties` and confirm pass; independently run `IW_HYPOTHESIS_PROFILE=deep uv run pytest tests/unit/properties/ -v --no-cov` (with generous local timeout — this is the on-demand sweep; if it surfaces a real bug, that's a finding worth gold) and report whether the deep profile passes too OR what fails (a deep-profile failure is a HIGH finding — the `ci` profile underestimated the example space); cross-doc-triangle (strategy §3/§5/§9 + tests/CLAUDE.md + skill) consistency check; verify the conftest's marker auto-apply hook actually fires by inspecting one test under `tests/unit/properties/` with `pytest --collect-only -m properties` (should list all 5 files' tests). Verify the (possibly extracted) `compute_batch_status` helper has no new behaviour beyond what was there. `make quality` + `make test-unit` still pass (test-unit now includes the 5 new property modules under the `ci` profile). | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` (now includes 5 new property modules at the `ci` profile via conftest default) | — |
| S09 | `qv-gate` (`integration-tests`) | `make test-integration` (no new integration tests this CR — but the existing next-id integration tests still pass, and the property-test conftest's testcontainer-fixture import does not regress) | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` (new property tests should cover the touched lines well) | — |
| S11 | `qv-gate` (`security-secrets`) | `make security-secrets` | — |
| S12 | `self-assess-impl` | SelfAssess via `iw-item-analyze`. Phase 2 second CR — surface findings about whether the full-setup shape (5 modules in one CR) was the right call vs CR-00059's spike-then-setup; whether any property test surfaced a real bug during S01's iteration; whether `derandomize=True` in `ci` profile is sufficient for merge-gate determinism. | — |

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
- `browser_verification` = **false**.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00060/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00060_CR_Design.md` | Design | This document |
| `CR-00060_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00060_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `prompts/CR-00060_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00060_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review |
| `prompts/CR-00060_S12_SelfAssess_prompt.md` | Prompt | S12 self-assess |
| `evidences/pre/cr-00060-profile-wall-clock.txt` | Evidence | per-profile wall-clock (S01 captures) |

(S04–S11 are QV gates — command-only.)

## Acceptance Criteria

### AC1: Hypothesis dependency installed and config block present

```
Given the patched pyproject.toml
When `uv run python -c "import hypothesis; print(hypothesis.__version__)"` is run
Then it prints a 6.100+ version (and <7)
And tomllib parsing of pyproject.toml exposes [tool.hypothesis] with the `database_file` key
And [tool.pytest.ini_options].markers includes `"properties"` (or equivalent)
```

### AC2: Three Hypothesis profiles registered and selectable

```
Given `tests/unit/properties/conftest.py`
When pytest collects `tests/unit/properties/`
Then the conftest registers profiles "ci", "dev", "deep"
And the active profile defaults to "ci" (or honours $IW_HYPOTHESIS_PROFILE)
And `IW_HYPOTHESIS_PROFILE=dev` causes a measurably larger example count per @given block than `IW_HYPOTHESIS_PROFILE=ci` (verifiable via Hypothesis's `--hypothesis-show-statistics`)
```

### AC3: Five property modules exist and run

```
Given the patched repo
When `pytest tests/unit/properties/ --collect-only -m properties` is run
Then exactly five files are listed:
  - test_work_item_lifecycle_properties.py
  - test_batch_lifecycle_properties.py
  - test_fix_cycle_cap_properties.py
  - test_doc_diff_round_trip_properties.py
  - test_iw_next_id_atomicity_properties.py
And every test collected is marked `properties` (via the conftest hook — no per-test decorator)
And `make test-properties` exits 0
```

### AC4: Each property module asserts named invariants

```
Given each of the 5 modules
When inspected for content
Then:
  - test_work_item_lifecycle_properties.py asserts the 4 named invariants (no transition from terminal merged; fix_cycle ≤ MAX; no re-claim of terminal; current_step_index monotonic)
  - test_batch_lifecycle_properties.py asserts the 5 properties of compute_batch_status (deterministic; held precedence; completed iff all-terminal+any-merged; failed iff all-terminal+none-merged; in_progress otherwise)
  - test_fix_cycle_cap_properties.py uses RuleBasedStateMachine with @rule(record_pass) + @rule(record_fail) + @invariant(cycle_count ≤ cap)
  - test_doc_diff_round_trip_properties.py asserts `parse(serialise(d)) == d` and `serialise(parse(s)) == s` (within whitespace normalisation)
  - test_iw_next_id_atomicity_properties.py asserts no duplicate (prefix, suffix) across arbitrary concurrent allocate_next_id calls under the testcontainer db_session fixture
```

### AC5: `ci` profile is fast enough for the merge gate

```
Given the patched repo
When `time make test-properties` is run on a clean dev environment
Then total wall-clock is <30 s
And the measurement is recorded in evidences/pre/cr-00060-profile-wall-clock.txt
```

### AC6: `deep` profile is reachable via Makefile and runs to completion

```
Given the patched Makefile
When `make test-properties-deep` is invoked
Then it sets IW_HYPOTHESIS_PROFILE=deep
And pytest runs with at least 1000 max_examples per @given/RuleBasedStateMachine
And the suite either exits 0 (all properties hold) OR exits non-zero with Hypothesis's shrunk-counterexample output (a real bug found)
```

### AC7: Marker registered + auto-applied

```
Given the patched pyproject.toml + tests/unit/properties/conftest.py
When `pytest --markers` is run
Then the `properties` marker appears
And `pytest tests/unit/properties/ --collect-only -m properties` lists every test under that directory (none missed)
And `pytest tests/unit/properties/ --collect-only -m "not properties"` lists zero tests under that directory (no unmarked stragglers)
```

### AC8: Strategy doc / tests/CLAUDE.md / skill updated and synced

```
Given S01's doc edits
When the four locations are read
Then docs/IW_AI_Core_Testing_Strategy.md §3 has a new "Property-based tests" sub-section
And §5 gate table has rows for the ci and deep profiles
And §9 known-gaps row "Property-based tests" is flipped from ❌ to ✅ with CR-00060
And tests/CLAUDE.md has a new "Property tests" sub-section naming the conventions
And skills/iw-ai-core-testing/SKILL.md has a new sub-section in conventions
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to the master (sync verified)
```

### AC9: Plan + changelog updated

```
Given S01's edits to ai-dev/work/TESTS_ENHANCEMENT.md
When the file is read
Then §6 item 2.2 Status is DONE — CR-00060 (2026-MM-DD)
And §11 has a new dated entry naming the 5 modules, 3 profiles, 2 new Makefile targets, the properties marker, wall-clock measurement
```

### AC10: QV chain passes

```
Given the patched worktree at S01 completion
When the daemon runs S04–S11
Then all eight gates exit 0
And S08 (make test-unit) includes the 5 new property modules at the ci profile
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the squash-merge commit. `hypothesis` leaves dev deps; `[tool.hypothesis]` block disappears; `tests/unit/properties/` directory disappears (5 modules + conftest); 2 Makefile targets disappear; `properties` marker un-registers; doc/skill changes revert; (if `compute_batch_status` was extracted) the helper inlines back. No production behaviour change; trivially safe to revert.
- **Data**: No data loss possible.

## Dependencies

- **Depends on**: nothing hard. **Compatible with CR-00059** (independent scopes — disjoint paths). May run in the same batch.
- **Blocks**: nothing. Phase 2 then has only item 2.3 left (CR-00061, separate CR — flaky/quarantine workflow).

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `.gitignore`
- `Makefile`
- `tests/unit/properties/**`
- `tests/unit/test_hypothesis_setup.py`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `tests/CLAUDE.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `orch/daemon/batch_manager.py`

(The `orch/daemon/batch_manager.py` entry is only exercised if a pure-helper extraction is needed — see Notes — but the path is declared up-front so scope enforcement doesn't block the helper extraction at merge time.)

## TDD Approach

- **RED-first evidence**: `tests/unit/test_hypothesis_setup.py` is written **before** the `hypothesis` dep / `[tool.hypothesis]` / `properties` marker / `tests/unit/properties/` exist; run; observed to fail with real AssertionError/KeyError/ImportError (the import-error case here is acceptable RED — `hypothesis` is actually missing pre-patch). The captured failure is recorded in `tdd_red_evidence`. After S01's implementation, the test passes (GREEN).
- **Unit tests**: `tests/unit/test_hypothesis_setup.py` (one-time guard) + the 5 property modules (these ARE the new tests).
- **Integration tests**: None new. The next-id property test uses the *integration* testcontainer fixture but lives in `tests/unit/properties/` per the GO decision.
- **Updated tests**: Only if S01 extracts a pure `compute_batch_status` helper from `orch/daemon/batch_manager.py` — in which case the existing example tests in `tests/integration/test_cli_batches.py` (or wherever batch-status assertions live) are sanity-checked to still pass at S01 completion (and again at S03 + S09).

## Notes

- **The full-setup shape is the right call.** Hypothesis is well-understood; the cost model is `max_examples × per-example-time`, which we can predict without a spike. CR-00059's spike-shape was justified because mutation testing's per-mutant-overhead was a true unknown — there is no analogous unknown for Hypothesis. Operator decision (recorded at GO time): full setup, all 5 targets, one CR.

- **`compute_batch_status` extraction risk.** `orch/daemon/batch_manager.py` is large and DB-heavy. If batch-status computation is currently a SQL query joining work items, S01 should extract a pure Python helper `compute_batch_status(items: list[tuple[ItemId, ItemStatus]]) -> BatchStatus` and route the existing query result through it. The change is purely structural: the SQL still loads the items; the new helper does the classification. If the existing call-site is too entangled to extract cleanly within S01's scope, raise a blocker and file `P2-CR-B-followup-batch-helper-extraction` rather than ship a broken helper. The remaining 4 property modules are unaffected — only batch-lifecycle properties depend on this.

- **`derandomize=True` in the `ci` profile.** Hypothesis's `derandomize` option causes the same examples to be generated on every run given the same code — eliminates flakiness in the merge-gate path. The `dev` and `deep` profiles use the default (random seed printed at run start) for genuine exploration. The conftest sets this explicitly in the `ci` profile registration.

- **Why the next-id property test lives in `tests/unit/properties/`.** Operator decision (recorded at GO time): keep the property layout flat. The test imports the testcontainer fixture via `pytest_plugins`, matching the existing pattern in `tests/unit/conftest.py:38–42` where a few unit tests legitimately need a real DB. The trade-off: `make test-unit` now starts a testcontainer for this one file. Acceptable — `make test-unit` already starts one when any unit test needs DB, and this is one more.

- **The `deep` profile may surface real bugs.** That's the entire point. If S03's independent `make test-properties-deep` run fails with a Hypothesis-shrunk counterexample, file the resulting bug as a separate incident (don't fix it within this CR — that's scope creep). Note the discovery in the §11 changelog as a Phase-2 success story.

- **Hypothesis's example DB at `.hypothesis/`.** Hypothesis caches failing examples between runs to speed shrinking. Add the directory to `.gitignore` (not committed; per-developer). If a CI run fails on a shrunk example, the example is in the test output — no need to share the cache.

- **No sibling-repo sync.** InnoForge already has `tests/unit/properties/`; podforger and cv are unaffected. The `iw-ai-core-testing` skill IS synced (via `iw sync-skills`) because it lives in this repo's `skills/`.
