# F-00089: Daemon chaos / fault-injection test layer

**Type**: Feature
**Priority**: High
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this Feature relies on the integration testcontainer (`postgres` Docker image) for the daemon-under-test.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This Feature adds no migrations.** Scenario S06 *simulates* a migration-rebase failure by injecting a conflicting `down_revision` into a throwaway revision file inside the testcontainer's per-worktree migration dir — no live DB schema change. The agent verifies behaviour against `orch/daemon/migration_rebase.py` AS-IS.

## Description

The daemon (`orch/daemon/`) is the riskiest component in IW AI Core: it creates worktrees, launches LLM agents, manages fix cycles, and squash-merges to `main`. A regression in its recovery logic means a half-merged `main`, a poisoned batch, or an item stuck in a terminal-but-not-merged state — and we have **zero deterministic tests** for any of the five documented failure modes today. This Feature adds an `orch.daemon` chaos / fault-injection test layer (new test package `tests/integration/daemon_chaos/`) consisting of a shared harness plus one scenario module per failure mode, then wires a blocking smoke subset on every PR and a full matrix nightly. This is **test-only scope**: zero production code under `orch/daemon/` (or anywhere else) is modified.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. In particular:

- The daemon polls PostgreSQL every 60s, manages worktree lifecycles, and is the *only* component that mutates `main`. Test infrastructure: see `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.
- Hard rule: NEVER connect tests to live DB (port 5433); use testcontainers only.
- Hard rule: `postgresql+psycopg2://` URLs must be rewritten to `postgresql+psycopg://`.
- Hard rule: agents must not apply migrations to the live DB.
- Cross-references: `docs/IW_AI_Core_Daemon_Design.md` (daemon design + state transitions), `docs/IW_AI_Core_Testing_Strategy.md` (current 7 test layers — this Feature adds Layer 9, daemon chaos; F-00088 took Layer 8 / E2E), `ai-dev/work/TESTS_ENHANCEMENT.md` §8 item 4.3 (this Feature), CR-00060 / P2-CR-B (Hypothesis property tests on state machines — this Feature is the runtime complement), CR-00021 (`migration_rebase.py` design + I-00075/76 failure mode), F-00084 (auto-merge resolution hooks — optional integration if landed).

## Scope

### In Scope

- **Test harness** (`tests/integration/daemon_chaos/harness.py` + `tests/integration/daemon_chaos/conftest.py`): a `chaos_daemon` pytest fixture that wraps `orch/daemon/main.py`'s poll loop with deterministic, named injection hooks (monkey-patch / dependency-injection based — NEVER `kill -9`, NEVER random failure). One hook per documented failure mode. Public harness API documented in a module docstring and cross-linked from `skills/iw-ai-core-testing/SKILL.md`.
- **Scenario 1** (`tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py`): worktree setup fails mid-way (e.g. `git worktree add` succeeds, `uv sync` fails). Assert: item → terminal-error state; no zombie worktree dir remains; the batch is not poisoned (sibling items continue picking).
- **Scenario 2** (`tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py`): an item whose CodeReview always fails increments the fix-cycle counter up to the configured cap. Assert: item marked terminal-failed exactly at the cap (never above); no further fix attempts launched; daemon picks next item without crashing. Runtime complement to CR-00060 / P2-CR-B's state-machine invariant.
- **Scenario 3** (`tests/integration/daemon_chaos/test_agent_stall_recovery.py`): an agent's `last_heartbeat` falls past `IW_CORE_STALL_THRESHOLD` (env var, read in `orch/config.py:222`). Assert: daemon detects the stall, terminates the agent process, marks the step `stalled`, and either retries (per the documented stall policy) or transitions to terminal-failed.
- **Scenario 4** (`tests/integration/daemon_chaos/test_squash_merge_conflict.py`): a conflicting commit lands on `main` while the worktree is mid-flight; the daemon's squash-merge step fails cleanly. Assert: merge attempt fails with a recognised error, item marked `merge_failed` (or routes to F-00084 auto-merge hooks if those exist on `main` at execution time — design must work without them), `main` is NOT half-merged.
- **Scenario 5** (`tests/integration/daemon_chaos/test_migration_rebase_failure.py`): inject a conflicting `down_revision` into a throwaway revision file so `orch/daemon/migration_rebase.py` fails the pre-merge rebase step. Assert: rebase detected as failed, item marked `migration_rebase_failed`, no migration applied to the testcontainer's prod-mirror DB, worktree left intact for inspection. Cross-references I-00075/76.
- **Makefile targets** (`Makefile`): `daemon-chaos-smoke` runs S02 + S03 (fastest, broadest coverage — fix-cycle cap and stall recovery exercise the largest fraction of daemon code paths); `daemon-chaos-full` runs all five scenario modules.
- **GitHub Actions** (`.github/workflows/daemon-chaos.yml`): `pull_request` + `push` triggers run `make daemon-chaos-smoke` (blocking); a nightly `schedule: cron` plus `workflow_dispatch` runs `make daemon-chaos-full` (non-blocking, reports via the existing Allure pipeline).
- **Workflow skill update** (`skills/iw-workflow/SKILL.md`, mirrored to `.claude/skills/iw-workflow/SKILL.md`): add `daemon-chaos-smoke` as the **9th canonical QV gate** so future items can opt in. `iw sync-skills --force iw-workflow`.
- **Testing skill update** (`skills/iw-ai-core-testing/SKILL.md`, mirrored to `.claude/skills/iw-ai-core-testing/**`): new section documenting the harness API + a scenario-addition checklist. `iw sync-skills --force iw-ai-core-testing`.
- **Strategy doc** (`docs/IW_AI_Core_Testing_Strategy.md`): §2 adds Layer 9 `tests/integration/daemon_chaos/`; §5 (CI gate matrix) adds two gate rows (smoke + full).
- **Daemon design doc** (`docs/IW_AI_Core_Daemon_Design.md`): cross-link the new test layer from the state-transition section.
- **Tracker** (`ai-dev/work/TESTS_ENHANCEMENT.md`): §8 row 4.3 → DONE; v1.4 header / changelog entry.

### Out of Scope

- **Any production-code change** under `orch/daemon/` or anywhere else. The daemon is exercised AS-IS through the harness's monkey-patch / DI injection hooks. If a scenario surfaces a genuine daemon bug, it is `xfail`-pinned (with a recorded reason) and filed as a separate Incident — same test-only scope discipline as the Phase 3 CRs (CR-00072 / CR-00073 / CR-00074 / CR-00075 / CR-00076 / F-00088).
- **The new `daemon-chaos-smoke` QV gate is not enforced on this Feature's own merge** (a gate cannot gate its own delivery). It applies to *future* work items.
- **F-00084 auto-merge-resolution wire-up** beyond Scenario 4's optional pass-through. Scenario 4 must work whether or not F-00084 is on `main`.
- **Visual / browser verification.** `browser_verification: false`.
- **No new dashboard surface, no new CLI command, no new DB column, no migration.**

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: one cohesive concern per step (one module or closely-related file group). The 5 scenario modules ride on 5 separate steps so the harness API is exercised five times against five distinct daemon code paths — bundling them would defeat the point. The harness step (S01) is the gate that fixes the API shape every later step inherits, so it gets a generous timeout.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Fault-injection harness (`tests/integration/daemon_chaos/harness.py` + `conftest.py`) — `chaos_daemon` fixture, named injection hooks, harness module docstring | — |
| S02 | `backend-impl` | Scenario 1: `test_worktree_setup_mid_failure.py` | — |
| S03 | `backend-impl` | Scenario 2: `test_fix_cycle_cap_exhaustion.py` | — |
| S04 | `backend-impl` | Scenario 3: `test_agent_stall_recovery.py` | — |
| S05 | `backend-impl` | Scenario 4: `test_squash_merge_conflict.py` | — |
| S06 | `backend-impl` | Scenario 5: `test_migration_rebase_failure.py` | — |
| S07 | `backend-impl` | Makefile targets + `.github/workflows/daemon-chaos.yml` + `skills/iw-workflow/SKILL.md` canonical-gate update + `iw sync-skills --force iw-workflow` | — |
| S08 | `backend-impl` | Tracker (`ai-dev/work/TESTS_ENHANCEMENT.md`) v1.4 + strategy doc Layer 9 + daemon-design cross-link + testing-skill harness section + `iw sync-skills --force iw-ai-core-testing` | — |
| S09 | `code-review-impl` | Per-agent CodeReview of S01..S08 (one reviewer, all backend) | — |
| S10 | `code-review-impl` | CodeReview_Final — global cross-step review | — |
| S11 | `qv-gate` | QV: `lint` | — |
| S12 | `qv-gate` | QV: `assertions` | — |
| S13 | `qv-gate` | QV: `format` | — |
| S14 | `qv-gate` | QV: `typecheck` | — |
| S15 | `qv-gate` | QV: `unit-tests` | — |
| S16 | `qv-gate` | QV: `integration-tests` | — |
| S17 | `qv-gate` | QV: `diff-coverage` | — |
| S18 | `qv-gate` | QV: `security-secrets` | — |
| S19 | `self-assess-impl` | SelfAssess (via `iw-item-analyze` skill) | — |

**Total: 19 steps.** All Backend. No Database / API / Frontend / Pipeline / Template steps. No Browser verification (`browser_verification: false`).

S01 carries an extended timeout (3600s) because the harness API is the gate — if its shape is wrong every scenario inherits the wrong shape. S05..S06 each carry 1800s because squash-merge and migration-rebase scenarios drive real git + alembic round-trips inside the testcontainer.

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: Scenario S06 *simulates* migration-rebase failure inside the testcontainer; **no real migration is generated or applied**.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/F-00089/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00089_Feature_Design.md` | Design | This document |
| `F-00089_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00089_S01_Backend_prompt.md` | Prompt | S01 — Fault-injection harness |
| `prompts/F-00089_S02_Backend_prompt.md` | Prompt | S02 — Scenario 1 worktree-setup mid failure |
| `prompts/F-00089_S03_Backend_prompt.md` | Prompt | S03 — Scenario 2 fix-cycle cap exhaustion |
| `prompts/F-00089_S04_Backend_prompt.md` | Prompt | S04 — Scenario 3 agent stall recovery |
| `prompts/F-00089_S05_Backend_prompt.md` | Prompt | S05 — Scenario 4 squash-merge conflict |
| `prompts/F-00089_S06_Backend_prompt.md` | Prompt | S06 — Scenario 5 migration-rebase failure |
| `prompts/F-00089_S07_Backend_prompt.md` | Prompt | S07 — Makefile + GH workflow + workflow-skill canonical-gate update |
| `prompts/F-00089_S08_Backend_prompt.md` | Prompt | S08 — Tracker + strategy doc + daemon-design cross-link + testing-skill update |
| `prompts/F-00089_S09_CodeReview_prompt.md` | Prompt | S09 — Per-agent CodeReview |
| `prompts/F-00089_S10_CodeReview_Final_prompt.md` | Prompt | S10 — Cross-step CodeReview_Final |
| `prompts/F-00089_S19_SelfAssess_prompt.md` | Prompt | S19 — SelfAssess via iw-item-analyze |

(QV gate steps S11..S18 are shell-command gates and do not consume per-step prompt files.)

Reports are created during execution in `ai-dev/work/F-00089/reports/`.

## Acceptance Criteria

### AC1: Harness provides named, deterministic injection hooks

```
Given the chaos_daemon fixture is requested in a test
When the test calls inject_worktree_setup_failure_after_clone(),
     inject_fix_cycle_always_fails(),
     inject_agent_stall_after_seconds(n),
     inject_squash_merge_conflict_on_main(), or
     inject_migration_rebase_conflict_revision()
Then the next iteration of the daemon poll loop deterministically
     triggers exactly that failure mode (no random failure, no kill -9),
     the failure is observable via the testcontainer DB state,
     and the fixture cleans up the injection on test teardown
```

### AC2: Scenario 1 — worktree setup mid-failure → terminal-error, no zombie dir, batch not poisoned

```
Given a batch with three items (A, B, C) and the worktree-setup injection
      armed to fail item A's `uv sync` step
When the chaos_daemon runs one poll cycle and picks item A
Then item A's WorkItem.status transitions to a terminal-error state
     (e.g. `setup_failed` or `failed`) with a non-null `failure_reason`,
     the worktree directory for item A does not exist (or contains a
     `setup_failed.flag` marker but no checked-out source tree),
     and items B and C remain pickable on subsequent poll cycles
     (the batch is not poisoned)
```

### AC3: Scenario 2 — fix-cycle cap exhaustion stops exactly at the cap

```
Given an item whose CodeReview step is injected to always return verdict=fail
      with mandatory_fix_count > 0
When the chaos_daemon advances poll cycles until the fix-cycle counter
     reaches MAX_FIX_CYCLE
Then WorkItem.fix_cycle_count equals MAX_FIX_CYCLE (never MAX_FIX_CYCLE + 1),
     the item's status is a terminal-failed state,
     no further fix attempts are recorded after the cap,
     and the daemon picks the next pickable item on the next poll cycle
     (proving the daemon did not crash or stall)
```

### AC4: Scenario 3 — agent stall is detected, killed, and routed per policy

```
Given an agent step has been running for longer than IW_CORE_STALL_THRESHOLD
      (the test sets a short threshold so the wall-clock cost is bounded)
When the chaos_daemon's stall-detection pass runs
Then the agent process is terminated (PID no longer exists or fixture
     records a "kill called" event),
     the step's status transitions to `stalled`,
     and the item's downstream state matches the documented stall policy
     (either a retry is scheduled or the item transitions to terminal-failed)
```

### AC5: Scenario 4 — squash-merge conflict fails cleanly, `main` not half-merged

```
Given a worktree mid-flight whose change set conflicts with a fresh commit
      written to the testcontainer's `main` branch (the simulated upstream)
When the chaos_daemon attempts the squash-merge for that item
Then the merge attempt returns a recognised git-merge-conflict error,
     the item's WorkItem.status is `merge_failed` (or routes to F-00084's
     auto-merge hook if those are present on `main` at execution time),
     `git status main` reports a clean tree (no half-merged state, no
     leftover MERGE_HEAD), and the conflicting upstream commit is the
     latest commit on `main`
```

### AC6: Scenario 5 — migration-rebase failure marks the item, leaves DB clean

```
Given a worktree carrying a new alembic revision whose down_revision is
      injected to conflict with the testcontainer DB's current head
When the chaos_daemon's migration_rebase pass runs for that item
Then the rebase is recorded as failed (caught exception logged with
     traceback), the item's WorkItem.status is `migration_rebase_failed`,
     the testcontainer DB's alembic_version row is unchanged from before
     the rebase attempt, and the worktree directory is preserved for
     operator inspection (not auto-cleaned)
```

### AC7: Smoke subset runs on every PR; full matrix runs nightly

```
Given the new .github/workflows/daemon-chaos.yml file
When a pull_request or push event fires
Then the `daemon-chaos-smoke` job runs `make daemon-chaos-smoke`
     (which exercises S02 + S03), and a failure of either scenario
     blocks the PR;
And given a nightly schedule event fires
When the workflow runs
Then the `daemon-chaos-full` job runs `make daemon-chaos-full`
     (all 5 scenarios) and its result is reported via the existing
     Allure pipeline (non-blocking on the merge queue)
```

### AC8: Skill + strategy + tracker + daemon-design docs are consistent

```
Given the master skill copies under skills/ and the .claude/skills/ mirrors
When `iw sync-skills --force iw-workflow` and
     `iw sync-skills --force iw-ai-core-testing` complete
Then the canonical QV gate table in skills/iw-workflow/SKILL.md lists
     `daemon-chaos-smoke` as the 9th gate (with its `make daemon-chaos-smoke`
     command and a non-zero exit-code semantics note),
     skills/iw-ai-core-testing/SKILL.md has a new section documenting the
     harness API + a scenario-addition checklist,
     docs/IW_AI_Core_Testing_Strategy.md §2 lists "Layer 9 — Daemon chaos"
     and §5 has two new gate rows (smoke blocking, full nightly),
     docs/IW_AI_Core_Daemon_Design.md cross-links the new test layer
     from its state-transition section,
     and ai-dev/work/TESTS_ENHANCEMENT.md §8 row 4.3 is marked DONE with
     the v1.4 header / changelog entry recording F-00089
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Injection hook armed but no matching poll cycle runs | `inject_*` called, then no poll cycles | Hook is teardown-safe; no leaked monkey-patch across tests |
| Injection hook fires twice | Same `inject_*` called twice before teardown | Second call is idempotent (no double-patch error); only one failure injected per matching daemon action |
| Worktree-setup failure on the very first command (`git worktree add`) | injection point set to `before_git_worktree_add` | Item marked failed; the worktree dir was never created (no cleanup needed); batch siblings still pickable |
| Fix-cycle cap = 1 (degenerate config) | `MAX_FIX_CYCLE=1` | One CodeReview attempt, one fix attempt, terminal-fail at cycle 1; never cycle 2 |
| Stall threshold = 0 | `IW_CORE_STALL_THRESHOLD=0` | All running agents flagged immediately; harness must reject this config or document its behaviour explicitly to prevent flake |
| Squash-merge conflict but `main` is empty | Repo with no `main` commits | Test xfails with a recorded reason — environmental precondition not met |
| Migration-rebase failure when no alembic revision exists | Worktree carries no new revision file | Scenario short-circuits with a `pytest.skip` (no rebase to fail) |
| Two scenarios run back-to-back in the same pytest session | `pytest tests/integration/daemon_chaos/ -v` | Each test's fixture teardown restores all monkey-patches; later tests see a clean daemon module-state |
| Harness used without the testcontainer fixture | `chaos_daemon` requested but no `db_session` upstream | Fixture errors loudly at setup time with a clear message; does NOT silently connect to live DB |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. **Test-only scope.** Across all S01..S08 commits, the diff against `main` contains **zero** modifications to any file outside `scope.allowed_paths`. Enforced by the executor's merge-time scope gate.
2. **No live-DB connection.** No test in `tests/integration/daemon_chaos/**` connects to port 5433; every test uses the testcontainer Postgres via the project's standard fixtures. Enforced by the existing live-DB guard test (`tests/integration/security/`).
3. **Deterministic failure injection.** No test uses `os.kill`, `subprocess.Popen.kill`, `kill -9`, `random.*`, `time.sleep` longer than 5 seconds, or any non-deterministic time source. All injection is via monkey-patch or DI.
4. **No production code change.** `git diff main -- 'orch/**' 'dashboard/**' 'executor/**'` is empty for this Feature's merge.
5. **No `xfail strict=False`.** Any `xfail` introduced by this Feature must be `strict=True` and reference a filed Incident ID.
6. **Cap honoured.** Scenario 2 asserts `fix_cycle_count == MAX_FIX_CYCLE` exactly — never `<` and never `>`.
7. **`main` never half-merged.** Scenario 4 asserts `git status main` is clean after the conflict, with no `MERGE_HEAD` / `ORIG_HEAD` leftovers.
8. **Alembic version unchanged on rebase failure.** Scenario 5 asserts the testcontainer's `alembic_version.version_num` is identical before and after the failed rebase attempt.
9. **Skill sync is committed.** S07 and S08 must include `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/**` in their `files_changed`. The master `skills/**` and the mirror `.claude/skills/**` must agree byte-for-byte (the executor's `iw sync-skills --force` produces this).
10. **The new gate is added to canon but not enforced on this Feature.** `skills/iw-workflow/SKILL.md`'s canonical list grows from 8 to 9 gates, but `workflow-manifest.json` for F-00089 itself uses only the existing 8.

## Dependencies

- **Depends on**: None (leaf — Phase 4 item 4.3 has no prerequisites).
- **Blocks**: None directly. Future Phase 4 items (4.5 self-dashboarding of test health, 4.6 regression-rate tracking) can build on the new gate but do not require it.
- **Optional integration**: If F-00084 (auto-merge resolution) has merged to `main` by the time this Feature executes, Scenario 4 (S05) recognises and accepts the F-00084 routing as a valid pass — but Scenario 4 must also pass cleanly when F-00084 is absent.

## Impacted Paths

```
tests/integration/daemon_chaos/**
Makefile
.github/workflows/daemon-chaos.yml
skills/iw-workflow/SKILL.md
.claude/skills/iw-workflow/SKILL.md
skills/iw-ai-core-testing/SKILL.md
.claude/skills/iw-ai-core-testing/**
docs/IW_AI_Core_Testing_Strategy.md
docs/IW_AI_Core_Daemon_Design.md
ai-dev/work/TESTS_ENHANCEMENT.md
```

These globs populate `WorkItem.impacted_paths` and are mirrored to `workflow-manifest.json:scope.allowed_paths` for the merge-time scope gate. Note: `tests/integration/conftest.py` is intentionally **not** listed — the new chaos package brings its own `conftest.py`; modifying the parent conftest would constitute a cross-cutting test-infrastructure change that warrants a separate item.

## TDD Approach

- **Unit tests**: None added. The harness is exclusively integration-grade (it wraps the real daemon poll loop).
- **Integration tests**: All five scenario modules. Each module's first test must be the **minimal RED case** for its scenario (e.g. for S02: "item must be marked failed when `uv sync` fails" — write the assertion first, prove it fails against the unaltered daemon path *with* the injection armed, then add the harness hook to make it deterministic). Per-step `tdd_red_evidence` must record the captured RED failure line — `AssertionError` only, never `ImportError`/`SyntaxError`/collection error.
- **Edge cases**: Every Boundary Behavior row above is a mandatory test case. Two are explicitly negative (`pytest.skip` and harness-misuse error), three are degenerate-config (cap=1, stall=0, empty main).
- **Negative determinism check**: S01 includes a meta-test (`test_harness_is_deterministic.py`) that runs Scenario 2 ten times in the same pytest session and asserts the same `fix_cycle_count` value every time. This guards against accidental introduction of non-determinism (e.g. via wall-clock sleeps) in later scenarios.

## Notes

- **Why "one scenario per step" and not one mega-Backend step**: Each scenario exercises a different daemon code path with different fixtures and different assertion shapes; bundling them produces a single agent session that has to read the entire `orch/daemon/` package, design five distinct test modules, and run them all in one go — the exact failure mode that exhausted CR-00076 S01's context budget (see `skills/iw-workflow/SKILL.md` line 72). Five small steps are also five small targets for fix-cycles if any scenario surfaces a subtle daemon bug.
- **Why S01 carries a 3600s timeout**: The harness API is the gate. If the `chaos_daemon` fixture's shape is wrong (wrong hook names, wrong cleanup contract, wrong fixture-scope), every later step inherits the bug and burns fix-cycles diagnosing the symptom. Give the agent room to iterate on the API before committing.
- **Why `daemon-chaos-smoke` is not a QV gate on this Feature**: A gate cannot gate its own delivery. The new gate is added to the canonical chain in `skills/iw-workflow/SKILL.md` so it applies to future items, but F-00089's own `workflow-manifest.json` uses only the existing 8 canonical gates.
- **Risk: scenarios accidentally test the test harness instead of the daemon**. Mitigation: every scenario must include at least one positive assertion against a daemon-mutated DB row or a daemon-emitted log line — not just "the injection hook was called". The CodeReview steps (S09, S10) must verify this.
- **Risk: flaky tests due to wall-clock sleeps in the stall scenario**. Mitigation: AC3 explicitly mandates a short `IW_CORE_STALL_THRESHOLD` via fixture override (not `time.sleep`); the meta-test in S01 catches regressions.
- **Decision: do not modify `tests/integration/conftest.py`**. Keeping the chaos package self-contained means future deletions or reorganisations don't ripple into the rest of the integration suite.
- **Decision: GH workflow is its own file** (`daemon-chaos.yml`) rather than extending `test-quality.yml`. Easier to disable the nightly matrix without touching the blocking-PR job.
- **Self-assess**: this project has `self_assess = true` in `projects.toml`, so S19 runs `iw-item-analyze` over the full execution history of F-00089 itself and produces `_self_assess_report.md` + `_self_assess_findings.json`.
