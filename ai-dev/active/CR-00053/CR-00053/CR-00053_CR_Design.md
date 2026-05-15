# CR-00053: Idempotent `iw next-id` via `--idempotency-key` flag

**Type**: Change Request
**Priority**: Medium
**Reason**: Latent issue today in CLI usage; becomes more visible once the upcoming Dashboard AI Assistant feature lands a chat panel that may retry tool calls on the user's behalf. Surfaced as a separate small CR by R-00074 §10.
**Created**: 2026-05-14
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR **adds one new Alembic migration** that introduces the `id_allocations` table. The agent writes the file; the daemon applies it during the merge pipeline.)

## Description

Add an optional `--idempotency-key <key>` flag to `iw next-id`. When the flag is provided and a row already exists for `(prefix, idempotency_key)`, the command returns the previously-allocated ID instead of allocating a new one. When the flag is omitted, behavior is identical to today. A new `id_allocations` table records key→allocation pairs; the existing `id_sequences` table (per-prefix monotonic counter) is left unchanged.

## Project Context

Read the project's [`CLAUDE.md`](../../CLAUDE.md) and [`orch/CLAUDE.md`](../../orch/CLAUDE.md) for architecture, conventions, and hard rules — notably the Alembic migration rules ("agents generate, daemon applies") and the `id_sequences` table description in `orch/CLAUDE.md` (composite PK on `prefix`, atomic `SELECT … FOR UPDATE` increment).

## Current Behavior

`orch/cli/id_commands.py:allocate_next_id()` unconditionally increments `id_sequences.next_number` for a given prefix and returns the new ID. Two consecutive calls with no shared context — e.g., an agent that retries a failed `iw next-id` invocation, or a future dashboard chat panel that re-issues a tool call after a session reconnect — allocate two distinct IDs (`R-00077`, then `R-00078`); the caller only uses the second, and the first is silently leaked.

```python
# orch/cli/id_commands.py (today, lines 28–61)
def allocate_next_id(session, project_id, prefix):
    session.execute(
        pg_insert(IdSequence).values(prefix=prefix, next_number=1).on_conflict_do_nothing()
    )
    session.flush()
    row = session.execute(
        select(IdSequence).where(IdSequence.prefix == prefix).with_for_update()
    ).scalar_one()
    number = row.next_number
    row.next_number = number + 1
    session.flush()
    return number, format_id(prefix, number)
```

The Click command `next_id` (lines 85–118) has no `--idempotency-key` flag and passes nothing beyond `prefix` and `project_id` to the allocator.

## Desired Behavior

`allocate_next_id()` accepts an optional `idempotency_key: str | None` parameter and the Click command accepts `--idempotency-key <key>`. Three cases:

1. **No key provided** (`idempotency_key is None`): identical to today — increment `id_sequences.next_number`, return new ID. No row is written to `id_allocations`. This is the backwards-compatible path.
2. **Key provided AND `(prefix, key)` exists in `id_allocations`**: return the previously-stored `(prefix, number)` formatted via `format_id()`. Exit code 0. Output is bit-identical to a fresh allocation.
3. **Key provided AND `(prefix, key)` does not exist**: in a single transaction — increment `id_sequences.next_number` (FOR UPDATE lock as today) **AND** insert into `id_allocations(prefix, number, idempotency_key, project_id, created_at)`. Return the new ID.

The partial unique index `(prefix, idempotency_key) WHERE idempotency_key IS NOT NULL` makes case 2 unambiguous and makes case 3 safe under concurrent callers with the same key — only one INSERT wins; the loser retries the SELECT and falls through to case 2.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/db/models.py` | `IdSequence` only | + new `IdAllocation` model |
| Alembic migrations | (current head) | + one new revision: create `id_allocations` table + partial unique index |
| `orch/cli/id_commands.py` `allocate_next_id()` | Takes `(session, project_id, prefix)` | Takes `(session, project_id, prefix, idempotency_key=None)` |
| `orch/cli/id_commands.py` `next_id` Click command | Has `--type` only | Adds optional `--idempotency-key <key>` |
| Callers using `allocate_next_id` directly | None pass a key | None changed — additional param is keyword-only with default `None` |

### Breaking Changes

- **None.** The `--idempotency-key` flag is optional. Existing callers (both CLI users and the internal `batch_commands.py` use at line 326) pass no key and get today's behavior unchanged.

### Data Migration

- New table only — no backfill required.
- Migration is **reversible**: `downgrade()` drops the partial unique index, then drops the `id_allocations` table.
- No risk of data loss on rollback (the table is empty until first keyed call).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `IdAllocation` ORM model + Alembic migration (table + partial unique index) | — |
| S02 | qv-gate | `make migration-check` (round-trip + drift) — immediately after Database per `orch/CLAUDE.md` guidance | — |
| S03 | backend-impl | Modify `allocate_next_id()` to accept `idempotency_key`; add `--idempotency-key` Click option; TDD (RED-first) for the three behavior cases | — |
| S04 | tests-impl | Integration test for repeated CLI invocations with the same key returning the same ID | — |
| S05 | code-review-impl | Per-agent review of S01/S03/S04 — schema correctness, transactional safety, TDD evidence, backwards compatibility | — |
| S06 | code-review-fix-impl | Address CRITICAL/HIGH findings from S05 | — |
| S07 | code-review-final-impl | Cross-agent review — independently re-run migration round-trip + integration test; check model↔migration parity; verify the no-key path is unchanged | — |
| S08 | code-review-fix-final-impl | Address findings from S07 | — |
| S09–S16 | qv-gate | Standard quality gates: lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S17 | self-assess-impl | Self-assessment via `iw-item-analyze` skill (project has `self_assess=true`) | — |

### Database Changes

- **New table**: `id_allocations`
- **Modified tables**: none
- **Migration notes**: Use `uv run alembic revision --autogenerate -m "Add id_allocations table for idempotent next-id"`. Verify the generated migration includes the partial unique index (autogenerate may need a manual touch for `WHERE idempotency_key IS NOT NULL`). Commit the migration file in the same step as the model addition.

**Schema**:

```sql
CREATE TABLE id_allocations (
    prefix           TEXT        NOT NULL,
    number           INTEGER     NOT NULL,
    idempotency_key  TEXT        NULL,
    project_id       TEXT        NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (prefix, number)
);

CREATE UNIQUE INDEX idx_id_allocations_key
    ON id_allocations (prefix, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
```

`project_id` is captured for audit (today's `allocate_next_id` already receives it as a parameter even though `IdSequence` no longer stores it; the same value flows through here). The PK on `(prefix, number)` makes this table a permanent audit log of every keyed allocation; the partial unique index enforces idempotency only when a key is present.

### API Changes

- **New endpoints**: none
- **Modified endpoints**: none
- **Removed endpoints**: none

### Frontend Changes

- **New components**: none
- **Modified components**: none
- **Removed components**: none

## File Manifest

All files for this work item live under `ai-dev/active/CR-00053/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00053_CR_Design.md` | Design | This document |
| `CR-00053_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00053_S01_Database_prompt.md` | Prompt | S01 — model + migration |
| `prompts/CR-00053_S03_Backend_prompt.md` | Prompt | S03 — `allocate_next_id` + CLI flag |
| `prompts/CR-00053_S04_Tests_prompt.md` | Prompt | S04 — integration test |
| `prompts/CR-00053_S05_CodeReview_prompt.md` | Prompt | S05 — per-agent review |
| `prompts/CR-00053_S06_CodeReview_FIX_prompt.md` | Prompt | S06 — per-agent fixes |
| `prompts/CR-00053_S07_CodeReview_Final_prompt.md` | Prompt | S07 — final cross-agent review |
| `prompts/CR-00053_S08_CodeReview_FIX_Final_prompt.md` | Prompt | S08 — final cross-agent fixes |
| `prompts/CR-00053_S17_SelfAssess_prompt.md` | Prompt | S17 — self-assessment |

Reports are created during execution in `ai-dev/work/CR-00053/reports/`.

## Acceptance Criteria

### AC1: Backwards-compatible default path

```
Given no --idempotency-key flag is provided
When `iw next-id --type research` is invoked twice in succession
Then two distinct IDs are returned (e.g., R-00100 and R-00101)
And no rows are inserted into id_allocations
And id_sequences.next_number is incremented by 2
```

### AC2: Repeat call with the same key returns the same ID

```
Given an idempotency_key "abc" that has never been used
When `iw next-id --type research --idempotency-key abc` is invoked once
Then a fresh ID is allocated (e.g., R-00102) and a row is written to id_allocations
When the same command is invoked a second time with the same key
Then the same ID (R-00102) is returned
And id_sequences.next_number is NOT incremented a second time
And no additional row is inserted into id_allocations
```

### AC3: Distinct keys allocate distinct IDs

```
Given two distinct idempotency_keys "abc" and "def"
When `iw next-id --type research --idempotency-key abc` is invoked
And `iw next-id --type research --idempotency-key def` is invoked
Then two distinct IDs are returned
And two rows exist in id_allocations
```

### AC4: Different prefixes with the same key are independent

```
Given an idempotency_key "abc"
When `iw next-id --type research --idempotency-key abc` is invoked
And `iw next-id --type feature   --idempotency-key abc` is invoked
Then two distinct IDs are returned (e.g., R-00104 and F-00088)
And two rows exist in id_allocations — one per prefix
```

### AC5: Migration round-trip is clean

```
Given the migration committed in this CR
When `make migration-check` runs the round-trip (upgrade base→head, downgrade head→base, upgrade base→head)
Then it exits 0 with no schema drift vs Base.metadata.create_all()
And the partial unique index is reproduced correctly on the second upgrade
```

## Rollback Plan

- **Database**: reverse migration available — `downgrade()` drops the partial unique index and then the `id_allocations` table. Empty table on rollback; no data loss.
- **Code**: revert commit. The model + CLI flag + allocator change all live on the same branch.
- **Data**: no data loss on rollback. The table is empty until first keyed call, and even after, dropping it loses only the audit history — `id_sequences.next_number` remains correct.

## Dependencies

- **Depends on**: None.
- **Blocks**: None at the technical level — the upcoming Dashboard AI Assistant FR can be implemented without this CR landing first, but lands more safely if it does.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/cli/id_commands.py`
- `tests/unit/test_id_allocations.py`
- `tests/integration/test_idempotency_key_cli.py`

## TDD Approach

- **Unit tests** (`tests/unit/test_id_allocations.py`):
  - `allocate_next_id(session, project_id, prefix)` (no key) returns sequential IDs and writes no `id_allocations` rows — covers AC1.
  - `allocate_next_id(..., idempotency_key="abc")` called twice returns the same ID and inserts only one `id_allocations` row — covers AC2.
  - `allocate_next_id(..., idempotency_key="abc")` and `allocate_next_id(..., idempotency_key="def")` for the same prefix return distinct IDs and produce two rows — covers AC3.
  - Same key under two different prefixes produces independent allocations — covers AC4.
- **Integration tests** (`tests/integration/test_idempotency_key_cli.py`):
  - CLI `iw next-id --type research --idempotency-key xyz` invoked twice returns identical stdout — covers AC2 end-to-end through the Click command.
  - Migration round-trip exercised by the existing `tests/integration/test_migrations_round_trip.py` pattern — the new `id_allocations` table and its partial unique index must round-trip cleanly — covers AC5.
- **Updated tests**: existing tests that call `allocate_next_id(session, project_id, prefix)` (positional, three args) keep working unchanged because `idempotency_key` is a keyword-only parameter with default `None`. Verify with a targeted grep before reporting completion in S03.

## Notes

- The `id_allocations` table is intentionally a separate concern from `id_sequences`. Keeping the increment counter unchanged means existing concurrent behavior (`SELECT … FOR UPDATE`) is preserved for the no-key path; the keyed path adds a SELECT-then-INSERT cycle inside the same transaction, and the partial unique index guarantees correctness under concurrent same-key INSERT attempts (loser retries the SELECT and sees the winner's row).
- The flag is **CLI-only** for this CR. No HTTP API exposes `next-id` today. If a future FR ever does, it should accept the same flag through whatever shape the API takes.
- The `project_id` column on `id_allocations` is nullable for forward compatibility — today the allocator receives one and we store it for audit, but future global-allocation paths could pass NULL.
- An alternative shape considered: store the key directly on `id_sequences` as a JSONB blob of recent keys. Rejected — would conflate per-prefix state with per-allocation history and complicate the index story. The two-table split is the cleaner SoC.
- No need to change `iw register` or `iw doc-update` for this CR — both are already idempotent on their respective IDs (`register` uses ON CONFLICT, `doc-update` is an upsert). Filed in this CR's scope so it doesn't drift.
