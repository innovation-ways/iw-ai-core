# CR-00081: Strengthen the 78 highest-priority assertion-scanner baseline entries (71 `no-assert` + 7 `mock-only`)

**Type**: Change Request
**Priority**: Medium
**Reason**: Incremental scrub of the assertion-scanner baseline filed as **P1-CR-A-followup** in `ai-dev/work/TESTS_ENHANCEMENT.md` §5. The 71 `no-assert` and 7 `mock-only` entries are the **most worthless** under the Phase 0 "every test must be able to fail" rule — a test with no assertion is provably useless, and a test whose only assertion is `mock.assert_called_*` checks its own scaffolding rather than behaviour. These two categories together (78 entries) are small enough to scope as a single CR; the 548 `tautology` entries stay in the baseline for now (deferred to future per-module follow-up CRs).
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR only touches tests, the baseline file, and the plan tracker — no Docker changes. The existing `testcontainers` fixtures in `tests/integration/conftest.py` are the (allowed) exception, used transparently by tests.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Strengthen all 71 `no-assert` and all 7 `mock-only` test entries currently listed in `tests/assertion_free_baseline.txt`, and shrink the baseline accordingly. Each addressed test is either **STRENGTHENED** (add a real, specific, behaviour-pinning assertion), **DELETED** (only if provably checking nothing of value and surface is already covered), or **CONVERTED** (rewrite `mock.assert_called_*`-only tests to assert on a real observable — return value, DB row, or log line via `caplog`). After this CR ships, the baseline contains zero `no-assert` and zero `mock-only` entries; the 548 `tautology` entries are explicitly out of scope and remain untouched.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `tests/CLAUDE.md` for testing rules (testcontainer-only, `monkeypatch.delenv` over `importlib.reload`, FTS DDL, `DaemonEvent.event_metadata`, per-worktree-DB caveats, the "every test must be able to fail" rule, and the pytest-randomly default-on contract). Read `skills/iw-ai-core-testing/SKILL.md` §0 (the "would this test fail if the production code regressed?" mutation-test heuristic) and §2/§8 for assertion-strength rules — this is the canonical source for what a "good" assertion looks like. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-A-followup` and the v1.3 header status block for the captured backlog counts.

## Current Behavior

`tests/assertion_free_baseline.txt` holds **626 entries** in total (categories per the file's header comment block): **71 `no-assert`**, **7 `mock-only`**, **548 `tautology`**. The baseline file is consumed by `scripts/check_test_assertions.py` and enforced by `make test-assertions` (the `assertions` QV gate added in CR-00046) — the gate admits these legacy offenders but flags any NEW violations against the same recipe.

The 78 in-scope entries today produce tests that fall into one of two failure modes:

- **`no-assert` (71 entries)**: the test body contains zero `assert …` statements. The test cannot fail for a behaviour reason; it can only fail by raising during setup/teardown. Deleting the production code line the test ostensibly covers would not turn the test red. Examples (sample, not exhaustive): `tests/dashboard/browser/test_i00070_clipboard_fallback.py::test_item_session`, `tests/dashboard/test_chat_security.py::test_loadartifact_calls_render_markdown_static`, `tests/dashboard/test_docs_pdf_chromium.py::test_doc`.
- **`mock-only` (7 entries)**: the test asserts only on `mock.assert_called_*` / `mock.call_args` — i.e. it verifies that *the test's own scaffolding* received a call. There is no assertion about an observable side-effect (return value, DB row, file, log line). If the production code rearranged its internal calls without changing observable behaviour, the test would fail even though nothing user-visible regressed; conversely, if the production code regressed an observable while still issuing the mocked call, the test would stay green.

Verification commands (run from repo root, current as of `2026-05-24`):

```bash
grep -c '# no-assert$'  tests/assertion_free_baseline.txt   # → 71
grep -c '# mock-only$'  tests/assertion_free_baseline.txt   # → 7
grep -c '# tautology$'  tests/assertion_free_baseline.txt   # → 548
grep -c '^tests/'       tests/assertion_free_baseline.txt   # → 626 (total entries; the rest of the file is the header comment block)
```

The 78 in-scope entries span **43 unique test files** across `tests/unit/`, `tests/integration/`, and `tests/dashboard/` (including `tests/dashboard/browser/`). `make test-assertions` currently passes because the baseline accepts these — the gate's job is to forbid NEW vacuous tests, not legacy ones.

## Desired Behavior

After this CR ships:

- `tests/assertion_free_baseline.txt` contains **zero** entries with `# no-assert` and **zero** entries with `# mock-only`. The 548 `# tautology` entries remain exactly as they are today (out of scope). The total baseline count drops from 626 → ~548.
- Each of the 78 in-scope tests has been resolved via one of three actions:
  - **STRENGTHEN** (default): the test now carries at least one real, specific, behaviour-pinning assertion that would fail if the production code line it covers regressed (per the mutation-test heuristic in `iw-ai-core-testing` skill §0). Examples: assert a returned value equals a specific literal; assert a DB row has a specific column value; assert an exception message matches a regex; assert a `caplog` record contains a specific substring at a specific level.
  - **DELETE**: the test is removed entirely. Permitted only when the test is provably checking nothing of value AND the surface is already covered by another existing test. The S01/S02 report must include a one-line rationale per deletion naming the covering test.
  - **CONVERT** (mock-only specific): the test is rewritten to assert on a real observable rather than `mock.assert_called_*`. The mock may stay (to isolate the unit) but it is no longer the only assertion. If the production code legitimately has no observable side-effect, the test belongs in the DELETE bucket instead.
- `make test-assertions` exits 0. (The gate's invariant is unchanged: NO new violations beyond the baseline. Shrinking the baseline by exactly the entries addressed simply tightens the gate by 78 entries.)
- `make test-unit` and `make test-integration` both exit 0. Strengthened/converted tests pass under the new assertions; deleted tests are simply removed (no skipped-test ghosts).
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-A-followup` records: "78 of 626 baseline entries strengthened in this CR (CR-00081, 2026-05-24); remaining 548 `tautology` entries deferred to future per-module CRs." The v1.3 header status block's baseline count is updated from `626 entries: 71 no-assert / 7 mock-only / 548 tautology` to `~548 entries: 0 no-assert / 0 mock-only / 548 tautology`. §11 receives a new changelog entry.
- No production code under `orch/`, `dashboard/`, `executor/`, `scripts/`, or `bin/` is touched. No skill files, no templates, no docs other than `TESTS_ENHANCEMENT.md`. No migrations.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/assertion_free_baseline.txt` | 626 entries: 71 `no-assert` / 7 `mock-only` / 548 `tautology` | ~548 entries: 0 `no-assert` / 0 `mock-only` / 548 `tautology` (re-written by the scanner after fixes) |
| 71 `no-assert` tests across `tests/**` | No behavioural assertion — provably cannot fail for the right reason | Each carries at least one real, specific, behaviour-pinning assertion (STRENGTHEN) or has been removed with rationale (DELETE) |
| 7 `mock-only` tests across `tests/**` | Only `mock.assert_called_*` / `mock.call_args` assertions — checks own scaffolding | Each asserts on a real observable (return value, DB row, log line via `caplog`); the mock may remain for isolation but is no longer the only assertion (CONVERT). DELETE permitted when no observable exists. |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-A-followup` + v1.3 header | "626 baseline entries: 71 no-assert / 7 mock-only / 548 tautology" | Row records the 78-entry strengthening (CR-00081, 2026-05-24); header counts updated to ~548 / 0 / 0 / 548; §11 changelog entry added |

### Breaking Changes

**None.** No API surface, no DB schema, no CLI flag, no daemon contract, no GH Actions workflow shape. Only test bodies, the baseline file, and one plan tracker document. The `assertions` QV gate's command (`make test-assertions`) is unchanged; only its baseline shrinks.

### Data Migration

**None.** No DB tables, rows, or migrations touched.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. The 78 entries split cleanly along category lines (the failure modes and remediation patterns differ between `no-assert` and `mock-only`), so S01 owns the 71 `no-assert` entries and S02 owns the 7 `mock-only` entries plus the baseline-rewrite, scanner re-run, and tracker update.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `tests-impl` | RED-first dump the 71 `no-assert` entries via the scanner; for each, STRENGTHEN (preferred) / DELETE (with one-line rationale + covering-test name) / CONVERT (if the test was mis-categorised as `no-assert` but is actually `mock-only` in disguise — rare). Run targeted `uv run pytest` on each modified file. Do NOT re-run the scanner here — S02 owns the baseline rewrite. Timeout 2400 s. | — |
| S02 | `tests-impl` | Strengthen the 7 `mock-only` entries (default action is CONVERT — assert on a real observable; DELETE permitted only with rationale). Re-run `uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/` to shrink the baseline. Verify `grep -cE '# (no-assert\|mock-only)$' tests/assertion_free_baseline.txt` returns 0. Verify `# tautology$` count is still 548 (untouched). Update `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row + v1.3 header counts + §11 changelog. | — |
| S03 | `code-review-impl` | Review S01: for every modified test, verify the new assertion is real and behaviour-pinning (the mutation-test question: "would this test fail if the production code regressed?"); flag any weakening, any `assert True`-equivalent fillers, any `mock.assert_called_*`-only conversions; flag every DELETE that lacks a one-line rationale or whose claimed covering test does not actually cover the same surface; flag any production-code edits (out of scope) | — |
| S04 | `code-review-impl` | Review S02: same assertion-strength check on the 7 converted/strengthened tests; verify the baseline rewrite shows exactly 78 entries removed (-71 no-assert, -7 mock-only) with the 548 tautology count untouched; verify the §5 / v1.3 header / §11 tracker edits are present and internally consistent | — |
| S05 | `code-review-final-impl` | Global cross-agent review: all 78 baseline entries are addressed; the baseline file contains 0 `no-assert` + 0 `mock-only` + 548 `tautology`; no production code outside `tests/**` + `tests/assertion_free_baseline.txt` + `ai-dev/work/TESTS_ENHANCEMENT.md` was touched; `make test-assertions` passes against the shrunken baseline; tracker edits consistent across §5 + header + §11 | — |
| S06 | `qv-gate` (`lint`) | `make lint` | — |
| S07 | `qv-gate` (`assertions`) | `make test-assertions` — the regression-net signal. Must pass because the baseline has been shrunk by exactly the entries addressed, so no NEW violations appear. | — |
| S08 | `qv-gate` (`format`) | `make format-check` | — |
| S09 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S10 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S11 | `qv-gate` (`integration-tests`) | `make allure-integration` | — |
| S12 | `qv-gate` (`diff-coverage`) | `make diff-coverage` | — |
| S13 | `qv-gate` (`security-secrets`) | `make security-secrets` — gitleaks (no secrets expected; tests-only change) | — |
| S14 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project has `self_assess = true`) | — |

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
- `browser_verification` = **false** (no UI surface; tests-only change).

## File Manifest

All files for this work item live under `ai-dev/active/CR-00081/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00081_CR_Design.md` | Design | This document |
| `CR-00081_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the daemon |
| `prompts/CR-00081_S01_Tests_prompt.md` | Prompt | S01 instructions (strengthen 71 `no-assert` entries) |
| `prompts/CR-00081_S02_Tests_prompt.md` | Prompt | S02 instructions (strengthen 7 `mock-only` entries + baseline + tracker) |
| `prompts/CR-00081_S03_CodeReview_prompt.md` | Prompt | S03 code-review instructions for S01 |
| `prompts/CR-00081_S04_CodeReview_prompt.md` | Prompt | S04 code-review instructions for S02 |
| `prompts/CR-00081_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent review instructions |
| `prompts/CR-00081_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess instructions |

(S06–S13 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00081/reports/`.

## Acceptance Criteria

### AC1: Baseline `no-assert` and `mock-only` entries fully addressed

```
Given the baseline state at CR open: tests/assertion_free_baseline.txt contains 71 entries with `# no-assert` and 7 entries with `# mock-only`
When S01 and S02 have completed and S02 has re-run `uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/`
Then `grep -c '# no-assert$' tests/assertion_free_baseline.txt` returns 0
And `grep -c '# mock-only$' tests/assertion_free_baseline.txt` returns 0
And `grep -c '# tautology$' tests/assertion_free_baseline.txt` returns 548 (the tautology set is explicitly untouched)
And `grep -c '^tests/' tests/assertion_free_baseline.txt` returns ~548 (down from 626; the exact number depends on whether any rare DELETE actions also coincidentally removed a tautology-bucket test from the scanner's input — the no-assert/mock-only counts being 0 is the load-bearing assertion)
```

### AC2: Strengthened tests carry real, behaviour-pinning assertions

```
Given S01/S02 have STRENGTHENED or CONVERTED a test that was previously listed in the baseline
When a reviewer reads the test body
Then the test contains at least one assertion that would fail if the specific production-code line it ostensibly covers were regressed (the mutation-test heuristic in `skills/iw-ai-core-testing/SKILL.md` §0)
And the assertion is NOT `assert True`, `assert obj is obj`, `assert <constant> == <constant>`, or any other tautology
And the assertion is NOT a `mock.assert_called_*` / `mock.call_args` check on its own (a converted test may keep the mock for isolation, but the strengthening assertion must be on a real observable — return value, DB row, or log line via `caplog`)
```

### AC3: Deleted tests have a one-line rationale naming the covering test

```
Given S01/S02 chose DELETE for any in-scope test
When the reviewer reads S01's or S02's step report
Then for every deletion the report records one line of the form: `DELETE tests/<path>::<test_name> — covered by tests/<other_path>::<other_test_name> (one-line reason)`
And no deletion lacks a covering-test reference
```

### AC4: Scope is tests + baseline + plan tracker only

```
Given S01/S02 have completed
When a reviewer inspects the diff against `main`
Then the only files changed live under `tests/**`, OR are exactly `tests/assertion_free_baseline.txt`, OR are exactly `ai-dev/work/TESTS_ENHANCEMENT.md`
And no file under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, `skills/`, or `.claude/skills/` is modified
And no Alembic migration is added or modified
```

### AC5: Plan tracker reflects the cleanup

```
Given S02 has completed its tracker edits
When the reviewer reads `ai-dev/work/TESTS_ENHANCEMENT.md`
Then §5 row `P1-CR-A-followup` records: "78 of 626 baseline entries strengthened in this CR (CR-00081, 2026-05-24); remaining 548 `tautology` entries deferred to future per-module CRs"
And the v1.3 header status block's baseline counts are updated from `626 entries: 71 no-assert / 7 mock-only / 548 tautology` to `~548 entries: 0 no-assert / 0 mock-only / 548 tautology` (with CR-00081 noted)
And §11 has a new changelog entry dated 2026-05-24 describing the 78-entry strengthening, the strengthen/delete/convert split per category, and a one-line forward link from CR-00046's entry
```

### AC6: All QV gates pass

```
Given the daemon launches CR-00081's steps S06–S13
When each gate runs against the patched worktree
Then S06 (lint), S07 (assertions), S08 (format-check), S09 (typecheck), S10 (unit-tests), S11 (integration-tests), S12 (diff-coverage), S13 (security-secrets) all exit 0
And S07 in particular passes WITHOUT requiring a fix cycle — the baseline was shrunk by exactly the entries addressed, so no NEW violations beyond the baseline appear
```

## Rollback Plan

- **Database**: Not applicable (no DB changes).
- **Code**: Revert the squash-merge commit. The 78 strengthened/deleted/converted tests revert to their prior state, the baseline file regains the 71 `no-assert` + 7 `mock-only` entries, and the tracker entries are removed. The `assertions` gate goes back to admitting the original 626-entry baseline.
- **Data**: No data loss possible (tests-only CR).

Partial rollback: if a single strengthened test surfaces an unexpected production-code regression after merge (i.e. the strengthening accidentally caught a real bug that's now blocking CI), file a follow-up Incident, mark that one test with `@pytest.mark.xfail(strict=False, reason="I-NNNNN: …")` as a temporary measure, and keep the rest of this CR's improvements. Do NOT re-add the test to the baseline — once a test has a real assertion, the baseline is the wrong escape hatch.

## Dependencies

- **Depends on**: CR-00046 (the assertion scanner + initial baseline that this CR scrubs)
- **Blocks**: Future per-module follow-up CRs that scrub the 548 `tautology` entries (none filed yet)

## Impacted Paths

- `tests/**`
- `tests/assertion_free_baseline.txt`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is an unusual case: the CR is *itself* about adding real assertions to tests that lack them. There is no separate "test the test" phase. The TDD-RED evidence is the baseline scanner output captured at S01 start (the explicit list of 71 `no-assert` entries) — those entries are by construction tests that cannot currently fail for behaviour reasons. The GREEN evidence is the targeted `uv run pytest tests/<modified_file>::<test_name> -v` run after each strengthening — the test now passes *with* a real assertion (not before, when there was no assertion to evaluate).

- **Unit tests**: None new. Each existing unit test in the in-scope set is either strengthened in place, converted, or deleted.
- **Integration tests**: None new. Same constraint — only existing integration/dashboard tests are edited.
- **Updated tests**: All 71 `no-assert` entries + all 7 `mock-only` entries (78 total, spread across 43 unique test files in `tests/unit/`, `tests/integration/`, `tests/dashboard/`, and `tests/dashboard/browser/`).
- **`tdd_red_evidence` contract**: S01 and S02 record the scanner's pre-edit dump (the in-scope list itself is the RED — these are tests that cannot fail) and, for one representative strengthening per category, the literal assertion line added plus a brief argument for why it would fail against pre-change production code if the covered line were regressed. The S01/S02 reports follow CR-00045's `tdd_red_evidence` format.

## Notes

- **Why this chunk first.** The 71 `no-assert` + 7 `mock-only` entries are 78 of 626 — small enough for a single CR. They are also the categorically *worst* baseline entries: a test with zero assertions cannot fail for the right reason, period. The 548 `tautology` entries are equally weak in spirit but much more numerous and frequently need a per-module deep read to fix correctly (the production behaviour they ostensibly cover varies widely). Deferring the tautology bucket to future per-module CRs is an explicit, design-document-recorded decision — not an oversight.
- **Risk: a strengthening surfaces a real bug.** A genuine assertion added to a previously-empty test body can fail not because the test is wrong but because the production code is wrong. If S01 or S02 hits a case where the natural strengthening assertion *fails* against current main, the response is: (a) confirm the failure is a real bug, not a fixture/scaffolding issue; (b) file a follow-up Incident; (c) keep the strengthening but add `@pytest.mark.xfail(strict=False, reason="I-NNNNN: …")` so the gate stays green while the Incident is triaged. Do NOT weaken the assertion to "make it pass" — that would defeat the entire CR.
- **Risk: a strengthening becomes a tautology in disguise.** Reviewers (S03/S04) explicitly check the mutation-test question: "would this test fail if the specific production line it covers regressed?" Examples of *bad* strengthenings to reject: `assert result is not None` when `result` is constructed unconditionally; `assert len(rows) >= 0` (always true); `assert isinstance(x, int)` when the constructor's return type is statically known to be `int`. Examples of *good* strengthenings: `assert result.status == "completed"`; `assert rows[0].batch_id == batch.id`; `assert caplog.records[-1].message.startswith("daemon: picked batch ")`.
- **No production code is touched.** This is enforced by the manifest's `scope.allowed_paths` (only `tests/**`, the baseline file, and the tracker). If S01 or S02 finds that a strengthening *requires* a production-code change (e.g. the production code lacks an observable to assert on), the correct response is DELETE the test (since the surface has no observable) AND raise a blocker so the operator can decide whether to file a separate Feature/CR to add the observable. Do not silently expand scope.
- **Sibling repos.** `tests/assertion_free_baseline.txt` is project-local to `iw-ai-core`. No other project consumes it. Sibling repos (`innoforge`, `cv`, `podforger`) are not affected.
- **No skill/template changes.** The rules for what a "good" assertion looks like already live in `skills/iw-ai-core-testing/SKILL.md`. This CR applies those rules; it does not change them.
