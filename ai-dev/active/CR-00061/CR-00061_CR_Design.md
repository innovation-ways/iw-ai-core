# CR-00061: Flaky test quarantine workflow (P2-CR-C)

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase-2 item 2.3 from `ai-dev/work/TESTS_ENHANCEMENT.md`. Flakiness in a session-scoped-fixture world is inevitable; today we have no process for it — flakes get silently rerun, ignored, or hidden behind ad-hoc `order_dependent` + `xfail(strict=False)` markers. This CR codifies a workflow: a dedicated `quarantine` marker, a strict separation between the merge gate (excludes quarantine) and an informational quarantine run (so we see when a flake recovers), `pytest-rerunfailures` wired only as a **nightly detector** (never an auto-fix), and a rule that quarantining a test files an incident.
**Created**: 2026-05-17
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Quarantine runs use the same testcontainer fixtures the regular suite uses; no new Docker invocations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Add a `quarantine` pytest marker (alongside the existing `order_dependent`, `smoke`, etc.). Wire it into a three-surface workflow:

1. **Merge gate**: `make test-unit` and `make test-integration` (and the QV gates that wrap them) deselect `quarantine` automatically via `addopts`. Quarantined tests cannot block a merge.
2. **Informational quarantine run**: a new `make test-quarantine` target runs *only* the quarantined tests, with `pytest-rerunfailures` set to 1 retry, and reports pass/fail per test. A recovered flake (consistently passing in this run for N consecutive invocations) is the signal to remove the marker.
3. **Nightly flake detector**: `make test-flake-detect` runs the FULL suite 3× and reports any test that passes on one run and fails on another (the textbook flake signature). `pytest-rerunfailures` is the mechanism, but with `--only-rerun-flagged` semantics — it is a DETECTOR, never an auto-fix on the merge path.

A new prose rule in `tests/CLAUDE.md` makes the quarantine workflow non-discretionary: adding `@pytest.mark.quarantine` to a test requires (a) a tracking comment naming the suspected cause, (b) filing an Incident via `/iw-new-incident`, and (c) recording the Incident ID in the marker reason string.

This CR also reconciles the existing ad-hoc `order_dependent` + `xfail(strict=False)` pattern (3 module-scoped quarantines from CR-00055) with the new workflow: leave them in place but document the equivalence in `tests/CLAUDE.md` (`order_dependent` is a narrower flavour of `quarantine`; both excluded from the merge gate; new entries default to `quarantine`).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `docs/IW_AI_Core_Testing_Strategy.md` — §3 (test infrastructure), §5 (gate table), §9 row "Flaky/quarantine workflow" which today reads `❌ (2.3)`. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.3 for the spec. Read `tests/CLAUDE.md` — especially the existing "Quarantine policy" sub-section around §7/§8 (added by CR-00055) for the `order_dependent` precedent. Read `pyproject.toml` `[tool.pytest.ini_options]` (around lines 156–165) for the existing markers list and `addopts` deselection pattern (`-m 'not browser'` is the model). Read `skills/iw-new-incident/SKILL.md` for the incident-filing flow the new rule references.

## Current Behavior

- **No `quarantine` marker.** Markers list in `pyproject.toml:158–164` lists `integration`, `smoke`, `slow`, `browser`, `order_dependent`. No general-purpose quarantine.
- **No `pytest-rerunfailures` dependency.** `grep -n rerunfailures pyproject.toml` returns nothing.
- **No `make test-quarantine` or `make test-flake-detect`.** `.PHONY` line doesn't list them; no recipes.
- **Ad-hoc quarantines exist.** Four tests today use `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False)` (per CR-00055/CR-00048):
  - `tests/integration/test_pending_migration_log_migration.py:157`
  - `tests/integration/db/test_i_00062_migration.py:141`
  - `tests/integration/test_db_identity_integration.py:297`
  - `tests/unit/test_browser_env.py` — the `test_pick_free_offset_returns_hash_offset_when_free` quarantine from CR-00048
  - (One additional `xfail(strict=False)` at `tests/dashboard/test_code_qa_sse_wire.py:389` is **not** order-dependent — it's an unrelated per-test xfail; mentioned for completeness but not part of the order_dependent population.)
- **No "filing an incident" rule.** Quarantines today get a `# NOTE(P1-CR-C-followup-randomly):` tracking comment but no DB-tracked incident — the quarantine backlog is a search-the-codebase artefact, not a queryable list.
- **No quarantine recovery signal.** Once a test is quarantined, nothing tells us when it would now pass. The merge gate excludes it forever (effectively).
- **Flake detection is implicit.** A pipeline flake today triggers an automatic retry of the QV gate via the existing fix-cycle mechanism (`orch/daemon/fix_cycle.py`); the fact that the test was flaky is lost in the noise. There's no per-test flake signal aggregated over time.
- **Strategy doc §9** row "Flaky/quarantine workflow" status: `❌ (2.3)`.
- **TESTS_ENHANCEMENT.md** §6 item 2.3 row Status: `TODO`.

## Desired Behavior

**Dependency + config:**

- `pytest-rerunfailures>=14.0,<16` added to `[dependency-groups] dev` in `pyproject.toml`. `uv.lock` regenerated.
- `quarantine` marker registered in `pyproject.toml` `[tool.pytest.ini_options].markers`:
  ```
  "quarantine: test is intermittently failing or order-dependent in a way we haven't root-caused; excluded from the merge gate; tracked via an Incident (ID in the marker reason). Recovery signal: passes consistently in `make test-quarantine` for ≥3 consecutive runs.",
  ```
- `addopts` extended to deselect quarantine on the merge path:
  ```
  -m 'not browser and not quarantine'
  ```
  - The existing `-m 'not browser'` becomes `-m 'not browser and not quarantine'`. `--strict-markers` stays.

**Three new Makefile targets:**

- `test-quarantine` — runs ONLY quarantined tests with 1 retry; reports pass/fail per test. Used to spot recovered flakes.
  ```
  test-quarantine:
      uv run pytest tests/ -m quarantine --reruns 1 --reruns-delay 1 -v --no-cov
  ```
- `test-flake-detect` — runs the FULL suite 3× and aggregates per-test outcomes; any test that passes some runs and fails others is a flake.
  ```
  test-flake-detect:
      @mkdir -p tests/output
      @rm -f tests/output/flake-detect-*.log
      @for i in 1 2 3; do \
          echo "=== flake-detect run $$i/3 ==="; \
          uv run pytest tests/unit tests/integration tests/dashboard --ignore=tests/dashboard/browser \
              --no-cov -v --tb=no 2>&1 | tee tests/output/flake-detect-$$i.log || true; \
      done
      @uv run python scripts/flake_detect_aggregate.py tests/output/flake-detect-{1,2,3}.log
  ```
  - A new helper script `scripts/flake_detect_aggregate.py` reads the three pytest log files, parses pass/fail per test id, and prints the flake report (tests that disagreed across runs).
- Both added to `.PHONY`. Neither runs as part of `make quality`, `make check`, or any QV gate — `test-quarantine` is operator-on-demand; `test-flake-detect` is nightly-cron material (a follow-up CR may wire that).

**The `scripts/flake_detect_aggregate.py` helper:**

Simple — parses pytest's `=== X passed, Y failed in Zs ===` summary line + the per-test `PASSED`/`FAILED` lines per log file; aggregates by test id; prints a report of tests that flipped (some runs PASSED, others FAILED). Exits 0 if no flakes detected, 1 if flakes detected (so a nightly cron can alert on regression). Output format:

```
Flake detection over 3 runs of the full suite

Found 2 flaky test(s):
  tests/integration/test_foo.py::test_bar
    run 1: PASSED  run 2: FAILED  run 3: PASSED
  tests/unit/test_baz.py::test_qux
    run 1: PASSED  run 2: PASSED  run 3: FAILED

Recommendation: file an incident, add `@pytest.mark.quarantine(reason="I-NNNNN: ...")`, exclude from merge gate.
```

**The quarantine-requires-incident rule (prose in tests/CLAUDE.md):**

New sub-section, e.g. "Quarantine workflow":

> A test is quarantined when it intermittently fails for a reason we haven't root-caused, OR when it requires a specific test ordering we haven't fixed. **Quarantining a test is not free**: it removes the test's signal from the merge gate, so the bug it was guarding for can land unnoticed.
>
> **The rules:**
>
> 1. Before adding `@pytest.mark.quarantine`, run `/iw-new-incident` and file an Incident describing the suspected cause and the test name(s). Use the Incident ID in the marker's `reason` argument.
> 2. The marker MUST carry a `reason` string of the form `"I-NNNNN: <one-liner — suspected cause + when added>"`. Example:
>    ```python
>    @pytest.mark.quarantine(reason="I-00099: race in foo() when bar is concurrent; added 2026-05-MM")
>    ```
> 3. The Incident's `Description` field must name the test(s) verbatim so a `git grep` from the test name finds the tracking ticket.
> 4. To remove the marker: run `make test-quarantine` for 3 consecutive runs (or 7 calendar days, whichever is more); if the test passed all of them, the marker can come off and the Incident can be closed with `verdict: not-reproducible`. (If it failed any run, root-cause it first.)
> 5. The existing `@pytest.mark.order_dependent` is a narrower flavour of `quarantine` — both are excluded from the merge gate; pre-existing `order_dependent`-marked tests are NOT migrated by this CR (they carry their own tracking from CR-00048/55); new quarantines default to `quarantine`.

**Documentation:**

- `docs/IW_AI_Core_Testing_Strategy.md` §3: new "Flaky/quarantine workflow" sub-section.
- `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table: new row "Quarantine deselection" (the `addopts` extension); new row "Flake detector (nightly)" labelled on-demand.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Flaky/quarantine workflow" flipped from `❌ (2.3)` to `✅ (CR-00061, 2026-MM-DD) — quarantine marker; 3 new make targets; quarantining requires filing an Incident; nightly flake-detect runs the suite 3× and reports disagreement`.
- `tests/CLAUDE.md`: new "Quarantine workflow" sub-section per above.
- `skills/iw-ai-core-testing/SKILL.md`: extended with a "Quarantine" sub-section in conventions (the 5-rule list + the recovery signal). Sync via `iw sync-skills --force iw-ai-core-testing`.

**Plan + changelog:**

- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.3 row Status: `TODO` → `DONE — CR-00061 (2026-MM-DD)`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11 changelog: new dated entry summarising the marker + addopts + 3 Makefile targets + the file-an-incident rule + the relationship to existing `order_dependent`.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml` `[dependency-groups] dev` | no `pytest-rerunfailures` | added |
| `pyproject.toml` `[tool.pytest.ini_options]` markers | no `quarantine` marker | added |
| `pyproject.toml` `[tool.pytest.ini_options]` addopts | `-m 'not browser' --strict-markers` | `-m 'not browser and not quarantine' --strict-markers` (the only change) |
| `uv.lock` | no pytest-rerunfailures | regenerated |
| `Makefile` `.PHONY` | no test-quarantine / test-flake-detect | adds both |
| `Makefile` recipes | no quarantine/flake recipes | 2 new recipes |
| `scripts/flake_detect_aggregate.py` | doesn't exist | new helper (≤120 lines, pure Python, no deps beyond stdlib) |
| `tests/CLAUDE.md` | "Quarantine policy" sub-section for `order_dependent` only | new "Quarantine workflow" sub-section with the 5-rule list |
| `docs/IW_AI_Core_Testing_Strategy.md` §3/§5/§9 | no quarantine workflow | new sub-section §3; 2 new rows §5; §9 row flipped ✅ |
| `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/...` | no quarantine guidance | new sub-section + sync |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §6/§11 | item 2.3 TODO | DONE + changelog |

### Breaking Changes

**None directly.** However, the `addopts` change to `-m 'not browser and not quarantine'` has one subtle effect: any test someone marks with `@pytest.mark.quarantine` is silently excluded from the merge gate. This is the intended behaviour, but: if anyone in the team has been using a different ad-hoc marker named `quarantine` for some other purpose (none found by `grep -rn "@pytest.mark.quarantine" tests/`), this CR captures it. The audit in S01 confirms no pre-existing usage.

### Data Migration

**None.** No DB tables, rows, or migrations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | (a) **RED-first**: write `tests/unit/test_quarantine_marker_setup.py` pinning: marker registered; `addopts` deselects it; `pytest-rerunfailures` importable; `make test-quarantine` and `make test-flake-detect` parse via `make -n`; `scripts/flake_detect_aggregate.py` exists and importable. Run RED; capture failure for `tdd_red_evidence`. (b) Add `pytest-rerunfailures>=14.0,<16` to dev deps; `uv lock`. (c) Register `quarantine` marker; extend `addopts` to add `not quarantine`. (d) Add 2 Makefile recipes (`test-quarantine`, `test-flake-detect`); update `.PHONY`. (e) Write `scripts/flake_detect_aggregate.py` (≤120 lines; parses 3 log files; reports flakes). (f) Audit pre-existing `@pytest.mark.quarantine` usage (`grep -rn`); confirm zero (HIGH if any found — likely a coincidence but worth flagging). (g) Re-run RED test → GREEN. (h) Verify the marker auto-deselection works: pick ONE existing `order_dependent` test, *temporarily* add `@pytest.mark.quarantine` to it as a smoke test, run `make test-unit`, confirm the test is deselected (not failing); then revert. Record this proof in step report. (i) Verify `make test-quarantine` runs correctly on the temporarily-added quarantine (same one) — should run + report; revert. (j) Verify `make test-flake-detect` runs a tiny subset 3× and the aggregator script produces the expected output format — use a small `tests/unit/test_smoke.py` subset (`-k "<name>"`) inside a wrapped invocation; do NOT run the full suite 3× as part of S01 (that's a 30+ minute operation — operator runs it on-demand). (k) Update docs: strategy §3/§5/§9; tests/CLAUDE.md "Quarantine workflow" sub-section (the 5 rules); skill sub-section + sync. (l) Update TESTS_ENHANCEMENT.md §6 + §11. **1800 s timeout** — no spike, no full-suite run. | — |
| S02 | `code-review-impl` | Review S01: dep added with correct pin; quarantine marker registered with prose matching design; addopts extended to `-m 'not browser and not quarantine'` (CRITICAL if old `-m 'not browser'` still present — would break the deselection); 2 Makefile recipes parse and follow the design's exact form (especially `test-quarantine` using `--reruns 1 --reruns-delay 1` — not `--reruns 3`, which would mask real failures); `scripts/flake_detect_aggregate.py` is pure Python stdlib (no pytest imports — must run standalone after pytest has logged), aggregates correctly (spot-check the parsing on a sample log), exits 0 when no flakes, 1 when flakes detected; the smoke-test in S01's report shows the deselection actually works (a tagged test was excluded from `make test-unit`) AND the marker shows up in `make test-quarantine`; tests/CLAUDE.md has the 5-rule sub-section verbatim (1: file incident; 2: marker reason includes incident ID; 3: incident describes test by name; 4: recovery = 3 consecutive passes / 7 days; 5: order_dependent stays separate); strategy doc §3/§5/§9 updated; skill sub-section + .claude sync byte-identical; §6 item 2.3 = DONE; §11 changelog has the marker + addopts + 3 targets + the incident rule + the order_dependent reconciliation; scope-creep audit: NO test bodies modified (the temp-tag-and-revert in deliverable (h)/(i) MUST not appear in the final diff — verify by checking the diff for any new `@pytest.mark.quarantine` outside the test file itself); NO production code touched; NO migration. | — |
| S03 | `code-review-final-impl` | Global cross-agent review: independently run `make test-quarantine` and confirm it (a) exits 0 if there are 0 quarantined tests today (the design says zero new quarantines this CR), OR (b) runs only the temporarily-tagged smoke if S01 left a fixture quarantine in place (CRITICAL — should have been reverted); independently run `make -n test-flake-detect` and confirm the recipe parses; independently run `scripts/flake_detect_aggregate.py` against THREE fabricated log files (e.g. create them via a tiny shell script: one with all pass, one with one fail, one with all pass — the aggregator should report the single test as flaky); cross-doc-square (strategy §3 sub-section + §5 rows + §9 row + tests/CLAUDE.md sub-section + skill sub-section — same 5 rules verbatim; CRITICAL on drift); independently confirm `addopts` deselection: `uv run pytest tests/ --collect-only -m quarantine 2>&1 | grep -c collected` should be 0 if there are no quarantines, NOT pytest's "no tests ran" error (the marker registration controls this — strict-markers must accept `quarantine`); run `make quality` + `make test-unit` and confirm pass; scope-creep audit: full file-list against design's Impacted Paths. Timeout 1800s. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` (deselects quarantine via the new addopts — verify no regression in unit-test count) | — |
| S09 | `qv-gate` (`integration-tests`) | `make test-integration` (same — quarantine deselection applies) | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` | — |
| S11 | `qv-gate` (`security-secrets`) | `make security-secrets` | — |
| S12 | `self-assess-impl` | SelfAssess via `iw-item-analyze`. Phase-2 closing CR — surface findings about: did the quarantine workflow surface a real flake during S01's smoke test of the marker; the cumulative Phase-2 cost (sum CR-00059 + CR-00060 + CR-00061); whether the file-an-incident rule is enforceable in practice (or operator-discretion only); Phase-3 readiness — which Phase-3 item should be first (3.1 E2E or 3.2 contract sweep is the typical next-most-valuable). | — |

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

| File | Type | Purpose |
|------|------|---------|
| `CR-00061_CR_Design.md` | Design | This document |
| `CR-00061_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00061_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `prompts/CR-00061_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00061_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review |
| `prompts/CR-00061_S12_SelfAssess_prompt.md` | Prompt | S12 self-assess |

(S04–S11 are QV gates — command-only.)

## Acceptance Criteria

### AC1: `quarantine` marker registered and `pytest-rerunfailures` installed

```
Given the patched pyproject.toml
When `uv run python -c "import pytest_rerunfailures"` is run
Then it succeeds
And `pytest --markers` lists `quarantine: …`
And `[tool.pytest.ini_options].markers` contains a "quarantine: …" entry whose description matches the design
```

### AC2: addopts deselects `quarantine` on the merge path

```
Given the patched pyproject.toml
When `python -c "import tomllib; ao = tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options']['addopts']; print(ao)"` is run
Then the output contains "not browser and not quarantine"
And does NOT contain a separate "-m 'not browser'" (the old marker filter was replaced, not appended)
And `--strict-markers` is still present
```

### AC3: `make test-quarantine` and `make test-flake-detect` parse and run

```
Given the patched Makefile
When `make -n test-quarantine` is run
Then it prints a recipe invoking `pytest -m quarantine --reruns 1 --reruns-delay 1`
And `make -n test-flake-detect` prints a recipe invoking pytest 3× and then `scripts/flake_detect_aggregate.py`
And both targets appear in the `.PHONY` line
```

### AC4: `scripts/flake_detect_aggregate.py` is pure-Python, ≤120 lines, exits per spec

```
Given the new script
When `python3 -c "import ast; ast.parse(open('scripts/flake_detect_aggregate.py').read())"` is run
Then it parses (valid Python)
And the file is ≤120 SLoC
And running it against 3 fabricated logs (one with a single per-run flip) prints a report naming the flake and exits 1
And running it against 3 logs that all agree exits 0
And the script uses only stdlib (no `import pytest`, no `import requests`, etc.)
```

### AC5: Marker deselection demonstrably works

```
Given the patched repo
When a single test is temporarily decorated `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` and `make test-unit` is run
Then that test is NOT collected (proof: pytest -v output shows it as deselected or absent)
And the same test IS collected by `make test-quarantine`
And after the temporary marker is reverted, the diff shows no test-body changes
```

### AC6: Strategy doc / tests/CLAUDE.md / skill updated and synced

```
Given S01's doc edits
When the four locations are read
Then docs/IW_AI_Core_Testing_Strategy.md §3 has a "Flaky/quarantine workflow" sub-section
And §5 has 2 new rows (quarantine deselection; flake-detect on-demand)
And §9 row "Flaky/quarantine workflow" is flipped from ❌ to ✅ with CR-00061
And tests/CLAUDE.md has a new "Quarantine workflow" sub-section with the 5-rule list (file incident; reason with ID; incident names test; recovery=3 consecutive or 7 days; order_dependent stays separate)
And skills/iw-ai-core-testing/SKILL.md has the same 5 rules
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to the master (sync verified)
```

### AC7: Plan + changelog updated

```
Given S01's edits
When ai-dev/work/TESTS_ENHANCEMENT.md is read
Then §6 item 2.3 Status is DONE — CR-00061 (2026-MM-DD)
And §11 has a new dated entry listing: marker; addopts change; 3 Makefile targets; file-an-incident rule; relationship to existing order_dependent
```

### AC8: No regressions in unit/integration test counts

```
Given S08 (`make test-unit`) and S09 (`make test-integration`) on the patched worktree
When test counts are compared to pre-CR baselines
Then unit-test count is unchanged (no quarantine markers added by this CR, so deselection trims nothing yet)
And integration-test count is unchanged
And both gates exit 0
```

### AC9: QV chain passes

```
Given the patched worktree at S01 completion
When the daemon runs S04–S11
Then all eight gates exit 0
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the squash-merge commit. `pytest-rerunfailures` leaves dev deps; `quarantine` marker unregisters; `addopts` reverts to `-m 'not browser'`; 2 Makefile targets disappear; `scripts/flake_detect_aggregate.py` deletes; doc/skill changes revert. No production behaviour change; trivially safe to revert. **The 4 existing `order_dependent` quarantines are unaffected** — this CR adds a sibling workflow, doesn't touch them.
- **Data**: No data loss possible.

## Dependencies

- **Depends on**: nothing hard. The Phase-2 ordering puts this after CR-00059 + CR-00060 by convention, but the scopes are disjoint — this CR can technically batch-run in parallel with both. (CR-00060 declares this CR in its "Blocks" — that's a soft sequencing hint, not a hard dependency.)
- **Blocks**: nothing. After this CR, Phase 2 is complete. Phase 3 begins (item 3.1 E2E layer recommended next per the plan).

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `scripts/flake_detect_aggregate.py`
- `tests/unit/test_quarantine_marker_setup.py`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `tests/CLAUDE.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **RED-first evidence**: `tests/unit/test_quarantine_marker_setup.py` is written **before** the marker / addopts change / `pytest-rerunfailures` / Makefile targets / aggregator script exist; run; observed to fail with a real AssertionError / KeyError / ImportError. Captured in `tdd_red_evidence`. After S01's implementation, the test passes (GREEN).
- **Unit tests**: `tests/unit/test_quarantine_marker_setup.py` — one-time guard pinning the config.
- **Integration tests**: None new.
- **Updated tests**: None permanent. S01's smoke-test in deliverable (h)/(i) temporarily decorates an existing test and reverts; the diff must show no test-body changes.
- **Aggregator script**: standalone Python; tested manually via the fabricated-log approach in AC4. A separate unit test for the aggregator (`tests/unit/test_flake_detect_aggregate.py`) is OPTIONAL — at this CR's scope, manual verification per AC4 is sufficient; if the aggregator grows complexity (e.g. JSON output, machine-readable summary) in a follow-up CR, that's the time to add unit tests.

## Notes

- **The file-an-incident rule is the load-bearing prose.** Without it, this CR is just a marker + two Makefile targets — useful but limited. The rule is what makes the quarantine backlog *queryable* (via Incident IDs in the Incidents table) and *bounded* (an Incident has a state machine; it can be closed; it has an owner). The temptation will be to skip the Incident-filing step when an agent or developer is in a hurry; `tests/CLAUDE.md` and the `iw-ai-core-testing` skill prose are the enforcement mechanism (this CR doesn't add a check; trust the workflow + reviewers).

- **`--reruns 1` is deliberate, not `--reruns 3`.** Rerunning a flake 3× and reporting "it passed eventually" hides the flake. We want the OPPOSITE — surface the flake. The single retry in `test-quarantine` is for the case where the test is genuinely flaky AND the run has unusually bad luck (so it fails twice in a row); the single retry catches the recovery without burying the signal.

- **`make test-flake-detect` is intentionally manual at this CR's scope.** Wiring it into a nightly cron is a separate CR (the platform doesn't have a cron surface yet; CR-00059's `mutation-audit` and CR-00060's `test-properties-deep` are in the same boat). Document them all as "nightly material" in the strategy doc §5, and a future CR adds the cron infrastructure for all three at once.

- **Why 3 runs, not 5 or 10.** 3 is the smallest N that can distinguish "consistent pass / consistent fail / flake" (pass-fail-pass is the textbook flake signature). More runs marginally improve confidence at multiplicative wall-clock cost; if the nightly cron later shows 3 is too few, that's a config bump in `make test-flake-detect`, not a redesign.

- **Why `pytest-rerunfailures>=14,<16` and not `latest`.** 14.x is the current stable line (as of 2026-05). The CLI flag surface (`--reruns`, `--reruns-delay`, `--only-rerun`) has been stable across 13.x and 14.x. Capping below 16 is conservative — a major version bump in a flake-detection dep is the kind of change that should be deliberate, not silent via `latest`.

- **Existing `order_dependent` tests stay as-is.** The 4 `order_dependent` tests were added by CR-00048/55 with their own tracking comments (`# NOTE(P1-CR-C-followup-randomly):`). Migrating them to `quarantine` would lose that tracking context for no real gain (both are excluded from the merge gate). Document the equivalence in `tests/CLAUDE.md` and move on. The marker registry simply ends up with two flavours of "this test is intentionally excluded from the gate".

- **Sibling-repo sync.** `iw-ai-core-testing` is a per-project skill — only iw-ai-core needs the update. No sync to InnoForge / podforger / cv.

- **Phase 2 closes with this CR.** After CR-00059 + CR-00060 + CR-00061 land, every Phase-2 item (2.1, 2.2, 2.3) is DONE. The remaining work in TESTS_ENHANCEMENT.md is P2-CR-A-followup-mutation-block (informed by CR-00059's spike numbers), P1-CR-A-followup (the 621-entry assertion baseline scrub), and all of Phase 3 + Phase 4.
