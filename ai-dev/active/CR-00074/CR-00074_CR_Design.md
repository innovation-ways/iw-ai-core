# CR-00074: Cross-Project Isolation Test Matrix

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 3 item 3.4 of the Testing Enhancement Plan — multi-project tenancy is the platform's core correctness axis, yet no systematic test today asserts that project B never sees project A's data on any project-scoped surface.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this CR's new tests use the existing testcontainer `db_session` fixture and nothing else.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — it adds no schema change and no migration file.

## Description

Add a systematic isolation test matrix that proves no project-scoped surface leaks project A's data into project B's view. A `second_project` fixture seeds a second project alongside the existing `test_project`; a parametrized matrix then asserts isolation across dashboard routes, `iw` CLI commands, the global-aggregation routes, and the per-worktree-DB vs orch-DB boundary defined by F-00062.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: IW AI Core is a multi-project platform; projects are registered in `projects.toml` and stored in the `Project` table; every project-scoped dashboard route, `iw` command, and DB query must scope its result set to the requested project; F-00062 introduced a per-worktree DB whose env vars (`IW_CORE_DB_*`) must never bleed orch-DB rows (on `IW_CORE_ORCH_DB_*`, port 5433); the dashboard uses `TestClient` + `app.dependency_overrides[get_db]` (see `tests/dashboard/test_jobs_filter_ui.py`); existing cross-project slices live in `tests/integration/test_per_worktree_isolation.py` and `tests/integration/test_chat_pi_mixed_tabs_independence.py`. This CR is part of the phased plan in `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.4).

## Current Behavior

- There is no test that systematically seeds two projects and asserts project-scoped surfaces return only the requested project's data.
- The standard `test_project` fixture creates exactly ONE project — cross-project leaks in a dashboard route handler, an `iw` command, or the per-worktree-DB boundary would be invisible to the test suite.
- Existing tests in `tests/integration/test_per_worktree_isolation.py` and `tests/integration/test_chat_pi_mixed_tabs_independence.py` cover specific slices but are not a complete matrix; they do not parametrize across all project-scoped surfaces.
- A cross-project data leak is a security and correctness bug that could ship unnoticed to any registered project.

## Desired Behavior

- A `second_project` fixture added to `tests/integration/conftest.py` creates a second `Project` row alongside the existing `test_project` (project A). Both projects are seeded with the full set of project-scoped entities: work items, batches, docs, code-index rows, and job-like rows.
- A new isolation test matrix module `tests/integration/test_cross_project_isolation.py` runs a parametrized suite of assertions covering four axes:
  1. **Dashboard-route isolation**: for every project-scoped dashboard route, request it scoped to project B; assert the response body contains none of project A's identifiers (item IDs, batch IDs, doc titles/slugs, job IDs). Uses the `TestClient` + `app.dependency_overrides[get_db]` pattern.
  2. **`iw`-command isolation**: run project-scoped `iw` commands scoped to project B. Project-scoped commands split into two isolation modes, each asserted appropriately: **read/query commands** (e.g. `iw search --project`, `iw item-status`, `iw item-report`) — assert the command's *output* contains none of project A's identifiers (output isolation, the CLI analogue of axis 1); **mutating commands** (e.g. `iw next-id`, `iw doc-update`) — assert project A's rows are byte-for-byte unchanged, counts AND content, before and after (mutation isolation). A bare "rows unchanged after a read" assertion is vacuous (a read never mutates) and must NOT be used.
  3. **Global-aggregation positive assertion**: the global `/docs` and `/jobs` routes DO show both projects' data; isolation must not over-filter.
  4. **Per-worktree-DB vs orch-DB boundary (F-00062)**: exercise the *actual* resolution code in `orch/config.py`, not two unrelated SQLAlchemy sessions. With `IW_CORE_DB_*` and `IW_CORE_ORCH_DB_*` pointed at two distinct testcontainers, assert `get_db_url()` resolves to the per-worktree container and `get_orch_db_url()` to the orch container (distinct URLs); that a session built on each URL sees only its own rows; and that `get_orch_db_url()` falls back to `IW_CORE_DB_*` when `IW_CORE_ORCH_DB_*` is unset (the `_prefer` contract). References `tests/integration/test_per_worktree_isolation.py` and the F-00062 rules in `CLAUDE.md`.
- A `KNOWN_LEAK` allowlist (keyed by route/command, each entry carrying a `TODO(file-incident)` placeholder + rationale) absorbs any genuine isolation leak found on current `main` — the corresponding case is `xfail`-ed. The implementer does **not** file the Incident from inside the worktree (an incident package would land outside `scope.allowed_paths`); each placeholder is surfaced as operator follow-up in the S01 report, and the operator files the Incident on `main` post-merge. A genuine pre-existing leak is **not** a blocker — allowlist it, report it, continue. A real leak is fixed in a SEPARATE incident; this CR stays strictly test-only.
- Tests land under `tests/integration/` so the existing `integration-tests` daemon QV gate runs them — **no new canonical QV gate**. A `test-isolation` convenience target is added to the `Makefile`.
- At S01 time, update `docs/IW_AI_Core_Testing_Strategy.md` (§3/§5/§9), `skills/iw-ai-core-testing/SKILL.md` (+ synced `.claude/skills/iw-ai-core-testing/SKILL.md` via `iw sync-skills --force iw-ai-core-testing`), and `ai-dev/work/TESTS_ENHANCEMENT.md` (mark item 3.4 DONE + §11 changelog entry).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/integration/conftest.py` | `test_project` fixture (one project only) | + `second_project` fixture; dual-project seeding helpers |
| `tests/integration/` | No systematic cross-project isolation matrix | + `test_cross_project_isolation.py` (parametrized matrix) |
| `Makefile` | No isolation convenience target | + `test-isolation` target |
| `docs/IW_AI_Core_Testing_Strategy.md` | No isolation-matrix layer documented | + updated §3/§5/§9 |
| `skills/iw-ai-core-testing/SKILL.md` | No isolation-matrix guidance | + sub-section on the matrix |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Synced copy | Re-synced via `iw sync-skills --force` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Item 3.4 in-progress | Item 3.4 → DONE |

### Breaking Changes

- None. This CR adds tests, a Makefile target, a new fixture, and doc updates. No production code, no API, no schema, no behaviour change.

### Data Migration

- None. No schema change, no migration file, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `second_project` fixture; isolation matrix module; `KNOWN_LEAK` allowlist; `test-isolation` Makefile target; strategy-doc + skill + plan updates | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-agent review of all work | — |
| S04 | qv-gate | `lint` → `make lint` | — |
| S05 | qv-gate | `assertions` → `make test-assertions` | — |
| S06 | qv-gate | `format` → `make format-check` | — |
| S07 | qv-gate | `typecheck` → `make type-check` | — |
| S08 | qv-gate | `unit-tests` → `make test-unit` | — |
| S09 | qv-gate | `integration-tests` → `make test-integration` (this runs the new isolation matrix) | — |
| S10 | qv-gate | `diff-coverage` → `make diff-coverage` | — |
| S11 | qv-gate | `security-secrets` → `make security-secrets` | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no migration file is added.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00074_CR_Design.md` | Design | This document |
| `CR-00074_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00074_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00074_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00074_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review instructions |
| `prompts/CR-00074_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00074/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/test_cross_project_isolation.py` | Create | The parametrized cross-project isolation matrix |
| `tests/integration/conftest.py` | Modify | Add `second_project` fixture and dual-project seeding helpers |
| `tests/fixtures/**` | Create (if needed) | Shared seed helper for dual-project seeding |
| `Makefile` | Modify | `test-isolation` convenience target, `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document the isolation matrix (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the isolation-matrix layer + cross-project extension guidance |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.4 DONE; §11 changelog; §9 row |

## Acceptance Criteria

### AC1: `second_project` fixture and dual-project seeding

```
Given tests/integration/conftest.py
When the second_project fixture is requested alongside test_project
Then a second Project row exists in the testcontainer DB alongside test_project (project A)
And both projects are seeded with at least one work item, one batch, one doc,
    one code-index row, and one job-like row each
And the two projects' seeded identifiers are guaranteed distinct (no ID overlap)
And the second_project fixture is usable by any integration or dashboard test
    without modifying existing test_project behaviour
```

### AC2: Dashboard-route isolation matrix (project B never shows project A's data)

```
Given both projects are seeded with the full entity set
When tests/integration/test_cross_project_isolation.py runs its dashboard-route
     isolation cases (TestClient + app.dependency_overrides[get_db])
Then for every project-scoped dashboard route, a request scoped to project B
     returns a response whose body contains none of project A's identifiers
     (work item IDs, batch IDs, doc titles/slugs, job IDs)
And each case is parametrized one route at a time so a failure names the leaking route
And genuine pre-existing leaks are recorded in the KNOWN_LEAK allowlist with a
     TODO(file-incident) placeholder and rationale, their cases are xfail-ed,
     and each placeholder is surfaced as operator follow-up in the S01 report
And the isolation matrix exits 0 on current main
```

### AC3: `iw`-command isolation assertions (read = output isolation, mutation = row isolation)

```
Given both projects are seeded
When project-scoped iw commands are invoked targeting project B
Then for a read/query command (e.g. iw search --project, iw item-status),
     the command's OUTPUT (stdout / --json payload) contains none of
     project A's identifiers — output isolation
And for a mutating command (e.g. iw next-id, iw doc-update), project A's
     rows are byte-for-byte unchanged — counts AND content — before and after,
     and project B's own rows did advance/change as expected — mutation isolation
And no command is asserted with a vacuous "rows unchanged after a read" check —
     a read never mutates, so such an assertion can never fail
And each case is parametrized with the command and its isolation mode
     (output / mutation) in the parametrize ID, so a failure names both
     the command and what it leaked
```

### AC4: Global-aggregation positive assertion (both projects appear in global views)

```
Given both projects are seeded
When the global /docs and /jobs routes are requested (no project scope filter)
Then the response bodies contain identifiers from BOTH project A and project B
And the positive-assertion cases are clearly labelled as aggregation checks,
     not isolation checks, so their intent is unambiguous in test output
```

### AC5: Per-worktree-DB vs orch-DB boundary (F-00062 — exercises real resolution code)

```
Given IW_CORE_DB_* points at one testcontainer (the per-worktree DB) and
     IW_CORE_ORCH_DB_* points at a second, distinct testcontainer (the orch DB),
     each seeded with a distinguishable row
When orch.config.get_db_url() and orch.config.get_orch_db_url() are resolved
Then get_db_url() resolves to the per-worktree container and get_orch_db_url()
     resolves to the orch container — the two URLs are not equal
And a SQLAlchemy session built on the per-worktree URL sees only per-worktree
     rows, while a session built on the orch URL sees only orch rows
And when IW_CORE_ORCH_DB_* is unset, get_orch_db_url() falls back to
     IW_CORE_DB_* (the _prefer contract) and resolves to the per-worktree container
And the test exercises orch/config.py resolution — NOT merely two unrelated
     SQLAlchemy sessions, which would assert Postgres behaviour, not IW AI Core's
And env vars are set via monkeypatch.setenv (never importlib.reload(orch.config))
```

### AC6: KNOWN_LEAK allowlist mechanism + "every test can fail" demonstration

```
Given a genuine isolation leak exists (or is deliberately injected for the demo)
When a KNOWN_LEAK entry is added for that route/command with a TODO(file-incident)
     placeholder and rationale
Then the corresponding parametrized case is xfail-ed (not deleted, not skipped silently)
And the placeholder is surfaced as operator follow-up in the S01 report so the
     operator files the Incident on main post-merge; S01 never runs /iw-new-incident
     or creates an incident package inside the worktree
And every other case without a KNOWN_LEAK entry would fail if the corresponding
     isolation were broken — demonstrated by temporarily inverting one isolation-matrix
     assertion inside the test file (e.g. assert that project B's response SHOULD
     contain project A's identifier), confirmed failing RED, then reverted, and the
     failing output recorded as tdd_red_evidence
And the demonstration NEVER touches orch/, dashboard/, executor/, or scripts/
And git diff origin/main -- orch/ dashboard/ executor/ scripts/ is empty before
     reporting completion
```

### AC7: Docs, skill, and plan updated and synced

```
Given the isolation test matrix now exists
When S01 completes
Then docs/IW_AI_Core_Testing_Strategy.md describes the isolation-matrix layer
     (§3 layers, §5 gate table, §9 gap rows)
And skills/iw-ai-core-testing/SKILL.md notes the matrix layer and how to extend it
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to its master
     (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.4 DONE with a §11 changelog entry
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only tests, a Makefile target, a new fixture, and doc updates — reverting removes them cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None functionally. The `pgtestdbpy` per-test DB isolation (CR-00055) and the `integration-tests` gate running `make test-integration` are already on `main`.
- **Shared-file serialization**: CR-00074 modifies `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`, and `tests/integration/conftest.py`, which are ALSO modified by CR-00072, CR-00073, CR-00075, and CR-00076 (the other Phase 3 testing CRs). These five CRs therefore **must NOT run in the same parallel batch** — the batch executor must serialize them (one at a time) to avoid merge conflicts on those shared files.
- **Blocks**: None.

## Impacted Paths

- `tests/integration/test_cross_project_isolation.py`
- `tests/integration/conftest.py`
- `tests/fixtures/**`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure CR — the new tests *are* the deliverable, so classic RED-GREEN does not apply to production code. The "every test must be able to fail" requirement is satisfied differently:

- **Isolation matrix — prove it can fail.** Before reporting completion, S01 must demonstrate the matrix catches a leak — **entirely within the test file**, no production code touched: temporarily invert one isolation-matrix assertion inside the test file (e.g. assert that project B's response SHOULD contain project A's identifier), run `make test-isolation`, confirm the corresponding parametrized case fails RED, then **revert the test-file edit**. The captured failing output is recorded as `tdd_red_evidence`. The demonstration MUST NOT touch `orch/`, `dashboard/`, `executor/`, or `scripts/`.
- **Per-worktree/orch-DB boundary — prove it can fail.** Similarly, and again entirely within the test file: temporarily assert that the two URLs ARE equal (invert the not-equal assertion), confirm the boundary case fails RED, then revert the test-file edit.
- **Unit tests**: none — there is no pure logic to unit-test; the deliverable is integration-level DB + TestClient assertions.
- **Integration tests**: `test_cross_project_isolation.py` — the full parametrized matrix. Uses the testcontainer `db_session` fixture; never touches the live DB.
- **Updated tests**: `tests/integration/conftest.py` gains the `second_project` fixture. Existing tests are unaffected.

## Notes

- **Risk — the matrix finds real leaks on `main`.** Expected and acceptable. The `KNOWN_LEAK` allowlist absorbs them so the CR can merge without expanding into a production fix; each entry carries a `TODO(file-incident)` placeholder and is surfaced as operator follow-up in the S01 report, and the operator files the high-priority Incident on `main` post-merge so the bug is tracked. The implementer must NOT edit production code and must NOT create an incident package inside the worktree (it would land outside `scope.allowed_paths`) — the merge-time scope gate enforces this.
- **Shared-file conflict risk.** CR-00074 touches the same shared files as CR-00072, CR-00073, CR-00075, CR-00076. The batch executor MUST serialize these five CRs. The Dependencies section above states this explicitly; the operator must enforce it at batch-plan time.
- **`second_project` fixture scope.** The fixture must be function-scoped (or at most session-scoped with per-test cleanup) to preserve the isolation guarantee of the `pgtestdbpy` template-clone strategy introduced in CR-00055. Do not introduce shared mutable state across tests via this fixture.
- **Seeding completeness matters.** A sparse seed (e.g., only a Project row, no work items) means project-scoped routes that join on work items return empty results for BOTH projects — a false-positive isolation pass. The seed must be rich enough that each entity type is present in both projects with distinguishable identifiers.
- **iw-command scope.** Only project-scoped `iw` commands are in scope for axis 2. Global commands (e.g., `iw db-identity check`) are not expected to be project-scoped and must not be asserted against.
- **Axis 2 — assert the right thing.** Most project-scoped `iw` commands are reads; "project A's row counts unchanged after a read" is a tautology (a read never mutates). Read commands must therefore assert *output* isolation (project A's identifiers absent from the project-B command output); only genuinely mutating commands use the before/after row-isolation assertion. This keeps every axis-2 case meaningful and avoids tripping the `test-assertions` scanner (S05).
- **Axis 4 — exercise real code, not Postgres.** Two unrelated SQLAlchemy sessions trivially do not share rows — asserting that proves nothing about IW AI Core. Axis 4 instead drives `orch/config.py`'s `get_db_url()` / `get_orch_db_url()` resolution and the `_prefer` fallback, which *is* the F-00062 env-var boundary. The complementary docker-compose-stack slice already lives in `tests/integration/test_per_worktree_isolation.py`; axis 4 is the lightweight config-resolution counterpart, not a duplicate.
- **Out of scope**: fixing any isolation leak the matrix finds; porting the matrix to sibling repos; asserting authentication/authorisation (a separate concern); sweeping non-GET routes on the dashboard (the route-contract sweep in CR-00072 handles that).
