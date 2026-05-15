# CR-00053_S03_Backend_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(You do NOT generate or apply migrations in this step. S01 added the `id_allocations` table; you only read/write rows.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design document (Sections "Desired Behavior", "Acceptance Criteria", "TDD Approach")
- `ai-dev/work/CR-00053/reports/CR-00053_S01_Database_report.md` -- S01 step report (confirms the `IdAllocation` model exists)
- `orch/cli/id_commands.py` -- current `allocate_next_id` and `next_id` Click command (lines 28–118)
- `orch/cli/batch_commands.py` line 326 -- one existing internal caller of `allocate_next_id` to verify backwards compatibility

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S03_Backend_report.md` -- Step report
- `orch/cli/id_commands.py` -- modified to accept `idempotency_key` and add `--idempotency-key` Click option
- `tests/unit/test_id_allocations.py` -- new unit tests covering AC1–AC4 (RED-first)

## Context

You are implementing the backend half of **CR-00053**. Make `allocate_next_id()` accept an optional `idempotency_key` and add the corresponding CLI flag.

Read the design document first. Then read `CLAUDE.md` and `orch/CLAUDE.md`.

## Requirements

### 1. Modify `allocate_next_id()` (TDD: write the failing tests FIRST)

The new signature is:

```python
def allocate_next_id(
    session: Session,
    project_id: str,
    prefix: str,
    *,
    idempotency_key: str | None = None,
) -> tuple[int, str]:
```

`idempotency_key` is keyword-only so existing positional callers (notably `orch/cli/batch_commands.py:326` — `allocate_next_id(session, project_id, "BATCH")`) keep working unchanged.

Behavior — exact transactional semantics:

- **`idempotency_key is None`** (default): identical to today. Initialise `IdSequence` row via `INSERT … ON CONFLICT DO NOTHING`, `SELECT … FOR UPDATE` to lock-and-increment, return `(number, format_id(prefix, number))`. **Do not insert into `id_allocations`.**
- **`idempotency_key is not None`**:
  1. `SELECT prefix, number FROM id_allocations WHERE prefix=? AND idempotency_key=?` — if a row exists, return `(row.number, format_id(prefix, row.number))` without touching `id_sequences`.
  2. If not, **inside a SAVEPOINT** (`session.begin_nested()`) so the IntegrityError catch in step 3 can `ROLLBACK TO SAVEPOINT` instead of aborting the outer transaction: increment `id_sequences.next_number` (same FOR UPDATE pattern as today) AND `INSERT INTO id_allocations (prefix, number, idempotency_key, project_id) VALUES (?, ?, ?, ?)`.
  3. If the INSERT raises a `UniqueViolation` on `idx_id_allocations_key` (concurrent same-key INSERT lost the race), catch it — the savepoint rollback already undid the speculative `id_sequences` increment — then retry from step 1 (the winner's row is now visible). Cap retries at 3.

Use `from sqlalchemy.exc import IntegrityError` for the concurrent-INSERT catch.

**Why the SAVEPOINT matters**: under psycopg v3, once a statement inside a transaction raises an error the connection is in a failed state until a rollback. Without `session.begin_nested()`, catching `IntegrityError` and retrying the SELECT in the same transaction would itself raise (`current transaction is aborted, commands ignored until end of transaction block`). The savepoint scopes the rollback to just the speculative SELECT-FOR-UPDATE + INSERT block, leaving the outer transaction healthy for the retry SELECT.

### 2. Add the `--idempotency-key` Click option

Modify the `next_id` Click command (line 85) to accept:

```python
@click.option(
    "--idempotency-key",
    "idempotency_key",
    required=False,
    default=None,
    type=str,
    help="If provided, return the previously-allocated ID for this (type, key) pair instead of allocating a new one.",
)
```

Thread `idempotency_key` through to `allocate_next_id()`. The output format (plain ID line or JSON) is bit-identical whether the call was a fresh allocation or an idempotent replay.

### 3. Write the unit tests FIRST (RED-first, mandatory)

Create `tests/unit/test_id_allocations.py`. Tests cover the four AC paths from the design doc:

- `test_no_key_path_unchanged` — call `allocate_next_id(session, "p", "R")` twice, assert returned IDs are sequential, assert `id_allocations` row count is 0 (covers AC1).
- `test_repeat_key_returns_same_id` — call `allocate_next_id(session, "p", "R", idempotency_key="abc")` twice, assert identical return value, assert exactly one `id_allocations` row, assert `id_sequences.next_number` advanced by exactly 1 (covers AC2).
- `test_distinct_keys_distinct_ids` — call with `idempotency_key="abc"` then `idempotency_key="def"`, assert distinct return values, assert two `id_allocations` rows (covers AC3).
- `test_same_key_different_prefixes_independent` — call with `prefix="R", key="abc"` then `prefix="F", key="abc"`, assert distinct return values, assert two `id_allocations` rows with distinct prefixes (covers AC4).
- `test_concurrent_same_key_retries_and_returns_winner` — simulate the `IntegrityError` path by manually inserting an `id_allocations` row mid-transaction (or by mocking the INSERT to raise once); assert the second call returns the winner's number and `id_sequences.next_number` was NOT double-incremented. This is the trickiest test and the highest-value one; consider using `monkeypatch` on `session.execute` to inject the IntegrityError on the first INSERT.

Use the project's existing unit-test conventions — read `tests/CLAUDE.md` and look at neighbours under `tests/unit/` for the testcontainer-or-sqlite-memory fixture pattern.

**RED phase**: write the tests, run **only the new file** (`uv run pytest tests/unit/test_id_allocations.py -v`), confirm the failures are `AssertionError` / `AttributeError` / `TypeError` (NOT `ImportError`, `SyntaxError`, fixture error, or collection error). Capture one failing line as `tdd_red_evidence`.

### 4. Verify backwards compatibility

After GREEN, search for any other callers:

```bash
grep -rn "allocate_next_id" --include="*.py" /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/
```

Verify each call site does NOT pass `idempotency_key` positionally and still passes correctly. Note in the report any caller you confirmed touches.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:
- Click 8.1+ for CLI; match the existing `next-id` command style
- SQLAlchemy 2.0 sync session pattern with `session.execute(...).scalar_one()` / `.scalars().first()`
- Append-only writes to audit-style tables — never UPDATE an existing `id_allocations` row
- `psycopg.errors.UniqueViolation` is the underlying cause of `sqlalchemy.exc.IntegrityError` for our partial unique index

## TDD Requirement

Mandatory RED-first per the standard prompt template. The five new tests in `tests/unit/test_id_allocations.py` MUST fail before the `allocate_next_id` signature changes. Capture the failure for `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only:

```bash
uv run pytest tests/unit/test_id_allocations.py -v
```

Do NOT run `make test-unit` or `make test-integration` — those are S13/S14 QV gates.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/id_commands.py",
    "tests/unit/test_id_allocations.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_id_allocations.py::test_repeat_key_returns_same_id — TypeError: allocate_next_id() got an unexpected keyword argument 'idempotency_key' (captured pre-implementation)",
  "blockers": [],
  "notes": ""
}
```
