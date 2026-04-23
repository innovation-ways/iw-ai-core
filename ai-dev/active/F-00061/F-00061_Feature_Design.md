# F-00061: Baseline QV gates to prevent fix-cycle scope expansion

**Type**: Feature
**Priority**: High
**Created**: 2026-04-23
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

The daemon records a per-gate failure fingerprint (lint findings, failing pytest nodeids, mypy errors) by running each QV gate against the branch's base SHA at worktree-setup time, persists it in a new `qv_baselines` table, and subtracts the baseline from the HEAD failure set before deciding pass/fail and before composing the fix-cycle prompt. Pre-existing failures — the category that caused I-00034's 30-file scope blowout on 2026-04-22 — become invisible to the fix-cycle so there is nothing for it to drive-by "fix". Bundles unit-test coverage for `executor/scope_gate.py`, the P1 helper that landed without tests in commit `42feca2`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Daemon architecture is in `docs/IW_AI_Core_Daemon_Design.md`. This feature modifies the worktree-setup hook path and the fix-cycle trigger path — both in `orch/daemon/`. Data model conventions: `orch/db/models.py`; migration convention: `orch/db/migrations/versions/<uuid>_<snake_case>.py`. The P1 scope gate this feature builds on top of lives at `executor/scope_gate.py` + `executor/worktree_commit.sh` Step 2.25.

## Scope

### In Scope

- New model `QvBaseline` (one row per `(workflow_step, gate_name, base_sha)`) with Alembic migration
- New module `orch/daemon/qv_baseline.py` containing pure functions:
  - per-gate stdout/stderr parsers (ruff, pytest, mypy) → canonical failure fingerprints
  - `compute_baseline(worktree_path, gate_spec) -> Fingerprint` — runs the gate's command against the worktree (which is already at base SHA at setup time)
  - `subtract(current: Fingerprint, baseline: Fingerprint) -> Fingerprint` — returns only NEW failures
- Worktree-setup hook in `orch/daemon/batch_manager.py` that enumerates the work item's QV gates (from `workflow-manifest.json`), runs each against the base SHA once, and persists the resulting baseline rows
- Subtraction integration in `orch/daemon/fix_cycle.py:_get_qv_findings()` so the fix-cycle prompt's "Errors to Fix" section contains only the delta
- Kill switch `IW_CORE_BASELINE_QV` env var + `DaemonConfig.baseline_qv_enabled` field; `false` disables all new behavior (legacy path)
- Rebase invalidation: when a gate runs, if the item's current base SHA differs from the stored baseline's `base_sha`, the stale baseline is deleted and recomputed lazily before subtraction
- Legacy fallback: items whose worktree was set up before F-00061 shipped have no baseline rows — legacy path applies (no subtraction)
- **Bundled P1 coverage**: unit tests for `executor/scope_gate.py` covering all seven AC7 cases

### Out of Scope

- Changes to `qv-gate` step execution itself (only finding extraction and fix-cycle prompt content change)
- Dashboard UI for inspecting baselines (future enhancement)
- Cross-project baseline sharing (baselines are per `workflow_step`)
- Per-rule / per-test waiver metadata beyond the raw fingerprint
- Changes to `executor/scope_gate.py` logic (tests only)
- Changes to any layer outside `orch/daemon/`, `orch/db/`, `orch/config.py` (no API, no dashboard, no frontend)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `QvBaseline` ORM model in `orch/db/models.py` + Alembic migration under `orch/db/migrations/versions/<uuid>_add_qv_baselines.py`. Composite unique constraint on `(step_id, gate_name, base_sha)`. FK to `workflow_steps(id)` ON DELETE CASCADE. Downgrade must drop table cleanly. | — |
| S02 | code-review-impl | Review S01: model fields match AC3 schema; migration up/down are idempotent; unique constraint + FK cascade correct; no schema changes elsewhere. | — |
| S03 | backend-impl | New pure module `orch/daemon/qv_baseline.py` — parsers, fingerprint dataclasses, `compute_baseline`, `subtract`. No DB calls, no subprocess orchestration beyond the gate's own command. Add `IW_CORE_BASELINE_QV` env var to `orch/config.py` and `baseline_qv_enabled: bool` to `DaemonConfig`. | — |
| S04 | code-review-impl | Review S03: parser correctness against real ruff/pytest/mypy output samples; fingerprint determinism (same failures → same fingerprint regardless of iteration order); subtraction algebra (identity, idempotence, delta); config wiring matches existing `IW_CORE_*` pattern. | — |
| S05 | backend-impl | Integration: (a) in `orch/daemon/batch_manager.py`, after `_setup_worktree()` and before `_launch_next_step()`, invoke baseline computation for each QV gate declared in the manifest and persist rows; (b) in `orch/daemon/fix_cycle.py:_get_qv_findings()`, look up baseline for `(step_id, gate_name, current base_sha)`, parse current gate log, subtract, feed subtracted failures to the prompt builder; (c) detect stale baseline (base_sha mismatch) and recompute lazily; (d) honor `baseline_qv_enabled=False`. | — |
| S06 | code-review-impl | Review S05: hook placement correct (baseline compute runs exactly once per setup); subtraction happens in the correct method and replaces — not augments — the legacy finding path; rebase invalidation works end-to-end; kill-switch fully short-circuits; no changes to `fix_cycle.py` control flow outside the declared hook; no unintended effects on non-QV steps. | — |
| S07 | tests-impl | Unit tests `tests/unit/orch/daemon/test_qv_baseline.py` — one class per parser (ruff/pytest/mypy) with representative-output fixtures, fingerprint determinism, subtraction algebra, and parser error-handling. Integration tests `tests/integration/daemon/test_baseline_qv_pipeline.py` — AC1 (pre-existing excluded), AC2 (regression surfaced cleanly), AC3 (baseline rows created at setup), AC4 (rebase invalidation), AC5 (kill switch), AC6 (legacy items without baseline). Bundled `tests/unit/executor/test_scope_gate.py` — AC7 covering legacy mode, exact paths, `dir/**`, fnmatch wildcards, implicit `ai-dev/active/<ID>/**` allows, violation listing, malformed manifest (rc=2). | — |
| S08 | code-review-impl | Review S07: every AC mapped to a test; testcontainer compliance (no `postgres:5433` writes); fixture reuse per `tests/CLAUDE.md`; tests fail on pre-fix code (RED) and pass on fixed code (GREEN); no `importlib.reload(orch.config)`. | — |
| S09 | code-review-final-impl | Global cross-agent review: AC1–AC7 coverage, scope discipline matches `workflow-manifest.json` `scope.allowed_paths`, no regressions to `fix_cycle.py` outside the one hook, no daemon changes beyond declared, CLAUDE.md compliance, no unintended changes outside `scope.allowed_paths`. | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `uv run ruff format --check .` | — |
| S12 | qv-gate | `uv run mypy orch/ dashboard/` | — |
| S13 | qv-gate | `make test-unit` | — |
| S14 | qv-gate | `make test-integration` (timeout 900s) | — |

No qv-browser step — backend-only feature.

### Database Changes

- **New tables**: `qv_baselines`
  - `id BIGINT PK`
  - `step_id BIGINT NOT NULL` — FK `workflow_steps(id)` ON DELETE CASCADE
  - `gate_name TEXT NOT NULL` — matches `WorkflowStep.gate` (e.g. `"lint"`, `"unit-tests"`)
  - `base_sha TEXT NOT NULL` — the git SHA the gate was evaluated against
  - `fingerprint JSONB NOT NULL` — canonical failure set (schema per parser; see §TDD Approach)
  - `computed_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE (step_id, gate_name, base_sha)`
- **Modified tables**: None
- **Migration notes**: straight additive. Up creates the table; down drops it. `iw_core_baseline` revision marker in the docstring so the migration pipeline recognises it as F-00061-owned. The daemon's `run_pre_merge_dry_run()` will exercise the migration on a testcontainer before main merge.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None

## File Manifest

All files for this work item live under `ai-dev/active/F-00061/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00061_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions + `scope.allowed_paths` for orchestrator |
| `prompts/F-00061_S01_Database_prompt.md` | Prompt | S01 (model + migration) |
| `prompts/F-00061_S02_CodeReview_Database_prompt.md` | Prompt | S02 review of S01 |
| `prompts/F-00061_S03_Backend_QvBaseline_prompt.md` | Prompt | S03 pure module + config |
| `prompts/F-00061_S04_CodeReview_Backend_QvBaseline_prompt.md` | Prompt | S04 review of S03 |
| `prompts/F-00061_S05_Backend_Integration_prompt.md` | Prompt | S05 daemon hook + fix-cycle integration |
| `prompts/F-00061_S06_CodeReview_Backend_Integration_prompt.md` | Prompt | S06 review of S05 |
| `prompts/F-00061_S07_Tests_prompt.md` | Prompt | S07 full test suite (incl. bundled scope_gate.py tests) |
| `prompts/F-00061_S08_CodeReview_Tests_prompt.md` | Prompt | S08 review of S07 |
| `prompts/F-00061_S09_CodeReview_Final_prompt.md` | Prompt | S09 global review |

Production files this feature creates or modifies:

| File | Change | Notes |
|------|--------|-------|
| `orch/db/models.py` | modify | Add `QvBaseline` class |
| `orch/db/migrations/versions/<uuid>_add_qv_baselines.py` | create | Alembic migration (file name auto-generated by `alembic revision --autogenerate`) |
| `orch/daemon/qv_baseline.py` | create | Pure module: parsers, fingerprint dataclass, `compute_baseline`, `subtract` |
| `orch/daemon/batch_manager.py` | modify | Baseline-compute hook after `_setup_worktree()` |
| `orch/daemon/fix_cycle.py` | modify | Subtraction in `_get_qv_findings()` |
| `orch/config.py` | modify | `IW_CORE_BASELINE_QV` + `DaemonConfig.baseline_qv_enabled` |
| `tests/unit/orch/daemon/test_qv_baseline.py` | create | Parser + algebra unit tests |
| `tests/integration/daemon/test_baseline_qv_pipeline.py` | create | End-to-end pipeline tests |
| `tests/unit/executor/test_scope_gate.py` | create | Bundled P1 scope gate tests (AC7) |

Note: the test directories above are created implicitly when the test files are written. No `__init__.py` package markers are added — pytest's rootdir-based discovery handles nested namespace-style directories fine, matching the pattern in existing nested test dirs like `tests/integration/api/`.

Reports are created during execution in `ai-dev/active/F-00061/reports/`.

## Acceptance Criteria

### AC1: Pre-existing failures are excluded from the fix-cycle

```
Given the branch's base SHA has the unit test `tests/unit/foo::test_flaky` failing
And the baseline for (step=S13, gate="unit-tests", base_sha=<base>) is stored
When the S13 unit-tests gate runs on HEAD, where `tests/unit/foo::test_flaky` still fails
 and no other test fails
Then the gate is recorded as `pass` (no new failures relative to baseline)
 And no fix-cycle is triggered for S13
```

### AC2: Genuine regressions are surfaced cleanly

```
Given the baseline for S13 contains `tests/unit/foo::test_flaky`
When the S13 gate runs on HEAD where `tests/unit/foo::test_flaky` is still failing
 and `tests/unit/bar::test_new_regression` is additionally failing
Then the gate is recorded as `fail`
 And the fix-cycle prompt's "Errors to Fix" section contains `tests/unit/bar::test_new_regression`
 And the fix-cycle prompt's "Errors to Fix" section does NOT mention `tests/unit/foo::test_flaky`
```

### AC3: Baselines are computed at worktree setup

```
Given a new work item X is approved with QV gates {S10 lint, S13 unit-tests, S14 integration-tests}
And the daemon provisions the worktree at base SHA Y
When worktree setup completes successfully
Then exactly three `qv_baselines` rows exist with (step_id in X's S10/S13/S14, base_sha=Y)
 And each row's `fingerprint` is the parsed failure set from running that gate's command at base SHA Y
```

### AC4: Rebase invalidates the baseline

```
Given a baseline row exists for (step=S13, gate="unit-tests", base_sha=Y)
When the branch is rebased and the daemon observes current base SHA is Z (≠ Y)
 And S13 is about to run on HEAD
Then the stale baseline row for Y is deleted
 And a fresh baseline is computed against Z and persisted
 And the subtraction applied to S13's run uses the Z baseline
```

### AC5: Kill switch disables all new behavior

```
Given `IW_CORE_BASELINE_QV=false` in the daemon's environment
When the daemon provisions a worktree and later runs a QV gate
Then no `qv_baselines` rows are created at setup
 And `_get_qv_findings()` returns the raw failure set (no subtraction)
 And legacy fix-cycle behavior applies
```

### AC6: Legacy items fall back gracefully

```
Given a work item whose worktree was provisioned before F-00061 shipped
  (so no `qv_baselines` rows exist for any of its steps)
When a QV gate runs for that item
Then no error is raised
 And the fix-cycle prompt contains the raw (unsubtracted) failure set
 And no new baseline row is created retroactively for the legacy item
```

### AC7: `executor/scope_gate.py` is covered by unit tests

```
Given the P1 helper at executor/scope_gate.py (landed in commit 42feca2 without tests)
When F-00061 merges
Then `tests/unit/executor/test_scope_gate.py` exists and passes
 And its cases cover, at minimum:
   - legacy mode (empty scope.allowed_paths → rc=0, no violations)
   - exact path match
   - `dir/**` prefix glob
   - fnmatch single-level wildcard (e.g. `dir/*.py`)
   - implicit `ai-dev/active/<ITEM_ID>/**` allows
   - implicit `ai-dev/archive/<ITEM_ID>/**` allows
   - violation listing (rc=1, stdout contains the offending paths)
   - malformed manifest (rc=2)
 And each case is an independent test function with a clear name
```

## Boundary Behavior

Every row below becomes a mandatory test case in S07.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Baseline gate times out or crashes at setup | Gate's command exceeds timeout budget or raises | Per-gate fail-soft: WARNING log (`[F-00061]` prefix, gate name, exception summary), no partial `qv_baselines` row is persisted, setup continues with the remaining gates. The affected gate falls through to legacy behaviour later (AC6 path — missing row = no subtraction) until a subsequent run recomputes its baseline. |
| Baseline gate passes on base | All gate failures set is empty on base | `fingerprint={"failures": []}` row is still persisted (sentinel); subtraction treats missing row differently from empty row |
| Parser encounters unexpected output | Gate emits output the parser can't classify | Parser logs a warning and returns the raw output as a single opaque "unparseable" failure entry; subtraction treats unparseable entries as never-matching (so they always surface as new) |
| Same failure on different line number | Base has `E501 dashboard/app.py:100`, HEAD has `E501 dashboard/app.py:200` | Fingerprint normalizes on `(file, rule)` — both entries collide, subtraction treats as pre-existing (excluded) |
| Same test fails with different error message | Base and HEAD both have `test_foo` failing, but error strings differ | Fingerprint uses pytest nodeid only — both entries collide, subtraction treats as pre-existing |
| Kill switch toggled mid-run | Baselines computed with flag on, flag turned off before gate runs | Subtraction is skipped (legacy path); stored baselines remain for observability but are not consulted |
| Rebase happens while gate is running | Base SHA changes during gate subprocess | Subtraction uses the baseline that matched the SHA at gate start; next gate run observes the new base and recomputes |
| Zero configured gates | Work item has no `qv-gate` steps | No baseline rows are created; no errors raised |
| Gate spec has no `command` field | e.g. `qv-browser` step | Skipped — baselines only apply to qv-gate steps with a declared `command` |

## Invariants

1. At most one `qv_baselines` row exists per `(step_id, gate_name, base_sha)` (enforced by unique constraint).
2. When `baseline_qv_enabled=False`, `qv_baselines` is never read or written by this feature's code paths.
3. Baseline subtraction is monotonic: `subtract(H, B) ⊆ H` for any fingerprints H, B.
4. Subtraction preserves ordering: the order of failures in the fix-cycle prompt matches the order in the gate's current run output, with pre-existing ones removed in place.
5. A missing baseline row is semantically distinct from an empty baseline row: missing → legacy path (no subtraction); empty → subtraction runs with `B=∅` so every current failure surfaces.
6. Parser determinism: running the same parser on the same input twice yields byte-identical JSON fingerprints (stable sort on failure identifiers).
7. `QvBaseline` rows are deleted when their parent `WorkflowStep` is deleted (FK CASCADE).
8. The `executor/scope_gate.py` helper's behavior is unchanged by this feature — tests only.

## Dependencies

- **Depends on**: P1 scope gate (commit `42feca2` on main, already landed — required for AC7's test subject to exist)
- **Blocks**: None currently. Future dashboard visibility of baselines (P5, not filed) would depend on this.

## TDD Approach

- **Unit tests** (`tests/unit/orch/daemon/test_qv_baseline.py`):
  - Per-parser fixture classes: `TestRuffParser`, `TestPytestParser`, `TestMypyParser`
    - Happy path: parse a representative gate log → expected fingerprint
    - Normalization: same failure with different line numbers / error messages collapses per the Boundary Behavior table
    - Determinism: parse same input twice → identical fingerprint (byte equality)
    - Unparseable: unexpected input → opaque entry, warning logged
  - `TestSubtract`:
    - Identity: `subtract(H, ∅) == H`
    - Full overlap: `subtract(H, H) == ∅`
    - Partial overlap: `subtract({a,b,c}, {a}) == {b,c}` preserving order
    - Monotonicity invariant check (property-style)

- **Unit tests** (`tests/unit/executor/test_scope_gate.py`, bundled P1 coverage for AC7):
  - `TestLegacyMode`: manifest without `scope.allowed_paths` → rc=0, no output
  - `TestExactPath`: exact match allows, anything else blocks
  - `TestDirStarStar`: `dashboard/routers/**` allows nested paths, blocks siblings
  - `TestFnmatchWildcard`: `dir/*.py` allows top-level .py, blocks nested, blocks .js
  - `TestImplicitActiveAllow`: `ai-dev/active/<ID>/**` implicitly allowed without declaration
  - `TestImplicitArchiveAllow`: `ai-dev/archive/<ID>/**` implicitly allowed without declaration
  - `TestViolationListing`: rc=1 with violating paths on stdout in input order
  - `TestMalformedManifest`: unreadable / invalid JSON → rc=2

- **Integration tests** (`tests/integration/daemon/test_baseline_qv_pipeline.py`):
  - `test_ac1_pre_existing_failure_excluded` — seed a work item + workflow step for gate="unit-tests"; seed baseline with failure F; run fake gate output containing only F; assert fix-cycle prompt content has no findings; gate recorded as pass.
  - `test_ac2_regression_surfaced_cleanly` — same setup; run fake gate output with F + G; assert prompt contains G only.
  - `test_ac3_baselines_created_at_setup` — provision a work item via the real setup hook (in-memory daemon); count `qv_baselines` rows; assert one per QV gate with matching base_sha.
  - `test_ac4_rebase_invalidates` — seed baseline at SHA Y; move branch HEAD to SHA Z; trigger gate; assert baseline row at Y is deleted and new row at Z exists with correct fingerprint.
  - `test_ac5_kill_switch_disables` — set `IW_CORE_BASELINE_QV=false`; provision; assert zero rows and raw findings pass through.
  - `test_ac6_legacy_item_graceful` — delete any baseline rows for a pre-existing item; run gate; assert no error, legacy path used.

- **Edge cases**: every Boundary Behavior row has a corresponding test in either the unit or integration suite as appropriate.

- **Testcontainer compliance**: integration tests use `db_session` from `tests/integration/conftest.py` (real PostgreSQL via testcontainer). No live DB writes. No `importlib.reload(orch.config)` — use `monkeypatch.setenv` / `monkeypatch.delenv`.

## Notes

- **Fingerprint schema** — each parser produces a sorted list of canonical identifiers: ruff → `[{"file": ..., "rule": ...}, ...]`; pytest → `[{"nodeid": ...}, ...]`; mypy → `[{"file": ..., "code": ...}, ...]`. Line numbers and error messages are deliberately excluded from the identifier so code drift between base and HEAD doesn't spuriously "invalidate" the match. Normalization rationale is documented per the Boundary Behavior table.

- **Format gate is intentionally excluded from `GATE_PARSERS`** — `ruff format --check` emits `Would reformat: <file>` lines whose shape is incompatible with `parse_ruff` (which targets `ruff check` output: `<file>:<line>:<col>: <rule> <msg>`). Piping format output through `parse_ruff` would route every finding to `unparseable`, which always surfaces in the delta, breaking AC1 for S11. Treating "format" as an unknown gate means S05's subtraction path falls through to legacy behaviour for S11 — acceptable because `ruff format --check` is all-or-nothing against a fully-formatted codebase, so pre-existing format drift is typically zero and the scope-expansion risk F-00061 addresses doesn't materialise for this gate. A future CR could add a dedicated `parse_ruff_format` parser if that calculus changes.

- **Rebase invalidation is lazy**, not eager. The daemon does not watch for base-SHA changes; the next gate execution observes the mismatch and recomputes. This avoids a second orchestration path and keeps rebase/merge flows simple. Cost: one extra gate run whenever a rebase happens right before a gate, which is rare in practice.

- **Kill switch defaults to ON after merge** (`IW_CORE_BASELINE_QV=true` by default). Legacy items (no rows) fall through to pre-feature behavior automatically (AC6), so the rollout is backward-safe. An operator can flip it off instantly if the feature misbehaves.

- **Why bundle scope_gate.py tests here** — the P1 helper at `executor/scope_gate.py` landed in commit `42feca2` without tests. F-00061 is the natural home for that coverage because (a) the QV gate surface is already being heavily tested here, so fixtures and patterns carry over, and (b) P1 and P2 are conceptually the same defensive layer. Keeping scope changes to `executor/scope_gate.py` itself out of scope (tests only) means the P1 behavior is frozen during F-00061 and can be audited independently.

- **Retrospective linkage** — the precedent for this feature is the 2026-04-22 I-00034 merge: S06 lint fix-cycle fixed pre-existing E501 + ARG001 in `project_pages.py:193` and `item_commands.py:593`; S10 integration-tests fix-cycle over 3 iterations fixed pre-existing `test_claude_md_references_migrations_policy` and two migration-roundtrip tests, and in doing so changed `create_app()` signature across 20 test files. Every one of those fixes would have been excluded by the subtraction in AC2 if F-00061 had existed.

- **Risk: parser drift** — ruff, pytest, mypy output formats change across major versions. The parsers are isolated in `orch/daemon/qv_baseline.py` and covered by representative-output unit tests; breaking changes surface immediately in S07's test suite. Kill switch provides a safe fallback if a parser breaks in production.

- **Risk: baseline compute time** — worst case is `make test-integration` running twice (once at setup, once at S14). On this project integration tests take ~2 min; adding 2 min to setup is acceptable. If it becomes a bottleneck, the compute can be parallelised across gates (not done in v1 for simplicity).

- **Non-goal (P5, future)**: dashboard visibility of baselines. Having a column in the item view that shows "5 pre-existing failures excluded from S13" would aid transparency. Not built here — that's a separate UI feature.
