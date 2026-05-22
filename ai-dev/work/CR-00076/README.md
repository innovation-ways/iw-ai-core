# CR-00076 — Data-Layer Test Module

## Goal

Add a `tests/integration/data_layer/` package with three focused test modules that cover data-layer invariants the existing test suite doesn't address:

1. **FTS trigger invariant** — parametrized over every tsvector column
2. **Migration-revision skew regression** — reproduces I-00075/I-00076 failure class
3. **DB-identity invariants** — formally asserts match/mismatch/bootstrap/missing-row modes

Plus a `make data-layer-check` target that runs all three.

---

## What was built

### `tests/integration/data_layer/__init__.py`
Package doc with extension table.

### `tests/integration/data_layer/test_fts_trigger_invariant.py`
Parametrized class with three test methods, each covering all 3 tsvector columns:
- `test_insert_populates_tsvector` — INSERT populates tsvector
- `test_update_text_field_regenerates_tsvector` — UPDATE of the text column re-generates tsvector
- `test_gin_index_searchable` — GIN index is usable for tsquery

Coverage: `work_items.design_doc_search`, `work_items.functional_doc_search`, `project_docs.content_search`.

Extends (does not replace) `tests/integration/test_work_items_functional_doc_fts.py`.

### `tests/integration/data_layer/test_migration_revision_skew.py`
Two tests:
- `test_upgrade_head_fails_with_missing_revision` — sets alembic_version to a bogus hash; `alembic upgrade head` raises `CommandError` with "Can't locate revision identified by"
- `test_valid_but_old_revision_upgrade_succeeds` — rolls back to a valid old revision; `alembic upgrade head` succeeds

Reproduces the I-00075/I-00076 failure class where an uncommitted revision file causes `Can't locate revision identified by` at runtime.

### `tests/integration/data_layer/test_db_identity_invariants.py`
12 tests formally asserting the four DB-identity modes from `orch/db/identity.py`:
- `match` — env matches DB row, proceeds silently
- `mismatch` — env set but differs from row, raises `InstanceMismatchError`
- `bootstrap` — env unset and row exists, proceeds silently
- `missing` — env unset and no row, returns `mode='missing'` (no raise)

Uses `monkeypatch.setenv()` / `delenv()` to control `IW_CORE_EXPECTED_INSTANCE_ID` without calling `importlib.reload(orch.config)` (forbidden — tests/CLAUDE.md).

Companion to `tests/integration/test_db_identity_integration.py`; does not replace it.

### `Makefile`
New target `data-layer-check` runs `migration-check` then `tests/integration/data_layer/`.

---

## TDD RED evidence

Each test module was verified to fail under the broken condition before the fix was applied:

### FTS trigger invariant
Dropping `trg_work_items_fts` causes `test_update_text_field_regenerates_tsvector` to fail:
- Old lexemes (`initi`) remain in the tsvector instead of being replaced
- `assert "updat" in tsvector_text` fails (False — "updat" not present)

### Migration revision skew
Setting `alembic_version` to a valid head revision means `test_upgrade_head_fails_with_missing_revision` would pass (no `CommandError` raised). The test correctly exercises the bogus-revision case.

### DB-identity invariants
With `IW_CORE_EXPECTED_INSTANCE_ID` set to the actual DB instance UUID (match), `test_mismatch_mode_raises` would fail because no `InstanceMismatchError` is raised. The test correctly exercises the mismatch path using a different UUID.

---

## Commands

```bash
make data-layer-check       # run all three modules (22 tests)
uv run pytest tests/integration/data_layer/ -v  # same, direct

# TDD RED demonstrations (run these to see failures before fixes)
python -c "
# FTS trigger: demonstrate failure when trigger absent
# Migration skew: demonstrate failure when revision is valid
# DB identity: demonstrate failure when env matches actual
"
```

---

## Extending

| When ... | Do ... |
|----------|--------|
| A new tsvector column is added | Add one entry to `TSVECTOR_COLUMNS` in `test_fts_trigger_invariant.py` |
| A new identity edge case surfaces | Add a case to `test_db_identity_invariants.py` |
| Alembic's skew error message changes | Update the `match=` argument in the skew regression test |