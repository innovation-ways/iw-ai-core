# CR-00076_S03_CodeReview_Final_prompt

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00076 adds no migration. A migration file anywhere in the changeset is a
**CRITICAL** finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00076 --json`.
- `ai-dev/work/CR-00076/CR-00076_CR_Design.md` — design document.
- All step reports: `ai-dev/work/CR-00076/reports/CR-00076_S*_*_report.md`.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00076/reports/CR-00076_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00076 — a
test-infrastructure CR adding a consolidated data-layer test package (FTS-trigger
invariants, revision-skew detection, DB-identity invariants). The per-agent review
(S02) is done; your job is to verify the whole package is coherent, complete
against the design, and safe to merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Cross-check
the four named test files against S01's `files_changed` — any missing one is
**CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — the FTS-trigger invariant module covers all three `tsvector` columns
  from `orch/db/models.py` (`work_items.design_doc_search`,
  `work_items.functional_doc_search`, `project_docs.content_search`); parametrized
  one case per `tsvector` column; INSERT + UPDATE + tsvector assertion;
  `test_work_items_functional_doc_fts.py` untouched.
- **AC2** — the revision-skew regression module points a testcontainer DB's
  `alembic_version` at a revision ID absent from the repo's migration graph, runs
  `alembic upgrade head`, and asserts it fails with the `Can't locate revision`
  resolution error (reproducing I-00075 / I-00076); no skew guard is added
  (`orch/` unchanged, no Incident filed for the absent guard); any Alembic
  downgrade targets a specific revision ID, never `-1`;
  `test_migrations_round_trip.py` untouched.
- **AC3** — the DB-identity invariants module covers the match path (proceed)
  and the mismatch path (refuse); env var controlled via `monkeypatch`;
  `test_db_identity_integration.py` untouched.
- **AC4** — `make data-layer-check` runs `make migration-check` as a prerequisite
  then `uv run pytest tests/integration/data_layer/ -v --no-cov`; in `.PHONY`.
- **AC5** — `git diff origin/main -- orch/db/migrations/` is empty; `make migration-check`
  still passes; no file outside `scope.allowed_paths` was modified.
- **AC6** — `tdd_red_evidence` contains three deliberate-break demonstrations
  (FTS trigger dropped, skew DB pointed at a valid head, identity mismatch
  vacuated) and all were reverted; strategy doc, skill, and plan updated;
  `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to master (run `diff`).

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/`, `dashboard/`,
  `executor/`, `scripts/` production code edited. No `orch/db/migrations/` file
  created or modified.
- **No residual deliberate-break injection** — run
  `git diff origin/main -- orch/ dashboard/` and confirm it is empty. Any
  residual injection would break the data layer in production → **CRITICAL**.
- Confirm `test_work_items_functional_doc_fts.py`, `test_db_identity_integration.py`,
  and `test_migrations_round_trip.py` are NOT modified — they are reference
  files that must remain untouched → **HIGH** if modified.

### 3. Cross-cutting coherence

- The Makefile `data-layer-check` target, the docs §5 gate-table entry, and the
  `TESTS_ENHANCEMENT.md` changelog all describe the same gate consistently.
- The FTS column list in the test module matches the three `tsvector` columns
  visible in `orch/db/models.py` — none silently omitted (`work_items` carries two).
- `TESTS_ENHANCEMENT.md` §11 changelog counts (FTS tables covered, xfail entries,
  Incidents filed) match S01's report exactly.
- `skills/iw-workflow/SKILL.md`'s canonical QV-gate list was **not** modified —
  this CR deliberately adds no new QV gate. A new gate entry is scope creep →
  **HIGH**.

### 4. Test effectiveness (holistic)

- All three new tests **can fail** — confirm `tdd_red_evidence` records a
  deliberate-break demonstration for each. As an independent spot-check, you MAY
  (when quick and safe) re-run one module after a temporary break, then revert —
  state explicitly whether you did this.
- Assertions are behavioural and strong (apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist). Particular attention: the tsvector assertion must inspect
  the actual DB value, not rely on an ORM attribute that may be stale.
- All new tests are order-independent under `pytest-randomly` and use the
  testcontainer DB, never the live DB.
- xfail entries (if any) have filed Incident IDs in their `reason` strings — not
  placeholder `TODO` comments → **HIGH** if absent.

### 5. Architecture & security

- Read `CLAUDE.md`. The new tests follow the established `tests/integration/`
  testcontainer + `db_session` fixture pattern.
- No hardcoded secrets, connection strings, or credentials in the test files.
- The Alembic rule (`tests/CLAUDE.md` 4a) is satisfied in `test_migration_revision_skew.py`.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` runs the new data-layer modules — if it fails, that is a
**CRITICAL** finding. Also run the convenience target:

```bash
make data-layer-check
```

Report results accurately. A failure in `make data-layer-check` is **CRITICAL**.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, migration file created, residual injection, missing requirement, Alembic `-1` downgrade, integration suite or data-layer-check fails |
| **HIGH** | Significant bug, missing AC, existing test file modified, xfail without Incident ID, scope creep (new QV gate) |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00076",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed; make data-layer-check exit 0",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `missing_requirements`: any AC with no corresponding implementation — each is automatically CRITICAL.
