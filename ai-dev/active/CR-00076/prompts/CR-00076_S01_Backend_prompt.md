# CR-00076_S01_Backend_prompt

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
**Step**: S01
**Agent**: backend-impl

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

This CR adds **no migration** and **no schema change**. You MUST NOT
create, modify, or apply any Alembic migration. If your work appears to
need one, STOP and raise a blocker — that means the scope is wrong.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00076 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00076/CR-00076_CR_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/work/CR-00076/CR-00076_Functional.md` — human-facing summary.
- Reference patterns: `tests/integration/test_work_items_functional_doc_fts.py` (existing FTS coverage — extend, do not replace), `tests/integration/test_db_identity_integration.py` (existing identity coverage — build on, do not replace), `tests/integration/test_migrations_round_trip.py` (existing migration gate — leave untouched), `tests/integration/conftest.py` (shared integration fixtures — `_migrate_template` shows how the template DB is built), `orch/db/models.py` (the three `tsvector` columns and their FTS function/trigger constants, and model definitions), `orch/db/identity.py` (fingerprint and pin logic). `orch/daemon/migration_rebase.py` is the CR-00021 down-revision rewriter — background only; the skew test adds no guard.

## Output Files

- `ai-dev/work/CR-00076/reports/CR-00076_S01_Backend_report.md` — step report.

## Context

You are implementing **all of CR-00076** — it is a single-step test-infrastructure
change. Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read for any
test work here.

This CR adds a consolidated data-layer test package. **It is strictly test-only:
you MUST NOT edit any production code** (`orch/`, `dashboard/`, `executor/`,
`scripts/`) and you MUST NOT create any Alembic migration file. The merge-time
scope gate enforces this against `scope.allowed_paths`.

## Requirements

### 1. Package structure — `tests/integration/data_layer/`

Create the package directory with `__init__.py`. All three new test modules
live here.

### 2. FTS-trigger invariant — `tests/integration/data_layer/test_fts_trigger_invariant.py`

Create a new test module that asserts the full-text-search trigger invariant
across every `tsvector` column.

- Inspect `orch/db/models.py` to enumerate every `tsvector` column. There are
  **three** — `work_items.design_doc_search`, `work_items.functional_doc_search`,
  and `project_docs.content_search` (note `work_items` carries two). Build a
  module-level constant of `(table, tsvector_column, searchable_text_column)`
  tuples — one entry per `tsvector` column. Verify the list against the models
  file rather than trusting this prompt; if a fourth column has landed, include it.
- Use the testcontainer `db_session` fixture from `tests/integration/conftest.py`.
  Its template DB installs all three FTS function+trigger pairs via
  `alembic upgrade head` (see `_migrate_template` in `conftest.py`), so a
  `db_session`-backed test inherits every trigger — you do NOT need to apply
  FTS DDL manually, and you MUST NOT modify `conftest.py` for this. If you
  instead build a raw `create_all()` engine, you MUST apply all three FTS
  function+trigger pairs (`FTS_*`, `PROJECT_DOCS_FTS_*`, `FUNCTIONAL_DOC_FTS_*`
  from `orch/db/models.py`) yourself.
- For each `tsvector` column: INSERT a representative row, then UPDATE a
  searchable text field, and assert the `tsvector` column is non-null and
  non-empty after the UPDATE. Use a direct SQL query to inspect the `tsvector`
  value — do not rely solely on ORM attributes.
- **Parametrize one case per `tsvector` column** so a failure names the column.
- This test EXTENDS `test_work_items_functional_doc_fts.py` — it does not
  replace it. Do NOT modify that file.

### 3. Revision-skew regression test — `tests/integration/data_layer/test_migration_revision_skew.py`

Create a new test module that **reproduces** the I-00075 / I-00076 failure class
as a regression test. There is no skew-detection guard in the codebase and this
CR adds none — the module pins the failure mode, it does not assert early detection.

- Using a testcontainer DB, put its `alembic_version` row at a revision ID that
  is **absent from the repo's migration graph** (e.g. upgrade to head, then
  `UPDATE alembic_version SET version_num = '<bogus-rev>'`). This recreates the
  state of an I-00075 / I-00076 worktree: a DB at a revision the checked-out
  migration files do not contain. Note that stamping the DB at an *older but
  valid* revision would NOT reproduce the bug — that is the normal "DB behind
  head" case Alembic handles fine.
- Run `alembic upgrade head` against that DB (via the Alembic `Config` API) and
  assert it raises the characteristic resolution failure — `alembic` surfaces it
  as a `CommandError` / resolution error whose message contains
  `Can't locate revision identified by`. Assert on that specific message (or the
  specific exception type), **not** a bare `pytest.raises(Exception)`.
- This proves the failure class is real and reproducible, and pins it: if the
  error signature changes, or the codebase ever gains skew-tolerant behaviour,
  the test notices.
- **Do NOT touch production code.** `orch/daemon/migration_rebase.py` and
  everything under `orch/` must be unchanged. Do **not** file an Incident for the
  absent guard — a missing guard is a feature request, out of scope here.
- **Rule from `tests/CLAUDE.md` (4a)**: this is a dedicated migration test, so
  invoking `alembic` is allowed; any `downgrade` call must target a **specific
  revision ID**, never `-1`.
- Do NOT modify `test_migrations_round_trip.py` or the `migration-check` Makefile
  target — those test a different invariant (full up-then-down round trip).

### 4. DB-identity invariants — `tests/integration/data_layer/test_db_identity_invariants.py`

Create a new test module that formally asserts the DB-identity invariants.

- Read `orch/db/identity.py` in full before writing the test.
- **Match path**: set `IW_CORE_EXPECTED_INSTANCE_ID` to the actual fingerprint of
  the testcontainer DB and assert that the identity check passes (no exception,
  connection proceeds).
- **Mismatch path**: set `IW_CORE_EXPECTED_INSTANCE_ID` to a UUID that differs
  from the actual fingerprint and assert that the identity check raises the
  expected exception or returns a refused signal.
- Use `monkeypatch.setenv` / `monkeypatch.delenv` to control the env var — never
  `importlib.reload(orch.config)` (see `CLAUDE.md`).
- Reference `test_db_identity_integration.py` for the existing fixture pattern.
  Do NOT modify that file — this module is a companion, not a replacement.

### 5. Makefile target — `make data-layer-check`

Add a `data-layer-check` target to the Makefile:

```makefile
data-layer-check: migration-check
	uv run pytest tests/integration/data_layer/ -v --no-cov
```

Add `data-layer-check` to the `.PHONY` line. The `migration-check` prerequisite
ensures the round-trip test runs first; if it fails, `data-layer-check` stops.
Verify the target runs both phases by executing it yourself before reporting
completion.

### 6. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: document the data-layer module — add it
  to the layers section (§3), add a gate-table row or note (§5), and flip the
  relevant "known gap" rows (§9) that describe the missing consolidated
  data-layer coverage.
- `skills/iw-ai-core-testing/SKILL.md`: add a short sub-section describing the
  data-layer package — what it covers, and how to extend it (when a new FTS table
  is added, add it to the parametrized list; when a new identity edge case is
  discovered, add a case to `test_db_identity_invariants.py`). Then run
  `uv run iw sync-skills --force iw-ai-core-testing` and verify
  `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.6's status to
  `DONE 2026-05-21 (CR-00076)` (note it was "TODO (partly done)"); add a
  `## 11. Changelog` entry (or append to an existing one) dated 2026-05-21
  summarising what shipped (three modules, data-layer-check target, any `xfail`
  entries + Incidents filed); update §9 prose if the data-layer module belongs
  in the blocking / periodic lists.

## "Every test must be able to fail" — required demonstration

This is a test-infrastructure CR, so there is no production code to RED-GREEN.
Instead, **prove each new test can fail**:

1. **FTS-trigger invariant**: temporarily `DROP` one FTS trigger inside the
   test's DB before the assertion (e.g.
   `DROP TRIGGER trg_work_items_fts ON work_items`), run
   `uv run pytest tests/integration/data_layer/test_fts_trigger_invariant.py -v --no-cov`,
   confirm that column's parametrized case fails because the tsvector is empty or
   null, then **revert completely**.
2. **Revision-skew regression**: temporarily point the DB's `alembic_version` at
   a **valid** head revision instead of a bogus one, run
   `uv run pytest tests/integration/data_layer/test_migration_revision_skew.py -v --no-cov`,
   confirm the test fails because `alembic upgrade head` now succeeds and the
   expected `Can't locate revision` error is not raised, then **revert completely**.
3. **DB-identity invariants**: temporarily change the mismatch path assertion (e.g.
   make the expected UUID match the actual fingerprint so the mismatch branch is
   not exercised), run
   `uv run pytest tests/integration/data_layer/test_db_identity_invariants.py -v --no-cov`,
   confirm the mismatch case fails or is vacuous, then **revert completely**.

Record all three demonstrations (the failing output snippets) as your
`tdd_red_evidence`. Double-check via `git status` / `git diff` that **no
injection remains** before reporting completion.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for: the live-DB guard (never touch port
5433), the testcontainer rules, the psycopg2 URL replacement requirement, the
FTS DDL requirement, the `pytest-randomly` order-independence requirement, and
the assertion-strength rules in `skills/iw-ai-core-testing/SKILL.md`. Match
existing code in `tests/integration/`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). Every assertion must be behavioural and meaningful.

## Test Verification (NON-NEGOTIABLE)

Run **only your own new test files** — do NOT run the full suite (that is the
QV gates' job, S08/S09/S10):

```bash
uv run pytest tests/integration/data_layer/ -v --no-cov
make data-layer-check
```

Do not report `tests_passed: true` unless all three modules pass (genuine
data-layer bugs `xfail`-ed with Incident IDs) and `make data-layer-check` exits 0.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (data_layer/); make data-layer-check exit 0",
  "tdd_red_evidence": "deliberate-break demonstrations — FTS: <column> case failed with empty tsvector when its trigger was dropped; skew: test failed when alembic_version pointed at a valid head; identity: mismatch case vacuous when UUID matched. All injections reverted (git status clean).",
  "blockers": [],
  "notes": "tsvector columns covered: <list>. xfail entries: <N> — list each with Incident ID. Skew test asserts on: <exact resolution-error message>. make data-layer-check: migration-check passed, data_layer/ passed."
}
```

- In `notes`, report: the `tsvector` columns enumerated, xfail count + each
  Incident ID (if any FTS/identity bug surfaced), and the exact resolution-error
  message the skew regression test asserts on.
- If you found a genuine data-layer bug you could not file an Incident for, set
  `completion_status: partial` and list it in `blockers` for the operator.
