# CR-00074 — S01 Backend Report

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
**Step**: S01 (backend-impl)
**Status**: complete — test-only CR, no production code edited

## What was done

Implemented the full cross-project isolation test matrix: a `second_project`
fixture seeding two fully-populated projects, and a parametrized test module
asserting isolation across four axes. Updated the strategy doc, the testing
skill, and the Phase-3 tracker.

### 1. `second_project` fixture + dual-project seeding

- **`tests/fixtures/dual_project_seed.py`** — rewritten. The file left by an
  earlier run did not import at all (three latent bugs: `ProjectIds` referenced
  in `field(default_factory=...)` before its own definition → `NameError` at
  import; `WorkItem(item_type="feature", ...)` — `item_type` is not a `WorkItem`
  column, the real column is `type` and takes a `WorkItemType` enum; and
  `seed_two_projects` re-created the `test-proj` `Project` already inserted by
  `test_project` → duplicate-PK `IntegrityError`). The rewrite exposes
  `seed_two_projects(session, proj_a=None)` (reuses an existing project A when
  provided), `TwoProjects`, `ProjectIds`, and `SHARED_SEARCH_KEYWORD`. Each
  project is seeded with a `WorkItem`, a `Batch`, an architecture `ProjectDoc`,
  a research `ProjectDoc`, a `CodeIndexJob` and a `DocGenerationJob`, with
  guaranteed-distinct identifiers (`Alpha`/`Beta` labelled). Work items and docs
  embed `SHARED_SEARCH_KEYWORD` so FTS-backed surfaces have real data.
- **`tests/integration/conftest.py`** — the `second_project` fixture now calls
  `seed_two_projects(db_session, proj_a=test_project)`, so project A is the
  existing `test_project` row (purely additive — existing `test_project` tests
  are unaffected). Function-scoped; no shared mutable state.

### 2. Isolation matrix — `tests/integration/test_cross_project_isolation.py`

- **Axis 1 — dashboard-route isolation** (5 parametrized cases): `/queue`,
  `/batches`, `/docs`, `/jobs`, `/research` scoped to project B each render
  project B's own identifier and **none** of project A's distinguishing
  identifiers. `TestClient` + `app.dependency_overrides[get_db]` per the
  `test_jobs_filter_ui.py` pattern (`IW_CORE_EXPECTED_INSTANCE_ID` popped).
  Scope: the project-scoped list/index routes — the genuine cross-project
  aggregation surface; detail routes keyed by a second entity id are not
  aggregation surfaces (a cross-project id 404s), documented in the module.
- **Axis 2 — `iw`-command isolation** (3 parametrized cases): `search-output`
  and `item-status-output` assert *output* isolation (no project A identifiers
  in the project-B-scoped output, with positive controls); `doc-update-mutation`
  asserts *mutation* isolation (project A's `ProjectDoc` rows byte-for-byte
  unchanged — id/title/slug/content/version/updated_at snapshot — and the new
  doc landed on project B). `iw next-id` is **excluded**: `id_sequences` is
  keyed by prefix only (`orch/db/models.py:IdSequence` — "Global atomic
  sequential ID allocation per prefix"), so `next-id` is a global allocator,
  not project-scoped.
- **Axis 3 — global-aggregation positive assertion** (2 cases,
  `aggregation_check-*` ids): the global `/docs` page and `/api/docs/search`
  both surface project A and project B. (There is no global `/jobs` route —
  `jobs_ui.py` is mounted under `/project/{project_id}`; documented in the
  test.)
- **Axis 4 — per-worktree-DB vs orch-DB boundary, F-00062** (4 cases): two
  distinct testcontainer Postgres DBs; `get_db_url()` resolves `IW_CORE_DB_*`
  to the per-worktree container and `get_orch_db_url()` resolves
  `IW_CORE_ORCH_DB_*` to the orch container (distinct URLs); sessions built
  from each see only their own rows; the `_prefer` fallback (orch env unset →
  falls back to `IW_CORE_DB_*`); the I-00062 agent-context orch-port-collision
  guard raises `RuntimeError`. Env vars set via `monkeypatch.setenv` only —
  no `importlib.reload(orch.config)`.
- **`KNOWN_LEAK`** module-level dict (keyed by route/command) → **empty**; the
  `_xfail_marks` helper attaches `xfail(strict=True)` automatically for any
  future entry. No genuine isolation leak found on `main`.

### 3. Makefile

- `test-isolation` target added (`uv run pytest …test_cross_project_isolation.py
  -v --no-cov`) and added to `.PHONY`.

### 4. Docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` — new **§2 Layer 6** (cross-project
  isolation matrix), **§5 gate-table row**, **§9 known-gap row flipped to ✅**.
- `skills/iw-ai-core-testing/SKILL.md` — §3 "Cross-project isolation" extended
  with a "The cross-project isolation matrix (CR-00074)" sub-section incl. how
  to extend it. `iw sync-skills --force iw-ai-core-testing` run;
  `.claude/skills/iw-ai-core-testing/SKILL.md` verified **byte-identical**.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — item 3.4 → `DONE 2026-05-21 (CR-00074)`;
  §11 changelog entry added.

## "Every test must be able to fail" — demonstration

- **Axis 1**: removed the `WorkItem.project_id == project_id` filter from
  `_queue_items` in `dashboard/routers/project_pages.py`. The `queue` case
  failed: `AssertionError: ISOLATION LEAK: /project/second-proj/queue (scoped
  to project B) leaked project A identifier 'WI-ALPHA-001'`. Reverted.
- **Axis 4**: made `get_orch_db_url()` in `orch/config.py` `return get_db_url()`
  (ignoring `IW_CORE_ORCH_DB_*`). The boundary cases failed:
  `test_axis4_sessions_see_only_their_own_rows` → `orch session saw
  ['per-worktree-db-row'] — expected only 'orch-db-row'`; the URL-resolution
  case → `get_orch_db_url() … did not resolve to the orch container`. Reverted.

Both injections fully reverted — `git diff origin/main -- orch/ dashboard/
executor/ scripts/` is **empty**; no `TDD-RED INJECTION` marker remains.

## Test results

```
uv run pytest tests/integration/test_cross_project_isolation.py -v --no-cov
14 passed in ~14s  (5 Axis 1 · 3 Axis 2 · 2 Axis 3 · 4 Axis 4; 0 xfailed, 0 failed)
```

Order-independence verified under `pytest-randomly` seeds 12345 / 67890 / 42424
— all green.

## Pre-flight quality gates

- `make format` — ok (849 files already formatted).
- `make typecheck` — ok (mypy: no issues in 274 source files).
- `make lint` — ok (ruff + templates: all checks passed).
- `make test-assertions` — ok (no new assertion-scanner violations, 538 files).

## Observations

- `iw next-id` is **not** project-scoped — `id_sequences` is a global per-prefix
  allocator. Correctly excluded from Axis 2 (documented in the module).
- There is **no global `/jobs` route** — `jobs_ui.py` carries the
  `/project/{project_id}` prefix. Axis 3 therefore covers `/docs` +
  `/api/docs/search` (documented in the module + changelog).
- No genuine cross-project leak was found on `main`: every project-scoped
  route handler and `iw` command audited filters correctly by `project_id`.
  **0 high-priority Incidents filed.**
