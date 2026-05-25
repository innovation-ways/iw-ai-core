# CR-00085_S01_Backend_prompt

**Work Item**: CR-00085 -- DB-column documentation gate
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

This step adds NO Alembic migration. Do not write one. Do not run any
`alembic upgrade/downgrade/stamp` command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00085 --json` over `workflow-manifest.json` (which may be stale per CR-00023).
- `ai-dev/work/CR-00085/CR-00085_CR_Design.md` — Design document (read FIRST, end-to-end).
- `orch/db/models.py` — the primary SQLAlchemy model file (READ ONLY in this step — you must NOT edit it; S08 scope-gate will reject any diff).
- `scripts/check_test_assertions.py` — structural reference for the scanner shape (assertion-scanner kit pattern; CR-00046).
- `tests/assertion_free_baseline.txt` — structural reference for the baseline-file shape.

## Output Files

- `scripts/check_db_column_docs.py` — the new scanner (NEW)
- `orch/db/column_docs_baseline.txt` — frozen baseline of today's undocumented columns (NEW)
- `tests/orch/db/__init__.py` — package init (NEW, empty)
- `tests/orch/db/test_column_docs.py` — RED-first library-form test (NEW)
- `ai-dev/work/CR-00085/reports/CR-00085_S01_Backend_report.md` — step report

## Context

You are implementing the **scanner + baseline + RED-first test** piece of CR-00085 — the DB-column documentation gate. The CR's structural sibling is CR-00046 (assertion scanner); read that pattern (`scripts/check_test_assertions.py` + `tests/assertion_free_baseline.txt`) before writing this one. Your job here is to land only the new files — Makefile/CI/docs/skill/tracker wiring is S02's job.

Read the design document first. Then read `CLAUDE.md` for project-specific patterns and conventions — especially the critical rule that `DaemonEvent.metadata` is renamed to `event_metadata` in Python because SQLAlchemy reserves the `metadata` attribute.

## Requirements

### 1. `scripts/check_db_column_docs.py` — the scanner

Mirror the public shape of `scripts/check_test_assertions.py`:

- A `Violation` dataclass with at least `module`, `class_name`, `column_name`, `fqn` (e.g. `models.WorkItem.id`), `message`. Provide `.as_baseline_line()` (one FQN per line) and `.as_human_line()` methods.
- A library-form entrypoint — e.g. `scan(baseline: Iterable[str] | None = None, mappers: Iterable[Mapper] | None = None) -> list[Violation]` — that the test file can call directly without shelling out. Default `mappers` to `Base.registry.mappers` from `orch.db.models`.
- A CLI:
  - `python scripts/check_db_column_docs.py` — scan all mappers, exit 0/1.
  - `python scripts/check_db_column_docs.py --baseline <path>` — scan with allowlist.
  - `python scripts/check_db_column_docs.py --write-baseline <path>` — rewrite baseline to current state.
  - `python scripts/check_db_column_docs.py --json` — JSON output.
  - `python scripts/check_db_column_docs.py --strict` — ignore baseline (audit mode).

**How to walk columns — CRITICAL.** Use SQLAlchemy's declarative registry, NOT python `__dict__` reflection. The canonical loop is:

```python
from orch.db.models import Base
for mapper in Base.registry.mappers:
    cls = mapper.class_
    for col in mapper.local_table.columns:
        # col.doc is the value of the doc= kwarg on Column(...)
        # col.name is the SQL column name (e.g. "metadata" for DaemonEvent)
        # The python attribute name may differ (e.g. "event_metadata")
        ...
```

Using `mapper.local_table.columns` walks the actual SQL columns by their SQL name — so the `DaemonEvent` table's `metadata` column (whose python attribute is `event_metadata`) is reported with its SQL name. Do NOT walk `cls.__dict__` or `vars(cls)` — that hits `Base.metadata` (the MetaData object on the declarative base) and trips over the rename.

For the FQN, use `f"{cls.__module__}.{cls.__name__}.{col.name}"` so the entry reads like `orch.db.models.DaemonEvent.metadata` (the SQL column name, not the python attribute).

**Acceptable description carriers** (in priority order):

1. `Column(..., doc="<non-empty string>")` — the `doc` attribute on the SA `Column` object is non-empty (`bool(col.doc)`).
2. The FQN appears in the baseline file (one FQN per line; `#`-prefixed lines and blank lines are comments).

Anything else is a violation.

**Baseline parser** — same shape as `tests/assertion_free_baseline.txt`: line-oriented; `#` comments and blank lines ignored; one FQN per line; trailing-whitespace tolerant; passing `--baseline <path-that-does-not-exist>` is an error (be explicit); passing `--baseline /dev/null` works (yields the empty allowlist — used by the RED test).

**Header docstring** — mirror `scripts/check_test_assertions.py`: docstring explains what the scanner does, lists categories (here just one: `missing-doc`), shows the Usage block, and points at the design (CR-00085) + tracker (TESTS_ENHANCEMENT.md §8 row 4.5).

### 2. `orch/db/column_docs_baseline.txt` — the frozen baseline

Generate by running the scanner against the current `main` tree:

```bash
uv run python scripts/check_db_column_docs.py --write-baseline orch/db/column_docs_baseline.txt
```

Header comment block (same pattern as `tests/assertion_free_baseline.txt`):

```
# DB-column doc baseline (CR-00085).
#
# Each line is one fully-qualified column name that currently lacks a
# `doc=` argument on its SQLAlchemy Column declaration. Format:
#
#     <module>.<Class>.<sql_column_name>
#
# Purpose: this is a *cleanup backlog*, not an accept-list. The gate
# (`make check-column-docs`) admits these legacy offenders so we can
# land the scanner without first writing descriptions for every column,
# but flags any NEW undocumented column added after this baseline.
#
# The right way to silence the gate is to ADD a real `doc="..."` on the
# Column declaration, NOT to add the FQN to this file. Run
#
#     uv run python scripts/check_db_column_docs.py \
#         --write-baseline orch/db/column_docs_baseline.txt
#
# only when you have *intentionally* accepted a legacy column staying
# undocumented (rare; reviewers should push back).
```

Then the FQN list, **sorted** for deterministic diffs.

**Record the exact entry count** in the S01 report's `tdd_red_evidence` field (the number is needed to validate AC3 and to anchor the incremental-scrub follow-up CR).

### 3. `tests/orch/db/__init__.py` + `tests/orch/db/test_column_docs.py`

Create the package init (empty file). Then a test module that imports the scanner's library entrypoint and covers:

**RED test** — `test_scanner_finds_undocumented_columns_against_empty_baseline`:

```python
def test_scanner_finds_undocumented_columns_against_empty_baseline():
    violations = scan(baseline=[])  # empty allowlist
    assert len(violations) > 0, "expected real undocumented columns on orch/db/models.py"
    # Strengthen: a specific column you know is undocumented today should appear.
    fqns = {v.fqn for v in violations}
    assert "orch.db.models.WorkItem.id" in fqns or any(
        "WorkItem" in f for f in fqns
    ), f"WorkItem columns should be undocumented today; got sample: {sorted(fqns)[:5]}"
```

This is your **RED** test — it would PASS against today's tree (because there are real undocumented columns). For the TDD RED-evidence contract, the relevant RED run is the moment BEFORE the scanner exists: run the test, see `ImportError` for the missing module, then implement, then green. That is the captured RED. Record it in `tdd_red_evidence`.

**GREEN test** — `test_scanner_returns_zero_new_violations_against_committed_baseline`:

```python
def test_scanner_returns_zero_new_violations_against_committed_baseline():
    new_violations = scan(baseline=load_baseline("orch/db/column_docs_baseline.txt"))
    assert new_violations == [], f"unexpected NEW undocumented columns: {[v.fqn for v in new_violations]}"
```

**Reserved-name regression test** — `test_scanner_handles_daemon_event_metadata_rename`:

```python
def test_scanner_handles_daemon_event_metadata_rename():
    from orch.db.models import DaemonEvent
    mapper = inspect(DaemonEvent)
    # The python attribute is event_metadata; the SQL column name is metadata.
    sql_names = {c.name for c in mapper.local_table.columns}
    assert "metadata" in sql_names
    # Scanner must run without raising and must report the SQL column name.
    violations = scan(baseline=[], mappers=[mapper])
    fqns = {v.fqn for v in violations}
    # Either "metadata" is documented (no violation) or it appears with its SQL name.
    assert all(".event_metadata" not in f for f in fqns), \
        "scanner must report SQL column name, not python attribute"
```

**Synthetic-mapper regression test** — `test_scanner_flags_new_undocumented_column_on_synthetic_mapper`:

Build a tiny standalone declarative base in-test (own `MetaData`, own `Base`), declare a class with one column that has no `doc=`, pass its mapper to `scan(mappers=[...], baseline=[])`, assert exactly one violation with the expected FQN. This proves the scanner is composable and not hardcoded to `orch.db.models.Base`.

**Baseline write-back smoke test** — `test_write_baseline_roundtrips`:

Write the current scan output to a `tmp_path` file, parse it back, assert the two sets are equal.

### 4. RED-evidence capture

Run the new tests targeted only:

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

Confirm all four+ tests pass. Then record in `tdd_red_evidence`:

- The initial `ImportError`/`ModuleNotFoundError` from running the test BEFORE writing the scanner (captured line),
- The post-implementation pass summary,
- The exact baseline entry count (e.g. "frozen at NNN entries").

If you cannot capture the pre-implementation ImportError (e.g. you wrote the scanner first), use `"n/a — wrote scanner before test; manually verified failure mode by temporarily renaming scan() and re-running: ModuleNotFoundError captured"` style — be honest, do not fabricate.

## Project Conventions

Read the project's `CLAUDE.md` — especially the `DaemonEvent.metadata` → `event_metadata` rename, and the `make lint` / `make format` / `make typecheck` pre-flight gates below.

Match the style of `scripts/check_test_assertions.py` — same dataclass shape, same CLI argparse conventions, same exit-code semantics, same `from __future__ import annotations` header.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write `tests/orch/db/test_column_docs.py` first with at minimum the RED-empty-baseline test. Run it. Capture the `ModuleNotFoundError` (or `ImportError` on the not-yet-existing `scan` function). That is your RED snapshot.
2. **GREEN**: Implement `scripts/check_db_column_docs.py` minimally to make the test pass.
3. Generate the baseline file with `--write-baseline`. Add the GREEN test that confirms zero NEW violations.
4. Add the reserved-name regression test, the synthetic-mapper test, and the write-baseline roundtrip test.
5. **REFACTOR**: tighten the code; ensure CLI argparse + JSON output work.

Do not skip the RED phase. Tests exist before implementation code.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched. Errors elsewhere are pre-existing — note them but do not ignore yours.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object in the Subagent Result Contract with `"ok"` / `"fixed"` / `"skipped:<reason>"`.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the new test file:

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

Do NOT run `make test-integration`, `make test-unit`, or the full assertion-scanner gate — those are S05–S12's job. If your targeted tests fail, fix them before reporting completion.

## Migration Verification

N/A — this step adds no migration.

## Scope discipline

- DO NOT edit `orch/db/models.py`. Reading it is fine; editing it is the follow-up scrub CR's job.
- DO NOT edit `docs/IW_AI_Core_Database_Schema.md`.
- DO NOT edit `Makefile`, `.github/workflows/test-quality.yml`, `docs/IW_AI_Core_Testing_Strategy.md`, or any `skills/` / `.claude/skills/` path — those are S02's scope.
- DO NOT edit `ai-dev/work/TESTS_ENHANCEMENT.md` — S02's scope.

If you discover you need to edit any of the above, STOP and raise a blocker in the report.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00085",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "scripts/check_db_column_docs.py",
    "orch/db/column_docs_baseline.txt",
    "tests/orch/db/__init__.py",
    "tests/orch/db/test_column_docs.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "tdd_red_evidence": "tests/orch/db/test_column_docs.py — pre-implementation run: ModuleNotFoundError: No module named 'scripts.check_db_column_docs'. Post-implementation: 5 passed. Baseline frozen at <NNN> entries.",
  "blockers": [],
  "notes": "Baseline entry count: <NNN>. See report for breakdown by class."
}
```

**`tdd_red_evidence` is required** — it must record the pre-implementation failure line (ImportError/ModuleNotFoundError) AND the post-implementation pass summary AND the exact baseline entry count.
