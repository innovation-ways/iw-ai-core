# CR-00091_S02_Backend_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Do not execute any docker container/volume/network management commands. Testcontainer fixtures in tests are exempt. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do not apply any migration to the live DB on port 5433.

## Context

Read `CLAUDE.md` and `orch/CLAUDE.md` before starting. Read S01's report to confirm `scripts/rewrite_down_revision.py` and the `migration-pending` Makefile target are in place.

This step implements the "validation side" of the PENDING sentinel: a resolver script that substitutes PENDING with the real chain head, updates `make migration-check` to call the resolver before running the round-trip test, adds a documentation comment to `migration_rebase.py`, and extends both unit and integration test suites.

**Design doc**: `ai-dev/active/CR-00091/CR-00091_CR_Design.md` — read AC2, AC3, AC4 before writing code.

## TDD — Write Tests FIRST

Write all failing tests before implementing. Capture RED run output in your step report.

### New unit tests in `tests/unit/daemon/test_migration_rebase.py`

Open the existing file and add one new test case at the end of the file:

**test_pending_sentinel_is_always_rewritten** — given a git repo (use `tmp_path` + `git init`) where:
- `origin/main` has one committed migration with revision `"aabbccdd1122"` (no PENDING, real value)
- the branch has one added migration file with `down_revision = "PENDING"` and `revision = "eeff99887766"`
- `run_pre_merge_rebase` is called

Assert:
- `result.success is True`
- `len(result.rewrites) == 1`
- `result.rewrites[0].old_down_revision == "PENDING"`
- `result.rewrites[0].new_down_revision == "aabbccdd1122"` (main's head)
- The migration file on disk now has `down_revision = "aabbccdd1122"` (not PENDING)

Follow the existing test patterns in `tests/unit/daemon/test_migration_rebase.py` for how to set up the fake git repo and migration files.

### New unit tests for the resolver script

Add `tests/unit/test_resolve_pending_migration.py` with these cases (use `tmp_path`):

1. **test_no_pending_files_is_noop** — directory has two migrations with real hex values; resolver exits 0 and makes no changes.

2. **test_resolves_single_pending_file** — directory has migrations `A → B (real) → C (PENDING)`; after running the resolver, `C` has `down_revision = "B"` (B's revision ID).

3. **test_resolves_pending_when_it_is_the_only_migration** — directory has a single migration with `down_revision = "PENDING"` and no other migrations (i.e., it is the chain root); after running the resolver, the file contains the literal line `down_revision = None` (the unquoted Python `None`, NOT the string `"None"`). Assert on the exact substring `down_revision = None` and that the substring `down_revision = "None"` is absent — Alembic would treat `"None"` (quoted) as a real revision ID and fail with `Can't locate revision identified by 'None'`.

4. **test_resolver_idempotent** — running the resolver twice on the same directory produces the same result as running it once.

### Integration test addition in `tests/integration/test_migrations_round_trip.py`

Add two new test functions at the end of the file:

**test_resolver_produces_valid_chain_against_real_versions_dir** — this test:
1. Copies the entire `orch/db/migrations/versions/` directory into a `tmp_path` scratch area.
2. Creates a synthetic migration file in the scratch area with `down_revision = "PENDING"` and a valid revision ID (e.g., `"0000000000ff"`) and trivial `upgrade()`/`downgrade()` bodies (no DDL).
3. Calls `resolve_pending_migration(scratch_dir)` (import from `scripts/resolve_pending_migration.py`).
4. Asserts that after resolution, no file in the scratch area contains `down_revision = "PENDING"`.
5. Asserts that the resolved value equals the current chain head (i.e., the newest real revision before the synthetic one).

This test does NOT spin a testcontainer — it only validates that the resolver produces a valid chain when given a realistic versions dir. The existing testcontainer round-trip tests cover the DB-side validation.

**test_ac4_resolver_is_noop_on_clean_versions_dir** (AC4 regression guard) — this test:
1. Copies the entire `orch/db/migrations/versions/` directory into a `tmp_path` scratch area (no PENDING files).
2. Captures a content snapshot of every file (e.g., a `{filename: sha256}` dict).
3. Calls `resolve_pending_migration(scratch_dir)`.
4. Asserts that the post-call content snapshot is byte-identical to the pre-call snapshot — no file was modified, no file was added, no file was removed.

This pins AC4 explicitly: `make migration-check` against a clean (no-PENDING) versions dir must not mutate any file.

## Deliverable 1: `scripts/resolve_pending_migration.py`

Create `scripts/resolve_pending_migration.py` as a standalone CLI script (no project imports — only stdlib). It may import from `scripts/rewrite_down_revision.py` by path if needed, or duplicate the regex helper (keep it simple).

**Behaviour when called with no arguments** (default: operates on `orch/db/migrations/versions/`):
1. Scan all `.py` files in the versions directory (skip `__pycache__`).
2. Parse each file for its `revision` and `down_revision` values using the same regex pattern as `rewrite_down_revision.py`.
3. Build the set of revision IDs that appear as `down_revision` of other files (i.e., files that ARE pointed to by other files). These are interior nodes in the chain.
4. Identify the current chain head: the revision whose ID does NOT appear as any other file's `down_revision`, excluding PENDING files from this computation.
5. For each file with `down_revision = "PENDING"`:
   a. Determine the correct parent: the current head of the non-PENDING chain.
   b. If the non-PENDING chain is empty (only PENDING files exist), set `down_revision = None`.
   c. Rewrite using the same regex as `rewrite_down_revision.py`.
6. Print a summary: `"Resolved N PENDING migration(s): <revision_id> → <new_down_revision>"`.
7. Exit 0 even if no PENDING files are found ("no PENDING migrations found — nothing to do").

**When called with a path argument**: operate on that directory instead of the default.

**CRITICAL — quoted vs. unquoted writes**:

The resolver writes TWO distinct forms depending on the resolved value:

- **Chain head exists**: write `down_revision = "<hex>"` — quoted string literal. Example: `down_revision = "76250ecb2593"`.
- **No real chain (PENDING is the only migration)**: write `down_revision = None` — the bare Python `None` literal, NO quotes.

Do **NOT** delegate this write to `scripts/rewrite_down_revision.py`. That script always wraps the value in quotes (`"PENDING"`) and would emit `down_revision = "None"` (a string) for the chain-root case — Alembic would then try to resolve a revision called `None` and crash with `Can't locate revision identified by 'None'`.

Duplicate the regex helper in the resolver and apply the value as-is (e.g., `f'"{hex}"'` for the head case, the literal `"None"` (the 4-character string `None`, no surrounding quotes in the replacement) for the chain-root case).

**Edge cases**:
- Multiple PENDING files (chain of PENDING files): resolve the root PENDING file to the real head; for any PENDING files that point to other PENDING files, leave their `down_revision` as PENDING. Resolving multi-PENDING chains is out of scope (see design doc Notes).
- If the chain has multiple real heads (pre-existing Alembic fork): print an error to stderr and exit 1 — do NOT attempt to resolve.

## Deliverable 2: `Makefile` — update `migration-check` target

Update the `migration-check` target to call the resolver before running pytest:

```makefile
migration-check:
	uv run python scripts/resolve_pending_migration.py
	uv run pytest tests/integration/test_migrations_round_trip.py --timeout=600 -v --no-cov
```

Do not change any other Makefile target.

## Deliverable 3: `orch/daemon/migration_rebase.py` — documentation comment

In `run_pre_merge_rebase`, locate Step 8 ("Rewrite stale files") and add a comment above the `if _down_revision == expected: continue` line:

```python
# "PENDING" is the canonical sentinel for late-bound migrations (CR-00091).
# It is never equal to any real revision ID, so it always triggers a rewrite
# here. No special-casing needed — the condition handles it correctly.
```

This is the only change to `migration_rebase.py`. Do NOT alter any logic.

## Preflight before committing

Run `make lint` and `make format-check` on all changed files. Fix any issues.

Run targeted tests:
```bash
uv run pytest tests/unit/daemon/test_migration_rebase.py tests/unit/test_resolve_pending_migration.py tests/integration/test_migrations_round_trip.py -v
```

Do not run `make test-integration` — that is reserved for S11.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|blocked",
  "files_changed": [
    "scripts/resolve_pending_migration.py",
    "Makefile",
    "orch/daemon/migration_rebase.py",
    "tests/unit/daemon/test_migration_rebase.py",
    "tests/unit/test_resolve_pending_migration.py",
    "tests/integration/test_migrations_round_trip.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok|skipped:stdlib-only-scripts",
    "lint": "ok|fixed"
  },
  "tests_passed": true,
  "test_summary": "N unit + M integration tests passed",
  "tdd_red_evidence": "<paste AssertionError snippet from RED run>",
  "blockers": [],
  "notes": ""
}
```
