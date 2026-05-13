# CR-00049: Re-enable `pytest-randomly` by default (P1-CR-C-followup-randomly)

**Type**: Change Request
**Priority**: Medium
**Reason**: Cleanup follow-up filed by CR-00048 (merged `a789701`, 2026-05-13). CR-00048 added `pytest-randomly` as a dev dep but had to ship with `-p no:randomly` (off-by-default) per its AC1 escape clause, because `make diff-coverage` surfaced ~50 collection-time `sqla…` errors across 12 integration test modules that 5 fix cycles could not converge. This CR finishes the work — eliminates the order-dependence (or registers each offender with `@pytest.mark.order_dependent`) and removes `-p no:randomly` from `addopts`, so randomisation is default-on going forward.
**Created**: 2026-05-13
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR only touches tests/configs/docs — no new Docker usage. The existing `testcontainers` fixtures in `tests/integration/conftest.py` are the (allowed) exception, and they are themselves the prime suspects for the order-dependence we are cleaning up.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Remove `-p no:randomly` from `pyproject.toml` `[tool.pytest.ini_options] addopts` and end with the full suite green under randomisation across `make test-unit`, `make test-integration`, and `make diff-coverage`. The deliverable is to fix the ~50 order-dependent integration test failures CR-00048's fallback bypassed — by repairing the underlying fixture leaks where reasonable, and quarantining the rest with `@pytest.mark.order_dependent` + `xfail(strict=False)` (the marker is already registered and the quarantine pattern is already proven by `tests/unit/test_browser_env.py:423`).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `tests/CLAUDE.md` for the testing rules (testcontainer-only, `monkeypatch` over `importlib.reload`, FTS DDL hook, `DaemonEvent.event_metadata`, per-worktree-DB caveats). Read `skills/iw-ai-core-testing/SKILL.md` §2/§7 for the current opt-in recipe + cleanup contract this CR satisfies. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-C-followup-randomly` for the captured failure list and §11 changelog entry for the CR-00048 fallback story.

## Current Behavior

`pytest-randomly>=3.15` is installed as a dev dependency but is **off-by-default** via `-p no:randomly` in `pyproject.toml` line 148 `[tool.pytest.ini_options] addopts`. `make test-unit`, `make test-integration`, and `make diff-coverage` all run in deterministic (alphabetical) file order. Running the integration + dashboard suites together under random order — `uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q` — produces ~50 collection-time `sqla…` errors across these 12 modules:

- `tests/integration/test_cli_steps.py`
- `tests/integration/test_dashboard_fragments.py`
- `tests/integration/test_history_sorting.py`
- `tests/integration/test_code_qa_routes.py`
- `tests/integration/test_doc_job_log_endpoints.py`
- `tests/integration/test_step_monitor_lifecycle.py`
- `tests/integration/test_register_persists_dependencies.py`
- `tests/integration/test_invariants_f00060.py`
- `tests/integration/test_phantom_gate_auto_skip.py`
- `tests/integration/test_project_onboarding_api.py`
- `tests/integration/daemon/test_batch_manager_scope_gate.py`
- `tests/integration/dashboard/test_F00077_enqueue_idempotency.py`

The `order_dependent` marker is already registered in `pyproject.toml` line 154. One unit-test (`tests/unit/test_browser_env.py::test_pick_free_offset_returns_hash_offset_when_free`, line 423) is already quarantined with `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False)`. The pattern is established; the work is to apply it (and real fixes) to the 12 modules above.

Docs that describe the off-by-default state and the opt-in recipe: `tests/CLAUDE.md` §7, `docs/IW_AI_Core_Testing_Strategy.md` §3 (subsection) + §9 (gaps table row), `skills/iw-ai-core-testing/SKILL.md` §2 (also synced to `.claude/skills/iw-ai-core-testing/SKILL.md`).

## Desired Behavior

After this CR ships:

- `pyproject.toml` `[tool.pytest.ini_options] addopts` no longer contains `-p no:randomly`. The default invocation is randomised; the per-run seed prints at the top of every pytest run (`Using --randomly-seed=<N>`).
- The integration + dashboard suite collects and runs cleanly under `-p randomly` across at least four seeds (12345, 67890, 11111, 42424). The daemon's S08 (unit-tests), S09 (integration-tests stub), and S10 (diff-coverage) gates pass — S10 in particular is the definitive proof because it re-runs the integration + dashboard suites with coverage.
- Every still-broken test has either been fixed at the fixture-leak level OR registered as `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="…")` with a one-line tracking comment naming the leak source. Quarantines are accepted but each one is filed in `ai-dev/work/TESTS_ENHANCEMENT.md` §5 for incremental cleanup.
- `tests/CLAUDE.md` §7, `docs/IW_AI_Core_Testing_Strategy.md` §3 + §9 row, `skills/iw-ai-core-testing/SKILL.md` §2 are flipped from ⚠️ "off-by-default fallback" to ✅ "default-on, suite robust to randomisation"; the fallback paragraph is moved to an "Earlier fallback (CR-00048)" historical note rather than deleted (so future readers understand the journey).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: §5 row `P1-CR-C-followup-randomly` marked **DONE (CR-00049, YYYY-MM-DD)** with the fix-vs-quarantine counts; item 1.4 flipped from **PARTIAL** → **DONE (CR-00049)**; §11 changelog entry added.
- `.claude/skills/iw-ai-core-testing/SKILL.md` in sync with `skills/iw-ai-core-testing/SKILL.md` (via `iw sync-skills --force iw-ai-core-testing`).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml [tool.pytest.ini_options] addopts` | trailing `-p no:randomly` | `-p no:randomly` removed; comment block above rewritten to drop the fallback paragraph |
| The 12 integration/dashboard test modules listed in *Current Behavior* | ~50 collection-time `sqla…` failures under random order | each test either passes under random order OR carries `@pytest.mark.order_dependent` + `xfail(strict=False, reason=…)` |
| Shared fixtures (`tests/conftest.py` autouse session at line 28; `tests/integration/conftest.py` session-scoped at lines 181 and 192) | hidden ordering dependence — module-import order or autouse interaction leaks state | leak fixed where reasonable; any residual leak documented at the fixture site with a `# NOTE(P1-CR-C-followup-randomly):` comment |
| `tests/CLAUDE.md` §7 | "off-by-default; opt-in recipe; cleanup contract" | "default-on; reproduce recipe; quarantine policy"; the old paragraph moves to an "Earlier fallback (CR-00048)" historical note at the section end |
| `docs/IW_AI_Core_Testing_Strategy.md` §3 + §9 row | ⚠️ rows + fallback paragraph | ✅ rows + "default-on" prose; same historical note pattern |
| `skills/iw-ai-core-testing/SKILL.md` §2 | "currently OFF-by-default" + opt-in recipe | "default-on" + reproduce recipe + quarantine policy |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | mirror of master | re-synced via `iw sync-skills --force iw-ai-core-testing` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §5 follow-up row open, item 1.4 PARTIAL, §11 changelog stops at 2026-05-13 | follow-up row DONE, item 1.4 DONE, new §11 entry for this CR |

### Breaking Changes

**None.** The `addopts` change is internal-only — no API surface, no DB schema, no CLI flag, no daemon contract, no GH Actions workflow shape. CI test commands (`make test-unit`, `make test-integration`, `make diff-coverage`) and daemon QV gate names are unchanged. The only externally observable effect is that pytest output gets one extra line ("`Using --randomly-seed=<N>`") at the top of each run.

### Data Migration

**None.** No DB tables, no rows, no migrations touched.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | RED-first reproduce → triage → fix-or-quarantine each of the ~50 offenders → remove `-p no:randomly` from addopts → update docs/plan/skills → `iw sync-skills` → `make quality` | — |
| S02 | `code-review-impl` | Review S01: order-dependent failures genuinely fixed (test-isolation only, no behavioural changes) or correctly quarantined with marker + xfail + tracking comment; `-p no:randomly` removed; doc/plan/skill updates correct (no stale fallback prose); `iw sync-skills` ran; no out-of-scope edits | — |
| S03 | `code-review-final-impl` | Global review: suite robust to randomisation across all 4 seeds in unit + integration + diff-coverage; quarantine count reasonable with each offender having a one-line tracking comment + filed follow-up row if any sub-cleanup remains; `make check` passes; no scope creep | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` — **now with `pytest-randomly` default-on** | — |
| S09 | `qv-gate` (`integration-tests`) | `make allure-integration` | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` — the gate that previously burned 5 cycles on CR-00048 | — |
| S11 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project has `self_assess = true`) | — |

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

All files for this work item live under `ai-dev/active/CR-00049/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00049_CR_Design.md` | Design | This document |
| `CR-00049_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the daemon |
| `prompts/CR-00049_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00049_S02_CodeReview_prompt.md` | Prompt | S02 code-review instructions |
| `prompts/CR-00049_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review instructions |
| `prompts/CR-00049_S11_SelfAssess_prompt.md` | Prompt | S11 self-assess instructions |

(S04–S10 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00049/reports/`.

## Acceptance Criteria

### AC1: `pytest-randomly` is default-on and the suite is robust to it

```
Given pyproject.toml [tool.pytest.ini_options] addopts contains NO occurrence of "no:randomly"
And pytest-randomly>=3.15 remains in [dependency-groups] dev (unchanged from CR-00048)
When `make test-unit` is run
And `make test-integration` is run
And `make diff-coverage` is run
Then each run prints "Using --randomly-seed=<N>" at the top (proof pytest-randomly is active)
And each run exits 0 with no collection-time errors
And each run is reproducible via `pytest -p randomly --randomly-seed=<N>` (idempotent under the same seed)
```

### AC2: The 12 affected modules are fixed or correctly quarantined

```
Given the failure list captured in this CR's "Current Behavior" section
When the bounded reproduction recipe is run (4 seeds: 12345, 67890, 11111, 42424) against tests/integration/ + tests/dashboard/
Then every previously-failing test either passes (the leak was fixed) OR carries:
  - `@pytest.mark.order_dependent` (marker already registered in pyproject.toml line 154)
  - `@pytest.mark.xfail(strict=False, reason="<one-line explanation pointing to the leak source>")`
  - A `# NOTE(P1-CR-C-followup-randomly):` tracking comment naming the suspected leak source
And no test is "ignored" via skip-without-reason or commented out
```

### AC3: Documentation flipped and follow-up row closed

```
Given S01 changed addopts
When the reviewer reads tests/CLAUDE.md §7, docs/IW_AI_Core_Testing_Strategy.md §3 + §9 row, skills/iw-ai-core-testing/SKILL.md §2
Then each describes: pytest-randomly is default-on; the per-run seed is printed; `pytest -p no:randomly` (or `--randomly-dont-shuffle`) disables it ad-hoc; `pytest --randomly-seed=<N>` reproduces; the quarantine policy
And the §9 gap-table row reads "✅ (CR-00049, YYYY-MM-DD)" instead of ⚠️
And the previous fallback prose is preserved as a brief historical note ("Earlier fallback (CR-00048): …") rather than being silently deleted
And `.claude/skills/iw-ai-core-testing/SKILL.md` matches `skills/iw-ai-core-testing/SKILL.md` byte-for-byte (verifies iw sync-skills ran)
```

### AC4: Plan + changelog updated

```
Given S01 finished its edits
When the reviewer reads ai-dev/work/TESTS_ENHANCEMENT.md
Then §5 row "P1-CR-C-followup-randomly" is marked DONE (CR-00049, YYYY-MM-DD) with the fix-vs-quarantine counts
And item 1.4 (`pytest-randomly` as default) is flipped from PARTIAL → DONE (CR-00049) with a one-liner naming what changed
And §11 has a new changelog entry dated YYYY-MM-DD describing: which leaks were fixed, how many tests were quarantined, which seeds passed, and a one-line link forward from CR-00048's entry
```

### AC5: All QV gates pass

```
Given the daemon launches CR-00049's steps S04–S10
When each gate runs against the patched worktree
Then S04 (lint), S05 (assertions), S06 (format-check), S07 (typecheck), S08 (test-unit), S09 (integration-tests stub), S10 (diff-coverage) all exit 0
And S10 in particular passes WITHOUT requiring any fix cycle — the seed used by the daemon (whichever seed pytest-randomly chose) finds zero order-dependent failures
```

## Rollback Plan

- **Database**: Not applicable (no DB changes).
- **Code**: Revert the squash-merge commit. The `addopts` line goes back to including `-p no:randomly`, the quarantines are removed, and the docs revert to the off-by-default prose. CR-00048's fallback state is restored exactly.
- **Data**: No data loss possible (tests-only CR).

A partial rollback path also exists if a previously-unknown order-dependent test is discovered post-merge in CI: add `-p no:randomly` back to `addopts` via a hotfix commit (1-line change), file a fresh follow-up, and keep the rest of this CR's quarantines. This degrades to CR-00048's known-good state without losing the fixture-leak fixes.

## Dependencies

- **Depends on**: CR-00048 (merged 2026-05-13 — installed the dep, added the marker, established the quarantine pattern, and applied the fallback this CR removes)
- **Blocks**: None (no downstream items wait on this; future items just get higher-fidelity test runs once it lands)

## Impacted Paths

- `pyproject.toml`
- `tests/**`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **RED-first** evidence is the failing reproduction itself: `uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q` — capture the failing module list + counts + first few stack traces. S01 records this verbatim into `tdd_red_evidence` per CR-00045's contract.
- **Unit tests**: None new. Any unit-test changes are limited to test-isolation fixes inside existing tests (e.g., adding a `monkeypatch.delenv`, scoping a `patch.dict`, draining a leaked module-global, or adding the quarantine marker). No new unit-test files.
- **Integration tests**: None new. Same constraint — only existing tests are edited.
- **Updated tests**: Up to ~50 tests across the 12 modules listed in *Current Behavior*. Edits are test-side only (no production code touched).
- **GREEN evidence** is the four-seed sweep: rerunning the same reproduction recipe with seeds 12345, 67890, 11111, 42424 (or letting the daemon's S08 and S10 supply their own seeds) — each exits 0.

## Notes

- **Risk: convergence loop.** CR-00048 burned 5 fix cycles on this exact problem. To prevent a repeat, S01 carries an extended timeout (≈2400 s — same as CR-00048's S01) and is **authorised by AC2 to quarantine** anything that resists a fixture-level fix within budget. The acceptance bar is not "zero quarantines" — it is "addopts no longer carries `-p no:randomly` AND every still-broken test has a marker + xfail + tracking comment." This is the explicit pressure-relief valve CR-00048's design named.
- **Sequencing under thrashing.** If S01 finds the leak originates in one of the session-scoped fixtures (`tests/conftest.py` line 28, `tests/integration/conftest.py` lines 181/192) and a single fixture fix cascades through many of the 12 modules, S01 should land the fixture fix first, re-run the recipe, and only quarantine offenders that survive the fixture fix. This avoids over-quarantining.
- **Why CR-00048 missed this.** S01 of CR-00048 ran its bounded multi-seed sweep using `make test-unit` 3× + `make test-integration` 1× (which today is a no-op stub) — neither hit `make diff-coverage`'s combined integration + dashboard invocation. The failure surfaced only at the QV gate. Two corrective lessons baked into this CR's S01 prompt: (a) always reproduce with the exact `diff-coverage` invocation, not just `test-unit`; (b) the `make allure-integration` stub being a no-op is tracked separately as P1-CR-E and is not in this CR's scope.
- **Sibling repos** (`iw-doc-plan`/`podforger`/`cv`) pick up the new state only when their next `iw sync-skills` is run — that's out of scope here.
