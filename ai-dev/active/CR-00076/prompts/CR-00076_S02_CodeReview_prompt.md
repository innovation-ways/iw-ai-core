# CR-00076_S02_CodeReview_prompt

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`,
`docker volume rm|prune`, `docker system prune`, …). Allowed: testcontainers via
pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make`
targets. If your task seems to require a prohibited command, STOP and raise a
blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00076 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00076 --json`.
- `ai-dev/work/CR-00076/CR-00076_CR_Design.md` — design document.
- `ai-dev/work/CR-00076/reports/CR-00076_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/CR-00076/reports/CR-00076_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of CR-00076 — a test-infrastructure CR
that adds a consolidated data-layer test package covering FTS-trigger invariants,
revision-skew detection, and DB-identity invariants. Read the design document
first (especially the Acceptance Criteria and TDD Approach sections), then the
S01 report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Every AC
is a mandatory check. Note the four files the design names by path
(`tests/integration/data_layer/__init__.py`,
`tests/integration/data_layer/test_fts_trigger_invariant.py`,
`tests/integration/data_layer/test_migration_revision_skew.py`,
`tests/integration/data_layer/test_db_identity_invariants.py`) — all MUST appear
in S01's `files_changed`; a missing one is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in any new test file is
**CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched and no migration file created.** The only files
  changed must be within `scope.allowed_paths`:
  `tests/integration/data_layer/**`, `tests/integration/conftest.py` (if needed),
  `tests/fixtures/**` (if needed), `Makefile`,
  `docs/IW_AI_Core_Testing_Strategy.md`,
  `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`,
  `ai-dev/work/TESTS_ENHANCEMENT.md`. Any edit to `orch/`, `dashboard/`,
  `executor/`, `scripts/` is a **CRITICAL** scope violation. Any file under
  `orch/db/migrations/` is a **CRITICAL** scope violation.
- **No deliberate-break injection left behind.** S01's TDD demonstrations inject
  temporary changes to prove each test can fail, then revert. Confirm via
  `git diff origin/main -- orch/ dashboard/` that **nothing** remains — any
  residual injection is **CRITICAL**.
- **Existing files untouched.** Confirm `test_work_items_functional_doc_fts.py`,
  `test_db_identity_integration.py`, and `test_migrations_round_trip.py` are NOT
  in S01's `files_changed` — modifying them is out of scope → **HIGH**.

### 2. AC1 — FTS-trigger invariant correctness

- The test enumerates all three `tsvector` columns from `orch/db/models.py`
  (`work_items.design_doc_search`, `work_items.functional_doc_search`,
  `project_docs.content_search`) — the module-level constant is exhaustive
  (spot-check by inspecting the models file; `work_items` carries two).
- The `db_session` fixture's template DB installs all FTS triggers via
  `alembic upgrade head` (see `_migrate_template` in `tests/integration/conftest.py`),
  so a `db_session`-backed test inherits them. If the test instead builds its own
  raw `create_all()` engine, it must apply all three FTS function+trigger pairs
  itself — verify whichever path the test takes is correct.
- For each `tsvector` column: INSERT then UPDATE, assert the column is non-null
  and non-empty after the UPDATE. The assertion inspects the actual DB value
  (not just the ORM attribute).
- The test is parametrized one case per `tsvector` column; failures name the column.
- `test_work_items_functional_doc_fts.py` is NOT in `files_changed`.

### 3. AC2 — revision-skew regression test

- The test points a testcontainer DB's `alembic_version` at a revision ID absent
  from the repo's migration graph, runs `alembic upgrade head`, and asserts it
  fails with the `Can't locate revision` resolution error — reproducing the
  I-00075 / I-00076 failure mode.
- The assertion is on the specific resolution error (message substring or
  exception type), **not** a bare `pytest.raises(Exception)` → **MEDIUM (fixable)**
  if the assertion is vacuous.
- **No skew guard is added** — `orch/daemon/migration_rebase.py` and everything
  under `orch/` must be unchanged; the test must not depend on a guard. No Incident
  may be filed for the absent guard (a missing guard is a feature, not a bug).
- **Alembic downgrade rule**: any `downgrade` call targets a specific revision ID,
  never `-1` (per `tests/CLAUDE.md` rule 4a). Any violation is **CRITICAL**.
- `test_migrations_round_trip.py` is NOT in `files_changed`.

### 4. AC3 — DB-identity invariants

- Match path: `IW_CORE_EXPECTED_INSTANCE_ID` = actual fingerprint → identity
  check passes (no exception).
- Mismatch path: `IW_CORE_EXPECTED_INSTANCE_ID` = different UUID → identity
  check raises or returns a refused signal; assertion is on the refusal, not
  a vacuous check.
- Env var is controlled via `monkeypatch` — never `importlib.reload(orch.config)`.
- `test_db_identity_integration.py` is NOT in `files_changed`.

### 5. AC4 — make data-layer-check

- `Makefile` has a `data-layer-check` target with `migration-check` as a
  prerequisite, followed by `uv run pytest tests/integration/data_layer/ -v --no-cov`.
- `data-layer-check` is in the `.PHONY` line.
- The existing `migration-check` target is unchanged.

### 6. AC5 — no new migration file; existing gates unaffected

- `git diff origin/main -- orch/db/migrations/` is empty → **CRITICAL** if not.
- `make migration-check` is documented in the S01 report as still passing.

### 7. AC6 — docs / skill / plan and tdd_red_evidence

- `docs/IW_AI_Core_Testing_Strategy.md` describes the data-layer module (§3/§5/§9).
- `skills/iw-ai-core-testing/SKILL.md` notes the data-layer package + how to
  extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the
  master (`diff` them — a mismatch means `iw sync-skills --force` was not run →
  **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.6 → DONE (CR-00076); a §11
  changelog entry exists; counts in the changelog match the S01 report.
- `tdd_red_evidence` contains three deliberate-break demonstrations (FTS, skew,
  identity). If any is missing or vacuous, raise a **HIGH** finding — a test that
  cannot be shown to fail is worthless.

### 8. Test quality & isolation

- All new tests use the testcontainer `db_session` — never the live DB.
- Tests are order-independent (`pytest-randomly` is on by default). Seeding
  happens per-test/per-fixture; no reliance on another test's state.
- Assertions are behavioural and strong — apply
  `skills/iw-ai-core-testing/SKILL.md`'s red-flag checklist.
- xfail entries (if any) have filed Incident IDs in their `reason` strings,
  not placeholder `TODO` comments → **HIGH** if a genuine bug is xfailed without
  an Incident ID.

## Test Verification (NON-NEGOTIABLE)

Run the new data-layer modules and the convenience target:

```bash
uv run pytest tests/integration/data_layer/ -v --no-cov
make data-layer-check
```

Report results accurately in the contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, migration file created, residual injection, security issue, Alembic `-1` downgrade |
| **HIGH** | Significant bug, missing AC, existing file modified out of scope, xfail without Incident ID, tdd_red_evidence missing |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00076",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (data_layer/); make data-layer-check exit 0",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
