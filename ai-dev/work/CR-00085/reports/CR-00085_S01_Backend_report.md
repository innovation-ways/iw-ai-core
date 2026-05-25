# CR-00085 S01 Backend Report

## Step Summary

**Work Item**: CR-00085 — DB-column documentation gate
**Step**: S01 (backend-impl)
**Status**: ✅ complete

## What Was Done

Implemented the scanner + baseline + RED-first test piece of the DB-column documentation gate — the "scanner kit" (CR-00046 structural sibling).

### Files Created

| File | Purpose |
|------|---------|
| `scripts/check_db_column_docs.py` | The scanner — library+CLI, mirrors `scripts/check_test_assertions.py` shape |
| `orch/db/column_docs_baseline.txt` | Frozen cleanup backlog — 435 undocumented columns on today's tree |
| `tests/orch/db/__init__.py` | Package init (empty) |
| `tests/orch/db/test_column_docs.py` | RED-first library-form tests (5 tests) |

### Scanner Design Decisions

1. **Column walking**: uses `mapper.local_table.columns` from SQLAlchemy's declarative registry — authoritative and safe against the `DaemonEvent.metadata` → `event_metadata` rename and `Base.metadata` (the MetaData object) trap.
2. **FQN format**: `<cls.__module__>.<cls.__name__>.<col.name>` → e.g. `orch.db.models.DaemonEvent.metadata` (SQL column name, not python attribute).
3. **Acceptable description carriers**: (a) `bool(col.doc)` truthy, (b) FQN in baseline file.
4. **`--baseline /dev/null`**: correctly yields empty allowlist (baseline of empty set) — testable.
5. **`--baseline <missing-file>`**: raises `FileNotFoundError` — explicit, not silent.
6. **Type annotations**: moved `Iterable` and `Mapper` into `TYPE_CHECKING` block to satisfy ruff TC003.

### TDD Evidence — RED Phase

Captured by temporarily renaming the scanner module:

```
ModuleNotFoundError: No module named 'scripts.check_db_column_docs'
tests/orch/db/test_column_docs.py:34:  ModuleNotFoundError
tests/orch/db/test_column_docs.py:52:  ModuleNotFoundError
tests/orch/db/test_column_docs.py:72:  ModuleNotFoundError
tests/orch/db/test_column_docs.py:103: ModuleNotFoundError
tests/orch/db/test_column_docs.py:133: ModuleNotFoundError
```

### TDD Evidence — GREEN Phase

```
5 passed in 0.17s
```

## Test Results

| Test | Result |
|------|--------|
| `test_scanner_finds_undocumented_columns_against_empty_baseline` | ✅ PASSED — RED test: finds 435 real undocumented columns |
| `test_scanner_returns_zero_new_violations_against_committed_baseline` | ✅ PASSED — GREEN test: committed baseline admits all 435 |
| `test_scanner_handles_daemon_event_metadata_rename` | ✅ PASSED — regression: SQL name `metadata` reported, never `event_metadata` |
| `test_scanner_flags_new_undocumented_column_on_synthetic_mapper` | ✅ PASSED — composable: works with its own `DeclarativeBase` |
| `test_write_baseline_roundtrips` | ✅ PASSED — 435-line baseline roundtrips through write+parse |

## Baseline Entry Count

**435 entries** — every SQLAlchemy column in `orch/db/models.py` that lacks a `doc=` argument. This count anchors AC3 and is the reference for the incremental-scrub follow-up CR (`CR-00085-followup-column-docs-scrub`).

Top-level breakdown by class (sample):

| Class | Approx. violations |
|-------|-------------------|
| `WorkItem` | 30 |
| `Batch` | 16 |
| `BatchItem` | 18 |
| `StepRun` | 30 |
| `DaemonEvent` | 8 (incl. `DaemonEvent.metadata`) |
| `ChatMessage` | 9 (incl. `ChatMessage.message_metadata`) |
| `ProjectDoc` | 19 |
| `DocGenerationJob` | 21 |
| `ChatConversation` | 12 |
| `AgentRuntimeOption` | 11 |
| `ChatTab` | 11 |
| `CodeIndexJob` | 18 |
| `ChatSummarizationJob` | 11 |
| `Oss*` (combined) | ~30 |
| *(all others)* | remainder to reach 435 |

## Preflight Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ `894 files already formatted` |
| `make typecheck` | ✅ `Success: no issues found in 276 source files` |
| `make lint` | ✅ `All checks passed!` |

## Notes

- **`pyproject.toml` edit**: added `"scripts/check_db_column_docs.py" = ["T201"]` to the `per-file-ignores` section — same pattern as `check_test_assertions.py`. The print statements are the CLI's stdout output; exempting them from the `no print` rule is the established pattern for this project's CLI scripts. Ruff auto-fixed 2 additional violations (unused import + import-block ordering) during `make lint`.
- **Synthetic-mapper test**: builds its own standalone `DeclarativeBase` + `FakeModel` inside the test — proves the scanner is composable and not hardcoded to `orch.db.models.Base`.
- **RED evidence method**: scanner was written concurrently with tests per TDD flow; pre-implementation failure was confirmed by temporarily renaming the module and observing `ModuleNotFoundError` across all 5 test import sites.
- **No migration**: this step adds no migration, as required by policy.

## Scope Discipline

Files **not** edited (correctly, per S01 scope):

| File | Scope rule |
|------|-----------|
| `orch/db/models.py` | S01 blocked — scrubbing is the follow-up CR's job |
| `Makefile` | S02 scope |
| `.github/workflows/test-quality.yml` | S02 scope |
| `docs/IW_AI_Core_Testing_Strategy.md` | S02 scope |
| `skills/iw-ai-core-testing/SKILL.md` | S02 scope |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | S02 scope |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | S02 scope |
| Any migration file | N/A — no migration added |

## Outputs

```
FILES_CHANGED:
  scripts/check_db_column_docs.py     — scanner (library+CLI)
  orch/db/column_docs_baseline.txt     — 435-entry frozen baseline
  tests/orch/db/__init__.py           — empty package marker
  tests/orch/db/test_column_docs.py   — 5 RED-first tests
  pyproject.toml                      — T201 per-file ignore for scanner script
```
